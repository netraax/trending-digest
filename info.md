1. Rendre le signal de croissance plus fiable
Snapshots d’étoiles : à chaque run, enregistre dans business_state.json le nombre d’étoiles de chaque candidat. Au run suivant, tu calcules la vélocité réelle (delta par jour) et l’accélération, sans requête supplémentaire. Étoiles/jour depuis la création est trompeur : un seul passage en première page de Hacker News fait exploser le compteur, puis plus rien.
Watchlist : garde les repos déjà repérés qui continuent de monter, même au-delà de 14 jours. Aujourd’hui, un projet qui décolle au bout de 3 semaines t’échappe.
Signaux de demande réelle : forks, contributeurs, issues ouvertes. 800★ avec presque aucun fork, c’est de la curiosité, pas de l’usage.
Filtrer ce qui est déjà monétisé : si le champ homepage ou le README mentionne Pricing, Cloud ou Hosted, l’opportunité est probablement prise. De même, un projet porté par une grosse organisation ne te laisse pas de place.
2. Donner plus de matière à Groq
Les titres des 10 dernières issues : c’est ce que les utilisateurs réclament, donc souvent les futures fonctionnalités payantes.
La licence : MIT ou Apache permettent un SaaS fermé. AGPL ou GPL compliquent le wrapper commercial, et l’absence de licence signifie « tous droits réservés ». Ajoute un champ ⚠️ Risque légal.
Deux passes : un modèle rapide trie ~30 candidats sur description et topics, puis un modèle plus costaud analyse en profondeur seulement les 5 à 8 retenus. Tu consommes moins de quota et la qualité monte.
Sortie JSON stricte, validée par un schéma, avec température basse.
Garde-fous anti-hallucination : interdiction d’inventer des chiffres de marché, et « inconnu » obligatoire quand l’info n’est pas dans les données fournies.
Score décomposé (douleur, taille de cible, faisabilité, concurrence) plutôt qu’une note unique, plus un champ « pourquoi ça pourrait échouer » pour contrer l’optimisme du modèle.
3. Personnaliser avec un fichier profile.yml

Décris ta stack, ton temps disponible, ton budget, ton audience et tes secteurs de prédilection, puis injecte-le dans le prompt. Le score devient « adéquation avec toi », ce qui est bien plus pertinent qu’un 8/10 universel. Tu peux aussi ajouter un angle francophone/européen (RGPD, hébergement souverain, localisation FR, facturation électronique qui se déploie en France), qui fait souvent la différence face aux outils américains.

4. Une boucle de feedback gratuite

Dans chaque fiche, ajoute deux liens 👍 / 👎 pointant vers une issue pré-remplie de ton dépôt (issues/new?title=...&labels=interessant). Au run suivant, le script lit les issues labellisées et les injecte comme exemples dans le prompt. Le radar apprend tes goûts sans infrastructure supplémentaire.

5. Croiser plusieurs sources

Un projet visible sur GitHub et Hacker News (Show HN, via l’API Algolia gratuite et sans clé) et avec des téléchargements npm/PyPI en hausse est un signal bien plus fort qu’une source isolée. Product Hunt est une autre option. Je me méfierais de Reddit, dont l’accès API est devenu contraignant.

6. Aller plus loin que la newsletter
Détection de thèmes : un récap hebdomadaire qui regroupe les repos par topics. Cinq projets sur le même sujet, c’est un marché qui bouge, souvent plus exploitable qu’un repo isolé.
Alerte rapide (ntfy.sh ou Telegram) via un workflow léger toutes les 6 h quand la vélocité dépasse un seuil, au lieu d’attendre 2 jours.
Brief de lancement à la demande : un workflow workflow_dispatch où tu donnes un repo, et il génère positionnement, texte de landing page, 5 questions d’interview client, communautés où poster et test de prix.
Archive consultable sur GitHub Pages : toutes les fiches passées, filtrables.
Fiche enrichie (exemple)
[ 🔥 8/10 · Adéquation avec toi : 7/10 ]   ★ 340 (+48★/j sur 3 j, accélération ↑)
acme/fast-invoice-parser · MIT · 41 forks · 12 issues

🎯 Problème · 👥 Cible · 💡 Angle (comme avant)
📊 Score : douleur 8 · marché 7 · faisabilité 9 · concurrence 5
🏁 Concurrents existants : …
🛠️ MVP : ~1 week-end · 🚀 Premiers clients : où les trouver
🇫🇷 Angle francophone/UE : …
⚠️ Risques : …
💬 Les utilisateurs demandent (issues) : export CSV, multi-devises…
[ 👍 Intéressant ]  [ 👎 Pas pour moi ]  [ Analyser le code → ]
Ordre que je te conseille
Snapshots et signaux de demande (issues, forks, licence).
JSON strict avec score décomposé.
profile.yml.
Boucle de feedback.
Autres sources, puis alertes et brief de lancement.

Petit détail technique : un cron */2 sur le jour du mois donne le 31 puis le 1er, soit deux jours consécutifs en fin de mois. Ce n’est pas grave, mais tu peux le contourner en comparant la date du dernier run dans le state.

Quel est ton objectif principal : lancer toi-même un micro-SaaS (le profil et le temps disponible comptent alors beaucoup), ou faire de la veille pour d’autres ? Dis-moi aussi par quelle étape tu veux commencer et je t’écris le code correspondant, adapté à tes fichiers actuels.

ok et pour le filtrage des depot tu as une idéé ? comment trouver les nouvelle petite ? mettre quoi comme regle ?

Pour trouver les petits projets avant tout le monde, il faut abandonner la requête unique triée par étoiles. Elle ne remonte que les plus gros, ceux qui sont déjà visibles partout. L’API Search autorise 30 requêtes par minute, donc 4 à 6 requêtes complémentaires par run ne posent aucun problème de quota.

1. Plusieurs filets au lieu d’un

Chaque requête cible un type de signal différent :

Filet	Ce qu’il attrape	Fenêtre d’étoiles
Frais	repos créés dans les 10 derniers jours	5 à 300
Réveillés	repos de 1 à 4 mois qui ont recommencé à bouger (pushed récent)	30 à 800
« Alternative à »	repos dont la description ou le README dit alternative to…	10 à 1000
Self-hosted / SaaS	topic:self-hosted, topic:saas, etc.	10 à 500

Le filet « alternative à » est à mon avis le meilleur pour ton objectif. Un projet qui se positionne contre un outil payant cible un marché dont la demande est déjà prouvée. Les « réveillés » règlent le défaut de la fenêtre de 14 jours, qui te fait rater les projets qui décollent plus tard.

Pour les étoiles, en dessous de 5 c’est du bruit, et au-dessus de 1000 le projet est déjà connu. La zone intéressante va de 10 à 300★ avec moins de 30 jours d’existence.

python
from datetime import datetime, timedelta, timezone

def d(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

BASE = "fork:false archived:false mirror:false size:>=50 NOT awesome in:name"

QUERIES = [
  ("frais",        f"created:>={d(10)} stars:5..300 {BASE}", "stars"),
  ("reveilles",    f"created:{d(120)}..{d(30)} pushed:>={d(5)} stars:30..800 {BASE}", "updated"),
  ("alternatives", f'"alternative to" in:description,readme created:>={d(45)} stars:10..1000 {BASE}', "stars"),
  ("self-hosted",  f"topic:self-hosted created:>={d(45)} stars:10..1000 {BASE}", "stars"),
  ("saas",         f"topic:saas created:>={d(30)} stars:10..500 {BASE}", "stars"),
]
# GET /search/repositories?q=...&sort=...&order=desc&per_page=50
# → pause de 2 s entre requêtes, dédoublonnage par full_name

size:>=50 (en Ko) élimine déjà les dépôts quasi vides. L’API limite chaque requête à 5 opérateurs AND/OR/NOT, donc garde les requêtes simples.

2. Règles de filtrage dures (gratuites, avant Groq)

Elles s’appliquent après récupération, sur les champs déjà renvoyés par l’API :

Bruit pédagogique : exclure si les topics contiennent tutorial, course, homework, leetcode, interview, cheatsheet, roadmap, dotfiles, portfolio, bootcamp, ou si le nom matche awesome|cheat|roadmap|leetcode.
Arnaques et spam : exclure airdrop, crack, keygen, cheat, trading-bot, pump. Ce sont des fermes à étoiles.
Étoiles suspectes : si stars > 100 et forks/stars < 1 %, c’est de la curiosité ou des étoiles achetées. Si le repo a moins de 3 jours et plus de 500★, méfiance aussi.
Projet mort-né : pushed_at à plus de 14 jours, ou une description vide, éliminés.
Grosses structures : liste noire de propriétaires (google, microsoft, nvidia, openai, meta, alibaba, tencent, bytedance, huggingface, aws…). Sinon, tu peux regarder owner.type == "Organization" avec un grand nombre de membres, mais cela demande un appel de plus.
Déjà monétisé : plutôt que d’exclure, marque le repo si homepage ou le README contient pricing, cloud, hosted, enterprise, YC. Groq peut le prendre en compte dans le champ concurrence.
Déjà envoyé : garde un seen dans le state, et ne renvoie un repo que si ses étoiles ont au moins doublé depuis la dernière fois.

Pour la licence, ne l’utilise pas comme filtre. Elle ne compte que si tu veux construire sur le code. Si tu réimplémentes l’idée, une licence AGPL ou l’absence de licence ne te gêne pas, donc un simple drapeau ⚠️ suffit.

3. Pré-score pour ne passer que les ~30 meilleurs à Groq

Les étoiles par jour depuis la création mesurent mal la croissance : un projet de 2 jours à 40★ écrase tout le reste. Je propose un score lissé, avec des signaux de demande :

python
def pre_score(r, now):
    age = max((now - parse(r["created_at"])).days, 2)
    stars = r["stargazers_count"]
    velocity = stars / (age + 3)                       # lisse les repos de 1-2 jours
    demand = min(r["forks_count"] / max(stars, 1), 0.15) / 0.15   # 0 à 1
    fresh = 1.0 if (now - parse(r["pushed_at"])).days <= 7 else 0.4
    return velocity * (0.5 + demand) * fresh

Ce score est le plus utile en 1er filtre. Dès que tu auras les snapshots d’étoiles dans business_state.json, remplace velocity par le vrai delta par jour, qui est bien plus fiable.

4. Régler les seuils

Logue le nombre de repos qui survivent à chaque étape du genre 240 trouvés → 130 après filtres → 30 pré-scorés → 6 retenus par Groq. Si moins de 15 survivent aux filtres, assouplis les seuils d’étoiles. Si plus de 100 passent, resserre-les. Après quelques runs, tu verras vite si le filtre est trop strict ou trop laxiste.

Pour aller encore plus tôt, il y a Hacker News (Show HN via l’API Algolia, sans clé), qui permet de repérer des repos de 5 à 40★ qui commencent à avoir de la traction avant même d’apparaître dans les tris par étoiles de GitHub.