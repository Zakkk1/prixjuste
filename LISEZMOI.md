# PrixJuste (V1)

Outil perso qui te dit si un prix est bon, s'il vaut mieux attendre, et si une promo est bidon.

## Utilisation

| Je veux… | Commande |
|---|---|
| Relever les prix du jour + mettre à jour le rapport | `python prixjuste.py tout` (ou double-clic sur `lancer.bat`) |
| Récupérer l'historique passé (archives web) | `python prixjuste.py historique` |
| Ajouter un prix vu à la main (site bloqué, magasin, pub…) | `python prixjuste.py prix mcmurdo 439 --barre 500 --marchand "Zalando"` |
| Signaler une rupture de stock vue à la main | `python prixjuste.py prix mcmurdo 279 --rupture --marchand "X"` |
| Revoir le rapport sans relever | `python prixjuste.py rapport` puis ouvrir `rapport.html` |

Ajouter un article : copier un bloc dans `wishlist.json` et changer les champs.

- `urgence` : `urgent` (7 jours), `bientot` (45 jours), `pas_urgent` (1 an), ou une date précise dans `acheter_avant`
- `categorie` : `vetement_hiver`, `vetement_ete`, `chaussures`, `electronique`, `composants_pc`, `autre`
- `liens` : pages relevées chaque jour. `liens_historiques` : anciennes pages (anciens coloris…) utilisées seulement pour l'historique
- `filtre` (optionnel, dans un lien) : texte à trouver dans la référence de l'offre pour ne garder qu'une taille

## Règles de conduite

- L'outil s'annonce comme un robot et respecte `robots.txt`.
- Si un site bloque les robots, il est marqué « bloqué » et **on ne contourne pas** : on utilise les archives web ou la saisie manuelle.
- Un relevé par jour maximum.

## Fichiers

- `wishlist.json` : ta liste · `prixjuste.db` : tous les prix relevés (ne pas supprimer : c'est ton historique)
- `rapport.html` : le tableau de bord · `journal.txt` : trace des relevés automatiques
