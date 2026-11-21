import datetime as dt

from prixjuste import ajout, analyse, build
from tests.test_analyse import ART, AUJ, annee, o
from tests.test_notifier import FauxGitHub, preparer
from prixjuste import notifier

ACHAT = {"prix": 230.0, "marchand": "Boutique A", "date": "2026-11-15"}


def test_protection_dates():
    pr = analyse.protection({**ART, "achat": ACHAT}, AUJ)
    assert pr["fin_retractation"] == dt.date(2026, 11, 29)
    assert pr["fin_garantie"] == dt.date(2028, 11, 15)
    assert pr["en_retractation"]
    assert analyse.protection({**ART, "achat": {**ACHAT, "date": "2024-02-29"}}, AUJ)["fin_garantie"] == dt.date(2026, 2, 28)


def test_releve_seulement_pendant_la_retractation():
    art = {**ART, "achat": ACHAT}
    assert analyse.a_relever(art, AUJ)
    assert not analyse.a_relever(art, dt.date(2026, 12, 1))
    assert analyse.a_relever(ART, AUJ)
    assert not analyse.a_relever({**ART, "statut": "a_identifier"}, AUJ)


def test_baisse_apres_achat():
    res = analyse.analyser({**ART, "achat": ACHAT}, [o(AUJ, 199, marchand="B")], AUJ)
    assert res["baisse_apres_achat"] == {"ecart": 31.0, "prix": 199, "marchand": "B"}
    res = analyse.analyser({**ART, "achat": ACHAT}, [o(AUJ, 227)], AUJ)  # 3 € : pas la peine
    assert "baisse_apres_achat" not in res


def test_lire_achat():
    a = ajout.lire_achat("", "Article : x\nPrix : 230\nMarchand : Boutique A\nDate : 2026-11-15", [{"id": "x", "nom": "X"}])
    assert a == {"article": "x", "prix": 230.0, "marchand": "Boutique A", "date": "2026-11-15"}


def test_notification_baisse_apres_achat(depot):
    preparer(depot, [o(AUJ, 199, marchand="B")])
    art = depot.article("x")
    depot.ecrire_article({**art, "achat": ACHAT})
    gh = FauxGitHub()
    assert notifier.notifier(depot, gh, "", AUJ, log=lambda *a: None) == 1
    assert "Il a baissé depuis ton achat" in gh.commentaires[0][1]
    assert "29/11/2026" in gh.commentaires[0][1]


def test_tampon_paye(depot, tmp_path):
    preparer(depot, annee(lambda m: 250) + [o(AUJ, 230)])
    depot.ecrire_article({**depot.article("x"), "achat": ACHAT})
    sortie = build.construire(depot, tmp_path / "site", aujourdhui=AUJ)
    fiche = (sortie / "a" / "x.html").read_text(encoding="utf-8")
    assert "PAYÉ" in fiche and "Garantie légale" in fiche and "28/11/2028" not in fiche and "15/11/2028" in fiche
    assert "form-achat" not in fiche  # déjà acheté
