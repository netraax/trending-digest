"""Editorial email template. Tables + inline styles only, so Gmail, Outlook and Apple Mail all keep the layout.
Web fonts load in Apple Mail / iOS; Gmail falls back to Georgia / Helvetica / Menlo, which is designed for."""
import html
from project_analysis import details_html
from datetime import datetime, timezone

INK, PAPER, LIME, MUTED, LINE = "#E6EDF3", "#0D1117", "#C6FF3D", "#8B949E", "#30363D"
DARK = "#111111"  # near-black blocks (header, footer, lead button)
SERIF = "'Instrument Serif',Georgia,'Times New Roman',serif"
SANS = "Inter,-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"
MONO = "'JetBrains Mono','SFMono-Regular',Menlo,Consolas,monospace"
DAYS_FR = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
MONTHS_FR = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
PERIOD_FR = {"daily": "aujourd’hui", "weekly": "cette semaine", "monthly": "ce mois-ci"}
PERIOD_LABEL_FR = {"daily": "AUJOURD’HUI", "weekly": "CETTE SEMAINE", "monthly": "CE MOIS-CI"}


def _split(name):
    owner, _, repo = name.partition("/")
    return html.escape(owner), html.escape(repo)


def _pill(text, fg, border):
    if not text:
        return ""
    return (f'<span style="display:inline-block;font:600 10px/1 {MONO};letter-spacing:1px;text-transform:uppercase;'
            f'color:{fg};border:1px solid {border};border-radius:99px;padding:5px 9px">{html.escape(text)}</span>')


def _bar(r, top, track, fill):
    pct = max(4, round(100 * (r["gained_n"] / top) ** 0.5)) if top else 4  # sqrt so small risers stay visible
    return f"""<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
<td style="padding-right:12px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="{track}" style="background:{track};border-radius:3px"><tr>
<td width="{pct}%" height="6" bgcolor="{fill}" style="background:{fill};border-radius:3px;font-size:0;line-height:0">&nbsp;</td><td style="font-size:0;line-height:0">&nbsp;</td></tr></table></td>
<td width="1" style="white-space:nowrap;font:600 11px/1 {MONO};color:{fill}">+{r['gained_n']:,}</td></tr></table>"""


def _meta(r, color):
    dot = (f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
           f'background:{r.get("lang_color", "#8b8b8b")};vertical-align:middle"></span>&nbsp;')
    parts = [dot + html.escape(r["language"])] if r["language"] else []
    parts += [f"&#9733;&nbsp;{r['stars']:,}", f"forks&nbsp;{r['forks']:,}"]
    return f'<div style="font:500 12px/1.5 {MONO};color:{color}">{"&nbsp;&nbsp;&middot;&nbsp;&nbsp;".join(parts)}</div>'


def _row(i, r, top):
    o, n = _split(r["name"])
    biz_html = ""
    if r.get("business_idea"):
        biz_html = (
            f'<div style="margin:10px 0 12px;padding:8px 12px;background:#1C2128;border-left:3px solid {INK};border-radius:0 4px 4px 0">'
            f'<span style="font:600 10px/1 {MONO};letter-spacing:1px;color:{INK};text-transform:uppercase">💡 ANGLE SAAS : </span>'
            f'<span style="font:400 13px/1.45 {SANS};color:#C9D1D9">{html.escape(r["business_idea"])}</span>'
            f'</div>'
        )
    return f"""
<tr><td class="px" style="padding:30px 40px;border-top:1px solid {LINE}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
<td class="rank" width="78" valign="top" style="font:400 52px/0.9 {SERIF};color:{INK};letter-spacing:-2px">{i:02d}</td>
<td valign="top">
  <a href="{r['url']}" style="text-decoration:none;color:{INK}"><span style="font:500 13px/1.3 {MONO};color:{MUTED}">{o}&thinsp;/</span><br>
  <span style="font:700 21px/1.25 {SANS};color:{INK};letter-spacing:-0.4px">{n}</span></a>
  {'<div style="height:10px;line-height:10px">&nbsp;</div>' + _pill(r.get('category'), MUTED, LINE) if r.get('category') else ''}
  <p style="margin:12px 0 14px;font:400 15px/1.6 {SANS};color:#C9D1D9">{html.escape(r['eli5'])}</p>
  {details_html(r, theme="editorial") if r.get("summary") else biz_html}
  {_meta(r, MUTED)}
  <div style="height:12px;line-height:12px">&nbsp;</div>{_bar(r, top, "#1C2128", INK)}
</td></tr></table>
</td></tr>"""


def _stat(value, label, color, last=False):
    pad = "18px 0 0 0" if last else "18px 12px 0 0"
    return (f'<td class="stat" width="33%" valign="top" style="padding:{pad}">'
            f'<div style="font:400 32px/1 {SERIF};color:{color}">{value}</div>'
            f'<div style="font:500 10px/1.4 {MONO};letter-spacing:1.5px;color:#8A8A8A;margin-top:6px">{label}</div></td>')


def render_html(repos, since):
    now = datetime.now(timezone.utc)
    period = PERIOD_FR.get(since, "aujourd’hui")
    period_label = PERIOD_LABEL_FR.get(since, "AUJOURD’HUI")
    day_name = DAYS_FR[now.weekday()]
    month_name = MONTHS_FR[now.month - 1]
    top = max((r["gained_n"] for r in repos), default=0)
    total = sum(r["gained_n"] for r in repos)
    langs = [r["language"] for r in repos if r["language"]]
    lead_lang = max(set(langs), key=langs.count) if langs else "Mixte"
    lead = repos[0]
    lo, lr = _split(lead["name"])
    lead_biz_html = ""
    if lead.get("business_idea"):
        lead_biz_html = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="{DARK}" style="background:{DARK};border-radius:8px;margin:20px 0 22px">
<tr><td style="padding:16px 20px">
  <div style="font:600 10px/1 {MONO};letter-spacing:1.5px;color:{LIME};text-transform:uppercase">&#9632;&nbsp;OPPORTUNITÉ SAAS &amp; BUSINESS</div>
  <div style="font:400 14px/1.55 {SANS};color:{INK};margin-top:6px">{html.escape(lead['business_idea'])}</div>
</td></tr>
</table>"""
    rows = "".join(_row(i, r, top) for i, r in enumerate(repos[1:], 2))

    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark"><meta name="supported-color-schemes" content="dark">
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;700&family=JetBrains+Mono:wght@500;600&display=swap" rel="stylesheet">
<title>The Trending Diff</title>
<style>
  a {{ color: inherit; }}
  @media (max-width: 620px) {{
    .px {{ padding-left: 22px !important; padding-right: 22px !important; }}
    .hl {{ font-size: 50px !important; }}
    .lead-n {{ font-size: 88px !important; }}
    .rank {{ width: 56px !important; font-size: 40px !important; }}
    .tb {{ font-size: 9px !important; letter-spacing: 1px !important; }}
    .hide-sm {{ display: none !important; }}
    .stat {{ display: block !important; width: 100% !important; padding: 0 0 16px !important; }}
  }}
</style></head>
<body style="margin:0;padding:0;background:{PAPER}" bgcolor="{PAPER}">
<div style="display:none;max-height:0;overflow:hidden;opacity:0">#1 {period} : {html.escape(lead['name'])}. {html.escape(lead['eli5'][:110])}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="{PAPER}" style="background:{PAPER}"><tr><td align="center" style="padding:0">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="width:100%;max-width:640px">

<tr><td class="px" bgcolor="{DARK}" style="background:{DARK};padding:16px 40px;border-bottom:1px solid #2A2A2A">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
<td class="tb" style="white-space:nowrap;font:600 11px/1 {MONO};letter-spacing:2px;color:{LIME}">&#9632;&nbsp;THE TRENDING DIFF</td>
<td class="tb" align="right" style="white-space:nowrap;font:500 11px/1 {MONO};letter-spacing:1px;color:#8A8A8A">N&ordm;&nbsp;{now.timetuple().tm_yday:03d}<span class="hide-sm"> &middot; {day_name}</span> &middot; {now:%d} {month_name} {now:%Y}</td>
</tr></table></td></tr>

<tr><td class="px" bgcolor="{DARK}" style="background:{DARK};padding:52px 40px 44px">
<div class="hl" style="font:400 66px/0.95 {SERIF};color:{INK};letter-spacing:-2px">Ce que GitHub<br>construit<br><i style="color:{LIME}">{period}.</i></div>
<p style="margin:22px 0 34px;font:400 16px/1.55 {SANS};color:#8B949E;max-width:440px">Une sélection de {len(repos)} tendances GitHub : fonctionnement, usages concrets et pistes de produits à explorer.</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #2E2E2E"><tr>
{_stat(f"+{total:,}", f"ÉTOILES {period_label}", LIME)}{_stat(html.escape(lead_lang), "LANGAGE PRINCIPAL", INK)}{_stat(f"{lead['gained_n']:,}", "ÉTOILES POUR #1", INK, last=True)}
</tr></table>
</td></tr>

<tr><td class="px" bgcolor="{LIME}" style="background:{LIME};padding:40px 40px 44px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
<td style="font:600 11px/1 {MONO};letter-spacing:2px;color:{DARK}">EN TÊTE DU CLASSEMENT</td>
<td align="right">{_pill(lead.get('category'), DARK, DARK)}</td></tr></table>
<div class="lead-n" style="font:400 120px/0.85 {SERIF};color:{DARK};letter-spacing:-6px;margin:22px 0 10px">01</div>
<a href="{lead['url']}" style="text-decoration:none;color:{DARK}"><span style="font:500 14px/1.3 {MONO};color:#3B4A12">{lo}&thinsp;/</span><br>
<span style="font:700 34px/1.1 {SANS};color:{DARK};letter-spacing:-1px">{lr}</span></a>
<p style="margin:18px 0 22px;font:400 23px/1.4 {SERIF};color:{DARK}">{html.escape(lead['eli5'])}</p>
{_meta(lead, "#2F3A0E")}
{details_html(lead, theme="editorial") if lead.get("summary") else lead_biz_html}
<div style="height:20px;line-height:20px">&nbsp;</div>
<table role="presentation" cellpadding="0" cellspacing="0"><tr><td bgcolor="{DARK}" style="background:{DARK};border-radius:99px">
<a href="{lead['url']}" style="display:inline-block;padding:14px 24px;font:600 13px/1 {SANS};color:{LIME};text-decoration:none;letter-spacing:0.3px">Ouvrir le dépôt &nbsp;&rarr;</a>
</td></tr></table>
</td></tr>

<tr><td class="px" style="padding:38px 40px 14px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
<td style="font:600 11px/1 {MONO};letter-spacing:2px;color:{INK}">AUSSI EN PROGRESSION</td>
<td align="right" style="font:500 11px/1 {MONO};letter-spacing:1px;color:{MUTED}">BARRE = ÉTOILES {period_label}</td></tr></table>
</td></tr>
{rows}

<tr><td class="px" bgcolor="{DARK}" style="background:{DARK};padding:44px 40px">
<div style="font:400 40px/1 {SERIF};color:{INK};letter-spacing:-1px">C’est la diff<i style="color:{LIME}">.</i></div>
<p style="margin:14px 0 0;font:400 13px/1.6 {SANS};color:#8B949E">Envoyé chaque matin depuis <a href="https://github.com/trending" style="color:#C9D1D9">github.com/trending</a>. Explications écrites par Groq.</p>
</td></tr>

</table></td></tr></table>
</body></html>"""
