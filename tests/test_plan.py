import datetime as dt
import json
import re
import shutil
import subprocess

import pytest

from prixjuste import analyse, build, plan
from prixjuste.donnees import Depot
from tests.test_donnees import DATA

AUJ = dt.date(2026, 11, 21)


def _cands():
    d = Depot(DATA)
    return plan.candidats([(a, analyse.analyser(a, analyse.filtrer_obs(a, d.releves(a["id"])), AUJ))
                           for a in d.articles()], AUJ)


def test_candidats_mois_par_mois_jusqu_a_la_limite():
    c = _cands()
    mc = next(a for a in c["articles"] if a["id"] == "mcmurdo")
    assert mc["mois"][0] == ["2026-11", mc["maintenant"]]  # mois en cours : prix actuel
    assert mc["mois"][-1][0] <= mc["limite"][:7]
    assert all(len(a["mois"]) <= plan.MOIS_MAX for a in c["articles"])


def test_sans_historique_pas_d_economie_inventee():
    art = {"id": "x", "nom": "x", "statut": "suivi"}
    res = {"chiffres": {}, "actuel": {"prix": 100.0}, "serie": {}, "limite": AUJ + dt.timedelta(days=90)}
    c = plan.candidats([(art, res)], AUJ)
    assert {p for _, p in c["articles"][0]["mois"]} == {100.0}
    assert plan.repartir(c)["economie"] == 0


def test_achete_et_en_attente_exclus():
    res = {"chiffres": {}, "actuel": {"prix": 1.0}, "serie": {}, "limite": AUJ}
    assert plan.candidats([({"id": "a", "nom": "a", "achat": {"prix": 1}}, res),
                           ({"id": "b", "nom": "b", "statut": "a_identifier"}, res)], AUJ)["articles"] == []


def test_repartition_respecte_le_budget():
    c = {"debut": "2026-11", "articles": [
        {"id": "a", "nom": "A", "maintenant": 100, "limite": "2027-01-31", "mois": [["2026-11", 100], ["2026-12", 80], ["2027-01", 90]]},
        {"id": "b", "nom": "B", "maintenant": 60, "limite": "2026-12-31", "mois": [["2026-11", 60], ["2026-12", 50]]},
        {"id": "c", "nom": "C", "maintenant": 500, "limite": "2026-11-30", "mois": [["2026-11", 500]]}]}
    r = plan.repartir(c, 120)
    assert r["hors"] == ["c"]
    assert r["mois"] == {"2026-12": [("b", 50)], "2027-01": [("a", 90)]}  # B, plus pressé, prend décembre
    assert r["total"] == 140 and r["economie"] == 20
    assert plan.repartir(c)["mois"]["2026-12"] == [("b", 50), ("a", 80)]


@pytest.mark.skipif(not shutil.which("node"), reason="node absent")
@pytest.mark.parametrize("budget", [0, 120, 200, 450, 1000])
def test_js_identique_au_python(budget):
    src = (build.STATIQUE / "site.js").read_text(encoding="utf-8")
    fn = re.search(r"// <repartir>.*?\n(.*)// </repartir>", src, re.S).group(1)
    c = _cands()
    c["articles"].append({"id": "z", "nom": "Z", "maintenant": 120, "limite": "2027-01-31",
                          "mois": [["2026-11", 120], ["2026-12", 99.5], ["2027-01", 99.5]]})
    js = fn + f"console.log(JSON.stringify(repartir({json.dumps(c)}, {budget})));"
    out = json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)
    py = plan.repartir(c, budget)
    assert out["mois"] == {k: [list(x) for x in v] for k, v in py["mois"].items()}
    assert out["hors"] == py["hors"] and out["total"] == py["total"] and out["economie"] == pytest.approx(py["economie"])


def test_bloc_sur_le_comptoir(tmp_path):
    sortie = build.construire(Depot(DATA), tmp_path / "site", aujourdhui=AUJ, quand="x")
    index = (sortie / "index.html").read_text(encoding="utf-8")
    assert '<details class="archives plan" data-plan=' in index and "Plan d'achat sous budget" in index
    assert "budget_mois" not in index  # le budget n'est jamais publié


def test_evenements_sur_la_courbe(tmp_path):
    sortie = build.construire(Depot(DATA), tmp_path / "site", aujourdhui=AUJ, quand="x")
    fiche = (sortie / "a" / "mcmurdo.html").read_text(encoding="utf-8")
    assert 'class="evt"><title>Soldes d&#x27;hiver' in fiche
    assert "Black Friday : 27/11/2026" in fiche
    assert "archive web · soldes d&#x27;hiver" in fiche  # la lecture au doigt nomme l'événement
