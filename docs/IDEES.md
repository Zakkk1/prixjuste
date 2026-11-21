# PrixJuste — au-delà du suivi de prix (à construire APRÈS la « Définition de fini » du BRIEF)

L'utilisateur veut un outil à fort potentiel, qui l'aide aussi sur des choses auxquelles il n'a pas pensé.
**Contrainte qui prime sur tout : l'écran reste propre.** Chaque idée ci-dessous s'intègre dans les 3 écrans
existants (une ligne, un tampon, un bloc repliable), jamais un nouvel onglet ou un tableau de bord surchargé.
Tout tourne sans Claude, sauf mention contraire. Faire dans l'ordre ; s'arrêter proprement si le temps manque.

## 1. Être prévenu sans ouvrir le site — notifications GitHub (priorité haute)
Quand un article passe à ACHÈTE, tombe sous son seuil d'alerte, ou qu'une promo bidon est détectée, `releve.yml`
**commente une issue dédiée à l'article** (une issue « Suivi : <article> » ouverte une fois, étiquette `suivi`).
L'utilisateur reçoit la notification sur l'app GitHub de son téléphone. Aucun secret, aucun service tiers.
Un seul message par changement de verdict (pas de spam quotidien).

## 2. Le coût réel, pas le prix affiché (priorité haute)
Pour chaque offre : prix + livraison + frais de retour éventuels, lus dans le JSON-LD (`shippingDetails`,
`hasMerchantReturnPolicy` : Sports Direct les publie déjà). Marquer les marchands **hors UE** (Suisse, Royaume-Uni,
États-Unis…) : « + droits de douane et TVA à l'import possibles ». Le tableau des marchands se trie sur le coût réel.
Le verdict se base sur le coût réel quand il est connu.

## 3. Protection après achat (priorité haute, rarement proposée ailleurs)
Bouton « Je l'ai acheté » (issue `achat` pré-remplie : prix payé, marchand, date). Ensuite l'article passe en mode
« protégé » :
- il continue d'être relevé pendant le **délai de rétractation de 14 jours** (droit européen pour la vente en ligne) ;
  si le prix baisse nettement, notification : « Il a baissé de X € chez <marchand> : retourne-le et rachète-le, ou
  demande un geste commercial » ;
- il rappelle la **garantie légale de conformité de 2 ans** (France/UE) avec sa date de fin ;
- tout ça dans un fichier calendrier (point 5).

## 4. Profil de tailles (priorité moyenne)
`data/profil.json` : pointure et taille habituelles, et ajustements appris par marque (ex. « Timberland 6-Inch : −0,5 »,
conseil documenté). À l'ajout d'un article d'une marque connue, la taille conseillée est pré-remplie et expliquée en
une ligne. Ne stocker que des tailles, rien d'autre de personnel (le site est public).

## 5. Le calendrier d'achat (priorité moyenne)
Générer `site/agenda.ics` (abonnement depuis le calendrier du téléphone) avec, pour chaque article : la fenêtre
d'achat conseillée, les grandes dates commerciales françaises (soldes d'hiver et d'été aux dates légales, Black
Friday, French Days, Prime Day quand elles sont connues), les fins de rétractation et de garantie (point 3).
Sur le site : une seule ligne en haut du comptoir, « Prochaine fenêtre : <article> — <date> ».

## 6. Plan d'achat sous budget (priorité moyenne, idée nouvelle)
Champ optionnel « budget par mois ». L'outil répartit la wishlist sur les mois à venir pour **dépenser au meilleur
moment sans dépasser le budget** : chaque article est placé dans sa fenêtre la moins chère, et l'urgence et le risque
de rupture de taille servent d'arbitrage (petit sac à dos, glouton explicable). Affichage : une frise de mois très sobre,
repliable sur la page d'accueil. Total estimé et économie attendue par rapport à « tout acheter aujourd'hui ».

## 7. Risque de rupture de ta taille (priorité moyenne)
Avec le stock par taille relevé chaque jour, estimer la vitesse à laquelle ta taille disparaît en période de soldes
(historique de `n_dispo`). Le verdict peut devenir « Attends… mais pas après le <date> : ta taille part vite ».

## 8. La carte « preuve » à partager (priorité moyenne — sert directement au projet TikTok de l'utilisateur)
Sur chaque fiche, un bouton « Carte 9:16 » qui génère une image verticale (SVG puis PNG, côté navigateur, sans
service tiers) dans la direction « Étiquette » : nom de l'article, prix barré annoncé contre vrai historique, courbe,
tampon BIDON ou BON PLAN, sources et dates. Factuelle, sans nom de personne, prête à poster. C'est le format vidéo
dont on a parlé (« promo ou arnaque ? »).

## 9. Repère des grands événements de prix (priorité basse)
Annoter la courbe avec les événements datés (Black Friday, soldes, sortie d'un nouveau modèle quand elle est connue)
pour qu'on lise d'un coup d'œil pourquoi le prix a bougé.

## 10. Recherche d'équivalents moins chers (priorité basse, **seule idée qui utilise Claude**)
Bouton « Trouver un équivalent » qui ouvre une issue `equivalent` ; traitée par `claude.yml` seulement si le secret
Claude existe. Propose 2 ou 3 alternatives argumentées (même usage, qualité comparable), ajoutées en articles
« à comparer ».

## Garde-fous (rappel)
Collecte honnête (robots.txt, User-Agent explicite, aucun contournement). Aucune donnée personnelle sur le site
public en dehors des articles, tailles et achats que l'utilisateur choisit d'y mettre. Aucun secret créé ni saisi.
Chaque ajout doit garder l'interface sobre : si une idée encombre l'écran, la mettre dans un bloc repliable ou ne pas la faire.
