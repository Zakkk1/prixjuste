import datetime as dt
import html
import re
import urllib.parse

from prixjuste import ajout, build
from prixjuste.donnees import Depot

CANDS = [
    {"nom": "Casque A", "reference": "A1", "variante": "noir", "image": "https://img.test/a.jpg", "prix": 199.0,
     "marchand": "Boutique A", "url": "https://a.test/p", "liens": [{"marchand": "Boutique A", "url": "https://a.test/p", "exact": True}]},
    {"nom": "Casque B", "reference": "B2", "prix": 149.0, "marchand": "Boutique B", "url": "https://b.test/p",
     "liens": [{"marchand": "Boutique B", "url": "https://b.test/p", "exact": True}]},
]


def _depot(tmp_path):
    d = Depot(tmp_path / "data")
    d.ecrire_article({"id": "casque", "nom": "casque bluetooth", "demande": "casque bluetooth", "statut": "a_choisir",
                      "issue": 9, "liens": [], "candidats": CANDS})
    return d


def test_fiche_propose_les_candidats_avec_photo_et_bouton(tmp_path):
    d = _depot(tmp_path)
    sortie = build.construire(d, tmp_path / "site", aujourdhui=dt.date(2026, 11, 21), quand="x")
    fiche = (sortie / "a" / "casque.html").read_text(encoding="utf-8")
    assert "Lequel veux-tu suivre" in fiche and "https://img.test/a.jpg" in fiche
    liens = [html.unescape(u) for u in re.findall(r'class="c-choisir" href="([^"]+)"', fiche)]
    assert len(liens) == 2
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(liens[1]).query)
    assert q["labels"] == ["choix"] and "Article : casque" in q["body"][0] and "Choix : 2" in q["body"][0]
    index = (sortie / "index.html").read_text(encoding="utf-8")
    assert "À CHOISIR" in index and "2 propositions" in index


def test_choix_applique_sans_ia(tmp_path):
    d = _depot(tmp_path)
    art, n = ajout.lire_choix("Choix : Casque B", "Article : casque\nChoix : 2\n", d.articles())
    art = ajout.appliquer_choix(d, art, n)
    assert art["statut"] == "suivi" and art["nom"] == "Casque B" and art["liens"][0]["url"] == "https://b.test/p"
    assert "candidats" not in d.article("casque")


def test_choix_invalide(tmp_path):
    d = _depot(tmp_path)
    import pytest
    with pytest.raises(ValueError):
        ajout.lire_choix("", "Article : casque\nChoix : 7\n", d.articles())
