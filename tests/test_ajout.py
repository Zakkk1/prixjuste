import datetime as dt

import pytest

from prixjuste import ajout

CORPS_LIENS = """Objet : Timberland 6-Inch Premium jaune
Taille : 40
Coloris : jaune
Urgence : bientôt
Budget : 230 €
Liens :
https://www.exemple-chaussures.fr/p/boot-6-inch-123?couleur=jaune.
https://shop.autre-boutique.com/boot

<!-- prixjuste:ajout -->"""


def test_lire_demande_avec_liens():
    d = ajout.lire_demande("Ajout : Timberland", CORPS_LIENS)
    assert d["objet"] == "Timberland 6-Inch Premium jaune"
    assert d["taille"] == "40" and d["coloris"] == "jaune"
    assert d["urgence"] == "bientot"
    assert d["budget_max"] == 230.0
    assert d["liens"] == ["https://www.exemple-chaussures.fr/p/boot-6-inch-123?couleur=jaune",
                          "https://shop.autre-boutique.com/boot"]


def test_lire_demande_texte_libre_depuis_le_titre():
    d = ajout.lire_demande("Ajout : une parka chaude pas trop chère", "")
    assert d["objet"] == "une parka chaude pas trop chère"
    assert d["liens"] == [] and d["urgence"] == "pas_urgent"


def test_formulaire_github_sections():
    corps = "### Objet\n\nCasque audio Exemple\n\n### Taille\n\n_No response_\n\n### Liens\n\nhttps://x.fr/casque"
    d = ajout.lire_demande("", corps)
    assert d["objet"] == "Casque audio Exemple" and d["taille"] is None and d["liens"] == ["https://x.fr/casque"]


def test_creer_article_avec_liens(depot):
    art = ajout.creer_article(depot, ajout.lire_demande("", CORPS_LIENS), issue=12)
    assert art["statut"] == "suivi" and art["issue"] == 12
    assert art["categorie"] == "chaussures"
    assert art["liens"][0] == {"marchand": "Exemple Chaussures", "url": art["liens"][0]["url"], "exact": True,
                               "coloris": "jaune", "taille": "40"}
    assert art["autres_coloris_ok"] is False
    assert depot.article(art["id"]) == art


def test_creer_article_sans_lien_attend_identification(depot):
    art = ajout.creer_article(depot, ajout.lire_demande("Ajout : doudoune légère", ""))
    assert art["statut"] == "a_identifier" and art["liens"] == []
    assert art["categorie"] == "vetement_hiver"


def test_liens_github_ignores():
    assert ajout.liens_du_texte("voir https://github.com/x/y/issues/1 et https://a.fr/p") == ["https://a.fr/p"]


def test_nom_marchand():
    assert ajout.nom_marchand("https://www.snowleader.com/m-x.html") == "Snowleader"
    assert ajout.nom_marchand("https://www.e.leclerc/fp/x") == "E.Leclerc"


def test_prix_vu():
    arts = [{"id": "timberland", "nom": "Timberland 6-Inch"}]
    corps = "Article : timberland\nPrix : 199,90\nPrix barré : 230\nMarchand : Magasin Lyon\nDate : 20/11/2026\nRupture : non"
    p = ajout.lire_prix_vu("Prix vu", corps, arts)
    assert p == {"article": "timberland", "prix": 199.9, "barre": 230.0, "marchand": "Magasin Lyon",
                 "date": "2026-11-20", "rupture": False, "note": None}


def test_prix_vu_article_inconnu():
    with pytest.raises(ValueError, match="Article inconnu"):
        ajout.lire_prix_vu("", "Article : truc\nPrix : 10", [{"id": "a", "nom": "A"}])


def test_compte_rendu(depot):
    art = {"id": "x", "nom": "X", "liens": [{"marchand": "A", "url": "https://a.fr/p"}]}
    depot.noter("x", "https://a.fr/p", "direct", "bloqué", "HTTP 403")
    txt = ajout.compte_rendu(art, [], depot.journal("x"), dt.date(2026, 11, 21))
    assert txt.startswith("**PAS ASSEZ DE DONNÉES**")
    assert "| A | bloqué (HTTP 403) |" in txt


def test_euros():
    assert ajout.euros(1299.9) == "1 299,90 €"
    assert ajout.euros(230.0) == "230 €"


def test_demande_completee_par_des_liens(depot):
    art = ajout.creer_article(depot, ajout.lire_demande("Ajout : doudoune légère", ""), issue=5)
    ajout.completer_liens(depot, art, ajout.lire_demande("", "Objet : doudoune\nhttps://a.fr/doudoune"))
    art = depot.article(art["id"])
    assert art["statut"] == "suivi" and art["liens"][0]["url"] == "https://a.fr/doudoune"
