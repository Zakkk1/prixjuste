"""PrixJuste - suivi de prix pense pour l'acheteur.

Commandes :
  python prixjuste.py collecter        releve les prix actuels de la wishlist
  python prixjuste.py historique       recupere l'historique depuis la Wayback Machine
  python prixjuste.py prix ID PRIX [--barre 500] [--marchand X] [--date AAAA-MM-JJ] [--rupture]
                                       ajoute un prix vu a la main (site bloque, magasin...)
  python prixjuste.py rapport          genere rapport.html
  python prixjuste.py tout             collecter + rapport (a lancer chaque jour)
"""
import argparse
import datetime as dt
import json
import sqlite3
import sys
import time
from pathlib import Path

import analyse
import collecte
import rapport

ICI = Path(__file__).resolve().parent
DB = ICI / "prixjuste.db"
WISHLIST = ICI / "wishlist.json"


def connexion():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.executescript("""
    CREATE TABLE IF NOT EXISTS releves(
        id INTEGER PRIMARY KEY, article TEXT, url TEXT, marchand TEXT, exact INTEGER,
        source TEXT, ts TEXT, prix REAL, devise TEXT, en_stock INTEGER,
        n_offres INTEGER, n_dispo INTEGER, prix_barre REAL, note TEXT);
    CREATE UNIQUE INDEX IF NOT EXISTS releve_unique ON releves(article, url, source, ts);
    CREATE TABLE IF NOT EXISTS journal(ts TEXT, article TEXT, url TEXT, action TEXT, statut TEXT, detail TEXT);
    CREATE TABLE IF NOT EXISTS wayback_vu(url TEXT, ts TEXT, PRIMARY KEY(url, ts));
    """)
    return db


def charger_wishlist():
    return json.loads(WISHLIST.read_text(encoding="utf-8"))["articles"]


def maintenant():
    return dt.datetime.now().replace(microsecond=0).isoformat()


def noter(db, article, url, action, statut, detail=""):
    db.execute("INSERT INTO journal VALUES(?,?,?,?,?,?)", (maintenant(), article, url, action, statut, detail))
    db.commit()


def enregistrer(db, art, lien, source, ts, r, prix_barre=None, note=None):
    db.execute("""INSERT OR IGNORE INTO releves(article,url,marchand,exact,source,ts,prix,devise,en_stock,
                  n_offres,n_dispo,prix_barre,note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
               (art["id"], collecte.cle(lien), lien.get("marchand", "?"), 1 if lien.get("exact", True) else 0,
                source, ts, r["prix"], r.get("devise", "EUR"), r.get("en_stock"), r.get("n_offres"),
                r.get("n_dispo"), prix_barre, note))
    db.commit()


# ---------------------------------------------------------------- commandes

def cmd_collecter(db, article=None):
    for art in charger_wishlist():
        if article and art["id"] != article:
            continue
        for lien in art.get("liens", []):
            url, k = lien["url"], collecte.cle(lien)
            try:
                r = collecte.releve_direct(url, lien.get("filtre"), lien.get("taille"))
            except collecte.Bloque as e:
                noter(db, art["id"], k, "direct", "bloqué", str(e))
                print(f"  [bloqué] {lien.get('marchand')}: {e}")
                continue
            except Exception as e:
                noter(db, art["id"], k, "direct", "erreur", repr(e)[:200])
                print(f"  [erreur] {lien.get('marchand')}: {e!r}")
                continue
            if r:
                enregistrer(db, art, lien, "direct", maintenant(), r)
                noter(db, art["id"], k, "direct", "ok", f"{r['prix']:.2f} €")
                print(f"  [ok] {lien.get('marchand')}: {r['prix']:.2f} € ({r.get('n_dispo')} dispo)")
            else:
                noter(db, art["id"], k, "direct", "vide", "aucun prix lisible sur la page")
                print(f"  [vide] {lien.get('marchand')}: aucun prix lisible")
            time.sleep(2)


def cmd_historique(db, max_captures=40, article=None):
    for art in charger_wishlist():
        if article and art["id"] != article:
            continue
        for lien in art.get("liens", []) + art.get("liens_historiques", []):
            url, k = lien["url"], collecte.cle(lien)
            print(f"- {art['id']} / {lien.get('marchand')} ({lien.get('coloris', '')})")
            try:
                caps = collecte.captures_wayback(url, max_captures)
            except collecte.Bloque as e:
                noter(db, art["id"], k, "wayback", "erreur", str(e))
                print(f"  [erreur] {e}")
                continue
            nouvelles = [c for c in caps if not db.execute(
                "SELECT 1 FROM wayback_vu WHERE url=? AND ts=?", (k, c[0])).fetchone()]
            print(f"  {len(caps)} capture(s), {len(nouvelles)} nouvelle(s)")
            n_ok = 0
            for ts, original in nouvelles:
                try:
                    r = collecte.releve_wayback(ts, original, lien.get("filtre"), lien.get("taille"))
                except Exception as e:
                    print(f"    {ts[:8]} illisible ({e!r:.60})")
                    time.sleep(3)
                    continue
                db.execute("INSERT OR IGNORE INTO wayback_vu VALUES(?,?)", (k, ts))
                if r:
                    iso = dt.datetime.strptime(ts, "%Y%m%d%H%M%S").isoformat()
                    enregistrer(db, art, lien, "archive", iso, r)
                    n_ok += 1
                    print(f"    {ts[:4]}-{ts[4:6]}-{ts[6:8]}  {r['prix']:.2f} €  dispo={r.get('n_dispo')}")
                db.commit()
                time.sleep(1.5)
            noter(db, art["id"], k, "wayback", "ok", f"{n_ok} prix récupérés")


def cmd_prix(db, a):
    arts = {x["id"]: x for x in charger_wishlist()}
    if a.id not in arts:
        sys.exit(f"Article inconnu : {a.id}. Articles : {', '.join(arts)}")
    ts = (a.date + "T12:00:00") if a.date else maintenant()
    lien = {"url": "", "marchand": a.marchand or "saisie manuelle", "exact": True}
    r = {"prix": a.prix, "en_stock": 0 if a.rupture else 1}
    enregistrer(db, arts[a.id], lien, "manuel", ts, r, prix_barre=a.barre)
    print(f"Ajouté : {a.id} à {a.prix:.2f} € ({lien['marchand']})")


def cmd_rapport(db):
    analyses = []
    for art in charger_wishlist():
        rows = [dict(r) for r in db.execute("SELECT * FROM releves WHERE article=? ORDER BY ts", (art["id"],))]
        if not art.get("autres_coloris_ok", True):
            rows = [r for r in rows if r["exact"]]
        journal = [dict(r) for r in db.execute(
            "SELECT * FROM journal WHERE article=? ORDER BY ts DESC LIMIT 400", (art["id"],))]
        analyses.append((art, rows, analyse.analyser(art, rows), journal))
    sortie = ICI / "rapport.html"
    sortie.write_text(rapport.generer(analyses), encoding="utf-8")
    print(f"Rapport : {sortie}")


def main():
    p = argparse.ArgumentParser(description="PrixJuste")
    sp = p.add_subparsers(dest="cmd", required=True)
    co = sp.add_parser("collecter")
    co.add_argument("--article")
    h = sp.add_parser("historique")
    h.add_argument("--max", type=int, default=40)
    h.add_argument("--article")
    pr = sp.add_parser("prix")
    pr.add_argument("id")
    pr.add_argument("prix", type=float)
    pr.add_argument("--barre", type=float)
    pr.add_argument("--marchand")
    pr.add_argument("--date")
    pr.add_argument("--rupture", action="store_true")
    sp.add_parser("rapport")
    sp.add_parser("tout")
    a = p.parse_args()
    db = connexion()
    if a.cmd == "collecter":
        cmd_collecter(db, a.article)
    elif a.cmd == "historique":
        cmd_historique(db, a.max, a.article)
    elif a.cmd == "prix":
        cmd_prix(db, a)
    elif a.cmd == "rapport":
        cmd_rapport(db)
    elif a.cmd == "tout":
        cmd_collecter(db)
        cmd_rapport(db)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
