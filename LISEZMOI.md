# PrixJuste

Tu dis quel objet tu veux. L'outil relève les prix tout seul chaque matin et te dit, avec un tampon :
**ACHÈTE**, **ATTENDS** (jusqu'à quand), **SURVEILLE**, **BIDON** (fausse promo) ou **PAS ASSEZ DE DONNÉES**.

Site : https://zakkk1.github.io/prixjuste/

## Ajouter un objet

1. Sur le site, tape l'objet dans « Qu'est-ce que tu veux acheter ? » → **Suivre**.
2. Précise si tu veux : taille, coloris, urgence, budget, et des **liens produit** si tu en as.
3. Le bouton ouvre GitHub avec la demande déjà écrite : appuie sur **Create**.

- **Avec des liens** : l'article est créé, relevé, et la demande reçoit le premier verdict puis se ferme (2 à 15 min).
- **Sans lien** : la demande attend que Claude trouve la référence exacte et des pages lisibles (voir plus bas).
  Pour aller plus vite : modifie la demande pour y coller un lien, puis retire et remets l'étiquette `ajout`.

Un prix vu en magasin ou sur un site bloqué : sur la fiche, **J'ai vu un prix** (même principe).

## Lire un verdict

| Tampon | Ça veut dire |
|---|---|
| ACHÈTE | Le prix actuel est parmi les plus bas vus sur 12 mois. |
| ATTENDS → mois | Le prix baisse d'habitude à ce moment-là (−10 % ou plus), avant ta date limite. |
| SURVEILLE | Ni bon ni mauvais : achète si le prix passe sous l'**alerte**. |
| BIDON | La meilleure offre affiche un prix barré trompeur (règle des 30 jours : le prix barré doit être le plus bas pratiqué par ce marchand dans les 30 jours d'avant). |
| PAS ASSEZ DE DONNÉES | Moins de 5 jours de prix connus : l'outil n'invente rien. |

Chaque fiche dit sur combien de jours de prix le verdict repose (**fiabilité** faible < 15, moyenne < 60, bonne au-delà),
d'où vient chaque prix (relevé direct, archive web, saisie) et quels sites ne se laissent pas lire.

## Activer Claude (identification en texte libre)

Seule étape qui utilise l'IA, et seulement pour les demandes sans lien. Sur ton ordinateur :

1. Lance `claude setup-token` et copie le jeton affiché.
2. Sur GitHub : dépôt → **Settings → Secrets and variables → Actions → New repository secret**,
   nom `CLAUDE_CODE_OAUTH_TOKEN`, colle le jeton.
3. C'est tout. Les demandes en attente se relancent en reposant l'étiquette `à-identifier` sur leur issue.

## Ce qui est bloqué, et pourquoi

L'outil s'annonce comme un robot (`PrixJuste/1.0`), respecte `robots.txt` et lit chaque page une fois par jour au plus.
Quand un site refuse, il est marqué **bloqué** et **on ne contourne jamais** (pas de faux navigateur, pas de proxy).
Aujourd'hui : **Snowleader** (robots.txt l'interdit) et **Weekendbee** (page anti-robot) — leurs prix viennent des
archives publiques du web ou de ta saisie. Tant que le secret Claude n'existe pas, les demandes sans lien restent
« en attente d'identification ».

## Pour qui veut regarder sous le capot

- `data/articles/*.json` les objets suivis · `data/releves/*.jsonl` un prix par ligne, jamais réécrit.
- `prixjuste/` le code (Python, sans dépendance) · `tests/` (`python -m pytest`).
- `.github/workflows/` : `releve.yml` (chaque matin), `ajout.yml` (demandes), `claude.yml` (identification), `tests.yml`.
- En local : `python -m prixjuste verdicts`, `python -m prixjuste site`, `python -m prixjuste verifier <url>`.
