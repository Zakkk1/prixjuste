import urllib.error

import pytest

from prixjuste import collecte


@pytest.fixture(autouse=True)
def sans_reseau(monkeypatch):
    collecte._robots_cache.clear()
    monkeypatch.setattr(collecte.time, "sleep", lambda s: None)


def fausse_toile(monkeypatch, pages):
    appels = []

    def telecharger(url):
        appels.append(url)
        rep = pages.get(url)
        if isinstance(rep, Exception):
            raise rep
        if rep is None:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        return rep

    monkeypatch.setattr(collecte, "telecharger", telecharger)
    return appels


ART = {"id": "x", "nom": "X", "liens": [{"marchand": "A", "url": "https://a.fr/p"}]}


def test_user_agent_explicite():
    assert collecte.USER_AGENT.startswith("PrixJuste/")
    assert "outil personnel" in collecte.USER_AGENT and "Mozilla" not in collecte.USER_AGENT


def test_robots_interdit_on_ne_lit_pas_la_page(monkeypatch, depot, page):
    appels = fausse_toile(monkeypatch, {"https://a.fr/robots.txt": "User-agent: *\nDisallow: /p",
                                        "https://a.fr/p": page("produit_simple.html")})
    collecte.collecter_article(depot, ART, log=lambda *a: None)
    assert "https://a.fr/p" not in appels
    assert depot.journal("x")[-1]["statut"] == "bloqué"
    assert depot.releves("x") == []


def test_site_qui_refuse_les_robots(monkeypatch, depot):
    fausse_toile(monkeypatch, {"https://a.fr/robots.txt": "", "https://a.fr/p": collecte.Bloque("HTTP 403")})
    collecte.collecter_article(depot, ART, log=lambda *a: None)
    assert depot.journal("x")[-1]["statut"] == "bloqué"


def test_releve_ok_puis_une_seule_visite_par_jour(monkeypatch, depot, page):
    appels = fausse_toile(monkeypatch, {"https://a.fr/robots.txt": "User-agent: *\nAllow: /",
                                        "https://a.fr/p": page("produit_simple.html")})
    assert collecte.collecter_article(depot, ART, log=lambda *a: None) == 1
    assert collecte.collecter_article(depot, ART, log=lambda *a: None) == 0
    assert appels.count("https://a.fr/p") == 1
    r = depot.releves("x")[0]
    assert r["prix"] == 373.9 and r["source"] == "direct" and r["en_stock"] == 1


def test_historique_wayback(monkeypatch, depot, page):
    cdx = '[["timestamp","original"],["20260105101010","https://a.fr/p"],["20260210101010","https://a.fr/p"]]'

    def telecharger(url):
        if "cdx/search" in url:
            return cdx
        if "20260105101010id_" in url:
            return page("produit_simple.html")
        return page("captcha.html")

    monkeypatch.setattr(collecte, "telecharger", telecharger)
    assert collecte.historique_article(depot, ART, log=lambda *a: None) == 1
    assert depot.releves("x")[0]["ts"] == "2026-01-05T10:10:10"
    assert depot.releves("x")[0]["source"] == "archive"
    # une capture illisible n'est pas marquée « vue » : elle sera retentée ; la bonne ne l'est plus
    assert collecte.historique_article(depot, ART, log=lambda *a: None) == 0
    assert ("https://a.fr/p", "20260105101010") in depot.captures_vues("x")


def test_prix_manuel(depot):
    collecte.prix_manuel(depot, ART, 199.0, "Magasin", barre=230, date="2026-11-20")
    r = depot.releves("x")[0]
    assert r == {"ts": "2026-11-20T12:00:00", "lien": "manuel", "marchand": "Magasin", "exact": True,
                 "source": "manuel", "prix": 199.0, "devise": "EUR", "en_stock": 1, "prix_barre": 230}
