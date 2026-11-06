"""GitHub Business Opportunities Radar (v2, multi-filets):
Cherche des repos récents via 5 requêtes complémentaires, applique des filtres durs gratuits,
pré-classe avec un score lissé (vélocité réelle dès le 2e run), puis demande à Groq d'arbitrer
le potentiel business des meilleurs candidats. Envoie un digest tous les 2 jours.

Sécurité et quotas :
- 5 requêtes Search (6 pages max) espacées de 2 s, bien sous la limite de 30 req/min,
  plus une lecture de README par candidat présélectionné (API core, 1 000 req/h).
- Un filet qui échoue ne bloque pas les autres.
- Backoff Groq conservé (429, 413, modèles de repli).
- État séparé (logs/business_state.json) : indépendant du digest quotidien.
"""
import argparse
import csv
import json
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

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

UA = {"User-Agent": "trending-digest/1.0"}
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
FALLBACK_MODELS = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]
LOG_DIR = os.getenv("LOG_DIR", "logs")
ERROR_DIR = os.getenv("ERROR_DIR", "errors")

GH_SEARCH_URL = "https://api.github.com/search/repositories"
SEARCH_PAUSE = float(os.getenv("GH_SEARCH_PAUSE", "2"))  # secondes entre deux requêtes Search
PER_PAGE = 50
MAX_PUSH_AGE_DAYS = 14   # sans commit depuis 2 semaines = projet mort-né
README_CHARS = 700       # extrait envoyé à Groq
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

    base = "fork:false archived:false mirror:false size:>=50"
    return [
        # Trié par étoiles : une fenêtre 5..300 ne remonterait que les repos proches de 300★.
        # On resserre sur 8..150 et on prend 2 pages pour vraiment attraper les petits.
        ("frais", f"created:>={d(days_back)} stars:8..150 {base}", "stars", 2),
        ("reveilles", f"created:{d(120)}..{d(30)} pushed:>={d(5)} stars:30..800 {base}", "updated", 1),
        ("alternatives", f'"alternative to" in:description,readme created:>={d(45)} stars:10..1000 {base}', "stars", 1),
        ("self-hosted", f"topic:self-hosted created:>={d(45)} stars:10..1000 {base}", "stars", 1),
        ("saas", f"topic:saas created:>={d(30)} stars:10..500 {base}", "stars", 1),
    ]


def gh_search(query, sort, page):
    params = {"q": query, "sort": sort, "order": "desc", "per_page": PER_PAGE, "page": page}
    r = None
    for _ in range(2):
        r = requests.get(GH_SEARCH_URL, headers=gh_headers(), params=params, timeout=30)
        if r.status_code in (403, 429):
            retry = r.headers.get("retry-after")
            reset = int(r.headers.get("x-ratelimit-reset", time.time() + 60))
            wait = int(retry) if retry else max(5, reset - int(time.time()))
            print(f"GitHub rate limit; attente {min(wait, 30)}s...", file=sys.stderr)
            time.sleep(min(wait, 30))
            continue
        break
    if r.status_code == 422:
        raise RuntimeError(f"requête refusée (422): {r.text[:200]}")
    r.raise_for_status()
    return r.json().get("items", [])


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
    nt = f"{c['name']} {' '.join(c['topics'])}"
    if NOISE_NAME_TOPICS.search(nt) or NOISE_DESC.search(c["description"]):
        return "bruit_pedagogique"
    if SCAM.search(f"{nt} {c['description']}"):
        return "spam_arnaque"
    if len(c["description"]) < 10:
        return "sans_description"
    if c["push_age_days"] > MAX_PUSH_AGE_DAYS:
        return "inactif"
    owner = c["owner"].lower()
    if owner in BIG_OWNERS or owner.startswith(BIG_PREFIXES):
        return "grosse_structure"
    if c["stars"] > 100 and c["forks"] / c["stars"] < 0.01:
        return "etoiles_suspectes"
    if c["age_days"] < 3 and c["stars"] > 500:
        return "etoiles_suspectes"
    return None


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
    with open(state_path(), "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def update_history(state, c, today):
    """Ajoute le snapshot du jour et calcule la vélocité réelle si un snapshot récent existe."""
    rec = state["repos"].setdefault(c["name"], {"first_seen": today, "history": []})
    hist = [h for h in rec.get("history", []) if h[0] != today]
    if hist:
        prev_day, prev_stars = hist[-1]
        days = (date.fromisoformat(today) - date.fromisoformat(prev_day)).days
        if 1 <= days <= 14:
            c["delta_per_day"] = round(max(c["stars"] - prev_stars, 0) / days, 1)
    hist.append([today, c["stars"]])
    rec["history"] = hist[-8:]
    rec["last_seen"] = today


def already_handled(c, state):
    """Déjà analysé : on ne le revoit que si ses étoiles ont au moins doublé."""
    prev = state["repos"].get(c["name"], {}).get("analyzed_stars")
    return prev is not None and c["stars"] < 2 * max(prev, 1)


def record_analysis(state, candidates, opportunities):
    kept = {o["name"] for o in opportunities}
    for c in candidates:
        rec = state["repos"].get(c["name"])
        if rec is not None:
            rec["analyzed_stars"] = c["stars"]
            rec["kept"] = c["name"] in kept


# ---------------------------------------------------------------------------
# 4. Pré-score : ne garder que les meilleurs candidats pour Groq
# ---------------------------------------------------------------------------
def pre_score(c):
    if c.get("delta_per_day") is not None:
        velocity, source = c["delta_per_day"], "mesurée"
    else:
        velocity, source = c["stars"] / (c["age_days"] + 3), "estimée"  # lissage des repos de 1-2 jours
    demand = min(c["forks"] / max(c["stars"], 1), 0.15) / 0.15  # 0 à 1 : forks = usage réel
    fresh = 1.0 if c["push_age_days"] <= 7 else 0.4
    multi = 1 + 0.1 * (len(c["nets"]) - 1)  # trouvé par plusieurs filets = signal plus fort
    c["stars_per_day"] = round(velocity, 1)
    c["velocity_source"] = source
    return round(velocity * (0.5 + demand) * fresh * multi, 3)


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
    fresh.sort(key=lambda c: c["pre_score"], reverse=True)
    short = fresh[:shortlist]
    funnel["shortlist"] = len(short)
    return short, funnel, rejects, net_counts


# ---------------------------------------------------------------------------
# README + Groq
# ---------------------------------------------------------------------------
def fetch_readme(name, limit=4000):
    try:
        r = requests.get(f"https://api.github.com/repos/{name}/readme",
                         headers=gh_headers("application/vnd.github.raw+json"), timeout=20)
        if r.ok:
            text = re.sub(r"<[^>]+>|!\[[^\]]*\]\([^)]*\)", " ", r.text)
            return re.sub(r"\s+", " ", text)[:limit]
    except requests.RequestException:
        pass
    return ""


def groq_chat(messages, api_key):
    models = [os.getenv("GROQ_MODEL")] if os.getenv("GROQ_MODEL") else FALLBACK_MODELS
    last = None
    for model in models:
        for attempt in range(3):
            body = {
                "model": model,
                "messages": messages,
                "temperature": 0.3,
                "max_completion_tokens": 3000,
                "response_format": {"type": "json_object"},
            }
            if model.startswith("openai/gpt-oss"):
                body["reasoning_effort"] = "low"
            r = requests.post(GROQ_URL, headers={"Authorization": f"Bearer {api_key}"}, json=body, timeout=60)
            if r.status_code == 429:
                time.sleep(float(r.headers.get("retry-after", 5 * (attempt + 1))))
                continue
            if r.status_code == 413 or (r.status_code in (400, 404) and "model" in r.text.lower()):
                last = r.text
                break
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"], model
        else:
            last = "rate limited"
    raise RuntimeError(f"Groq call failed: {last}")


def load_profile():
    path = os.getenv("PROFILE_PATH", "profile.yml")
    if not os.path.exists(path):
        return None
    try:
        try:
            import yaml
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except ImportError:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
    except Exception as exc:
        print(f"Warning: could not load {path}: {exc}", file=sys.stderr)
        return None


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
    except Exception:
        pass
    return {"liked": liked, "disliked": disliked}


def fill_defaults(c):
    c.setdefault("score", 5)
    c.setdefault("fit_score", 5)
    c.setdefault("category", "Tendance")
    c.setdefault("problem", c.get("description") or "Outil open-source récent")
    c.setdefault("code_mechanism", "Architecture technique et code source open-source")
    c.setdefault("target", "Développeurs et technophiles")
    c.setdefault("idea", "Tester le projet et évaluer une version cloud")
    c.setdefault("mvp", "1 à 2 semaines")
    c.setdefault("eu_angle", "Alternative souveraine / RGPD")
    c.setdefault("france_competition", "Océan bleu en France : aucun acteur direct identifié")
    c.setdefault("risk", "")
    return c


def analyze_business_opportunities(candidates, api_key, profile=None):
    for c in candidates:
        full = fetch_readme(c["name"])
        c["readme"] = full[:README_CHARS]
        c["monetized_hints"] = sorted(set(c["monetized_hints"]) | set(monetized_hints(full)))

    items = [
        {
            "name": c["name"],
            "description": c["description"],
            "language": c["language"],
            "topics": c["topics"][:6],
            "stars": c["stars"],
            "forks": c["forks"],
            "open_issues": c["open_issues"],
            "age_days": c["age_days"],
            "stars_per_day": c["stars_per_day"],
            "license": c["license"],
            "owner_type": c["owner_type"],
            "homepage": c["homepage"][:80],
            "monetized_hints": c["monetized_hints"],
            "readme_excerpt": c["readme"],
        }
        for c in candidates
    ]

    profile_ctx = ""
    if profile:
        p_str = json.dumps(profile, ensure_ascii=False, indent=2) if isinstance(profile, dict) else str(profile)
        profile_ctx = f"\nPROFIL DU CRÉATEUR (à utiliser pour calculer 'fit_score', l'angle FR/UE et la faisabilité MVP) :\n{p_str}\n"

    feedback = fetch_user_feedback()
    feedback_ctx = ""
    if feedback.get("liked") or feedback.get("disliked"):
        feedback_ctx = (
            f"\nRETROACTIONS DU CRÉATEUR (Feedback Loop) :\n"
            f"- Projets déjà validés / appréciés par le créateur : {', '.join(feedback['liked']) or 'aucun'}\n"
            f"- Projets rejetés par le créateur : {', '.join(feedback['disliked']) or 'aucun'}\n"
            f"Prends en compte ses préférences : favorise les opportunités similaires à ce qu'il aime, écarte celles similaires aux rejets.\n"
        )

    prompt = (
        "Tu es un analyste en capital-risque et créateur de micro-SaaS expérimenté. "
        "Voici des dépôts GitHub récents, déjà pré-filtrés sur leur croissance.\n"
        "Ta mission : éliminer les projets gadget/jouets/académiques et sélectionner TOUS les dépôts "
        "qui ont un réel potentiel commercial ou de création de produit (jusqu'à 10 opportunités maximum). "
        "Ne te restreins pas arbitrairement à un petit nombre : si un projet présente une vraie valeur, inclus-le.\n"
        f"{profile_ctx}\n"
        f"{feedback_ctx}\n"
        "RÈGLES STRICTES :\n"
        "- Base-toi UNIQUEMENT sur les données fournies. N'invente aucun chiffre de marché "
        "et ne cite un concurrent que si tu es certain qu'il existe. Écris 'inconnu' si l'info manque.\n"
        "- Si monetized_hints n'est pas vide ou si homepage est renseignée, une offre commerciale existe "
        "peut-être déjà : baisse le score et dis-le dans risk.\n"
        "- Une licence AGPL/GPL/SSPL ou 'aucune', ou un owner_type Organization, doit apparaître dans risk.\n\n"
        "Pour chaque opportunité retenue, réponds en français avec précision :\n"
        "- name: nom exact du repo (ex: 'owner/repo')\n"
        "- score: note entière de 1 à 10 de viabilité commerciale globale\n"
        "- fit_score: note entière de 1 à 10 d'adéquation avec le profil du créateur (stack, temps dispo, budget)\n"
        "- category: 1 à 2 mots (ex: 'Micro-SaaS', 'API & Données', 'Outil Pro', 'Extension')\n"
        "- problem: Quel est le problème douloureux résolu en 1 phrase claire ?\n"
        "- code_mechanism: Concrètement, comment le code résout-il le problème ? (1 à 2 phrases précises sur l'architecture, l'algorithme, la librairie ou le composant technique du repo)\n"
        "- target: Qui est la cible qui a du budget pour payer (ex: comptables, agences, e-commerçants) ?\n"
        "- idea: Quelle est l'opportunité de monétisation concrète (ex: version hébergée sans code, wrapper UI, connecteur) ?\n"
        "- mvp: temps estimé pour construire un premier prototype (ex: '1 week-end', '10 jours')\n"
        "- eu_angle: opportunité spécifique marché France/Europe (RGPD, souveraineté, langue française, facturation)\n"
        "- france_competition: Quel est le paysage concurrentiel en France/Europe ? (Cite 1 ou 2 acteurs établis connus s'ils existent, sinon écris obligatoirement 'Océan bleu en France : aucun acteur direct identifié')\n"
        "- risk: Pourquoi ça pourrait échouer, en 1 phrase (concurrence, licence, marché étroit)\n\n"
        'Format de réponse STRICT en JSON :\n'
        '{"opportunities": [{"name": "...", "score": 8, "fit_score": 7, "category": "...", "problem": "...", '
        '"code_mechanism": "...", "target": "...", "idea": "...", "mvp": "...", "eu_angle": "...", '
        '"france_competition": "...", "risk": "..."}]}\n\n'
        + json.dumps(items, ensure_ascii=False)
    )

    raw, model = groq_chat([{"role": "user", "content": prompt}], api_key)
    res = json.loads(raw).get("opportunities", [])

    by_name = {c["name"]: c for c in candidates}
    validated = []
    for item in res:
        name = item.get("name")
        if name in by_name:
            full = dict(by_name[name])
            full.update({
                "score": parse_score(item.get("score")),
                "fit_score": parse_score(item.get("fit_score"), default=parse_score(item.get("score"))),
                "category": item.get("category") or "Micro-SaaS",
                "problem": item.get("problem") or full.get("description", ""),
                "code_mechanism": item.get("code_mechanism") or "Architecture technique open-source",
                "target": item.get("target") or "Professionnels et développeurs",
                "idea": item.get("idea") or "Créer une version hébergée ou une extension",
                "mvp": item.get("mvp") or "1 à 2 semaines",
                "eu_angle": item.get("eu_angle") or "",
                "france_competition": item.get("france_competition") or "Océan bleu en France : aucun acteur direct identifié",
                "risk": item.get("risk") or "",
            })
            validated.append(full)

    validated.sort(key=lambda x: (int(x.get("score", 0)) + int(x.get("fit_score", 0))), reverse=True)
    if validated:
        return validated[:10], model
    return [fill_defaults(dict(c)) for c in candidates[:max(4, min(10, len(candidates)))]], model


# ---------------------------------------------------------------------------
# Sorties
# ---------------------------------------------------------------------------
def render_plain_text(opportunities):
    lines = ["RADAR OPPORTUNITÉS GITHUB (Dépôts récents à croissance rapide)\n" + "=" * 60]
    for i, op in enumerate(opportunities, 1):
        v_src = f"({op.get('velocity_source', '')})" if op.get('velocity_source') else ""
        lines.append(
            f"\n{i}. {op['name']} (★ {op.get('stars', 0)} | {op.get('stars_per_day', 0):.1f}★/j "
            f"{v_src} | {op.get('forks', 0)} forks | {op.get('license', '?')})\n"
            f"   Lien: {op.get('url', '')}\n"
            f"   Score: {op.get('score', 5)}/10 [Fit profil: {op.get('fit_score', 5)}/10 · {op.get('category', '')}]\n"
            f"   Problème: {op.get('problem', '')}\n"
            f"   Code source: {op.get('code_mechanism', '')}\n"
            f"   Cible: {op.get('target', '')}\n"
            f"   Opportunité: {op.get('idea', '')}\n"
            f"   MVP estimé: {op.get('mvp', '1 à 2 semaines')}\n"
            f"   Angle FR/UE: {op.get('eu_angle', 'n/a')}\n"
            f"   Concurrence FR: {op.get('france_competition', '')}\n"
            f"   Risque: {op.get('risk') or 'non renseigné'}"
        )
    return "\n".join(lines)


def send_email(subject, html_body, text_body):
    user = os.environ["GMAIL_ADDRESS"]
    pw = os.environ["GMAIL_APP_PASSWORD"].replace(" ", "")
    to = os.getenv("EMAIL_TO") or user
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
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
    ap.add_argument("--shortlist", type=int, default=22, help="nombre de candidats envoyés à Groq")
    args = ap.parse_args()

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
        if funnel.get("filtres", 0) < 15:
            print("Peu de survivants aux filtres : seuils peut-être trop stricts.")
        elif funnel.get("filtres", 0) > 100:
            print("Beaucoup de survivants aux filtres : seuils peut-être trop souples.")

        if not candidates:
            print("No candidates found; nothing to send.")
            if not args.dry_run:
                save_state(state, sent=False)
            log_business_run("ok", mode, model, 0, "aucun candidat | " + funnel_str(funnel))
            return

        if args.no_llm:
            opportunities = [fill_defaults(c) for c in candidates[:4]]
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
