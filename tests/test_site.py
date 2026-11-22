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
    # tri par urgence de la décision : l'ordre des articles suit ORDRE (indépendant des prix du jour)
    data = json.loads((sortie / "data.json").read_text(encoding="utf-8"))
    codes = {a["id"]: a["tampon"] for a in data["articles"]}
    pos = sorted(codes, key=lambda i: index.find(f'href="a/{i}.html"'))
    assert [build.ORDRE[codes[i]] for i in pos] == sorted(build.ORDRE[codes[i]] for i in pos)
    fiche = (sortie / "a" / "mcmurdo.html").read_text(encoding="utf-8")
    classe, mots = build.TAMPONS[codes["mcmurdo"]]
    assert f'class="tampon t-{classe} grand"' in fiche and mots[0] in fiche  # tampon en texte réel
    assert "courbe-etroite" in fiche and "courbe-large" in fiche
    assert "Contrôle des promos" in fiche and "trompeuse" in fiche
    assert "archives seulement" in fiche and "bloqué" in fiche
    data = json.loads((sortie / "data.json").read_text(encoding="utf-8"))
    assert {a["id"] for a in data["articles"]} >= {"mcmurdo", "timberland"}  # les vrais ajouts s'y ajoutent


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


def test_carte_9_16_sans_donnee_personnelle(tmp_path):
    import html as h
    sortie = build.construire(Depot(DATA), tmp_path / "site", aujourdhui=dt.date(2026, 11, 21))
    fiche = (sortie / "a" / "mcmurdo.html").read_text(encoding="utf-8")
    m = re.search(r'data-carte="([^"]+)"', fiche)
    d = json.loads(h.unescape(m.group(1)))
    assert d["tampon"] and d["prix"].endswith("€")
    assert set(d) >= {"nom", "serie", "fiabilite", "date"} and "issue" not in d


def test_origine_de_l_historique():
    obs = [{"ts": "2025-12-10T01:00:00", "source": "archive", "prix": 230},
           {"ts": "2026-11-19T10:00:00", "source": "direct", "prix": 220}]
    t = build.origine_historique(obs, dt.date(2026, 11, 22))
    assert t.startswith("Relevé chaque matin depuis le 19/11/2026") and "1 prix retrouvé" in t
