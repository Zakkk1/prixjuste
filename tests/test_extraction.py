from prixjuste.sources.jsonld import extraire_offres, prix_nombre


def test_produit_simple(page):
    nom, offres = extraire_offres(page("produit_simple.html"))
    assert nom == "Parka Exemple homme"
    assert len(offres) == 1
    assert offres[0]["prix"] == 373.90
    assert offres[0]["en_stock"] is True
    assert offres[0]["sku"] == "PX-100"


def test_variantes_avec_tailles(page):
    _, offres = extraire_offres(page("variantes_tailles.html"))
    par_taille = {o["taille"]: o for o in offres}
    assert set(par_taille) == {"39", "39.5", "40", "41"}  # « 39,5 » normalisé en « 39.5 »
    assert par_taille["39.5"]["en_stock"] is False
    assert par_taille["40"]["prix"] == 199.0
    assert par_taille["41"]["en_stock"] is True  # LimitedAvailability = disponible


def test_aggregate_avec_sous_offres(page):
    _, offres = extraire_offres(page("aggregate_offres.html"))
    assert [o["prix"] for o in offres] == [176.0, 170.0, 176.0]
    assert offres[2]["en_stock"] is False


def test_aggregate_sans_detail_et_graph(page):
    nom, offres = extraire_offres(page("aggregate_seul.html"))
    assert nom == "Casque Exemple"
    assert offres[0]["prix"] == 1299.90
    assert offres[0]["en_stock"] is None  # stock inconnu, pas « en rupture »


def test_repli_meta(page):
    _, offres = extraire_offres(page("meta_seulement.html"))
    assert offres == [{"prix": 89.90, "devise": "EUR", "en_stock": None, "sku": "", "nom": "", "taille": ""}]


def test_json_irregulier_et_price_specification(page):
    nom, offres = extraire_offres(page("ld_irregulier.html"))
    assert nom == "Veste Exemple"
    assert offres[0]["prix"] == 149.5


def test_page_sans_offre(page):
    assert extraire_offres(page("captcha.html")) == (None, [])


def test_prix_nombre():
    assert prix_nombre("1 299,90 €") == 1299.90
    assert prix_nombre("1.299,90") == 1299.90
    assert prix_nombre("1,299.90") == 1299.90
    assert prix_nombre(230) == 230.0
    assert prix_nombre("gratuit") is None
    assert prix_nombre(None) is None
