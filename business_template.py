"""Email template for the GitHub Business Opportunities Radar.
Clean, responsive table-based layout compatible with Gmail, Outlook, Apple Mail.
"""
import html
import os
import urllib.parse
from datetime import datetime, timezone

INK = "#111111"
PAPER = "#F7F5F0"
ACCENT = "#2563EB"  # Clean business blue
LIME = "#C6FF3D"
MUTED = "#6E6A62"
LINE = "#DCD6C8"
CARD_BG = "#FFFFFF"

SERIF = "'Instrument Serif',Georgia,'Times New Roman',serif"
SANS = "Inter,-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"
MONO = "'JetBrains Mono','SFMono-Regular',Menlo,Consolas,monospace"

DAYS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def _score_badge(score, fit_score=None):
    s = int(score) if str(score).isdigit() else 7
    if s >= 8:
        color = "#15803D"
        bg = "#DCFCE7"
        text = f"🔥 Potentiel · {s}/10"
    elif s >= 6:
        color = "#B45309"
        bg = "#FEF3C7"
        text = f"⚡ Viable · {s}/10"
    else:
        color = "#4B5563"
        bg = "#F3F4F6"
        text = f"💡 Niche · {s}/10"

    badge = (f'<span style="display:inline-block;font:600 11px/1 {MONO};letter-spacing:0.5px;'
             f'color:{color};background:{bg};border-radius:99px;padding:6px 11px">{text}</span>')
    if fit_score is not None:
        f = int(fit_score) if str(fit_score).isdigit() else s
        fit_badge = (f'<span style="display:inline-block;font:600 11px/1 {MONO};letter-spacing:0.5px;'
                     f'color:#1D4ED8;background:#DBEAFE;border-radius:99px;padding:6px 11px;margin-left:6px">'
                     f'🎯 Fit profil · {f}/10</span>')
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
    score = item.get("score", 7)
    problem = html.escape(item.get("problem", ""))
    target = html.escape(item.get("target", ""))
    idea = html.escape(item.get("idea", ""))
    risk = html.escape(item.get("risk", ""))
    category = html.escape(item.get("category", "SaaS"))
    monetized = item.get("monetized_hints") or []

    lic_color = "#B45309" if any(x in lic.lower() for x in ("agpl", "gpl", "aucune")) else MUTED
    monetized_html = ""
    if monetized:
        m_str = html.escape(", ".join(monetized[:3]))
        monetized_html = f'<div style="margin-top:6px"><span style="display:inline-block;font:600 10px/1 {MONO};color:#9A3412;background:#FFEDD5;border-radius:4px;padding:4px 8px">⚡ Offre existante détectée: {m_str}</span></div>'

    risk_html = ""
    if risk:
        risk_html = f"""
      <tr>
        <td style="padding:8px 0;border-top:1px solid #F3F4F6">
          <div style="font:600 11px/1.4 {MONO};letter-spacing:1px;color:#DC2626;text-transform:uppercase">⚠️ Risque identifié</div>
          <div style="font:400 13px/1.55 {SANS};color:#991B1B;margin-top:4px">{risk}</div>
        </td>
      </tr>"""

    mvp_html = ""
    if item.get("mvp") or item.get("eu_angle"):
        mvp_val = html.escape(item.get("mvp") or "1 à 2 semaines")
        eu_val = html.escape(item.get("eu_angle") or "Alternative souveraine / RGPD")
        mvp_html = f"""
      <tr>
        <td style="padding:8px 0;border-top:1px solid #F3F4F6">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
            <td width="48%" valign="top">
              <div style="font:600 11px/1.4 {MONO};letter-spacing:1px;color:{MUTED};text-transform:uppercase">🛠️ MVP estimé</div>
              <div style="font:500 13px/1.5 {SANS};color:#1F2937;margin-top:3px">{mvp_val}</div>
            </td>
            <td width="4%">&nbsp;</td>
            <td width="48%" valign="top">
              <div style="font:600 11px/1.4 {MONO};letter-spacing:1px;color:#1D4ED8;text-transform:uppercase">🇫🇷 Angle FR / UE</div>
              <div style="font:500 13px/1.5 {SANS};color:#1E3A8A;margin-top:3px">{eu_val}</div>
            </td>
          </tr></table>
        </td>
      </tr>"""

    my_repo = os.getenv("GITHUB_REPOSITORY", "netraax/trending-digest")
    q_up_title = urllib.parse.quote(f"[Feedback] Intéressant : {name}")
    q_up_body = urllib.parse.quote(f"J'apprécie ce genre d'opportunité : {url}\n\nPourquoi : ")
    thumb_up_url = f"https://github.com/{my_repo}/issues/new?title={q_up_title}&labels=interessant&body={q_up_body}"

    q_down_title = urllib.parse.quote(f"[Feedback] Rejet : {name}")
    q_down_body = urllib.parse.quote(f"Pas pour moi : {url}\n\nRaison du rejet : ")
    thumb_down_url = f"https://github.com/{my_repo}/issues/new?title={q_down_title}&labels=pas-pour-moi&body={q_down_body}"

    return f"""
<tr><td style="padding:16px 32px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="{CARD_BG}" style="background:{CARD_BG};border:1px solid {LINE};border-radius:12px;padding:24px 28px;box-shadow:0 1px 3px rgba(0,0,0,0.04)">
<tr>
  <td valign="top">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
      <td valign="middle">{_score_badge(score, item.get("fit_score"))} &nbsp; <span style="font:500 11px/1 {MONO};color:{MUTED};text-transform:uppercase">{category}</span></td>
      <td align="right" valign="middle" style="font:600 12px/1 {MONO};color:{MUTED}">★ {stars:,} <span style="font-weight:400;color:#9CA3AF">({stars_per_day:.1f}★/j {v_src} · {age_days}j)</span></td>
    </tr></table>

    <div style="margin:14px 0 6px">
      <a href="{url}" style="text-decoration:none;font:700 20px/1.3 {SANS};color:{INK}">{name}</a>
      {monetized_html}
    </div>

    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:14px 0">
      <tr>
        <td style="padding:8px 0;border-top:1px solid #F3F4F6">
          <div style="font:600 11px/1.4 {MONO};letter-spacing:1px;color:{MUTED};text-transform:uppercase">🎯 Problème douloureux</div>
          <div style="font:400 14px/1.55 {SANS};color:#1F2937;margin-top:4px">{problem}</div>
        </td>
      </tr>
      <tr>
        <td style="padding:8px 0;border-top:1px solid #F3F4F6">
          <div style="font:600 11px/1.4 {MONO};letter-spacing:1px;color:{MUTED};text-transform:uppercase">👥 Cible solvable</div>
          <div style="font:400 14px/1.55 {SANS};color:#1F2937;margin-top:4px">{target}</div>
        </td>
      </tr>
      <tr>
        <td style="padding:8px 0;border-top:1px solid #F3F4F6">
          <div style="font:600 11px/1.4 {MONO};letter-spacing:1px;color:{ACCENT};text-transform:uppercase">💡 Angle Business / Monétisation</div>
          <div style="font:500 14px/1.55 {SANS};color:#111827;margin-top:4px">{idea}</div>
        </td>
      </tr>
      {mvp_html}
      {risk_html}
    </table>

    <table role="presentation" cellpadding="0" cellspacing="0" style="margin-top:12px"><tr>
      <td><a href="{url}" style="display:inline-block;padding:9px 16px;background:{INK};color:#FFFFFF;border-radius:6px;font:600 12px/1 {SANS};text-decoration:none">Analyser le code &rarr;</a></td>
      <td style="padding-left:10px"><a href="{thumb_up_url}" target="_blank" style="display:inline-block;padding:8px 12px;background:#F0FDF4;border:1px solid #BBF7D0;color:#15803D;border-radius:6px;font:600 11px/1 {SANS};text-decoration:none">👍 Intéressant</a></td>
      <td style="padding-left:6px"><a href="{thumb_down_url}" target="_blank" style="display:inline-block;padding:8px 12px;background:#FEF2F2;border:1px solid #FECACA;color:#991B1B;border-radius:6px;font:600 11px/1 {SANS};text-decoration:none">👎 Pas pour moi</a></td>
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
<title>Radar Opportunités GitHub</title>
<style>
  a {{ color: inherit; }}
  @media (max-width: 620px) {{
    .wrap {{ width: 100% !important; }}
    .px {{ padding-left: 18px !important; padding-right: 18px !important; }}
  }}
</style></head>
<body style="margin:0;padding:0;background:{PAPER}" bgcolor="{PAPER}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="{PAPER}"><tr><td align="center" style="padding:24px 0 40px">
<table class="wrap" role="presentation" width="640" cellpadding="0" cellspacing="0" style="width:100%;max-width:640px">

<tr><td class="px" style="padding:24px 32px 12px">
  <div style="font:600 11px/1 {MONO};letter-spacing:2px;color:{ACCENT};text-transform:uppercase">&#9632;&nbsp;RADAR BUSINESS GITHUB</div>
  <div style="font:400 36px/1.1 {SERIF};color:{INK};margin:12px 0 6px">Pépites récentes &amp; Opportunités</div>
  <div style="font:400 14px/1.5 {SANS};color:{MUTED}">
    Sélection des dépôts récents avec traction rapide analysés par Groq.
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
    Critères : dépôts récents à croissance rapide, évaluation pain point &amp; cible solvable.
  </div>
</td></tr>

</table>
</td></tr></table>
</body></html>"""
