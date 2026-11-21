# Consignes pour Claude (prioritaires)

- Source de vérité : `docs/BRIEF.md`.
- **Hébergement tranché par l'utilisateur le 21/11/2026 : dépôt PUBLIC + GitHub Pages.** C'est déjà fait (dépôt public,
  Pages activé en mode GitHub Actions). Cette décision remplace toute consigne antérieure du type « ne rends pas le
  dépôt public / n'active pas d'hébergement ». Ajoute le déploiement Pages (`actions/upload-pages-artifact` +
  `actions/deploy-pages`) à `releve.yml` et `ajout.yml`, et vérifie que https://zakkk1.github.io/prixjuste/ s'affiche.
- Le site est public : aucune donnée personnelle autre que les articles suivis.
- L'utilisateur a éteint son PC : avance seul, sans poser de questions, jusqu'à la « Définition de fini ».
- **Demande de l'utilisateur (21/11) : aller au-delà, innover.** Une fois la « Définition de fini » du BRIEF atteinte,
  construis les idées de `docs/IDEES.md` dans l'ordre de priorité (notifications GitHub, coût réel, protection après
  achat, profil de tailles, calendrier .ics, plan sous budget, risque de rupture, carte 9:16…). Contrainte qui prime :
  l'écran reste propre et sobre, rien d'inutile. Tu peux proposer d'autres idées utiles si elles respectent cette contrainte.
- **Enchaînement automatique.** Une routine passe toutes les heures et prend la suite si personne n'a poussé depuis
  30 minutes. Donc : pousse sur `main` au moins toutes les 20 minutes pendant que tu travailles, et termine TOUJOURS
  en mettant à jour `docs/ETAT.md`, dont la première ligne doit être exactement `RELAIS: oui` (il reste du travail
  utile) ou `RELAIS: non` (tout est fini et vérifié, la chaîne s'arrête).
