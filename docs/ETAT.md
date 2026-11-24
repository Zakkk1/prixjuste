RELAIS: non

- 24/11 soir : alertes fixées (Timberland 160 €, Patagonia 110 €) ; Outnorth retiré (taille illisible, `liens_retires`) ; Heritage 6-Inch soldée au Canada vérifiée (129,99 $ CA, US 7 en stock) ; Sporting Life refuse désormais le robot.

## Refonte du 24/11 : assistant d'achat (demande de l'utilisateur)
- Mode principal : l'utilisateur écrit à Claude (photo de tenue, produit à acheter, bons plans) ; skills
  `.claude/skills/{tenue,achat,bons-plans}`, méthode `docs/ASSISTANT.md`, rôle décrit en tête de `CLAUDE.md`.
- Dossiers `data/dossiers/*.json` (types tenue / achat / bons-plans), vérifiés par `python -m prixjuste dossier`,
  publiés sur le site (accueil « Ton assistant d'achat » + « Mes dossiers », pages `d/<id>.html`).
- `python -m prixjuste convertir 230 CAD` (prix au Québec taxes comprises) ; `annoncer` (job de `site.yml`) commente
  les dossiers `"annoncer": true` sur l'issue « Assistant : nouveaux dossiers » avec mention (téléphone).
- 3 premiers dossiers réels du 24/11 : achat Timberland (ATTENDS → 30/11, cible 160 €), bons plans Black Friday
  (McMurdo 325 €, Patagonia 1/4 zip 104 €), tenue « Hiver à Québec » (≈ 620 € ou ≈ 490 €).
- Routines Black Friday (27/11) et Cyber Monday (30/11) : dossier bons plans fait sans l'utilisateur, annoncé.
- Profil : taille M, préférences (1/4 zip), Québec ; seules les tailles sont publiées sur le site.

# État de la construction

Dernière mise à jour : 21/11/2026, ~16 h 40 UTC. Tout le BRIEF et toutes les idées de IDEES.md sont faits ; design refait pour la lisibilité.

## Définition de fini (docs/BRIEF.md) — atteinte
- [x] Données migrées SQLite → `data/` ; `prixjuste.db` retiré.
- [x] `releve.yml` : 6 runs `workflow_dispatch` verts (relevé, archives, notifications, commit, Pages), dont les
      runs 5 et 6 de ce maillon ; cron 04:41 UTC.
- [x] `ajout.yml` : testé de bout en bout avec l'issue n°1 ; article de test retiré ensuite.
- [x] `claude.yml` : job « verifier » vert sans secret, identification ignorée proprement.
- [x] Site déployé sur Pages (job deploy vert à chaque relevé). Non consultable depuis le conteneur (réseau
      bloqué vers github.io) : vérifié en local à 375 px / 1280 px, clair / sombre, sans défilement horizontal.
- [x] Tests : 91 pytest verts en local (Python 3.12) et en CI.
- [x] LISEZMOI.md à jour.

## Idées (docs/IDEES.md) — toutes faites
- [x] 1 Notifications · 2 Coût réel · 3 Protection après achat · 4 Profil de tailles · 5 Agenda .ics
- [x] 6 Plan d'achat sous budget : bloc replié sur le comptoir, budget gardé sur l'appareil (localStorage, jamais
      publié) ; même algorithme Python/JS, vérifié l'un contre l'autre par les tests (node).
- [x] 7 Risque de rupture · 8 Carte 9:16
- [x] 9 Soldes et Black Friday : retirés de la courbe le 21/11 (illisible) ; ils restent dans l'agenda .ics.
- [x] 10 Équivalents moins chers : lien sur la fiche → demande « ajout » pré-remplie → `claude.yml` (si le secret
      existe) propose 2 ou 3 articles liés à l'original (« À comparer »). Non testé de bout en bout : secret absent.

## Design refait (21/11, après retour de l'utilisateur : « illisible »)
- Texte IBM Plex Sans 16 px, prix IBM Plex Mono, titres IBM Plex Sans Condensed ; contraste renforcé.
- Courbe : 12 mois pleins, un point par jour, prix du jour et plus bas écrits dessus, ligne « acheter sous X € » ;
  plus de hachures, repères de soldes ni légende. Libellés placés hors du tracé.
- Fiche allégée (5 repères, promos seulement s'il y en a, actions regroupées) ; comptoir sans mini-courbe.
- Vérifié en ligne sur https://zakkk1.github.io/prixjuste/ (mobile 400 px et 800 px, clair et sombre).
- `site.yml` redéploie le site quand le code du site ou un article change, sans relever de prix.

## Design « Météo des prix » (21/11, choisi par l'utilisateur parmi 3 pistes)
- Clair uniquement, Manrope, cartes blanches ; photo produit (lue dans la page déjà relevée, sinon archives web).
- Fiche : jauge « ce prix est bas / dans la moyenne / plutôt élevé » sur 12 mois, carte Prévision (verdict +
  prix médians des 4 prochains mois relevés les années passées), courbe, repères, marchands.
- Vérifié en ligne (mobile et ordinateur). Maquettes des 3 pistes : canevas de design privé de l'utilisateur.

## Ajout « comme en boutique » (21/11)
- Sans lien : la routine propose 3 à 5 produits avec photo (statut `a_choisir`) ; « C'est celui-là » ouvre une issue
  `choix` traitée par `ajout.yml` sans IA (premier relevé, réponse, fermeture, site).
- Testé de bout en bout le 21/11 (demandes n°5 et n°6, casque de test retiré ensuite).

## Demandes en texte libre
- Identifiées sans jeton par la routine Claude programmée (toutes les 3 h), procédure dans `CLAUDE.md`.
- Demande n°3 (Patagonia Better Sweater noir, M) identifiée le 21/11 : 4 pages lisibles, issue fermée avec le détail.
- Demande n°4 (équivalent moins cher des Timberland) identifiée de bout en bout par la routine : 2 CAT Colorado 2.0.
- Demande n°4 (équivalents moins chers des Timberland 6-Inch, pointure 39,5 → 40 chez CAT) identifiée le 21/11 par la
  routine via le workflow « Vérifier des pages » : CAT Colorado 2.0 Hiker WP jaune miel (90,99 €, Sportano) et
  CAT Colorado 2.0 WP Pyramid (151,16 €, Butyjana) ; premier relevé publié, issue fermée avec le détail.
- Facultatif : le secret `CLAUDE_CODE_OAUTH_TOKEN` (LISEZMOI) rend l'identification immédiate via `claude.yml`.

## Contrôle du 22/11 (routine, ~06:35 UTC)
- Relevé programmé (cron 04:41 UTC) **non déclenché par GitHub** : à 06:30 UTC, aucun run `schedule` dans l'historique
  de `releve.yml` (8 runs, tous `workflow_dispatch`). Retard/omission côté GitHub, pas une erreur du code. Relevé lancé
  à la main : run n°8 (44994069910) **vert**, jobs `releve` et `deployer` (deploy-pages) en succès à 06:32 UTC.
  S'il part en retard, le cron ne revisitera pas les pages (« déjà lu aujourd'hui »).
- Commits du run : `0208558` « Relevé du 22/11/2026 », `5a76f4f` « Archives et notifications du 22/11/2026 ».
- Photos : `equivalent-moins-cher-timberland-6-inch` → photo sportano.com, `…-2` → photo butyjana, lues sur la page
  suivie pendant le relevé direct (aucune visite en plus).
- Relevé direct du 22/11 pour chaque article (journal `data/journal/*.jsonl`) : Timberland 6/6 ok ; CAT Hiker 2/2 ok
  (90,99 €) ; CAT WP 2/2 ok (139 € Natural Shoes, 151,16 € Butyjana) ; McMurdo 2 ok (500 €, 373,90 €) + 2 Snowleader
  « robots.txt interdit » + Weekendbee « captcha » ; Patagonia 3 ok (149,95 € au plus bas) + End « captcha ». Aucun
  blocage contourné.
- Site : https://zakkk1.github.io/prixjuste/ n'est pas joignable depuis le conteneur (hôte hors du réseau autorisé).
  À la place : déploiement Pages vert, et le même site reconstruit en local (Python 3.12) depuis `main` affiche
  « 22/11/2026 » et les 5 photos de l'accueil, dont les deux CAT.
- Rien à corriger dans le code.
- Mise à jour 22/11 ~13 h UTC : le cron **a bien été déclenché**, avec retard (run n°9, `schedule`, 12:53 UTC) et
  il est **vert** ; comme le relevé du jour était déjà fait, il n'a revisité aucune page (une visite par jour).

## 22/11 soir (retours de l'utilisateur)
- Champ « Qu'est-ce que tu veux acheter ? » : pistes immédiates (déjà dans la liste + idealo / Le Dénicheur /
  Google Shopping) et délai affiché (2 min avec un lien, 3 h au plus sans lien).
- Courbe : trous marqués « aucun prix connu » + origine de l'historique. Prévision : un mois exige 2 jours de prix
  (le « ~176 € en janvier » des Timberland reposait sur 1 prix suédois ; McMurdo passe de ATTENDS à SURVEILLE).
- Demande n°7 (polaire TNF Glacier, M, noir) : 4 propositions publiées, issue fermée ; l'utilisateur choisit.
- Canada (réponse de l'utilisateur : option 1, voyage à Québec) : FAIT. Liens `pays: CA` (jamais dans le verdict),
  taux BCE quotidien (`data/change.json`), bloc « Au Québec » taxes TPS+TVQ comprises, franchise 430 €.
- Combler la courbe : idealo interdit par robots.txt (recherche et API du graphique) ; Le Dénicheur renvoie une
  page anti-robot ; Keepa = Amazon seulement + clé API payante ; camelcamelcamel = Amazon seulement. Aucun
  contournement. Levier honnête : plus de marchands lisibles par article (plus de points chaque jour + leurs
  archives). Zalando « wheat » = probablement le modèle femme (10361, tailles 35-42) : non ajouté.

## Recherche de marchands supplémentaires (22/11, 23 h)
- 10 candidats testés (Intersport, Citadium, Trekkinn, Alpinstore, Decathlon, Patagonia EU, 43einhalb, Zalando enfant,
  La Redoute, Spartoo) : AUCUN lisible honnêtement (robots.txt, 403, anti-robot ou pas de prix JSON-LD). Archives
  Wayback de ces pages : 0 copie sur 2 ans sauf Zalando (3). La recherche par préfixe dans les archives d'idealo
  expire (trop gros) ; il faudrait l'URL exacte d'une fiche idealo pour lire ses copies archivées.
- Ajouté : sur chaque fiche, liens « Historique plus ancien : idealo · Le Dénicheur · Keepa » + « J'ai vu un prix »
  avec date pour recopier un prix lu sur la courbe d'un comparateur (marqué « saisie »).
- Pistes légales restantes, à décider par l'utilisateur : flux d'affiliation (Awin, Effiliation : inscription éditeur,
  catalogues autorisés de Zalando, La Redoute, Decathlon…) ; Keepa API payante (Amazon seulement).

## Enquête à la demande via Claude dans Chrome (22/11, décision de l'utilisateur)
- Le robot quotidien reste pour les sites lisibles et les alertes ; l'historique et les boutiques qui refusent les
  robots passent par une ENQUÊTE ponctuelle que l'utilisateur lance depuis son Chrome (extension Claude in Chrome).
- Fiche : bloc « Enquête complète (Claude dans Chrome) » = consigne prête à copier (`prixjuste/enquete.py`) :
  courbe idealo / Le Dénicheur / Keepa, prix dans la taille, prix au Canada, puis issue `enquete` pré-remplie.
- `ajout.yml` intègre l'issue `enquete` sans IA : points « historique » sur la courbe, prix « navigateur »,
  prix canadiens dans « Au Québec ». TESTÉ de bout en bout le 23/11 (issue n°8, Timberland : 12 points d'historique
  idealo/Keepa, 5 prix FR, 2 prix CA). Correctifs issus de ce test : un point d'historique n'est jamais le prix
  actuel ; point aberrant (< 60 % de la médiane de l'historique) écarté avec une note ; verdict « Plus cher que
  d'habitude ». L'étiquette `enquete` n'existait pas encore (posée à la main sur l'issue n°8) : elle existe désormais.

## 23/11 : Patagonia 1/4 zip, Glacier, équivalents, Québec
- Nouvel article `patagonia-better-sweater-1-4-zip` (25523 noir M ; Hawaiisurf, Outnorth, Alpinstore lisibles).
  L'ancien article zip intégral (25528) est gardé en attendant la décision de l'utilisateur.
- Enquête : comparaison de plusieurs modèles (lignes « Modèle », pour les fiches à choisir), « Équivalent »
  (bloc « Aussi bien, à comparer » + bouton « Le suivre aussi »), promo « au panier » à vérifier en ajoutant au
  panier sans compte ni paiement.
- Timberland Canada officiel suivi par le robot (filtre US 7 largeur M) ; le -30 % au panier n'est pas visible
  par robot : à confirmer par l'enquête. Notification « Au Québec, sous ton alerte » ajoutée.

## Ce que l'utilisateur doit faire
- Rien d'obligatoire. Ajouter des objets depuis le site ; les verdicts se fiabilisent au fil des relevés quotidiens.

## Points d'attention
- Wayback est lent : plafonné à 25 min par passe, reprise à la passe suivante.
- Relevés JSONL en `merge=union` ; une file de concurrence par demande.
- `deploy-pages@v4` / `upload-pages-artifact@v3` : avertissement Node 20 sans effet.
- Ne jamais afficher sur le site de donnée personnelle autre que les articles et les tailles.
