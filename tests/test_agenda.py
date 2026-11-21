import datetime as dt

from prixjuste import agenda, analyse
from tests.test_analyse import ART, AUJ, annee, o


def test_dates_legales_des_soldes():
    assert agenda.soldes_hiver(2025) == dt.date(2025, 1, 8)
    assert agenda.soldes_hiver(2026) == dt.date(2026, 1, 7)
    assert agenda.soldes_hiver(2027) == dt.date(2027, 1, 6)   # 2e mercredi le 13 > 12 : avancé
    assert agenda.soldes_ete(2025) == dt.date(2025, 6, 25)
    assert agenda.soldes_ete(2026) == dt.date(2026, 6, 24)
    assert agenda.soldes_ete(2022) == dt.date(2022, 6, 22)    # dernier mercredi le 29 > 28 : avancé
    assert agenda.black_friday(2026) == dt.date(2026, 11, 27)
    assert agenda.black_friday(2025) == dt.date(2025, 11, 28)


def test_ics_valide():
    prix = {1: 150, 2: 165}
    art = {**ART, "id": "x", "nom": "Parka; test, longue " + "x" * 80}
    res = analyse.analyser(art, annee(lambda m: prix.get(m, 220)) + [o(AUJ, 220)], AUJ)
    txt = agenda.ics([(art, res)], AUJ, "https://ex.io/pj")
    assert txt.startswith("BEGIN:VCALENDAR\r\n") and txt.endswith("END:VCALENDAR\r\n")
    assert "DTSTART;VALUE=DATE:20270101" in txt and "DTEND;VALUE=DATE:20270201" in txt  # janvier entier
    assert "Parka\; test\\, longue" in txt
    assert all(len(l.encode()) <= 75 for l in txt.split("\r\n"))
    assert "Soldes d'hiver" in txt and "Black Friday" in txt
    assert agenda.prochain([(art, res)], AUJ) == (dt.date(2026, 11, 27), "Black Friday (jusqu'au Cyber Monday)")
