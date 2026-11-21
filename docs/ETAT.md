RELAIS: oui

# État de la construction

Dernière mise à jour : 21/11/2026, fin de la session de construction.

## Définition de fini (docs/BRIEF.md) — atteinte
- [x] Données migrées SQLite → `data/` : 35/35 relevés, 70/70 journal, 24/24 captures ; `prixjuste.db` retiré.
- [x] `releve.yml` : 3 runs `workflow_dispatch` verts (relevé, archives, notifications, commit, Pages) ; cron 04:41 UTC.
- [x] `ajout.yml` : testé de bout en bout avec l'issue n°1 (article créé, relevé réel, verdict commenté, issue
      fermée, site déployé) ; article de test retiré ensuite.
- [x] `claude.yml` : lancé à la main sans secret → job « verifier » vert, identification ignorée. Activation : LISEZMOI.
- [x] Site conforme à la DA, vérifié 375 px / 1280 px, clair / sombre ; déployé sur Pages (« Reported success »,
      https://zakkk1.github.io/prixjuste/). Non consultable depuis le conteneur de la session (réseau), à revoir à l'œil.
- [x] Tests pytest verts en CI (78 tests).
- [x] LISEZMOI.md.

## Idées (docs/IDEES.md)
- [x] 1 Notifications · [x] 2 Coût réel · [x] 3 Protection après achat · [x] 4 Profil de tailles
- [x] 5 Agenda .ics · [x] 7 Risque de rupture · [x] 8 Carte 9:16
- [ ] 6 Plan d'achat sous budget (frise repliable sur le comptoir, champ « budget par mois »)
- [ ] 9 Événements de prix annotés sur la courbe (sobre : petits repères sous l'axe)
- [ ] 10 Équivalents moins chers (issue `equivalent`, via claude.yml, seulement si le secret existe)

## Points d'attention
- Wayback est lent : plafonné à 25 min par passe (`historique --minutes`), reprise à la passe suivante.
- Relevés JSONL en `merge=union` (`.gitattributes`) ; une file de concurrence par demande.
- `actions/deploy-pages@v4` et `upload-pages-artifact@v3` émettent un avertissement Node 20 (sans effet).
- Ne jamais afficher sur le site de donnée personnelle autre que les articles et les tailles.
