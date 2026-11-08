"""GitHub Business Opportunities Radar (v2, multi-filets):
Cherche des repos récents via 5 filets historiques et 2 filets d'exploration,
pré-classe avec un score lissé (vélocité réelle dès le 2e run), puis demande à Groq d'arbitrer
le potentiel business des meilleurs candidats. Envoie un digest quotidien.

Sécurité et quotas :
- 7 requêtes Search (8 pages max) espacées de 2 s,
  plus des lectures ciblées de documentation et exemples par candidat.
- Un filet qui échoue ne bloque pas les autres.
- Backoff Groq conservé (429, 413, modèles de repli).
- État séparé (logs/business_state.json) : indépendant du digest quotidien.
"""
import argparse
import csv
import json
import math
import os
import re
import smtplib
import sys
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from business_template import render_html
from project_analysis import analyze_projects, details_text
from builder_profile import load_profile
from chatgpt_export import make_message, export_files

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

UA = {"User-Agent": "trending-digest/1.0"}
LOG_DIR = os.getenv("LOG_DIR", "logs")
ERROR_DIR = os.getenv("ERROR_DIR", "errors")

GH_SEARCH_URL = "https://api.github.com/search/repositories"
SEARCH_PAUSE = float(os.getenv("GH_SEARCH_PAUSE", "2"))  # secondes entre deux requêtes Search
PER_PAGE = 50
MAX_PUSH_AGE_DAYS = 14   # Signal de prudence, jamais un motif d'exclusion à lui seul
STATE_KEEP_DAYS = 45     # durée de conservation d'un repo dans l'état

# ---------------------------------------------------------------------------
# Règles de filtrage (tout est modifiable ici)
# ---------------------------------------------------------------------------
NOISE_NAME_TOPICS = re.compile(
    r"(awesome|cheat-?sheet|roadmap|leetcode|interview|homework|dotfiles|portfolio|"
    r"bootcamp|tutorial|course|curated|assignment)", re.I)
NOISE_DESC = re.compile(
    r"\b(awesome list|curated list|leetcode|homework|interview questions|"
    r"cheat ?sheet|tutorial|coursework|assignment)\b", re.I)
SCAM = re.compile(
    r"(airdrop|keygen|\bcrack(ed)?\b|trading-?bot|\bpump(fun)?\b|giveaway|memecoin)", re.I)
MONETIZED_RE = re.compile(
    r"\b(pricing|hosted|cloud|enterprise|managed|saas|y\s?combinator|yc\s?[sw]\d{2})\b", re.I)

BIG_OWNERS = {
    "google", "microsoft", "nvidia", "openai", "meta", "facebook", "facebookresearch",
    "alibaba", "tencent", "bytedance", "huggingface", "aws", "amazon", "apple", "ibm",
    "oracle", "salesforce", "deepseek-ai", "qwenlm", "anthropics", "baidu", "samsung",
}
BIG_PREFIXES = ("google", "microsoft", "azure", "aws-", "awslabs", "nvidia")


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------
def parse_dt(s, default):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return default


def gh_headers(accept="application/vnd.github+json"):
    h = {**UA, "Accept": accept}
    if os.getenv("GITHUB_TOKEN"):
        h["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    return h


def monetized_hints(*texts):
    return sorted({m.group(0).lower() for t in texts for m in MONETIZED_RE.finditer(t or "")})


def parse_score(v, default=5):
    try:
        return max(1, min(10, int(float(str(v).split("/")[0]))))
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# 1. Les 5 filets de recherche
# ---------------------------------------------------------------------------
def build_queries(now, days_back=10):
    """(nom, requête, tri, nb de pages). Max 5 opérateurs AND/OR/NOT par requête côté GitHub."""
    def d(n):
        return (now - timedelta(days=n)).strftime("%Y-%m-%d")

    base = "fork:false archived:false mirror:false"
    return [
        # Trié par étoiles : une fenêtre 5..300 ne remonterait que les repos proches de 300★.
        # On resserre sur 8..150 et on prend 2 pages pour vraiment attraper les petits.
        ("frais", f"created:>={d(days_back)} stars:8..150 {base}", "stars", 2),
        ("reveilles", f"created:{d(120)}..{d(30)} pushed:>={d(5)} stars:30..800 {base}", "updated", 1),
        ("alternatives", f'"alternative to" in:description,readme created:>={d(45)} stars:10..1000 {base}', "stars", 1),
        ("self-hosted", f"topic:self-hosted created:>={d(45)} stars:10..1000 {base}", "stars", 1),
        ("saas", f"topic:saas created:>={d(30)} stars:10..500 {base}", "stars", 1),
        # Complement the existing nets, rather than replacing their coverage.
        ("discrets", f"created:>={d(days_back)} stars:3..50 {base}", "updated", 1),
        ("recents", f"created:{d(max(30, days_back + 1))}..{d(days_back)} stars:5..3000 {base}", "updated", 1),
    ]


def gh_search(query, sort, page):
    params = {"q": query, "sort": sort, "order": "desc", "per_page": PER_PAGE, "page": page}
    r = None
    for attempt in range(3):
        try:
            r = requests.get(GH_SEARCH_URL, headers=gh_headers(), params=params, timeout=30)
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(15)
            continue
        if r.status_code in (403, 429) or r.status_code >= 500:
            if attempt == 2:
                break
            retry = r.headers.get("retry-after")
            reset = int(r.headers.get("x-ratelimit-reset", time.time() + 60))
            wait = int(retry) if retry else max(5, reset - int(time.time()))
            print(f"GitHub indisponible (HTTP {r.status_code}); attente {min(wait, 30)}s...", file=sys.stderr)
            time.sleep(min(wait, 30))
            continue
        break
    if r.status_code == 422:
        raise RuntimeError(f"requête refusée (422): {r.text[:200]}")
    r.raise_for_status()
    payload = r.json()
    if payload.get("incomplete_results"):
        print("GitHub Search : résultats partiels pour ce filet", file=sys.stderr)
    return payload.get("items", [])


def make_candidate(item, net, now):
    desc = (item.get("description") or "").strip()
    created = parse_dt(item.get("created_at", ""), now)
    pushed = parse_dt(item.get("pushed_at", ""), created)
    owner = item.get("owner") or {}
    lic = (item.get("license") or {}).get("spdx_id") or "aucune"
    if lic == "NOASSERTION":
        lic = "autre/inconnue"
    stars = int(item.get("stargazers_count", 0))
    age_days = max(1, (now - created).days)
    name = item.get("full_name", "")
    homepage = (item.get("homepage") or "").strip()
    return {
        "name": name,
        "url": item.get("html_url", f"https://github.com/{name}"),
        "description": desc,
        "language": item.get("language") or "",
        "stars": stars,
        "forks": int(item.get("forks_count", 0)),
        "open_issues": int(item.get("open_issues_count", 0)),
        "age_days": age_days,
        "created_str": f"{created:%d/%m/%Y}",
        "push_age_days": max(0, (now - pushed).days),
        "stars_per_day": round(stars / age_days, 1),
        "topics": item.get("topics") or [],
        "owner": owner.get("login", ""),
        "owner_type": owner.get("type", ""),
        "license": lic,
        "homepage": homepage,
        "pushed_at": item.get("pushed_at", ""),
        "archived": bool(item.get("archived")),
        "disabled": bool(item.get("disabled")),
        "fork": bool(item.get("fork")),
        "mirror": bool(item.get("mirror_url")),
        "nets": [net],
        "monetized_hints": monetized_hints(desc, homepage),
    }


def collect_repos(now, days_back):
    found, net_counts, errors = {}, Counter(), []
    for net, query, sort, pages in build_queries(now, days_back):
        for page in range(1, pages + 1):
            try:
                items = gh_search(query, sort, page)
            except Exception as exc:  # un filet qui casse ne bloque pas les autres
                errors.append(f"{net}: {exc}")
                print(f"Filet '{net}' en échec: {exc}", file=sys.stderr)
                break
            time.sleep(SEARCH_PAUSE)
            net_counts[net] += len(items)
            for it in items:
                c = make_candidate(it, net, now)
                if not c["name"]:
                    continue
                if c["name"] in found:
                    if net not in found[c["name"]]["nets"]:
                        found[c["name"]]["nets"].append(net)
                else:
                    found[c["name"]] = c
            if len(items) < PER_PAGE:
                break
    if not found and errors:
        raise RuntimeError("Tous les filets ont échoué: " + " | ".join(errors)[:300])
    return found, net_counts


# ---------------------------------------------------------------------------
# 2. Filtres durs (gratuits, avant tout appel Groq)
# ---------------------------------------------------------------------------
def reject_reason(c):
    """Only structural exclusions; ambiguous textual signals stay reviewable."""
    for flag in ("archived", "disabled", "fork", "mirror"):
        if c.get(flag):
            return flag
    return None


def candidate_signals(c):
    """Warnings are ranking hints, never proof of spam, fraud or abandonment."""
    signals = []
    nt = f"{c['name']} {' '.join(c['topics'])}"
    if NOISE_DESC.search(c["description"]) or NOISE_NAME_TOPICS.search(" ".join(c["topics"])):
        signals.append("contenu_pedagogique_ou_liste_possible")
    elif NOISE_NAME_TOPICS.search(c["name"]):
        signals.append("mot_cle_ambigu_dans_nom")  # e.g. portfolio-builder: no penalty alone
    if SCAM.search(f"{nt} {c['description']}"):
        signals.append("contenu_hors_cible_possible")
    if len(c["description"]) < 10:
        signals.append("description_courte")
    if c["push_age_days"] > MAX_PUSH_AGE_DAYS:
        signals.append("activite_a_verifier")
    owner = c["owner"].lower()
    if owner in BIG_OWNERS or owner.startswith(BIG_PREFIXES):
        signals.append("auteur_etabli")
    if c["stars"] > 100 and c["forks"] / c["stars"] < 0.01:
        signals.append("peu_de_forks")
    if c["age_days"] < 3 and c["stars"] > 500:
        signals.append("pic_initial_a_verifier")
    return signals


# ---------------------------------------------------------------------------
# 3. État : snapshots d'étoiles + repos déjà analysés
# ---------------------------------------------------------------------------
def state_path():
    return os.path.join(LOG_DIR, "business_state.json")


def load_state():
    try:
        with open(state_path(), encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}
    if not isinstance(data.get("repos"), dict):
        data["repos"] = {}
    return data


def prune_state(state, today):
    limit = (date.fromisoformat(today) - timedelta(days=STATE_KEEP_DAYS)).isoformat()
    state["repos"] = {n: r for n, r in state["repos"].items() if r.get("last_seen", today) >= limit}


def save_state(state, sent):
    now = datetime.now(timezone.utc)
    today = f"{now:%Y-%m-%d}"
    if sent:
        state["last_sent"] = today
        state["at"] = now.isoformat()
    prune_state(state, today)
    os.makedirs(LOG_DIR, exist_ok=True)
    temporary = state_path() + ".tmp"
    with open(temporary, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(temporary, state_path())


def update_history(state, c, today):
    """Ajoute le snapshot du jour et calcule la vélocité réelle si un snapshot récent existe."""
    rec = state["repos"].setdefault(c["name"], {"first_seen": today, "history": []})
    hist = [h for h in rec.get("history", []) if h[0] != today]
    if hist:
        prev_day, prev_stars = hist[-1]
        days = (date.fromisoformat(today) - date.fromisoformat(prev_day)).days
        if 1 <= days <= 14:
            c["delta_per_day"] = round((c["stars"] - prev_stars) / days, 1)
    hist.append([today, c["stars"]])
    rec["history"] = hist[-8:]
    rec["last_seen"] = today


def already_handled(c, state):
    """Avoid repeats, but reconsider growth, later updates and stale assessments."""
    rec = state["repos"].get(c["name"], {})
    prev = rec.get("analyzed_stars")
    if prev is None or c["stars"] >= 2 * max(prev, 1):
        return False
    last = rec.get("analyzed_at") or rec.get("first_seen")
    today = rec.get("last_seen")
    if last and today:
        elapsed = (date.fromisoformat(today) - date.fromisoformat(last)).days
        if elapsed >= 30:
            return False
        if elapsed >= 14 and rec.get("analyzed_push") and c.get("pushed_at", "") > rec["analyzed_push"]:
            return False
    return True


def record_analysis(state, candidates, opportunities):
    kept = {o["name"] for o in opportunities}
    for c in candidates:
        rec = state["repos"].get(c["name"])
        if rec is not None:
            rec["analyzed_stars"] = c["stars"]
            rec["analyzed_at"] = rec["last_seen"]
            rec["analyzed_push"] = c.get("pushed_at", "")
            rec["kept"] = c["name"] in kept


# ---------------------------------------------------------------------------
# 4. Pré-score : ne garder que les meilleurs candidats pour Groq
# ---------------------------------------------------------------------------
def pre_score(c):
    if c.get("delta_per_day") is not None:
        velocity, source = c["delta_per_day"], "mesurée"
    else:
        velocity, source = c["stars"] / (c["age_days"] + 3), "estimée"  # lissage des repos de 1-2 jours
    c["stars_per_day"] = round(velocity, 1)
    c["velocity_source"] = source
    c["signals"] = candidate_signals(c)
    parts = {
        "interet": 2 * math.log1p(max(velocity, 0)) * (1 if source == "mesurée" else .75),
        "forks": .35 * math.log1p(min(c["forks"], 100)),
        "recence": 1.5 / (1 + c["age_days"] / 30),
        "activite": 1 / (1 + c["push_age_days"] / 30),
        "plusieurs_filets": .15 * min(len(c["nets"]) - 1, 2),
    }
    # Moderate penalties for ambiguous signals; established authors are neutral.
    weights = {"contenu_pedagogique_ou_liste_possible": .65,
               "contenu_hors_cible_possible": .45, "description_courte": .9,
               "peu_de_forks": .9, "pic_initial_a_verifier": .9}
    factor = max(.3, math.prod(weights.get(s, 1) for s in c["signals"]))
    c["score_components"] = dict(parts, facteur_prudence=factor)
    return round(sum(parts.values()) * factor, 3)


def choose_shortlist(candidates, limit):
    """Soft diversity plus a small exploration share, with no extra LLM calls."""
    remaining = sorted(candidates, key=lambda c: (-c["pre_score"], c["name"]))
    chosen = []

    def utility(c):
        same_owner = sum(x["owner"] == c["owner"] for x in chosen)
        same_language = sum(x["language"] == c["language"] for x in chosen) if c["language"] else 0
        return c["pre_score"] / (1 + .45 * same_owner + .08 * same_language)

    def take(pool, reason):
        if not pool:
            return
        best = max(pool, key=utility)
        best["selection_reason"] = reason
        chosen.append(best)
        remaining.remove(best)

    slots = min(3, max(0, limit // 5))
    for _ in range(min(max(0, limit - slots), len(remaining))):
        take(remaining, "classement_avec_diversite_souple")
    for _ in range(slots):
        exploratory = [c for c in remaining if c["stars"] <= 50 and c["age_days"] <= 30]
        take(exploratory or remaining, "exploration_projet_discret" if exploratory else "classement_complementaire")
    return chosen


def select_candidates(state, now, days_back, shortlist):
    today = f"{now:%Y-%m-%d}"
    found, net_counts = collect_repos(now, days_back)
    funnel = {"trouves": len(found)}
    rejects = Counter()

    survivors = []
    for c in found.values():
        reason = reject_reason(c)
        if reason:
            rejects[reason] += 1
        else:
            survivors.append(c)
    funnel["filtres"] = len(survivors)

    fresh = []
    for c in survivors:
        update_history(state, c, today)  # on suit la croissance même des repos déjà vus
        if already_handled(c, state):
            rejects["deja_analyse"] += 1
        else:
            fresh.append(c)
    funnel["nouveaux"] = len(fresh)

    for c in fresh:
        c["pre_score"] = pre_score(c)
    short = choose_shortlist(fresh, shortlist)
    funnel["shortlist"] = len(short)
    return short, funnel, rejects, net_counts


# ---------------------------------------------------------------------------
# README + Groq
# ---------------------------------------------------------------------------
def fetch_user_feedback():
    """Reads labeled issues from the repo to learn user preferences (100% free feedback loop)."""
    repo = os.getenv("GITHUB_REPOSITORY")
    if not repo or not os.getenv("GITHUB_TOKEN"):
        return {"liked": [], "disliked": []}

    headers = gh_headers()
    liked, disliked = [], []
    try:
        r_up = requests.get(
            f"https://api.github.com/repos/{repo}/issues",
            headers=headers,
            params={"labels": "interessant", "state": "all", "per_page": 10},
            timeout=15,
        )
        if r_up.ok:
            for it in r_up.json():
                title = it.get("title", "").replace("[Feedback] Intéressant :", "").strip()
                if title:
                    liked.append(title)
        else:
            print(f"Feedback positif indisponible (HTTP {r_up.status_code})", file=sys.stderr)

        r_down = requests.get(
            f"https://api.github.com/repos/{repo}/issues",
            headers=headers,
            params={"labels": "pas-pour-moi", "state": "all", "per_page": 10},
            timeout=15,
        )
        if r_down.ok:
            for it in r_down.json():
                title = it.get("title", "").replace("[Feedback] Rejet :", "").strip()
                if title:
                    disliked.append(title)
        else:
            print(f"Feedback négatif indisponible (HTTP {r_down.status_code})", file=sys.stderr)
    except (requests.RequestException, ValueError):
        print("Feedback indisponible : préférences non récupérées", file=sys.stderr)
    return {"liked": liked, "disliked": disliked}


def fill_defaults(c):
    # Preview without a model: never manufacture a business assessment.
    c.update(score=None, fit_score=None, profile_loaded=False,
             category="Non analysé", summary=c.get("description") or "Description indisponible",
             problem=c.get("description") or "Description indisponible",
             evidence={"sources": [], "notes": ["Mode sans IA : analyse non réalisée"]})
    return c


def analyze_business_opportunities(candidates, api_key, profile=None):
    model = analyze_projects(candidates, api_key, "business", profile=profile,
                             feedback=fetch_user_feedback())
    selected = []
    for candidate in candidates:
        if not candidate["eligible"]:
            continue
        candidate.update(problem=candidate["summary"], code_mechanism=candidate["workflow"],
                         target=candidate["monetization"], idea=candidate["products"],
                         mvp=candidate["build_plan"], risk=candidate["limitations"],
                         france_competition="Non étudiée : aucune recherche de marché réalisée.", eu_angle="Non établi")
        selected.append(candidate)
    selected.sort(key=lambda c: c["score"] + (c["fit_score"] or 0), reverse=True)
    return selected[:6], model


# ---------------------------------------------------------------------------
# Sorties
# ---------------------------------------------------------------------------
def render_plain_text(opportunities):
    return "RADAR BUSINESS — projets et pistes à explorer\n\n" + "\n\n".join(
        f"{i}. {op['name']} ({op['url']})\n{op.get('summary', op.get('problem', ''))}\n"
        + details_text(op) for i, op in enumerate(opportunities, 1))


def send_email(subject, html_body, text_body):
    user = os.environ["GMAIL_ADDRESS"]
    pw = os.environ["GMAIL_APP_PASSWORD"].replace(" ", "")
    to = os.getenv("EMAIL_TO") or user
    msg = make_message(subject, user, to, html_body, text_body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(user, pw)
        s.sendmail(user, [a.strip() for a in to.split(",")], msg.as_string())
    return to


def log_business_run(status, mode, model, count, note=""):
    now = datetime.now(timezone.utc)
    os.makedirs(LOG_DIR, exist_ok=True)
    path = os.path.join(LOG_DIR, "business_runs.csv")
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "time_utc", "status", "mode", "model", "opportunities", "note"])
        w.writerow([f"{now:%Y-%m-%d}", f"{now:%H:%M:%S}", status, mode, model, count, note[:200]])


def funnel_str(f):
    return " > ".join(f"{k}={v}" for k, v in f.items())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="write business_digest.html instead of emailing (état non modifié)")
    ap.add_argument("--no-llm", action="store_true", help="skip Groq analysis for offline smoke test")
    ap.add_argument("--out", default=os.getenv("OUT_DIR", "."), help="output directory")
    ap.add_argument("--days-back", type=int, default=10, help="fenêtre (jours) du filet 'frais'")
    ap.add_argument("--shortlist", type=int, default=15, help="nombre de candidats envoyés à Groq")
    args = ap.parse_args()
    if args.no_llm and not args.dry_run:
        ap.error("--no-llm exige --dry-run : aperçu uniquement, aucun envoi")
    if args.shortlist < 1 or args.days_back < 1:
        ap.error("--shortlist et --days-back doivent être positifs")

    mode = "dry-run" if args.dry_run else "email"
    model = ""
    opportunities = []
    funnel = {}
    now = datetime.now(timezone.utc)
    state = load_state()
    profile = load_profile()
    if profile:
        print("Profil du créateur chargé depuis profile.yml")

    try:
        candidates, funnel, rejects, net_counts = select_candidates(state, now, args.days_back, args.shortlist)
        print("Résultats par filet: " + ", ".join(f"{k}={v}" for k, v in net_counts.items()))
        print("Entonnoir: " + funnel_str(funnel))
        print("Rejets: " + (", ".join(f"{k}={v}" for k, v in rejects.most_common()) or "aucun"))
        os.makedirs(args.out, exist_ok=True)
        report = {"at": now.isoformat(), "funnel": funnel, "results_by_net": dict(net_counts),
                  "exclusions": dict(rejects), "coverage": "Échantillon GitHub Search, non exhaustif",
                  "selected": [{k: c.get(k) for k in
                                ("name", "stars", "age_days", "nets", "pre_score", "signals",
                                 "score_components", "selection_reason", "velocity_source")}
                               for c in candidates]}
        with open(os.path.join(args.out, "discovery_report.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        # Keep observations even if Groq or SMTP fails later, without marking any send.
        if not args.dry_run:
            save_state(state, sent=False)

        if not candidates:
            opportunities = []
        elif args.no_llm:
            opportunities = [fill_defaults(c) for c in candidates[:6]]
        else:
            key = os.getenv("GROQ_API_KEY")
            if not key:
                raise RuntimeError("GROQ_API_KEY is not set (use --no-llm for an offline test)")
            opportunities, model = analyze_business_opportunities(candidates, key, profile=profile)
            print(f"Identified {len(opportunities)} business opportunities with {model}")
        funnel["retenus"] = len(opportunities)

        html_body = render_html(opportunities, funnel.get("trouves", len(candidates)))
        text_body = render_plain_text(opportunities)
        subject = f"Radar Opportunités GitHub · {now:%d/%m/%Y} · {len(opportunities)} pépites récentes"

        export_files(args.out, subject, html_body, "business")
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, "business_digest.html"), "w", encoding="utf-8") as f:
            f.write(html_body)
        with open(os.path.join(args.out, "business_digest.json"), "w", encoding="utf-8") as f:
            clean = [{k: v for k, v in op.items() if k != "readme"} for op in opportunities]
            json.dump(clean, f, indent=2, ensure_ascii=False)

        if args.dry_run:
            print(f"Dry run: wrote {args.out}/business_digest.html, no email sent")
            print(text_body)
            note = "dry run"
        else:
            to = send_email(subject, html_body, text_body)
            print(f"Business email sent to {to}")
            record_analysis(state, candidates, opportunities)
            save_state(state, sent=True)
            note = "email sent"

        log_business_run("ok", mode, model, len(opportunities), f"{note} | {funnel_str(funnel)}")

    except Exception as exc:
        log_business_run("error", mode, model, len(opportunities), f"{exc} | {funnel_str(funnel)}")
        print(f"FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
