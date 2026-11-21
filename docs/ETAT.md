RELAIS: non

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

## Ce que l'utilisateur doit faire
- Rien d'obligatoire. Ajouter des objets depuis le site ; les verdicts se fiabilisent au fil des relevés quotidiens.

## Points d'attention
- Wayback est lent : plafonné à 25 min par passe, reprise à la passe suivante.
- Relevés JSONL en `merge=union` ; une file de concurrence par demande.
- `deploy-pages@v4` / `upload-pages-artifact@v3` : avertissement Node 20 sans effet.
- Ne jamais afficher sur le site de donnée personnelle autre que les articles et les tailles.
