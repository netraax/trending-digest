# 🚀 Trending & Business Radar : Le Guide Complet du Projet

> **En résumé :** Ce projet est ton assistant de veille automatisé 100% autonome. Il tourne gratuitement dans le cloud sur GitHub, scanne des millions de lignes de code chaque jour, demande à une IA (Groq) de les analyser pour toi, et t'envoie directement par email des **idées concrètes de Micro-SaaS et d'outils web à créer**.

---

## 📌 1. Pourquoi ce projet existe ?

Sur GitHub, des milliers de projets incroyables sortent chaque semaine. Le problème :
1. **La page Trending officielle ne montre que la partie émergée de l'iceberg :** les projets déjà connus ou poussés par de grosses entreprises (Nvidia, Google, Vercel).
2. **Le bruit est massif :** 80% des dépôts sont des devoirs d'étudiants, des listes de liens (`awesome-...`) ou des arnaques sans valeur commerciale.
3. **Le manque de recul business :** quand on voit un script technique en Python ou en Rust, il est difficile de savoir immédiatement : *« Est-ce que des gens paieraient pour ça sous forme de site web ? Est-ce qu'il y a de la concurrence en France ? Combien de temps ça prendrait à coder ? »*.

Ce projet résout tout cela automatiquement avec **deux flux d'emails complémentaires**.

---

## 📬 2. Les Deux Radars (Ce que tu reçois)

```text
┌───────────────────────────────────────────────┐
│              TES DEUX EMAILS                  │
├───────────────────────┬───────────────────────┤
│ 1. Le Digest Matinal  │ 2. Le Radar Business  │
│    (Chaque matin 8h)  │    (Tous les 2 jours) │
├───────────────────────┼───────────────────────┤
│ • 10 Tendances du jour│ • Jusqu'à 10 pépites  │
│ • Buzz mondial        │ • Pépites cachées     │
│ • Idées SaaS express  │ • Fiches complètes    │
│ • Style éditorial     │ • Fit profil & Marché │
└───────────────────────┴───────────────────────┘
```

---

### Email 1 · Le Digest Quotidien du Matin (Trending Digest)
- **Fréquence :** Tous les matins vers 08h00.
- **Rôle :** Prendre le pouls du monde tech en 2 minutes au réveil.
- **Ce qu'il fait :**
  - Récupère les 10 dépôts qui ont pris le plus d'étoiles sur les dernières 24 heures.
  - Explique chaque projet en français simple, sans jargon (comme à un curieux de 10 ans).
  - **Sur le projet n°1 du jour :** Affiche un encadré noir contrasté avec une **opportunité concrète de SaaS** à lancer pour surfer sur la hype du jour.
  - **Sur les 9 autres projets :** Ajoute une ligne sobre `💡 ANGLE SAAS : [Idée]`.

#### Aperçu visuel de l'email matinal :
```text
THE TRENDING DIFF                         Nº 311 · sam. · 07 nov. 2026

Ce que GitHub
construit
aujourd’hui.

Les 10 dépôts les plus chauds de GitHub, chacun expliqué comme à un enfant.
Environ trois minutes, sans jargon.

+10 214 ÉTOILES AUJOURD’HUI     LANGAGE PRINCIPAL Python     2 679 ÉTOILES POUR #1


EN TÊTE DU CLASSEMENT
01
NVIDIA / auto-ontology

Il construit une sorte de plan qui dit à une IA où sont les données et ce
qu’elles veulent dire, comme un catalogue de bibliothèque pour un robot.
Les développeurs l’utilisent pour faire des assistants plus fiables.

┌──────────────────────────────────────────────────────────────┐
│ ■ OPPORTUNITÉ SAAS & BUSINESS                                │
│ Créer une interface web à 49€/mois pour connecter            │
│ automatiquement les bases SQL des PME aux agents sans coder. │
└──────────────────────────────────────────────────────────────┘

Python · ★ 8 125 · forks 312
[ Ouvrir le dépôt → ]


AUSSI EN PROGRESSION                         BARRE = ÉTOILES AUJOURD’HUI

02  mattpocock/skills
    De petites fiches qui apprennent aux assistants IA à faire de vraies tâches.
    💡 ANGLE SAAS : Marketplace web de fiches et prompts certifiés pour agences.

03  garrytan/gstack
    ...
```

---

### Email 2 · Le Radar Business (Pépites cachées & Micro-SaaS)
- **Fréquence :** Tous les 2 jours le matin.
- **Rôle :** Dénicher les projets récents et discrets (10 à 300 étoiles) avant tout le monde pour créer des outils web monétisables.
- **Ce qu'il fait :**
  - Cherche sur tout GitHub avec 5 filets intelligents.
  - Calcule la vitesse réelle d'acquisition des étoiles.
  - Analyse le code source et la concurrence en France avec Groq.
  - Te donne une fiche décisionnelle complète par projet.

#### Aperçu visuel d'une fiche d'opportunité :
```text
┌────────────────────────────────────────────────────────────────────────┐
│ [ 🔥 Potentiel · 8/10 ]  [ 🎯 Fit profil · 9/10 ]   MICRO-SAAS   #01   │
│                                                                        │
│ acme/fast-invoice-parser                                               │
│ [ ⚡ Offre existante détectée : pricing, cloud ]                       │
│                                                                        │
│ ┌──────────────────┬──────────────────────┬──────────────────────────┐ │
│ │ TOTAL ÉTOILES    │ TRACTION & USAGE     │ DATE DE CRÉATION         │ │
│ │ ★ 340            │ 🚀 FULGURANT (+48★/j)│ Créé le 25/10/2026 (12j) │ │
│ │ mesurée sur 2j   │ 42 forks · 15 issues │ Commit aujourd’hui       │ │
│ └──────────────────┴──────────────────────┴──────────────────────────┘ │
│                                                                        │
│ 🎯 PROBLÈME DOULOUREUX                                                 │
│ Extraction automatique des montants et TVA sur factures PDF sans       │
│ envoyer les documents confidentiels dans le cloud d'un tiers.          │
│                                                                        │
│ ⚙️ CE QUE FAIT LE CODE SOURCE                                          │
│ Moteur Python léger utilisant un modèle local ONNX + regex pour parser │
│ les tableaux de factures en JSON en moins de 200ms sans GPU.           │
│                                                                        │
│ 👥 CIBLE SOLVABLE                                                      │
│ Cabinets comptables indépendants, freelances et TPE débordés.          │
│                                                                        │
│ 💡 ANGLE BUSINESS (SAAS EN LIGNE)                                      │
│ Créer une application web drag-and-drop à 29€/mois avec export Excel.  │
│                                                                        │
│ 🛠️ MVP ESTIMÉ : 1 week-end     🇪🇺 ATOUT RÉGIONAL : RGPD & Facture 2026  │
│                                                                        │
│ 🇫🇷 CONCURRENCE EN FRANCE / EUROPE                                      │
│ Océan bleu sur le local-first : les géants (Pennylane, Dext) sont      │
│ 100% cloud américain. Forte opportunité sur la souveraineté.           │
│                                                                        │
│ ⚠️ RISQUE IDENTIFIÉ                                                    │
│ Les formats de factures atypiques ou manuscrites peuvent bloquer l'OCR.│
│                                                                        │
│ [ Analyser le code → ]   [ 👍 Intéressant ]   [ 👎 Pas pour moi ]       │
│ Langage: Python · Licence: MIT · 42 forks · 15 issues                  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ 3. Comment ça marche sous le capot ? (La Méthode)

Le pipeline de détection fonctionne comme un entonnoir de tri chirurgical :

```text
1. Collecte (5 filets GitHub)
   ↓  ~250 dépôts bruts captés
2. Filtres durs anti-bruit (Gratuits)
   ↓  Élimine 80% des faux projets (scams, cours, Big Tech)
3. Mémoire d'état & Vélocité réelle
   ↓  Compare les étoiles avec le run précédent (delta réel)
4. Pré-classement mathématique
   ↓  Sélectionne les 15 meilleurs candidats
5. Cerveau IA Groq (Analyste VC + Profil Builder)
   ↓  Élimine les jouets, évalue le potentiel SaaS et le fit
6. Envoi de l'Email & Boucle de Feedback
   ↓  Email HTML prêt à l'emploi avec boutons interactifs
```

### Étape 1 · Les 5 filets de recherche GitHub
Plutôt que de faire une seule recherche qui ne remonte que les gros projets, le robot lance 5 requêtes spécialisées :
1. **Frais :** projets créés il y a moins de 10 jours avec entre 8 et 150 étoiles.
2. **Réveillés :** projets de 1 à 4 mois qui ont recommencé à s'activer récemment (`pushed < 5 jours`, 30 à 800 étoiles).
3. **Alternatives :** projets qui écrivent explicitement *"alternative to"* dans leur description (ils s'attaquent à un marché où les clients paient déjà).
4. **Self-hosted :** projets orientés auto-hébergement (candidats parfaits pour créer une version hébergée clé en main pour ceux qui ne savent pas déployer un serveur).
5. **SaaS :** projets récents identifiés sous le topic `saas`.

### Étape 2 · Le filtrage dur anti-bruit
Avant même d'appeler l'IA, le robot élimine gratuitement :
- **Le bruit pédagogique :** les devoirs d'école, exercices d'entretien (`leetcode`, `interview`, `homework`, `tutorial`, `cheatsheet`, `roadmap`).
- **Les arnaques :** fausses cryptos, bots de trading, memecoins, airdrops, cracks.
- **Les mastodontes Big Tech :** Google, Microsoft, Meta, Nvidia, OpenAI, Alibaba, Vercel (impossible de concurrencer un projet soutenu par 200 ingénieurs).
- **Les fausses étoiles :** si un projet a 300 étoiles mais 0 fork, c'est de l'achat d'étoiles ou du buzz passif sans usage réel.
- **Les projets abandonnés :** aucun commit depuis plus de 14 jours.

### Étape 3 · La mémoire d'état (`business_state.json`)
L'API GitHub ne donne pas le nombre d'étoiles gagnées hier. Pour le savoir :
- À chaque run, le robot enregistre une photo : `{ "date": "2026-11-06", "stars": 120 }`.
- Au run suivant, il compare : s'il est à 180 étoiles, il calcule : $(180 - 120) / 2 = \mathbf{+30\text{ étoiles/jour}}$.
- C'est ce qui permet d'afficher la mention **`mesurée`** et d'activer le badge **`🚀 FULGURANT`**.
- Un projet déjà analysé ne t'est jamais renvoyé, **sauf s'il double ses étoiles**.

### Étape 4 · L'analyse Groq & Ton Profil (`profile.yml`)
Groq ne fait pas un bête résumé : il joue le rôle d'un **analyste en capital-risque et créateur de SaaS** :
- Il lit ton fichier `profile.yml` (ton objectif de créer des outils web en ligne, tes compétences en Python/Next.js/React, ton rythme de 8-10h/jour et ton souhait de MVP rapide en 24-72h).
- Il note l'adéquation : **Fit Profil (1 à 10)**.
- Il explique concrètement ce que fait le code.
- Il évalue le paysage concurrentiel en France (détection d'océans bleus).
- Il avertit sur les risques légaux (licence AGPL ou absence de licence).

### Étape 5 · La boucle de feedback (Boutons 👍 / 👎)
Dans chaque fiche de l'email, tu as deux boutons :
- `[ 👍 Intéressant ]`
- `[ 👎 Pas pour moi ]`

Quand tu cliques, une page GitHub s'ouvre pour créer une issue avec le label correspondant. Au run suivant, le robot lit tes retours et dit à Groq :
> *"Le créateur a adoré les projets X et Y, mais a rejeté Z. Propose-lui en priorité des projets du même genre que X et Y."*
**L'IA apprend tes goûts automatiquement, sans base de données externe.**

---

## 💻 4. Pourquoi les emails sont beaux et ne cassent jamais ?

Créer des emails HTML est notoirement difficile car chaque client mail (Gmail sur Android, Apple Mail sur iPhone, Outlook sur Windows) interprète le CSS différemment :
- Les fichiers `email_template.py` et `business_template.py` utilisent une architecture **table-based 100% inline**.
- Aucune balise `<style>` externe qui se ferait écraser par Gmail.
- Les polices sont typographiques et éditoriales (*Inter* pour la clarté, *JetBrains Mono* pour les chiffres et les badges tech).
- L'affichage s'adapte automatiquement sur smartphone comme sur grand écran.

---

## ⚡ 5. Combien ça coûte et est-ce risqué ?

### Zéro euro dépensé (100% Gratuit)
- **GitHub Actions :** 2 000 minutes gratuites par mois sur les dépôts publics (nos runs durent moins de 2 minutes).
- **Groq :** compte gratuit avec modèles ultra-rapides.
- **Gmail SMTP :** gratuit via ton mot de passe d'application 16 lettres.
- **Hébergement :** aucun serveur à payer, pas de VPS, pas de base de données externe.

### Sécurité & Quotas anti-ban
- **Quotas GitHub :** 5 requêtes espacées de 2 secondes, bien en dessous de la limite des 30 requêtes/minute.
- **Jeton sécurisé :** utilisation du token temporaire `${{ github.token }}` dans les Actions.
- **Quotas Groq :** les requêtes ont été calibrées à **~4 200 tokens**, soit la moitié de la limite de 8 000 tokens/minute du palier gratuit.
- **Secrets :** aucun mot de passe ou clé API n'est écrit dans le code. Tout est stocké dans les **Secrets GitHub** chiffrés.

---

## 📂 6. Organisation des Fichiers

| Fichier | Ce qu'il fait |
|---|---|
| `digest.py` | Le moteur du **Digest du matin** (scrape github.com/trending, appel Groq, envoi). |
| `email_template.py` | La maquette HTML éditoriale du mail du matin (bloc vert fluo, typographie Serif/Mono). |
| `business_digest.py` | Le moteur du **Radar Business** (5 filets de recherche, mémoire d'état, scoring VC). |
| `business_template.py` | La maquette HTML des fiches d'opportunités (cartes, badges, métriques, boutons 👍/👎). |
| `profile.yml` | **Ton profil de builder :** tes technos, ton temps, ton focus absolu sur les outils SaaS web. |
| `.github/workflows/digest.yml` | Automatisation GitHub Actions du mail quotidien. |
| `.github/workflows/business_digest.yml` | Automatisation GitHub Actions du Radar Business tous les 2 jours. |
| `logs/business_state.json` | La mémoire des étoiles et l'historique des snapshots pour calculer les accélérations. |

---

## 🎯 7. Comment modifier ton profil plus tard ?

Si tes envies évoluent (par exemple si tu veux explorer les extensions VSCode ou les apps mobiles), il te suffit d'ouvrir le fichier `profile.yml` et de modifier la liste :
- Tout ce qui est sous `high_priority_sectors` recevra un gros bonus de score par Groq.
- Tout ce qui est sous `disqualified_sectors` sera pénalisé ou écarté.

---

*Projet configuré, automatisé et déployé sur GitHub (`netraax/trending-digest`).*
