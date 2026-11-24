import json
from pathlib import Path

from prixjuste import build, dossiers, notifier
from prixjuste.donnees import Depot

RACINE = Path(__file__).resolve().parent.parent
CHANGE = {"date": "2026-11-24", "taux": {"CAD": 1.5}}


def piece(**kv):
    p = {"nom": "Boot", "prix": 100.0, "url": "https://ex.fr/b", "verdict": "acheter"}
    p.update(kv)
    return p


def tenue(*pieces_):
    return {"type": "tenue", "titre": "Look", "le": "2026-11-24", "resume": "r",
            "options": [{"nom": "Exacte", "pieces": list(pieces_)}]}


def test_les_dossiers_publies_sont_valides():
    depot = Depot(RACINE / "data")
    ds = dossiers.charger(depot)
    assert ds, "au moins un dossier d'exemple"
    for d in ds:
        assert dossiers.verifier(d, depot.articles()) == [], d["id"]


def test_prix_canadien_converti_taxes_du_quebec_comprises():
    p = piece(prix=150.0, devise="CAD", pays="CA")
    assert dossiers.en_euros(p, CHANGE) == round(100 * 1.14975, 2)
    assert dossiers.en_euros(piece(), None) == 100.0
    assert dossiers.en_euros(p, None) is None


def test_total_sans_les_pieces_deja_possedees():
    assert dossiers.total([piece(), piece(prix=50.0), piece(prix=80.0, verdict="deja")], CHANGE) == 150.0
    assert dossiers.total([piece(), piece(prix=None, url=None)], CHANGE) is None


def test_erreurs_detectees():
    assert dossiers.verifier({"type": "autre"}) != []
    err = dossiers.verifier(tenue(piece(url=None), piece(verdict="peut-etre"), piece(devise="CAD")))
    assert any("url" in x for x in err)
    assert any("verdict" in x for x in err)
    assert any("pays" in x for x in err)
    err = dossiers.verifier(tenue(piece(article="inconnu")), [{"id": "timberland"}])
    assert any("inconnu" in x for x in err)
    assert dossiers.verifier(tenue(piece())) == []


def test_page_d_une_tenue(tmp_path):
    d = tenue(piece(nom="Parka", prix=150.0, devise="CAD", pays="CA", marchand="Sporting Life"),
              piece(nom="Polaire", prix=104.0, verdict="attendre", quand_court="→ 30/11"))
    d["id"] = "t"
    h = build.page_dossier(d, CHANGE, {}, "24/11/2026")
    ca = dossiers.en_euros(d["options"][0]["pieces"][0], CHANGE)
    assert "Parka" in h and "150,00 $ CA" in h and f"≈ {build.euros(ca)} taxes comprises" in h
    assert build.euros(ca + 104) in h  # total de l'option
    assert "ATTENDS" in h and "→ 30/11" in h and "Suivre son prix" in h


def test_le_site_publie_les_dossiers(tmp_path):
    racine = tmp_path / "data"
    (racine / "dossiers").mkdir(parents=True)
    d = tenue(piece(nom="Polaire"))
    (racine / "dossiers" / "tenue-test.json").write_text(json.dumps(d), encoding="utf-8")
    sortie = build.construire(Depot(racine), tmp_path / "site", quand="24/11/2026")
    assert (sortie / "d" / "tenue-test.html").exists()
    accueil = (sortie / "index.html").read_text(encoding="utf-8")
    assert "Mes dossiers" in accueil and "d/tenue-test.html" in accueil and "Demander à Claude" in accueil


class FauxGitHub:
    def __init__(self):
        self.ouvertes, self.comms = [], []

    def issues(self, etiquette):
        return [{"number": i + 1, "title": t} for i, t in enumerate(self.ouvertes)]

    def commentaires(self, numero):
        return [{"body": c} for n, c in self.comms if n == numero]

    def ouvrir(self, titre, corps):
        self.ouvertes.append(titre)
        return len(self.ouvertes)

    def commenter(self, numero, corps):
        self.comms.append((numero, corps))


def test_annonce_une_seule_fois(tmp_path):
    racine = tmp_path / "data"
    (racine / "dossiers").mkdir(parents=True)
    d = {"type": "bons-plans", "titre": "Black Friday", "le": "2026-11-27", "resume": "2 affaires",
         "plans": [piece()], "annoncer": True}
    (racine / "dossiers" / "bp.json").write_text(json.dumps(d), encoding="utf-8")
    (racine / "dossiers" / "silencieux.json").write_text(json.dumps(dict(d, annoncer=False)), encoding="utf-8")
    gh, depot = FauxGitHub(), Depot(racine)
    assert notifier.annoncer(depot, gh, "https://ex.io/pj", log=lambda *a: None, mention="moi") == 1
    corps = gh.comms[0][1]
    assert "https://ex.io/pj/d/bp.html" in corps and "@moi" in corps
    assert notifier.annoncer(depot, gh, "", log=lambda *a: None) == 0
    assert gh.ouvertes == [notifier.TITRE_ANNONCES]


def test_un_lien_retire_ne_compte_plus():
    from prixjuste import analyse
    art = {"id": "p", "liens_retires": ["https://a.fr/x"]}
    obs = [{"lien": "https://a.fr/x", "prix": 104}, {"lien": "https://b.fr/y", "prix": 129.95}]
    assert [o["prix"] for o in analyse.filtrer_obs(art, obs)] == [129.95]
