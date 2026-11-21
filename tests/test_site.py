import datetime as dt
import json
import re

from prixjuste import build
from prixjuste.donnees import Depot
from tests.test_donnees import DATA


def test_site_complet(tmp_path):
    sortie = build.construire(Depot(DATA), tmp_path / "site", aujourdhui=dt.date(2026, 11, 21), quand="21/11/2026 à 06:00")
    noms = {p.relative_to(sortie).as_posix() for p in sortie.rglob("*") if p.is_file()}
    assert {"index.html", "ajouter.html", "style.css", "site.js", "data.json", "a/mcmurdo.html", "a/timberland.html"} <= noms
    index = (sortie / "index.html").read_text(encoding="utf-8")
    assert "Qu'est-ce que tu veux acheter" in index
    # tri : ATTENDS (McMurdo) passe avant « pas assez de données » (Timberland)
    assert index.lower().index("mcmurdo") < index.lower().index("timberland")
    fiche = (sortie / "a" / "mcmurdo.html").read_text(encoding="utf-8")
    assert 'class="tampon t-attends grand"' in fiche and "ATTENDS" in fiche  # tampon en texte réel
    assert "courbe-etroite" in fiche and "courbe-large" in fiche
    assert "Contrôle des promos" in fiche and "trompeuse" in fiche
    assert "archives seulement" in fiche and "bloqué" in fiche
    data = json.loads((sortie / "data.json").read_text(encoding="utf-8"))
    assert {a["id"] for a in data["articles"]} == {"mcmurdo", "timberland"}


def test_aucune_dependance_externe_hors_polices(tmp_path):
    sortie = build.construire(Depot(DATA), tmp_path / "site", aujourdhui=dt.date(2026, 11, 21))
    for p in sortie.rglob("*.html"):
        h = p.read_text(encoding="utf-8")
        for src in re.findall(r'<script[^>]*src="([^"]+)"', h):
            assert not src.startswith("http"), src
        for href in re.findall(r'<link[^>]*href="(https?://[^"]+)"', h):
            assert "fonts.g" in href, href


def test_article_en_attente(tmp_path):
    d = Depot(tmp_path / "data")
    d.ecrire_article({"id": "doudoune", "nom": "doudoune légère", "statut": "a_identifier", "issue": 7,
                      "demande": "doudoune légère", "liens": []})
    sortie = build.construire(d, tmp_path / "site", aujourdhui=dt.date(2026, 11, 21))
    assert "EN ATTENTE" in (sortie / "index.html").read_text(encoding="utf-8")
    assert "/issues/7" in (sortie / "a" / "doudoune.html").read_text(encoding="utf-8")
