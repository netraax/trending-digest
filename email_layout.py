"""Small, table-based email shell with mobile defaults."""
import html
from datetime import datetime, timezone

MAX_HTML_BYTES = 90000


def check_size(body):
    size = len(body.encode("utf-8"))
    if size > MAX_HTML_BYTES:
        raise ValueError(f"Email trop volumineux : {size} octets (limite {MAX_HTML_BYTES}). Réduire les analyses avant envoi.")
    return body


def button(url, label, accent="#C6FF3D"):
    return (f'<a href="{html.escape(url, quote=True)}" style="display:inline-block;margin:6px 8px 6px 0;'
            f'padding:13px 16px;background:{accent};color:#0D1117;border-radius:6px;'
            f'font:bold 15px/20px Arial;text-decoration:none">{html.escape(label)}</a>')


def card(content):
    return ('<tr><td class="pad" style="padding:24px;border-bottom:1px solid #30363D;'
            'overflow-wrap:anywhere;word-break:break-word">' + content + '</td></tr>')


def shell(title, heading, intro, content, accent):
    today = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    return check_size(f'''<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>@media(max-width:620px){{.pad{{padding:20px 16px!important}}h1{{font-size:30px!important}}}}
</style></head><body style="margin:0;background:#0D1117;color:#E6EDF3;font:16px/1.6 Arial,sans-serif">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="#0D1117"><tr><td align="center">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="width:100%;max-width:640px;table-layout:fixed">
<tr><td class="pad" style="padding:32px 24px;background:#161B22;border-top:4px solid {accent}">
<div style="font-size:13px;letter-spacing:1px;color:{accent}">{title} · {today}</div>
<h1 style="font:36px/1.15 Georgia;margin:18px 0">{heading}</h1><p style="color:#B7C1CD;margin:0">{intro}</p></td></tr>
{content}
<tr><td class="pad" style="padding:24px;font:13px/1.6 Arial;color:#AAB4BF">
Veille quotidienne · GitHub + Groq. Idées, prix et délais : hypothèses à valider.
Le quota gratuit Groq concerne le radar ; les produits envisagés ont leurs propres coûts.
</td></tr></table></td></tr></table></body></html>''')
