RELAIS: oui

# État de la construction

Dernière mise à jour : session du 21/11/2026 (construction de la plateforme).

## Définition de fini (docs/BRIEF.md)
- [x] Données migrées SQLite → `data/` : 35/35 relevés, 70/70 journal, 24/24 captures ; `prixjuste.db` retiré.
- [ ] `releve.yml` testé via `workflow_dispatch` (en cours de vérification).
- [ ] `ajout.yml` testé de bout en bout avec l'issue n°1 (en cours).
- [x] `claude.yml` prêt, inactif sans secret ; activation documentée dans LISEZMOI.md.
- [x] Site conforme à la DA, vérifié 375 px / desktop, clair / sombre. [ ] En ligne sur Pages (en cours).
- [x] Tests pytest verts en CI (`tests.yml`).
- [x] LISEZMOI.md.

## Idées (docs/IDEES.md)
- [x] 1. Notifications (issue « Suivi » par article, `data/signaux.json`).
- [x] 2. Coût réel (livraison JSON-LD, hors UE, tri par coût).
- [x] 3. Protection après achat (issue `achat`, tampon PAYÉ, rétractation 14 j, garantie 2 ans).
- [ ] 4. Profil de tailles · [ ] 5. Calendrier .ics · [ ] 6. Plan sous budget · [ ] 7. Risque de rupture
- [ ] 8. Carte 9:16 · [ ] 9. Événements sur la courbe · [ ] 10. Équivalents (Claude)

## Points d'attention pour la suite
- La lecture des archives Wayback est lente : plafonnée à 25 min par passe (`--minutes`), reprise ensuite.
- Les relevés JSONL fusionnent en `merge=union` (`.gitattributes`) ; chaque demande a sa propre file.
