"""Offline layout fixtures: python preview_emails.py. No API or email."""
from pathlib import Path
from copy import deepcopy
from email_template import render_html as trending
from business_template import render_html as business

SAMPLE = dict(name="exemple/projet-demonstration", url="https://github.com", stars=1234,
    forks=12, language="Python", gained_n=42, age_days=12, score=7, fit_score=8,
    profile_loaded=True, category="Outil développeur", stars_per_day=12,
    summary="APERÇU FICTIF — Un outil qui transforme des documents en données structurées. Une équipe peut tester son intégration avant de construire un produit.",
    workflow="Un utilisateur fournit un document. Le logiciel extrait les champs et produit un résultat à contrôler. Les formats réellement acceptés restent à vérifier.",
    use_cases="Une agence prépare des imports clients ; une équipe interne organise ses archives. Chaque usage demande un essai sur des documents représentatifs.",
    products="Hypothèses : un assistant d’import pour agences, ou un outil local de préparation de données. La valeur ajoutée serait le contrôle des erreurs et la simplicité du parcours.",
    monetization="L’agence pourrait payer par dossier traité. Un prix de 20 à 40 € par mois est une hypothèse à confronter au volume, au support et aux coûts de traitement, sans demande validée.",
    build_plan="Réutiliser le moteur après vérification de licence. Ajouter un formulaire, un aperçu et un export. Exclure la facturation du premier essai. Charge et coût non estimables sans test du moteur.",
    limitations="Qualité sur les fichiers complexes et maintenance non établies. Vérifier la licence et les données envoyées aux services externes. Le quota gratuit du radar ne finance pas ce produit.",
    next_step="Tester dix documents variés et noter les erreurs. Demander à une agence combien de temps elle consacre actuellement à corriger ces imports.",
    assessment="Intérêt exploratoire pour un développeur Python ; potentiel commercial non validé. Le premier test doit établir si le moteur apporte un avantage utilisable.",
    evidence={"sources": [], "notes": []})


def generate():
    out = Path("out/design-preview")
    out.mkdir(parents=True, exist_ok=True)
    for label, count, render in (("trending", 10, lambda rows: trending(rows, "daily")),
                                  ("business", 6, lambda rows: business(rows, 120))):
        rows = [dict(deepcopy(SAMPLE), name=f"exemple/projet-demonstration-{i+1}") for i in range(count)]
        body = render(rows)
        (out / f"{label}.html").write_text(body, encoding="utf-8")
        print(f"{label}: {len(body.encode('utf-8'))} octets, {count} projets")
    return out


if __name__ == "__main__":
    generate()
