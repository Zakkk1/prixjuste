# PrixJuste — cahier des charges (source de vérité pour la construction)

Outil perso d'aide à l'achat. L'utilisateur dit **quel objet** il veut (et sa taille/pointure/coloris), l'outil suit les prix
tout seul et affiche **une décision claire** : Achète / Attends (jusqu'à quand) / Surveille / Promo bidon.
Utilisateur francophone, non développeur, consulte surtout **sur téléphone**. Toute l'interface est en français.

## Principes non négociables

1. **Claude le moins possible.** Tout ce qui est répétitif (relevés, calculs, verdicts, site) est du code classique
   qui tourne sans IA. Claude n'intervient que pour ce que le code ne sait pas faire : identifier un produit à partir
   d'un texte libre et trouver les pages marchands correspondantes.
2. **Collecte honnête.** User-Agent explicite (`PrixJuste/x.y (outil personnel de suivi de prix)`), respect de
   `robots.txt`, un relevé par jour max par page. Si un site refuse (403/429/captcha/robots) : on note « bloqué » et on
   **ne contourne jamais** (pas d'usurpation de navigateur, pas de proxy, pas de rotation d'IP). Repli : archives
   Wayback Machine, flux d'affiliation, saisie manuelle.
3. **Verdicts vérifiables.** Chaque verdict dit sur combien de prix il repose (fiabilité), et n'invente rien quand
   l'historique est trop court (pas de seuil d'alerte calculé sur 2 points, etc.).
4. **Pas d'AI slop.** Pas de dégradés violets, pas d'emojis décoratifs, pas de cartes génériques, pas de texte
   marketing, pas de « ✨ IA ». Rien qui gêne la lecture. Peu d'éléments, chacun utile.

## Ce qui existe déjà (V1, racine du dépôt)

- `collecte.py` : lecture JSON-LD schema.org (Product/Offer/AggregateOffer, variantes `hasVariant` avec `size`),
  filtres par taille (`taille`) ou par texte/regex (`filtre`, préfixe `re:`), robots.txt, Wayback (CDX + `id_`).
- `analyse.py` : série du meilleur prix dispo par jour, plus bas 12 mois, même période l'an dernier, fenêtre de mois
  la moins chère, tendance 90 j, contrôle des fausses promos (règle des 30 jours, par marchand), verdict selon
  urgence/date limite/budget, fiabilité.
- `rapport.py` : ancien rapport HTML (à remplacer par le vrai site).
- `prixjuste.py` : CLI (`collecter`, `historique`, `prix`, `rapport`, `tout`, option `--article`).
- `wishlist.json` : 2 articles réels (McMurdo TNF, Timberland 6-Inch jaune 39,5/40) — à conserver.
- `prixjuste.db` : SQLite avec l'historique déjà récupéré — **à migrer sans perte** vers le nouveau format.

## Architecture cible

```
GitHub (dépôt Zakkk1/prixjuste)
├─ data/
│  ├─ articles/<id>.json        un fichier par article (objet, variante, urgence, liens marchands)
│  └─ releves/<id>.jsonl        un relevé par ligne, append-only (lisible en diff, jamais réécrit)
├─ prixjuste/  (package Python, stdlib + truststore uniquement)
│  ├─ collecte.py  analyse.py  sources/ (adaptateurs génériques + spécifiques si utile)
│  └─ build.py     génère le site statique dans site/ (HTML + data.json)
├─ site/  (généré, non versionné)
├─ .github/workflows/
│  ├─ releve.yml      cron quotidien (~06:00 Paris) : collecte → commit data → build → déploiement
│  ├─ ajout.yml       sur issue étiquetée « ajout » : crée l'article (voir flux d'ajout) → commit → build
│  └─ (optionnel) claude.yml  identification d'un produit en texte libre via anthropics/claude-code-action
└─ tests/  (pytest sur analyse + extraction avec pages HTML d'exemple anonymisées)
```

### Flux d'ajout (« je dis l'objet »)

Sur le site, un seul champ « Qu'est-ce que tu veux acheter ? » + champs optionnels (taille, coloris, urgence,
budget, liens si on en a). Le bouton ouvre une **issue GitHub pré-remplie** (URL `issues/new?title=…&body=…&labels=ajout`)
— l'utilisateur est déjà connecté à GitHub sur son téléphone, aucun token n'est stocké dans le site.

- Si l'issue contient des liens marchands → `ajout.yml` crée l'article directement (sans Claude), lance un premier
  relevé + import Wayback, commente l'issue avec le premier verdict, ferme l'issue.
- Si c'est du texte libre → l'issue reçoit l'étiquette `à-identifier`. C'est là, et seulement là, que Claude
  intervient : workflow `claude.yml` (anthropics/claude-code-action) qui trouve la référence exacte et 3 à 6 pages
  marchands FR/UE lisibles (robots OK), écrit `data/articles/<id>.json`, ouvre une PR ou commite, commente.
  Ce workflow a besoin d'un secret (`CLAUDE_CODE_OAUTH_TOKEN` via `claude setup-token`, ou l'app GitHub Claude) que
  **l'utilisateur doit ajouter lui-même** : ne jamais créer ni saisir ce secret. Documenter l'étape en 3 lignes dans
  LISEZMOI.md. Tant qu'il n'est pas configuré, le site affiche ces demandes comme « en attente d'identification ».
- Saisie manuelle d'un prix vu (magasin, site bloqué) : même mécanique (issue `prix`), formulaire simple sur le site.

### Hébergement du site

**Décidé par l'utilisateur : dépôt public + GitHub Pages.** Le dépôt est public et Pages est activé en mode
« GitHub Actions » (`build_type=workflow`). URL : https://zakkk1.github.io/prixjuste/ . Déployer `site/` avec
`actions/upload-pages-artifact` + `actions/deploy-pages` à la fin de `releve.yml` et `ajout.yml` (permissions
`pages: write`, `id-token: write`, environnement `github-pages`). Le site étant public : ne jamais y afficher de
donnée personnelle autre que les articles suivis (pas de nom, pas d'e-mail).

## Le site — direction artistique : « Étiquette »

Concept assumé jusqu'au bout : **l'étiquette de prix / le ticket de caisse d'un commerçant honnête.**
Papier, encre, tampon. Le verdict est un **tampon encreur** posé sur l'article.

- **Fond** papier chaud `#F3EFE6`, encre presque noire `#1A1917`, filets fins `#1A1917` à 12–20 % d'opacité.
  Mode sombre = « carbone » : fond `#141312`, encre `#ECE6D9`. Pas d'autres couleurs que les couleurs de tampon.
- **Couleurs de tampon** (une seule visible par article) : ACHÈTE vert encre `#1F6B45`, ATTENDS bleu encre `#23479A`,
  SURVEILLE ocre `#9A5B12`, BIDON rouge tampon `#B3261E`, PAS ASSEZ DE DONNÉES gris `#7A766E`.
- **Typo** (Google Fonts) : chiffres et étiquettes en mono à chasse fixe (`JetBrains Mono` ou `IBM Plex Mono`,
  chiffres tabulaires), titres d'articles en grotesque condensée (`Archivo` en largeur condensée, ou `Barlow Condensed`)
  en capitales. Aucune troisième police.
- **Tampon** : texte en capitales dans un cadre double, légèrement tourné (−4° à −7°), texture d'encre irrégulière
  via un filtre SVG (feTurbulence + feDisplacementMap) discret, opacité ~0.85, mélange `multiply` (`screen` en sombre).
  Il ne doit jamais masquer le prix.
- **Prix** : énorme, mono, avec l'ancien prix barré seulement s'il est réel. Les écarts en `−33 %` mono.
- **Courbe** : trait d'encre fin en escalier (pas de lissage), points pleins pour relevés directs, creux pour archives,
  bande hachurée pour la « fenêtre d'achat » conseillée, trait pointillé pour l'alerte. Pas de grille lourde.
- **Bords** : séparateurs perforés (pointillés) façon ticket ; coins nets ; pas d'ombres portées molles.
- **Mouvement** : un seul — le tampon « se pose » (scale 1.15 → 1, 140 ms) à l'ouverture d'une fiche. Respecter
  `prefers-reduced-motion`.

### Écrans (3, pas plus)

1. **Le comptoir** (accueil) : liste des articles, triés par urgence de la décision (ACHÈTE d'abord). Par ligne :
   nom, variante, meilleur prix actuel + marchand, tampon, mini-courbe (sparkline) et la phrase d'explication en une
   ligne. En haut : le champ « Qu'est-ce que tu veux acheter ? ». Rien d'autre.
2. **La fiche** d'un article : tampon + phrase, prix actuel, plus bas 12 mois (date, tailles dispo), même période
   l'an dernier, fenêtre d'achat conseillée, alerte, contrôle des promos, courbe, tableau des marchands (statut de
   lecture honnête : ok / bloqué / archives seulement), bouton « j'ai vu un prix ».
3. **Ajouter** (ou panneau dans le comptoir) : le formulaire décrit plus haut.

Mobile d'abord (375 px), gouttière 16 px, aucun défilement horizontal. Accessibilité : contraste AA, focus visibles,
le tampon a un texte réel (pas une image). Pas de framework lourd : HTML/CSS/JS vanilla générés par `build.py`
(un `data.json` + des pages statiques). Aucune dépendance npm obligatoire.

## Définition de « fini »

- [ ] Données migrées (SQLite → JSON/JSONL), aucun relevé perdu, `prixjuste.db` retiré.
- [ ] `releve.yml` tourne chaque jour sur GitHub Actions et commite les relevés ; testé via `workflow_dispatch`.
- [ ] `ajout.yml` : ajout par liens fonctionne de bout en bout (testé avec une vraie issue, puis fermée).
- [ ] `claude.yml` prêt, inactif tant que le secret n'existe pas, étape d'activation documentée.
- [ ] Site généré conforme à la direction artistique, vérifié à 375 px et en desktop, clair et sombre, et en ligne sur https://zakkk1.github.io/prixjuste/ .
- [ ] Tests pytest verts en CI.
- [ ] LISEZMOI.md court : comment ajouter un objet, lire un verdict, activer Claude, ce qui est bloqué et pourquoi.
