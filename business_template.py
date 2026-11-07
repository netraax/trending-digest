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
    name = html.escape(item.get("name", ""))
    url = html.escape(item.get("url", f"https://github.com/{name}"))
    stars = item.get("stars", 0)
    stars_per_day = item.get("stars_per_day", 0.0)
    v_src = f"({item.get('velocity_source')})" if item.get("velocity_source") else ""
    age_days = item.get("age_days", 1)
    forks = item.get("forks", 0)
    open_issues = item.get("open_issues", 0)
    lang = html.escape(item.get("language") or "Général")
    lic = html.escape(item.get("license") or "aucune")
    score = item.get("score")
    category = html.escape(item.get("category", "SaaS"))
    monetized = item.get("monetized_hints") or []

    lic_color = "#FBBF24" if any(x in lic.lower() for x in ("agpl", "gpl", "aucune")) else MUTED
    monetized_html = ""
    if monetized:
        m_str = html.escape(", ".join(monetized[:3]))
        monetized_html = f'<div style="margin-top:6px"><span style="display:inline-block;font:600 10px/1 {MONO};color:#FB923C;background:#2D1B0E;border-radius:4px;padding:4px 8px">⚡ Indice commercial non vérifié: {m_str}</span></div>'

    spd = item.get("stars_per_day", 0.0)
    measured = item.get("velocity_source") == "mesurée"
    if measured:
        growth_label = f"Variation mesurée : {spd:+.1f} ★/j"
    else:
        growth_label = f"Indice estimé : {spd:.1f} ★/j"
    growth_badge = (f'<span style="font:600 11px/1.5 {MONO};color:#C9D1D9">'
                    f'{growth_label}</span>')
    growth_note = "Entre deux relevés" if measured else "Total / (âge + 3) ; pas une croissance récente mesurée"

    created_str = item.get("created_str") or f"il y a {age_days}j"
    push_days = item.get("push_age_days", 0)
    active_str = "Push aujourd’hui" if push_days == 0 else f"Dernier push il y a {push_days}j"

    my_repo = os.getenv("GITHUB_REPOSITORY", "netraax/trending-digest")
    q_up_title = urllib.parse.quote(f"[Feedback] Intéressant : {name}")
    q_up_body = urllib.parse.quote(f"J'apprécie ce genre d'opportunité : {url}\n\nPourquoi : ")
    thumb_up_url = f"https://github.com/{my_repo}/issues/new?title={q_up_title}&labels=interessant&body={q_up_body}"

    q_down_title = urllib.parse.quote(f"[Feedback] Rejet : {name}")
    q_down_body = urllib.parse.quote(f"Pas pour moi : {url}\n\nRaison du rejet : ")
    thumb_down_url = f"https://github.com/{my_repo}/issues/new?title={q_down_title}&labels=pas-pour-moi&body={q_down_body}"

    return f"""
<tr><td class="cardpx" style="padding:16px 32px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="{CARD_BG}" style="background:{CARD_BG};border:1px solid {LINE};border-radius:12px;padding:24px 28px">
<tr>
  <td valign="top">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
      <td valign="middle">{_score_badge(score, item.get("fit_score"))} &nbsp; <span style="font:600 11px/1 {MONO};color:{MUTED};text-transform:uppercase">{category}</span></td>
      <td align="right" valign="middle"><span style="font:600 11px/1 {MONO};color:{MUTED}">#{i:02d}</span></td>
    </tr></table>

    <div style="margin:14px 0 4px">
      <a href="{url}" class="repo-name" style="text-decoration:none;font:700 22px/1.25 {SANS};color:{INK}">{name}</a>
      {monetized_html}
    </div>

    <!-- Mini tableau de bord : Métriques, traction & dates précises -->
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="{TILE_BG}" style="background:{TILE_BG};border:1px solid {LINE};border-radius:8px;margin:12px 0 16px">
    <tr>
      <td class="metric" width="33%" valign="top" style="padding:10px 12px;border-right:1px solid {LINE}">
        <div style="font:600 9px/1 {MONO};color:{MUTED};letter-spacing:1px;text-transform:uppercase">TOTAL ÉTOILES</div>
        <div style="font:700 20px/1.2 {SANS};color:{INK};margin-top:4px">★ {stars:,}</div>
        <div style="font:500 10px/1.3 {MONO};color:{MUTED};margin-top:3px">Total relevé sur GitHub</div>
      </td>
      <td class="metric" width="34%" valign="top" style="padding:10px 12px;border-right:1px solid {LINE}">
        <div style="font:600 9px/1 {MONO};color:{MUTED};letter-spacing:1px;text-transform:uppercase">ÉTOILES & ACTIVITÉ</div>
        <div style="margin-top:4px">{growth_badge}</div><div style="font:10px/1.4 Arial;color:{MUTED}">{growth_note}</div>
        <div style="font:500 10px/1.3 {MONO};color:{MUTED};margin-top:3px">{forks} forks &middot; {open_issues} issues/PR ouvertes</div>
      </td>
      <td class="metric" width="33%" valign="top" style="padding:10px 12px">
        <div style="font:600 9px/1 {MONO};color:{MUTED};letter-spacing:1px;text-transform:uppercase">DATE DE CRÉATION</div>
        <div style="font:600 12px/1.3 {SANS};color:{INK};margin-top:4px">{created_str} ({age_days}j)</div>
        <div style="font:500 10px/1.3 {MONO};color:{MUTED};margin-top:3px">{active_str}</div>
      </td>
    </tr>
    </table>

    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="{TILE_BG}" style="width:100%;background:{TILE_BG};border-left:3px solid {ACCENT};margin:14px 0">
      <tr><td style="padding:11px 13px;font:600 10px/1.4 {MONO};letter-spacing:1px;color:{ACCENT};text-transform:uppercase">Le projet en bref</td></tr>
      <tr><td style="padding:0 13px 13px;font:14px/1.6 {SANS};color:#C9D1D9">{html.escape(item.get('summary', item.get('problem', '')))}</td></tr>
    </table>
    {details_html(item, theme="business", show_scores=False)}

    <table role="presentation" cellpadding="0" cellspacing="0" style="margin-top:12px"><tr>
      <td><a href="{url}" style="display:inline-block;padding:9px 16px;background:#1F6FEB;color:#FFFFFF;border-radius:6px;font:600 12px/1 {SANS};text-decoration:none">Analyser le code &rarr;</a></td>
      <td style="padding-left:10px"><a href="{thumb_up_url}" target="_blank" style="display:inline-block;padding:8px 12px;background:#12261A;border:1px solid #1E5E34;color:#4ADE80;border-radius:6px;font:600 11px/1 {SANS};text-decoration:none">👍 Intéressant</a></td>
      <td style="padding-left:6px"><a href="{thumb_down_url}" target="_blank" style="display:inline-block;padding:8px 12px;background:#2D1414;border:1px solid #5E2626;color:#F87171;border-radius:6px;font:600 11px/1 {SANS};text-decoration:none">👎 Pas pour moi</a></td>
    </tr></table>

    <div style="margin-top:10px;font:500 11px/1.4 {MONO};color:{MUTED}">
      Langage: {lang} &middot; Licence: <span style="color:{lic_color}">{lic}</span> &middot; {forks} forks &middot; {open_issues} issues
    </div>
  </td>
</tr>
</table>
</td></tr>"""


def render_html(opportunities, total_scanned=0):
    now = datetime.now(timezone.utc)
    day_name = DAYS_FR[now.weekday()]
    month_name = MONTHS_FR[now.month - 1]
    cards = "".join(_card(i, op) for i, op in enumerate(opportunities, 1))

    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark"><meta name="supported-color-schemes" content="dark">
<title>Radar Opportunités GitHub</title>
<style>
  a {{ color: inherit; }}
  @media (max-width: 620px) {{
    .wrap {{ width: 100% !important; }}
    .px {{ padding-left: 18px !important; padding-right: 18px !important; }}
    .cardpx {{ padding: 10px 10px !important; }}
    .repo-name {{ font-size: 18px !important; }}
    .hl-title {{ font-size: 28px !important; }}
    .metric {{ display: block !important; width: 100% !important;
               border-right: none !important; border-bottom: 1px solid #30363D !important; }}
  }}
</style></head>
<body style="margin:0;padding:0;background:{PAPER}" bgcolor="{PAPER}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="{PAPER}"><tr><td align="center" style="padding:24px 0 40px">
<table class="wrap" role="presentation" width="640" cellpadding="0" cellspacing="0" style="width:100%;max-width:640px">

<tr><td class="px" style="padding:24px 32px 12px">
  <div style="font:600 11px/1 {MONO};letter-spacing:2px;color:{ACCENT};text-transform:uppercase">&#9632;&nbsp;RADAR BUSINESS GITHUB</div>
  <div class="hl-title" style="font:400 36px/1.1 {SERIF};color:{INK};margin:12px 0 6px">Pépites récentes &amp; Opportunités</div>
  <div style="font:400 14px/1.5 {SANS};color:{MUTED}">
    Projets récents expliqués : usages, produits possibles et hypothèses de monétisation.
    &middot; {day_name.capitalize()} {now:%d} {month_name} {now:%Y}
  </div>
</td></tr>

<tr><td class="px" style="padding:12px 32px 18px">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid {LINE};border-bottom:1px solid {LINE};padding:12px 0"><tr>
    <td style="font:600 12px/1.4 {MONO};color:{INK}">{len(opportunities)} opportunités retenues</td>
    <td align="right" style="font:500 12px/1.4 {MONO};color:{MUTED}">{total_scanned} dépôts récents scannés</td>
  </tr></table>
</td></tr>

{cards}

<tr><td class="px" style="padding:28px 32px;text-align:center">
  <div style="font:400 12px/1.6 {SANS};color:{MUTED}">
    Généré automatiquement tous les 2 jours &middot; Filtrage intelligent GitHub Search + Groq.<br>
    Pistes exploratoires : les prix et la demande restent à valider auprès des clients.
  </div>
</td></tr>

</table>
</td></tr></table>
</body></html>"""
