# PrixJuste

Tu dis quel objet tu veux. L'outil relève les prix tout seul chaque matin et te dit, avec un tampon :
**ACHÈTE**, **ATTENDS** (jusqu'à quand), **SURVEILLE**, **BIDON** (fausse promo) ou **PAS ASSEZ DE DONNÉES**.

Site : https://zakkk1.github.io/prixjuste/

## Ajouter un objet

1. Sur le site, tape l'objet dans « Qu'est-ce que tu veux acheter ? » → **Suivre**.
2. Précise si tu veux : taille, coloris, urgence, budget, et des **liens produit** si tu en as.
3. Le bouton ouvre GitHub avec la demande déjà écrite : appuie sur **Create**.

- **Avec des liens** : l'article est créé, relevé, et la demande reçoit le premier verdict puis se ferme (2 à 15 min).
- **Sans lien** : comme une recherche en boutique. Claude trouve 3 à 5 produits qui correspondent, avec photo, prix
  et marchand (au plus tard dans les 3 heures, rien à configurer). Sur la fiche, touche **C'est celui-là** sur le bon :
  une demande « choix » s'ouvre sur GitHub, appuie sur **Create**, et le suivi démarre aussitôt (sans IA).

Sur chaque fiche, même principe (une demande pré-remplie sur GitHub) :
- **J'ai vu un prix** : un prix vu en magasin ou sur un site bloqué.
- **Je l'ai acheté** : le prix reste surveillé pendant les 14 jours de rétractation (s'il baisse, tu es prévenu
  pour renvoyer et racheter) ; la fin de la garantie légale de 2 ans est notée.
- **Carte 9:16** : une image verticale à partager (prix, historique réel, tampon, sources).
- **Trouver un équivalent moins cher** : Claude (s'il est activé) propose 2 ou 3 produits comparables moins chers,
  suivis ensuite comme les autres ; les fiches se renvoient l'une à l'autre (« À comparer »).

Sur le comptoir, **Plan d'achat sous budget** (replié) : indique un budget par mois, chaque article est placé dans
son mois historiquement le moins cher avant sa date limite, sans dépasser le budget. Le budget reste sur ton
appareil, il n'est jamais publié. Sur les courbes, un trait ocre sur l'axe marque les soldes et le Black Friday.

## Être prévenu

Quand un article passe à ACHÈTE, tombe sous son alerte ou affiche une promo bidon, l'issue « Suivi : <article> »
reçoit un message (une fois par changement) : l'app GitHub du téléphone te notifie. L'agenda des fenêtres d'achat
et des soldes s'ajoute au calendrier du téléphone depuis le lien « ajouter à mon agenda » du comptoir.

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

## Identification immédiate (facultatif)

Seules étapes qui utilisent l'IA : les demandes sans lien et la recherche d'équivalents. Elles marchent déjà sans
rien faire (routine toutes les 3 heures). Pour qu'elles se fassent dans la minute, sur ton ordinateur :

1. Lance `claude setup-token` et copie le jeton affiché.
2. Sur GitHub : dépôt → **Settings → Secrets and variables → Actions → New repository secret**,
   nom `CLAUDE_CODE_OAUTH_TOKEN`, colle le jeton.
3. C'est tout. Les demandes en attente se relancent en reposant l'étiquette `à-identifier` sur leur issue.

## Ce qui est bloqué, et pourquoi

L'outil s'annonce comme un robot (`PrixJuste/1.0`), respecte `robots.txt` et lit chaque page une fois par jour au plus.
Quand un site refuse, il est marqué **bloqué** et **on ne contourne jamais** (pas de faux navigateur, pas de proxy).
Aujourd'hui : **Snowleader** (robots.txt l'interdit) et **Weekendbee** (page anti-robot) — leurs prix viennent des
archives publiques du web ou de ta saisie. Les demandes sans lien attendent au plus
3 heures leur identification.

## Pour qui veut regarder sous le capot

- `data/articles/*.json` les objets suivis · `data/releves/*.jsonl` un prix par ligne, jamais réécrit ·
  `data/profil.json` tes tailles habituelles (pointure, ajustements par marque).
- `prixjuste/` le code (Python, sans dépendance) · `tests/` (`python -m pytest`).
- `.github/workflows/` : `releve.yml` (chaque matin), `ajout.yml` (demandes), `claude.yml` (identification), `tests.yml`.
- En local : `python -m prixjuste verdicts`, `python -m prixjuste site`, `python -m prixjuste verifier <url>`.
