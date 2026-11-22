import datetime as dt

from prixjuste import analyse, enquete, etranger

CORPS = """Article : timberland
Historique : 2025-11-28 | 160 | idealo
Historique : 2026-01-15 | 175,50 | idealo
Prix : 190.79 | E.Leclerc | https://www.e.leclerc/fp/x | oui | 229.99
Prix : 229,99 | Foot Locker | https://www.footlocker.fr/x | non
Canada : 230 | JD Sports Canada | https://jdsports.ca/x | oui
Note : Plus bas vu au Black Friday 2025."""


def test_lire_enquete():
    e = enquete.lire(CORPS, [{"id": "timberland"}])
    assert e["historique"] == [{"date": "2025-11-28", "prix": 160.0, "source": "idealo"},
                               {"date": "2026-01-15", "prix": 175.5, "source": "idealo"}]
    assert e["prix"][0] == {"prix": 190.79, "marchand": "E.Leclerc", "url": "https://www.e.leclerc/fp/x",
                            "en_stock": 1, "barre": 229.99}
    assert e["prix"][1]["en_stock"] == 0 and e["canada"][0]["prix"] == 230.0
    assert e["note"].startswith("Plus bas")


def test_enregistrer_puis_courbe_et_quebec(depot):
    art = {"id": "timberland", "nom": "T", "categorie": "chaussures", "urgence": "pas_urgent", "liens": []}
    depot.ecrire_article(art)
    e = enquete.lire(CORPS, [art])
    assert enquete.enregistrer(depot, art, e, ts="2026-11-22T20:00:00") == (2, 2, 1)
    assert enquete.enregistrer(depot, art, e, ts="2026-11-22T20:00:00") == (0, 0, 0)  # pas de doublon
    obs = depot.releves("timberland")
    res = analyse.analyser(art, analyse.filtrer_obs(art, obs), dt.date(2026, 11, 22))
    assert res["chiffres"]["min_12m"] == 160.0          # l'historique lu remplit la courbe
    c = etranger.comparaison(obs, 190.79, {"date": "2026-11-20", "taux": {"CAD": 1.5723}}, dt.date(2026, 11, 22))
    assert c["prix_local"] == 230.0


def test_consigne_contient_l_essentiel():
    art = {"id": "timberland", "nom": "Timberland 6-Inch", "reference": "TB110061713", "taille": "40",
           "categorie": "chaussures", "liens": [{"marchand": "JD Sports (Canada)", "url": "https://jdsports.ca/x", "pays": "CA"}]}
    t = enquete.consigne(art, "Zakkk1/prixjuste")
    assert "US 7" in t and "idealo" in t and "captcha" in t and "labels=enquete" in t and "jdsports.ca/x" in t


def test_historique_canada_et_sources(depot):
    corps = CORPS + "\nHistorique Canada : 2025-11-28 | 199 | RedFlagDeals\nSources : idealo, Dealabs, Shopbot, Flipp"
    art = {"id": "timberland", "nom": "T", "categorie": "chaussures", "urgence": "pas_urgent", "liens": []}
    depot.ecrire_article(art)
    e = enquete.lire(corps, [art])
    assert e["historique_ca"][0]["prix"] == 199.0 and e["sources"].startswith("idealo")
    assert enquete.enregistrer(depot, art, e, ts="2026-11-22T20:00:00") == (3, 2, 1)
    ca = [o for o in depot.releves("timberland") if o.get("pays") == "CA" and o["source"] == "historique"]
    assert ca and ca[0]["prix"] == 199.0
    res = analyse.analyser(art, analyse.filtrer_obs(art, depot.releves("timberland")), dt.date(2026, 11, 22))
    assert res["chiffres"]["min_12m"] == 160.0  # le prix canadien ne se mêle pas à la courbe française


def test_consigne_ouverte():
    t = enquete.consigne({"id": "x", "nom": "X", "categorie": "autre", "liens": []}, "a/b")
    assert "EXEMPLES" in t and "Dealabs" in t and "RedFlagDeals" in t and "Flipp" in t and "Sources :" in t
