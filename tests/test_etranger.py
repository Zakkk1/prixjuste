import datetime as dt
import json

from prixjuste import analyse, build, etranger
from tests.test_analyse import AUJ, ART, o

XML = """<?xml version="1.0" encoding="UTF-8"?><gesmes:Envelope><Cube><Cube time='2026-11-21'>
<Cube currency='USD' rate='1.0412'/><Cube currency='CAD' rate='1.6250'/></Cube></Cube></gesmes:Envelope>"""
CHANGE = {"date": "2026-11-21", "taux": {"CAD": 1.625}}


def ca(jour, prix, marchand="The North Face (Canada)"):
    r = o(jour, prix, marchand=marchand)
    r.update({"pays": "CA", "devise": "CAD", "lien": "https://www.thenorthface.com/en-ca/p/x"})
    return r


def test_lire_bce():
    assert etranger.lire_bce(XML) == ("2026-11-21", {"USD": 1.0412, "CAD": 1.625})


def test_comparaison_quebec_taxes_comprises():
    c = etranger.comparaison([ca(AUJ, 97.5), o(AUJ, 90)], 90.0, CHANGE, AUJ)
    assert c["eur_ht"] == 60.0                      # 97,50 / 1,625
    assert c["eur_ttc"] == round(60 * 1.14975, 2)   # TPS + TVQ
    assert c["ecart"] == round(60 * 1.14975 - 90, 2) and c["ecart"] < 0
    assert c["nom_pays"] == "au Québec"


def test_sans_taux_ou_prix_ancien_rien():
    assert etranger.comparaison([ca(AUJ, 97.5)], 90.0, None, AUJ) is None
    assert etranger.comparaison([ca(AUJ - dt.timedelta(days=30), 97.5)], 90.0, CHANGE, AUJ) is None


def test_prix_etranger_jamais_dans_le_verdict():
    obs = [o(AUJ, 90), ca(AUJ, 50)]
    res = analyse.analyser(ART, obs, AUJ)
    assert res["actuel"]["prix"] == 90 and len(analyse.filtrer_obs(ART, obs)) == 1


def test_bloc_quebec_sur_la_fiche(depot, tmp_path):
    depot.ecrire_article({"id": "x", "nom": "Polaire X", "categorie": "autre", "urgence": "pas_urgent",
                          "liens": [{"marchand": "TNF", "url": "https://www.thenorthface.com/fr-fr/p/x"},
                                    {"marchand": "The North Face (Canada)", "url": "https://www.thenorthface.com/en-ca/p/x",
                                     "pays": "CA", "devise": "CAD"}]})
    for r in (o(AUJ, 90), ca(AUJ, 97.5)):
        depot.ajouter_releve("x", r)
    (depot.racine / "change.json").write_text(json.dumps(CHANGE))
    sortie = build.construire(depot, tmp_path / "site", aujourdhui=AUJ)
    fiche = (sortie / "a" / "x.html").read_text(encoding="utf-8")
    assert "Au Québec" in fiche and "taxes comprises" in fiche and "de moins qu’en France" in fiche
    assert "430 €" in fiche and "1,625" in fiche
    assert fiche.count("en-ca/p/x") == 0  # pas mêlé à la liste des marchands français
    assert "au Québec ≈" in (sortie / "index.html").read_text(encoding="utf-8")
