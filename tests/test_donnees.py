import json
from pathlib import Path

from prixjuste.donnees import Depot, slug

DATA = Path(__file__).resolve().parent.parent / "data"


def test_releves_append_only_sans_doublon(depot):
    r = {"ts": "2026-11-20T08:00:00", "lien": "https://a.fr/p", "marchand": "A", "source": "direct", "prix": 10.0}
    assert depot.ajouter_releve("x", r)
    assert not depot.ajouter_releve("x", dict(r))  # même lien/source/horodatage : ignoré
    assert depot.ajouter_releve("x", {**r, "ts": "2026-11-21T08:00:00"})
    lignes = (depot.racine / "releves" / "x.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lignes) == 2
    assert json.loads(lignes[0])["prix"] == 10.0
    assert "note" not in json.loads(lignes[0])  # champs vides omis : diff lisible


def test_nouvel_id_unique(depot):
    depot.ecrire_article({"id": "parka-mcmurdo"})
    assert depot.nouvel_id("Parka McMurdo") == "parka-mcmurdo-2"
    assert slug("La parka McMurdo de The North Face, taille L") == "parka-mcmurdo-the-north-face-taille-l"


def test_journal_et_captures(depot):
    depot.noter("x", "https://a.fr/p", "direct", "bloqué", "HTTP 403")
    depot.marquer_capture("x", "https://a.fr/p", "20260101000000")
    assert depot.journal("x")[0]["statut"] == "bloqué"
    assert depot.captures_vues("x") == {("https://a.fr/p", "20260101000000")}


def test_donnees_migrees_de_la_v1():
    """La migration SQLite -> JSONL n'a perdu aucun relevé (35 relevés, 70 entrées de journal, 24 captures)."""
    d = Depot(DATA)
    ids = {a["id"] for a in d.articles()}
    assert {"mcmurdo", "timberland"} <= ids
    v1 = [r for i in ("mcmurdo", "timberland") for r in d.releves(i) if r["ts"] < "2026-11-20"]
    assert len(v1) == 35
    assert len([j for i in ("mcmurdo", "timberland") for j in d.journal(i) if j["ts"] < "2026-11-20"]) == 70
    assert sum(len(d.captures_vues(i)) for i in ("mcmurdo", "timberland")) >= 24
    manuel = [r for r in d.releves("mcmurdo") if r["source"] == "manuel"]
    assert manuel[0]["prix"] == 439.0 and manuel[0]["prix_barre"] == 500.0


def test_fichiers_articles_valides():
    for p in (DATA / "articles").glob("*.json"):
        art = json.loads(p.read_text(encoding="utf-8"))
        assert art["id"] == p.stem
        assert art.get("statut", "suivi") in ("suivi", "a_identifier")
        for lien in art.get("liens", []):
            assert lien["url"].startswith("http")
