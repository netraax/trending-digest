# Trending Digest

## Groq gratuit : appels progressifs pour les deux emails

Les recherches GitHub restent inchangées. Le digest explique ses 10 projets
un par un ; le radar analyse les 15 candidats présélectionnés un par un, puis
classe l'ensemble et retient jusqu'à 6 résultats. Le nombre peut être inférieur
si le modèle écarte des candidats. Une sélection vide n'est plus remplacée par
des opportunités artificielles.

`groq_client.py` est partagé par les deux scripts :

- Pause prudente de 65 secondes entre appels, et respect des délais de quota
  retournés par Groq. Les attentes sont découpées en pauses de 30 secondes.
- Découpage supplémentaire si Groq refuse la taille du lot ou tronque la réponse.
  Un dépôt encore trop volumineux seul provoque un arrêt explicite.
- Validation JSON et des noms avant utilisation ; aucun email partiel n'est
  envoyé si un lot échoue.
- Cache des réponses validées pendant 24 heures, réutilisé uniquement lorsque
  les entrées, instructions et modèles sont identiques. Les nouvelles métriques
  peuvent donc nécessiter une nouvelle analyse.
- Registre partagé dans `logs/groq_runtime.json`, sauvegardé avant chaque appel.
  Il contient les réponses et compteurs, jamais la clé API ni le prompt.
  Comme les autres logs, ce fichier est commité par les workflows.
- Tokens réels de `usage` lorsqu'ils sont disponibles ; réservation estimée
  conservatrice pour les appels en échec ou interrompus. Le total porte sur les
  deux emails et tous les modèles, sur une fenêtre glissante de 24 heures.

Valeurs par défaut configurables par variables d'environnement Python :

| Variable | Défaut | Fonction |
|---|---:|---|
| `GROQ_DAILY_TOKEN_BUDGET` | 180000 | Budget partagé sur 24 h |
| `GROQ_DAILY_REQUEST_BUDGET` | 900 | Nombre maximal d'appels sur 24 h |
| `GROQ_REQUEST_TOKEN_LIMIT` | 7000 | Estimation entrée + sortie par appel |
| `GROQ_MAX_WAIT_SECONDS` | 1800 | Attente cumulée maximale par exécution |

Pour Docker, transmettre une variable avec `-e NOM` après l'avoir définie dans
l'environnement du workflow. Les limites exactes de l'organisation Groq font
autorité ; les autres applications utilisant cette organisation ne figurent pas
dans ce registre. Le client ne souscrit à aucune offre payante.

Si le budget journalier ou le délai maximal est atteint, le run s'arrête avec
une erreur explicite et conserve les lots terminés. Le prochain lancement pourra
réutiliser ceux dont les entrées sont identiques et le cache encore valide.
Il n'attend pas indéfiniment sur un runner GitHub.

Les workflows disposent désormais de 60 minutes et partagent un groupe de
concurrence. Ne pas lancer les deux scripts simultanément en local contre le
même `LOG_DIR` : le registre est conçu pour un seul écrivain.

Tests hors ligne, sans secrets ni envoi d'email :

```bash
python -B -m unittest test_groq_client test_project_analysis test_profile_trust test_discovery -v
```

Every morning at 8:00 IST a GitHub Action scrapes [github.com/trending](https://github.com/trending), asks Groq for French explanations, concrete uses and product hypotheses for each of the top 10 repos, and emails you the list.

```
GitHub Actions cron ─► docker build/run ─► scrape trending ─► README excerpts ─► Groq (ELI5) ─► Gmail SMTP ─► your inbox
```

## 1. Get the two keys (both free)

- **Groq:** create a key at https://console.groq.com/keys
- **Gmail app password:** turn on 2-Step Verification, then create an app password at https://myaccount.google.com/apppasswords. It's 16 letters. Use it here, never your normal Gmail password.

## 2. Test locally in Docker

```bash
cp .env.example .env        # then fill in your keys
docker compose build
docker compose run --rm digest --dry-run --no-llm   # scrape only, no keys needed
docker compose run --rm digest --dry-run            # + Groq, writes out/digest.html
docker compose run --rm digest                      # real run, sends the email
```

Open `out/digest.html` in a browser to see exactly what the email will look like.

### Test with a Docker Agent

`test-agent.yaml` is a [Docker Agent](https://docs.docker.com/ai/docker-agent/) QA tester that runs on Groq. It builds the image, does a dry run, and checks the output: 10 repos, valid links, star counts, and readable ELI5 text. It ends with a PASS/FAIL table and never sends email.

```bash
docker agent run test-agent.yaml --env-from-file .env --exec "run the tests"
```

## 3. Deploy on GitHub Actions

1. Push this folder to a new GitHub repo (private is fine).
2. In the repo, go to **Settings → Secrets and variables → Actions** and add these secrets:
   `GROQ_API_KEY`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `EMAIL_TO`
3. Two workflows are available in the **Actions** tab:
   - **Trending digest:** daily morning digest of top GitHub trending repos explained simply in French.
   - **Business radar:** runs every 2 days, scanning recent fast-growing repos and using Groq to detect micro-SaaS / business opportunities.

Tick "Dry run" first if you want to see the HTML artifact without sending an email.

After that it runs on its own every day. To change the time, edit the `cron` in `.github/workflows/digest.yml`. Cron times are in UTC, and GitHub can start scheduled runs a few minutes late.

> GitHub turns off scheduled workflows in a repo after 60 days with no commits. If the emails stop, click "Enable workflow" in the Actions tab.

## History and errors

Every run commits a dated record back to this repo, authored as you, so each day shows up as a green square on your GitHub profile.

```
logs/runs.csv                          one line per run: date, time, ok/error, mode, model, top repo
logs/history/2026/10/2026-10-15.md     that day's digest as a table plus the explanations
logs/history/2026/10/2026-10-15.json   the same data as JSON
logs/state.json                        last day an email went out
errors/2026/10/2026-10-15_083012.log   stage, error and traceback for any failed run
```

A failed run still commits its error log, so the day stays green and you can see what broke. The schedule also has backup slots at 09:00, 11:00 and 14:00 IST. GitHub sometimes runs schedules late or drops them, so a later slot retries if the 08:00 run failed or never started, and it does nothing if today's email already went out.

> Because this repo is private, the green squares only appear if your profile has **Private contributions** turned on. On your profile, open the "Contribution settings" dropdown above the contribution graph and tick it. The commit email in the workflow (`COMMIT_EMAIL`) must be an email on your GitHub account.

## Settings (env vars)

| Var | Default | |
|---|---|---|
| `TOP_N` | `10` | how many repos |
| `SINCE` | `daily` | `daily`, `weekly` or `monthly` |
| `GROQ_MODEL` | tries `openai/gpt-oss-120b`, then `qwen/qwen3.8-27b`, then `openai/gpt-oss-20b` | pin one model |
| `EMAIL_TO` | your `GMAIL_ADDRESS` | comma-separated for several people |


## Comprendre et exploiter les projets (étape 2)

`project_analysis.py` collecte pour chaque dépôt la révision courante, son
arborescence, puis jusqu'à trois fichiers : README, manifeste de dépendances,
exemple d'utilisation ou point d'entrée. Les fichiers volumineux et les liens
symboliques sont exclus. Les sections utiles du README sont privilégiées ;
l'analyse reste partielle, aucun code tiers n'est exécuté.

Les extraits sont liés à une révision GitHub précise. Ils sont bornés en octets
et réduits avant l'appel pour réserver la place de la réponse sous le budget
prudent de 7 000 tokens estimés. Chaque projet est analysé séparément :
1 900 tokens de sortie pour les tendances, 2 400 pour le radar. Les pauses,
le suivi partagé et la reprise de l'étape 1 restent actifs.

Chaque fiche HTML et texte présente : fonctionnement entrée/traitement/sortie,
deux usages, deux pistes de produits, acheteur et modèle économique hypothétiques,
périmètre de première version, travail à ajouter, limites et premier test.
La longueur demandée est de 220–300 mots dans le quotidien, 350–450 dans le radar.
Ces longueurs sont des consignes éditoriales, pas une garantie du modèle.

Les identifiants de sources renvoyés sont validés contre ceux fournis. Cela ne
prouve pas automatiquement que chaque affirmation est vraie : l'email précise
que les extraits ont été consultés, le code non exécuté et le marché non étudié.
Aucun prix ni idée ne constitue une demande solvable validée. Les erreurs de
collecte sont visibles dans la fiche. Sans profil transmis à l’analyse, le score de fit est supprimé et indiqué comme non évalué.

La collecte par tendances et les cinq recherches business ne changent pas.
Le radar conserve jusqu'à six projets parmi les quinze analysés. La recherche
web de concurrence et le déploiement GitHub ne font pas partie de cette étape.


## Profil et niveau de preuve (étape 3)

Le Dockerfile copie `profile.yml` et vérifie sa validité lors de la construction.
Les deux emails chargent ce profil via `builder_profile.py`. Par défaut, le fichier
est recherché à côté du module, indépendamment du dossier de lancement.
`PROFILE_PATH` permet de sélectionner un autre fichier. Un profil absent, un YAML
invalide ou des rubriques obligatoires manquantes provoquent une erreur explicite.

Le contexte transmis conserve toutes les rubriques et leurs clés, en abrégeant
les textes de façon répartie pour tenir dans 2 400 octets ; il ne coupe plus
arbitrairement le début du JSON en perdant les préférences en fin de fichier.
Le profil privilégie la découverte et l'inspiration, avec Groq gratuit pour la veille.
Les prix, délais et avantages régionaux sont des préférences à vérifier.

Les emails distinguent désormais : métadonnées seules, documentation/dépendances,
et lecture partielle d'un extrait technique. Aucun de ces niveaux n'est un test
exécuté ou une étude de marché. Les scores sont des jugements provisoires et une
rubrique en demande la justification ; ils ne constituent pas des faits vérifiés.

L'indice de croissance estimé porte sa formule et n'est plus qualifié de rapide
ou fulgurant. Une variation mesurée est identifiée séparément, y compris en cas
de perte d'étoiles. Les compteurs d'issues GitHub sont affichés comme issues/PR
ouvertes, et `pushed_at` comme dernier push plutôt que dernier commit.

`--no-llm` exige désormais `--dry-run` dans les deux scripts. Les aperçus sans IA
n'inventent ni notes, ni durée de MVP, ni opportunité de marché. La lecture du
feedback dispose de `issues: read` dans le workflow business et signale ses échecs.

Ces garde-fous améliorent la transparence mais ne garantissent pas la véracité
sémantique de chaque phrase du modèle. Une recherche externe de concurrence
et une validation auprès d'utilisateurs restent des étapes distinctes.


## Découverte progressive et filtres souples (étape 4)

Les cinq filets historiques (frais, réveillés, alternatives, self-hosted, SaaS)
sont conservés avec leurs fenêtres, tris et nombres de pages. La taille minimale
de 50 Ko est supprimée pour ne pas éliminer les petits composants utiles.
Deux recherches complémentaires, une page chacune, ajoutent :

- Discrets : moins de 10 jours par défaut, 3 à 50 étoiles, tri par mise à jour.
- Récents : entre 10 et 30 jours par défaut, 5 à 3 000 étoiles, tri par mise à jour.

Au total : huit pages maximum (400 résultats bruts avant doublons), contre six.
Ce n'est pas une recherche exhaustive. Une réponse Search incomplète est signalée.
Le digest Trending conserve sa source et ses dix projets.

Seuls les forks, miroirs, dépôts archivés ou désactivés sont exclus structurellement.
Les descriptions courtes, pauses d'activité, petits ratios de forks et pics initiaux
restent analysables. Un auteur établi n'est plus exclu ni pénalisé à ce seul titre.
Les mots-clés pédagogiques/hors cible sont des indices, jamais une preuve d'arnaque.
Un mot ambigu dans le nom seul (ex. portfolio-builder) ne réduit pas le score.

Le préscore logarithmique tempère les pics d'étoiles et combine récence, activité,
forks et diversité des filets. Les pondérations sont des heuristiques initiales
à calibrer sur les résultats, pas un modèle de potentiel commercial validé.
Le classement réduit légèrement la priorité d'un auteur ou langage déjà représenté,
sans quota bloquant : il peut toujours remplir une sélection peu diversifiée.

Pour 15 candidats, jusqu'à trois places servent à explorer les projets de 50 étoiles
ou moins, âgés de 30 jours maximum. Faute de candidats correspondants, les places
reviennent au classement général. Le total envoyé à Groq reste 15 ; l'email retient
jusqu'à six projets après analyse. Les signalements n'augmentent pas les appels IA.

`out/discovery_report.json` (ou le dossier `--out`) décrit les volumes, exclusions,
filets d'origine, composantes du préscore, indices de prudence et motif de sélection.
Les snapshots sont enregistrés avant Groq hors dry-run. Une panne de l'analyse ou
de l'envoi ne les efface donc plus, sans marquer l'email comme envoyé.

La mémoire historique reste compatible. Un projet peut revenir si ses étoiles
doublent, si un nouveau push est constaté au moins 14 jours après l'analyse, ou
pour réévaluation après 30 jours. Ces règles évitent de le renvoyer quotidiennement.
Les anciens enregistrements sans date d'analyse utilisent leur première observation.
