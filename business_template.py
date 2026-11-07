"""Email template for the GitHub Business Opportunities Radar.
Clean, responsive table-based layout compatible with Gmail, Outlook, Apple Mail.
"""
import html
import os
import urllib.parse
from datetime import datetime, timezone

from project_analysis import details_html

INK = "#E6EDF3"
PAPER = "#0D1117"
ACCENT = "#58A6FF"  # readable blue on dark
LIME = "#C6FF3D"
MUTED = "#8B949E"
LINE = "#30363D"
CARD_BG = "#161B22"
TILE_BG = "#1C2128"

SERIF = "'Instrument Serif',Georgia,'Times New Roman',serif"
SANS = "Inter,-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"
MONO = "'JetBrains Mono','SFMono-Regular',Menlo,Consolas,monospace"

DAYS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def _score_badge(score, fit_score=None):
    if score is None:
        return '<span style="font:12px Arial;color:#8B949E">Non évalué · aperçu sans analyse</span>'
    s = int(score) if str(score).isdigit() else 0
    if s >= 8:
        color = "#4ADE80"
        bg = "#12261A"
        text = f"Intérêt estimé · {s}/10"
    elif s >= 6:
        color = "#FBBF24"
        bg = "#2A2110"
        text = f"Intérêt estimé · {s}/10"
    else:
        color = "#9CA3AF"
        bg = "#1F2937"
        text = f"Intérêt estimé · {s}/10"

    badge = (f'<span style="display:inline-block;font:600 11px/1 {MONO};letter-spacing:0.5px;'
             f'color:{color};background:{bg};border-radius:99px;padding:6px 11px">{text}</span>')
    if fit_score is not None:
        f = int(fit_score) if str(fit_score).isdigit() else s
        fit_badge = (f'<span style="display:inline-block;font:600 11px/1 {MONO};letter-spacing:0.5px;'
                     f'color:#58A6FF;background:#0D2540;border-radius:99px;padding:6px 11px;margin-left:6px">'
                     f'Adéquation estimée · {f}/10</span>')
        return badge + " " + fit_badge
    return badge


def _card(i, item):
    from email_layout import card, button
    from project_analysis import field_text
    name = item.get("name", "")
    url = item.get("url", "https://github.com/" + name)
    measured = item.get("velocity_source") == "mesurée"
    spd = item.get("stars_per_day", 0)
    growth = (f"Variation mesurée : {spd:+.1f} ★/j entre deux relevés" if measured else
              f"Indice estimé : {spd:.1f} ★/j · total / (âge + 3), pas une croissance récente mesurée")
    meta = f"★ {item.get('stars', 0):,} · Âge : {item.get('age_days', '?')} jours · {item.get('language') or 'Langage non indiqué'} · Licence : {item.get('license') or 'à vérifier'}"
    content = (f'<div style="font-size:14px;color:#58A6FF">PISTE {i:02d} · {html.escape(item.get("category", "Projet"))}</div>'
               f'<h2 style="font:700 24px/1.3 Arial;margin:8px 0">{html.escape(name)}</h2>'
               + _score_badge(item.get("score"), item.get("fit_score") if item.get("profile_loaded") else None)
               + f'<p style="font-size:13px;color:#AAB4BF">{html.escape(meta)}<br>{html.escape(growth)}</p>'
               + '<strong>Le projet en bref</strong><p>'
               + html.escape(field_text(item.get("summary") or item.get("problem", ""))) + '</p>'
               + details_html(item, theme="business", show_scores=False)
               + button(url, "Explorer le projet →", "#58A6FF"))
    my_repo = os.getenv("GITHUB_REPOSITORY", "netraax/trending-digest")
    for label, tag in (("Intéressant", "interessant"), ("Pas pour moi", "pas-pour-moi")):
        query = urllib.parse.urlencode({"title": f"[Feedback] {label} : {name}", "labels": tag,
                                       "body": f"Projet : {url}\n\nPourquoi : "})
        content += button(f"https://github.com/{my_repo}/issues/new?{query}", label, "#B7C1CD")
    return card(content)


def render_html(opportunities, total_scanned=0):
    from email_layout import shell, card
    cards = "".join(_card(i, op) for i, op in enumerate(opportunities, 1))
    if not opportunities:
        cards = card("Aucun nouveau projet retenu aujourd’hui. La veille continue demain ; les projets déjà présentés restent suivis.")
    intro = (f"{len(opportunities)} opportunités retenues · {total_scanned} dépôts récents scannés. "
             "Des projets récents à comprendre, des produits à imaginer, puis un premier test pour chacun. "
             "Objectif : 5 à 6 pistes lorsque la collecte le permet. Les notes sont des jugements provisoires.")
    return shell("RADAR BUSINESS GITHUB", "Pépites récentes &amp; opportunités", intro, cards, "#58A6FF")
