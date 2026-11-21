RELAIS: non

# État de la construction

Dernière mise à jour : 21/11/2026, ~14 h 15 UTC (maillon horaire). Tout le BRIEF et toutes les idées de IDEES.md sont faits.

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
- [x] 9 Soldes et Black Friday : trait ocre sur l'axe de la courbe, nommés dans la lecture au doigt.
- [x] 10 Équivalents moins chers : lien sur la fiche → demande « ajout » pré-remplie → `claude.yml` (si le secret
      existe) propose 2 ou 3 articles liés à l'original (« À comparer »). Non testé de bout en bout : secret absent.

## Ce que l'utilisateur doit faire
- Ouvrir https://zakkk1.github.io/prixjuste/ et vérifier à l'œil (le conteneur ne peut pas l'atteindre).
- Facultatif : ajouter le secret `CLAUDE_CODE_OAUTH_TOKEN` (LISEZMOI) pour l'identification en texte libre et les
  équivalents.

## Points d'attention
- Wayback est lent : plafonné à 25 min par passe, reprise à la passe suivante.
- Relevés JSONL en `merge=union` ; une file de concurrence par demande.
- `deploy-pages@v4` / `upload-pages-artifact@v3` : avertissement Node 20 sans effet.
- Ne jamais afficher sur le site de donnée personnelle autre que les articles et les tailles.
