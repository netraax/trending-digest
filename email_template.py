"""Ten trends: concise explanations and inspiration, in GitHub order."""
import html
from project_analysis import details_html, field_text
from email_layout import shell, card, button


def render_html(repos, since):
    period = {"daily": "aujourd’hui", "weekly": "cette semaine", "monthly": "ce mois-ci"}.get(since, since)
    rows = []
    for i, repo in enumerate(repos, 1):
        name = html.escape(repo["name"])
        url = repo.get("url", "https://github.com/" + repo["name"])
        summary = html.escape(field_text(repo.get("summary") or repo.get("eli5", "")))
        meta = html.escape(f"{repo.get('language') or 'Langage non indiqué'} · ★ {repo.get('stars', 0):,} · +{repo.get('gained_n', 0):,} {period}")
        content = (f'<div style="color:#C6FF3D;font-size:14px">{i:02d} · {html.escape(repo.get("category", "Tendance"))}</div>'
                   f'<h2 style="font:700 24px/1.3 Arial;margin:8px 0">{name}</h2>'
                   f'<div style="font-size:13px;color:#AAB4BF">{meta}</div><p>{summary}</p>')
        content += details_html(repo, theme="editorial")
        content += button(url, "Ouvrir le dépôt →")
        rows.append(card(content))
    total = sum(r.get("gained_n", 0) for r in repos)
    intro = (f"{len(repos)} tendances pour comprendre ce qui se construit et trouver de l’inspiration. "
             f"+{total:,} étoiles {period} sur cette sélection. Ordre de GitHub Trending ; pas un classement business.")
    return shell("THE TRENDING DIFF", "Ce que GitHub construit aujourd’hui.", intro, "".join(rows), "#C6FF3D")
