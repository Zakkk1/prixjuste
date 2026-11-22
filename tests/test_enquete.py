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
    assert "PriceCanada" not in t and "estimées" in t


def test_point_isole_ecarte_mais_pas_les_soldes():
    obs = [{"ts": f"2026-{m:02d}-15T12:00:00", "source": "historique", "prix": p, "marchand": "idealo (historique)"}
           for m, p in ((1, 162), (2, 132), (3, 160), (5, 143), (6, 159), (7, 75), (9, 166), (11, 159))]
    obs += [{"ts": "2026-11-22T08:00:00", "source": "direct", "prix": 230, "marchand": "Officiel"}] * 3
    gardes, isoles = analyse.ecarter_isoles(obs)
    assert [o["prix"] for o in isoles] == [75]
    art = {"id": "x", "categorie": "autre", "urgence": "pas_urgent"}
    res = analyse.analyser(art, obs, dt.date(2026, 11, 22))
    assert res["chiffres"]["min_12m"] == 132 and res["actuel"]["prix"] == 230  # l'historique n'est pas une offre
    assert any("75,00 €" in n for n in res["notes"])


def test_modeles_et_equivalents(depot, tmp_path):
    from prixjuste import build
    art = {"id": "g", "nom": "Glacier", "statut": "a_choisir", "categorie": "vetement_hiver", "urgence": "pas_urgent",
           "liens": [], "candidats": [{"nom": "Glacier zippée", "prix": 90.0, "marchand": "TNF", "liens": []},
                                      {"nom": "Glacier col zippé", "prix": 70.0, "marchand": "TNF", "liens": []}]}
    depot.ecrire_article(art)
    corps = ("Article : g\nModèle : 2 | 49 | The North Face | https://tnf.fr/x | oui | plus bas 45 € (idealo, 28/11/2025)\n"
             "Équivalent : Columbia Steens Mountain | 45 | Decathlon | https://ex.fr/c | plus chaude, moins habillée\n"
             "Sources : idealo, Dealabs")
    e = enquete.lire(corps, [art])
    assert e["modeles"][0]["n"] == 2 and e["equivalents"][0]["prix"] == 45.0
    assert enquete.enregistrer(depot, art, e, ts="2026-11-23T10:00:00") == (0, 0, 0)  # pas de relevé avant le choix
    a = depot.article("g")
    assert a["candidats"][1]["enquete"]["prix"] == 49.0 and a["equivalents"][0]["nom"] == "Columbia Steens Mountain"
    sortie = build.construire(depot, tmp_path / "site", aujourdhui=dt.date(2026, 11, 23))
    fiche = (sortie / "a" / "g.html").read_text(encoding="utf-8")
    assert "Enquête du 23/11/2026" in fiche and "Aussi bien, à comparer" in fiche and "Le suivre aussi" in fiche
    assert "JE N" in fiche  # la consigne d'enquête compare les modèles proposés


def test_alerte_quebec(depot):
    import json
    from prixjuste import notifier
    from tests.test_notifier import FauxGitHub
    from tests.test_analyse import annee, o, AUJ
    depot.ecrire_article({"id": "x", "nom": "Parka X", "categorie": "autre", "urgence": "pas_urgent", "liens": []})
    for r in annee(lambda m: 250) + [o(AUJ, 260)]:
        depot.ajouter_releve("x", r)
    ca = o(AUJ, 150, marchand="Boutique CA")
    ca.update({"pays": "CA", "devise": "CAD", "lien": "https://ex.ca/x"})
    depot.ajouter_releve("x", ca)
    (depot.racine / "change.json").write_text(json.dumps({"date": "2026-11-20", "taux": {"CAD": 1.6}}))
    gh = FauxGitHub()
    assert notifier.notifier(depot, gh, "", AUJ, log=lambda *a: None) == 1
    assert "Au Québec, sous ton alerte" in gh.commentaires[0][1]
