"""GitHub Trending digest: scrape trending repos, explain concrete uses and product ideas in French (Groq), email it (Gmail SMTP).

Env vars:
  GROQ_API_KEY        required (free key from console.groq.com)
  GMAIL_ADDRESS       Gmail account that sends the email
  GMAIL_APP_PASSWORD  16-char Gmail app password (not your normal password)
  EMAIL_TO            recipient, defaults to GMAIL_ADDRESS
  TOP_N               how many repos, default 10
  SINCE               daily | weekly | monthly, default daily
  GROQ_MODEL          pin one model (default: first available in FALLBACK_MODELS)
  GITHUB_TOKEN        optional, raises the README fetch rate limit

Flags:
  --dry-run   write digest.html instead of sending email
  --no-llm    skip Groq, use repo descriptions (offline smoke test)
"""
import argparse
import html
import json
import os
import re
import smtplib
import sys
import time
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from bs4 import BeautifulSoup

import run_log
from email_template import render_html
from project_analysis import analyze_projects, details_text
from builder_profile import load_profile

UA = {"User-Agent": "trending-digest/1.0"}


def num(text):
    m = re.search(r"[\d,]+", text or "")
    return int(m.group().replace(",", "")) if m else 0


def scrape_trending(since="daily", top_n=10):
    r = requests.get("https://github.com/trending", params={"since": since}, headers=UA, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    repos = []
    for row in soup.select("article.Box-row")[:top_n]:
        link = row.select_one("h2 a")
        if not link:
            continue
        name = link["href"].strip("/")
        desc = row.select_one("p")
        lang = row.select_one('[itemprop="programmingLanguage"]')
        stars = row.select_one('a[href$="/stargazers"]')
        forks = row.select_one('a[href$="/network/members"], a[href$="/forks"]')
        gained = next((s.get_text(" ", strip=True) for s in row.select("span")
                       if re.search(r"stars? (today|this week|this month)", s.get_text())), "")
        dot = row.select_one(".repo-language-color")
        color = re.search(r"#[0-9a-fA-F]{3,6}", dot.get("style", "")) if dot else None
        repos.append({
            "name": name,
            "url": f"https://github.com/{name}",
            "description": desc.get_text(" ", strip=True) if desc else "",
            "language": lang.get_text(strip=True) if lang else "",
            "stars": num(stars.get_text() if stars else ""),
            "forks": num(forks.get_text() if forks else ""),
            "gained": gained,
            "gained_n": num(gained),
            "lang_color": color.group() if color else "#8b8b8b",
        })
    if not repos:
        raise RuntimeError("No repos parsed; GitHub may have changed the trending page markup.")
    return repos


def explain(repos, api_key):
    return analyze_projects(repos, api_key, "trending", profile=load_profile())


def render_text(repos):
    return "\n\n".join(
        f"{i}. {r['name']} ({r['url']})\n{r['eli5']}\n{details_text(r)}"
        for i, r in enumerate(repos, 1)
    )


def send_email(subject, html_body, text_body):
    user, pw = os.environ["GMAIL_ADDRESS"], os.environ["GMAIL_APP_PASSWORD"].replace(" ", "")
    to = os.getenv("EMAIL_TO") or user
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(user, pw)
        s.sendmail(user, [a.strip() for a in to.split(",")], msg.as_string())
    return to


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="write digest.html instead of emailing")
    ap.add_argument("--no-llm", action="store_true", help="skip Groq and use repo descriptions")
    ap.add_argument("--out", default=os.getenv("OUT_DIR", "."), help="folder for digest.html/json")
    args = ap.parse_args()
    if args.no_llm and not args.dry_run:
        ap.error("--no-llm exige --dry-run : aperçu uniquement, aucun envoi")

    since = os.getenv("SINCE", "daily")
    top_n = int(os.getenv("TOP_N", "10"))
    mode = "dry-run" if args.dry_run else "email"
    stage, model, repos = "scrape", "", []

    try:
        repos = scrape_trending(since, top_n)
        print(f"Scraped {len(repos)} trending repos ({since})")

        stage = "explain"
        if args.no_llm:
            for r in repos:
                r["eli5"], r["category"] = r["description"] or "Aucune description disponible.", ""
        else:
            key = os.getenv("GROQ_API_KEY")
            if not key:
                raise RuntimeError("GROQ_API_KEY is not set (use --no-llm for an offline test)")
            model = explain(repos, key)
            print(f"Explanations generated with {model}")

        stage = "render"
        html_body, text_body = render_html(repos, since), render_text(repos)
        subject = f"Tendances GitHub · {datetime.now(timezone.utc):%d/%m/%Y} · {repos[0]['name']} et {len(repos) - 1} autres"
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, "digest.html"), "w", encoding="utf-8") as f:
            f.write(html_body)
        with open(os.path.join(args.out, "digest.json"), "w", encoding="utf-8") as f:
            json.dump([{k: v for k, v in r.items() if k != "readme"} for r in repos], f, indent=2, ensure_ascii=False)

        stage = "send"
        if args.dry_run:
            print(f"Dry run: wrote {args.out}/digest.html, no email sent")
            print(text_body)
            note = "no email sent"
        else:
            print(f"Email sent to {send_email(subject, html_body, text_body)}")
            note = "email sent"  # no address: logs/ is committed to a public repo
            run_log.mark_sent()

        print(f"History: {run_log.write_history(repos, since, mode, model)}")
        run_log.append_run("ok", mode, model, repos, note)
    except Exception as exc:
        path = run_log.write_error(exc, mode, stage)
        run_log.append_run("error", mode, model, repos, f"{stage}: {type(exc).__name__}: {exc}")
        print(f"FAILED at {stage}; details in {path}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
