import datetime as dt

from prixjuste import analyse

AUJ = dt.date(2026, 11, 21)


def o(jour, prix, marchand="Boutique A", source="direct", barre=None, en_stock=1, exact=True, n_dispo=None):
    d = jour if isinstance(jour, dt.date) else dt.date.fromisoformat(jour)
    r = {"ts": d.isoformat() + "T08:00:00", "lien": f"https://{marchand}.fr/p", "marchand": marchand,
         "exact": exact, "source": source, "prix": prix, "en_stock": en_stock}
    if barre:
        r["prix_barre"] = barre
    if n_dispo is not None:
        r["n_dispo"] = n_dispo
    return r


def annee(prix_du_mois, pas=7):
    """Un relevé par semaine sur les 12 derniers mois, prix selon le mois."""
    res, d = [], AUJ - dt.timedelta(days=364)
    while d < AUJ:
        res.append(o(d, prix_du_mois(d.month), source="archive"))
        d += dt.timedelta(days=pas)
    return res


ART = {"id": "x", "nom": "X", "categorie": "autre", "urgence": "pas_urgent"}


def test_aucun_prix():
    res = analyse.analyser(ART, [], AUJ)
    assert res["verdict"][0] == "donnees"
    assert res["chiffres"]["n_releves"] == 0


def test_historique_trop_court_pas_de_seuil_invente():
    obs = [o("2026-11-01", 200), o("2026-11-10", 210), o("2026-11-20", 190)]
    res = analyse.analyser(ART, obs, AUJ)
    assert res["verdict"][0] == "donnees"
    assert "alerte" not in res["chiffres"]  # pas de seuil calculé sur 3 prix
    assert "3 jour(s)" in res["verdict"][2]


def test_budget_sert_de_seuil_meme_avec_peu_de_donnees():
    obs = [o("2026-11-20", 190)]
    res = analyse.analyser({**ART, "budget_max": 150}, obs, AUJ)
    assert res["chiffres"]["alerte"] == 150


def test_achete_quand_prix_parmi_les_plus_bas():
    obs = annee(lambda m: 250) + [o(AUJ, 199)]
    res = analyse.analyser(ART, obs, AUJ)
    assert res["verdict"][0] == "acheter"
    assert res["chiffres"]["min_12m"] == 199


def test_attends_le_mois_le_moins_cher_avec_date():
    prix = {1: 150, 2: 165}
    obs = annee(lambda m: prix.get(m, 220)) + [o(AUJ, 220)]
    res = analyse.analyser(ART, obs, AUJ)
    code, titre, _ = res["verdict"]
    assert code == "attendre"
    assert titre == "Attends janvier"
    assert res["jusqu_a"] == dt.date(2027, 1, 31)


def test_meilleur_moment_apres_la_date_limite():
    prix = {1: 150}
    obs = annee(lambda m: prix.get(m, 220)) + [o(AUJ, 220)]
    res = analyse.analyser({**ART, "urgence": "urgent"}, obs, AUJ)
    assert res["verdict"][0] == "surveiller"
    assert "après ta date limite" in res["verdict"][1]
    assert res["jusqu_a"] is None


def test_surveille_si_prix_correct_sans_plus():
    obs = annee(lambda m: 200 + (m % 3)) + [o(AUJ, 215)]
    res = analyse.analyser(ART, obs, AUJ)
    assert res["verdict"][0] == "surveiller"
    assert res["chiffres"]["alerte"] <= 201


def test_tendance_haussiere_signalee():
    obs = [o(AUJ - dt.timedelta(days=d), 300 - d) for d in range(0, 90, 10)]
    res = analyse.analyser(ART, obs, AUJ)
    assert res["chiffres"]["tendance_90j"] > 8


def test_rupture_exclue_de_la_serie():
    obs = [o("2026-11-20", 100, en_stock=0), o("2026-11-20", 150, marchand="B")]
    res = analyse.analyser(ART, obs, AUJ)
    assert res["serie"][dt.date(2026, 11, 20)]["prix"] == 150
    assert res["actuel"]["prix"] == 150


def test_autre_coloris_exclu_si_demande():
    obs = [o("2026-11-20", 100, exact=False), o("2026-11-20", 150, marchand="B")]
    assert analyse.analyser({**ART, "autres_coloris_ok": False}, obs, AUJ)["actuel"]["prix"] == 150
    assert analyse.analyser(ART, obs, AUJ)["actuel"]["prix"] == 100


# ---------------------------------------------------------------- fausses promos (règle des 30 jours)

def test_promo_bidon_regle_des_30_jours():
    obs = annee(lambda m: 420)
    obs += [o("2026-11-05", 400, marchand="Shop"), o(AUJ, 420, marchand="Shop", barre=500)]
    res = analyse.analyser(ART, obs, AUJ)
    assert res["verdict"][0] == "bidon"
    pr = res["promos"][0]
    assert pr["alerte"].startswith("Prix barré 500 €")
    assert "400 €" in pr["alerte"] and "SignalConso" in pr["alerte"]
    assert round(pr["remise_affichee"]) == 16


def test_promo_honnete():
    obs = annee(lambda m: 500, pas=14)
    obs += [o("2026-11-05", 500, marchand="Shop"), o(AUJ, 400, marchand="Shop", barre=500)]
    res = analyse.analyser(ART, obs, AUJ)
    pr = res["promos"][0]
    assert not pr["douteuse"]
    assert res["verdict"][0] == "acheter"


def test_promo_ancienne_de_plus_de_30_jours_ignoree():
    obs = [o("2026-10-01", 400, marchand="Shop"), o(AUJ, 450, marchand="Shop", barre=500)]
    res = analyse.analyser(ART, obs, AUJ)
    assert "alerte" not in res["promos"][0]


def test_promo_douteuse_hors_meilleure_offre_ne_change_pas_le_tampon():
    obs = annee(lambda m: 300)
    obs += [o("2026-11-05", 380, marchand="Shop"), o(AUJ, 439, marchand="Shop", barre=500), o(AUJ, 290, marchand="B")]
    res = analyse.analyser(ART, obs, AUJ)
    assert res["verdict"][0] == "acheter"
    assert res["promos"][0]["douteuse"]


def test_remise_sur_prix_jamais_pratique():
    obs = annee(lambda m: 250) + [o(AUJ, 439, marchand="Vu", source="manuel", barre=500)]
    res = analyse.analyser(ART, obs, AUJ)
    assert "Ce n'est pas une bonne affaire" in res["promos"][0]["contexte"]
    assert res["verdict"][0] == "bidon"
    assert res["verdict_initial"][0] != "bidon"


# ---------------------------------------------------------------- fiabilité

def test_fiabilite_seuils():
    assert analyse.fiabilite(0) == "faible"
    assert analyse.fiabilite(14) == "faible"
    assert analyse.fiabilite(15) == "moyenne"
    assert analyse.fiabilite(59) == "moyenne"
    assert analyse.fiabilite(60) == "bonne"


def test_fiabilite_compte_les_jours_pas_les_releves():
    obs = [o("2026-11-20", 100, marchand=m) for m in "ABCDEFGH"]
    res = analyse.analyser(ART, obs, AUJ)
    assert res["chiffres"]["n_releves"] == 1
    assert res["chiffres"]["n_sources"] == 8


def test_prochaine_fenetre():
    assert analyse.prochaine_fenetre(1, 2, AUJ) == (dt.date(2027, 1, 1), dt.date(2027, 2, 28))
    assert analyse.prochaine_fenetre(11, 1, AUJ) == (AUJ, dt.date(2027, 1, 31))
    assert analyse.prochaine_fenetre(12, 12, AUJ) == (dt.date(2026, 12, 1), dt.date(2026, 12, 31))


def test_pas_de_fenetre_sur_4_jours():
    obs = [o("2026-01-10", 150), o("2026-03-10", 200), o("2026-06-10", 210), o("2026-11-20", 220)]
    res = analyse.analyser(ART, obs, AUJ)
    assert "fenetre" not in res["chiffres"] and res["verdict"][0] == "donnees"


def test_rupture_de_taille_avance_la_date():
    prix = {1: 150, 2: 165}
    obs = annee(lambda m: prix.get(m, 220)) + [o(AUJ, 220)]
    r = o("2026-01-20", 150, marchand="Shop", en_stock=0)
    r["lien"] = "https://shop.fr/p#taille=40"
    res = analyse.analyser(ART, obs + [r], AUJ)
    assert res["verdict"][0] == "attendre"
    assert res["jusqu_a"] == dt.date(2027, 1, 15)
    assert "Ta taille a déjà manqué" in res["verdict"][2] and "janvier 2026" in res["verdict"][2]


def test_un_prix_isole_ne_fait_pas_un_meilleur_mois():
    # 1 seul prix bas en janvier (une archive) : pas de « attends janvier » ni de « déjà vu vers … en janvier »
    obs = annee(lambda m: 220)
    obs = [r for r in obs if dt.date.fromisoformat(r["ts"][:10]).month != 1] + [o("2026-01-15", 150), o(AUJ, 220)]
    res = analyse.analyser(ART, obs, AUJ)
    assert res["chiffres"].get("meilleur_mois") != 1
    assert not any("janvier" in n for n in res["notes"])
