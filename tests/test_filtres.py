import pytest

from prixjuste import collecte
from prixjuste.sources.jsonld import extraire_offres


def offres(page, nom):
    return extraire_offres(page(nom))[1]


def test_taille_exacte_en_stock(page):
    r = collecte.resumer(offres(page, "variantes_tailles.html"), taille="40")
    assert r == {"prix": 199.0, "livraison": None, "devise": "EUR", "en_stock": 1, "n_offres": 1, "n_dispo": 1}


def test_taille_avec_virgule_en_rupture(page):
    r = collecte.resumer(offres(page, "variantes_tailles.html"), taille="39,5")
    assert r["en_stock"] == 0 and r["prix"] == 230.0


def test_taille_absente_de_la_page(page):
    assert collecte.resumer(offres(page, "variantes_tailles.html"), taille="45") is None


def test_taille_non_detaillee_garde_le_prix_mais_stock_inconnu(page):
    r = collecte.resumer(offres(page, "produit_simple.html"), taille="L")
    assert r["prix"] == 373.90 and r["en_stock"] is None and r["n_dispo"] is None


def test_sans_filtre_meilleur_prix_disponible(page):
    r = collecte.resumer(offres(page, "variantes_tailles.html"))
    assert r["prix"] == 199.0 and r["n_dispo"] == 3 and r["n_offres"] == 4


def test_filtre_texte(page):
    r = collecte.resumer(offres(page, "aggregate_offres.html"), filtre="tb-2")
    assert r["prix"] == 170.0


def test_filtre_regex_exclut_demi_pointure(page):
    # « US 7 » mais pas « US 7.5 »
    r = collecte.resumer(offres(page, "aggregate_offres.html"), filtre="re:US 7$")
    assert r["prix"] == 176.0 and r["n_offres"] == 1


def test_filtre_sans_correspondance(page):
    assert collecte.resumer(offres(page, "aggregate_offres.html"), filtre="re:US 12$") is None


def test_captcha_est_signale_comme_bloque(page):
    with pytest.raises(collecte.Bloque):
        collecte.lire_page(page("captcha.html"))


def test_cle_inclut_la_taille():
    assert collecte.cle({"url": "https://x.fr/p", "taille": "40"}) == "https://x.fr/p#taille=40"
    assert collecte.cle({"url": "https://x.fr/p"}) == "https://x.fr/p"
