"""GitHub Trending digest: scrape trending repos, explain each in French like you're five (Groq), email it (Gmail SMTP).

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

UA = {"User-Agent": "trending-digest/1.0"}
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
FALLBACK_MODELS = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]


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


def fetch_readme(name, limit=600):  # 10 x 600 chars keeps Groq call well under 8k tokens/min
    headers = {**UA, "Accept": "application/vnd.github.raw+json"}
    if os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    try:
        r = requests.get(f"https://api.github.com/repos/{name}/readme", headers=headers, timeout=20)
        if r.ok:
            text = re.sub(r"<[^>]+>|!\[[^\]]*\]\([^)]*\)", " ", r.text)  # drop html tags and images
            return re.sub(r"\s+", " ", text)[:limit]
    except requests.RequestException:
        pass
    return ""


def groq_chat(messages, api_key):
    models = [os.getenv("GROQ_MODEL")] if os.getenv("GROQ_MODEL") else FALLBACK_MODELS
    last = None
    for model in models:
        for attempt in range(3):
            body = {"model": model, "messages": messages, "temperature": 0.4,
                    "max_completion_tokens": 2500, "response_format": {"type": "json_object"}}
            if model.startswith("openai/gpt-oss"):
                body["reasoning_effort"] = "low"  # short task; saves tokens for the answer
            r = requests.post(GROQ_URL, headers={"Authorization": f"Bearer {api_key}"}, json=body, timeout=60)
            if r.status_code == 429:  # free tier rate limit, back off
                time.sleep(float(r.headers.get("retry-after", 5 * (attempt + 1))))
                continue
            if r.status_code == 413 or (r.status_code in (400, 404) and "model" in r.text.lower()):
                last = r.text
                break  # request over this model's per-minute budget, or model retired: try the next one
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"], model
        else:
            last = "rate limited"
    raise RuntimeError(f"Groq call failed: {last}")


def explain(repos, api_key):
    for repo in repos:
        repo["readme"] = fetch_readme(repo["name"])
    items = [{"name": r["name"], "description": r["description"], "language": r["language"],
              "readme_excerpt": r["readme"]} for r in repos]
    prompt = (
        "Pour chaque dépôt GitHub ci-dessous, rédige en français :\n"
        "1. 'eli5' : une explication simple en 1 à 2 phrases courtes qu’un enfant curieux de 10 ans comprendrait, "
        "avec une analogie quotidienne si ça aide. Dis ce que fait le projet et qui l’utiliserait. Pas de jargon.\n"
        "2. 'category' : 1 à 3 mots (ex. 'Agent IA', 'Outil Dev', 'Automatisation', 'Data').\n"
        "3. 'business_idea' : une idée concrète d'outil web en ligne / Micro-SaaS ou de produit monétisable à construire "
        "autour de ce projet ou de son cas d'usage, en 1 phrase percutante (ex: 'Créer un wrapper web simple à 29€/mois avec export automatique').\n\n"
        'Réponds STRICTEMENT en JSON : {"repos": [{"name": "...", "eli5": "...", "category": "...", "business_idea": "..."}]} '
        "dans le même ordre.\n\n" + json.dumps(items, ensure_ascii=False)
    )
    raw, model = groq_chat([{"role": "user", "content": prompt}], api_key)
    by_name = {x.get("name"): x for x in json.loads(raw).get("repos", [])}
    for r in repos:
        got = by_name.get(r["name"], {})
        r["eli5"] = got.get("eli5") or r["description"] or "Aucune description disponible."
        r["category"] = got.get("category", "")
        r["business_idea"] = got.get("business_idea", "Créer un outil web en ligne ou un wrapper automatisé.")
    return model


def render_text(repos):
    return "\n\n".join(
        f"{i}. {r['name']} ({r['url']})\n   {r['eli5']}\n   💡 Idée SaaS: {r.get('business_idea', '')}"
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
