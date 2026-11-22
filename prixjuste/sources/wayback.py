"""Archives publiques de la Wayback Machine (web.archive.org).

Sert à reconstituer l'historique d'une page, et de repli quand un site refuse les robots :
on lit la copie archivée publiquement, jamais le site lui-même.
"""
import json
import time
import urllib.error
import urllib.parse

CDX = "https://web.archive.org/cdx/search/cdx"


def captures(telecharger, url, max_captures=40):
    """Liste des captures (timestamp, url d'origine), une par jour max, réparties dans le temps.
    Lève RuntimeError si l'archive ne répond pas."""
    q = urllib.parse.urlencode({
        "url": url.split("#")[0],
        "output": "json",
        "filter": "statuscode:200",
        "collapse": "timestamp:8",
        "fl": "timestamp,original",
    })
    lignes = None
    for essai in range(3):
        try:
            txt = telecharger(f"{CDX}?{q}")
            lignes = json.loads(txt) if txt.strip() else []
            break
        except (json.JSONDecodeError, urllib.error.URLError, TimeoutError, OSError, Exception):
            time.sleep(5 * (essai + 1))
    if lignes is None:
        raise RuntimeError("Wayback Machine indisponible pour le moment")
    caps = [tuple(l) for l in lignes[1:]]
    return echantillonner(caps, max_captures)


def echantillonner(caps, max_captures):
    """Garde au plus `max_captures` captures régulièrement espacées, toujours la plus récente."""
    if len(caps) <= max_captures:
        return caps
    pas = len(caps) / max_captures
    return [caps[int(i * pas)] for i in range(max_captures - 1)] + [caps[-1]]


def url_capture(ts, original):
    """`id_` : la page archivée brute, sans la barre d'outils de l'archive."""
    return f"https://web.archive.org/web/{ts}id_/{original}"


def pages_archivees(telecharger, prefixe, contient=None, limite=60):
    """URLs distinctes archivées sous un préfixe (ex. « www.idealo.fr/prixcomparaison/OffersOfProduct/ »),
    filtrées sur un mot ; sert à retrouver la page d'un produit sans interroger le site lui-même."""
    params = {"url": prefixe.rstrip("*"), "matchType": "prefix", "output": "json", "fl": "original,timestamp",
              "filter": ["statuscode:200"], "collapse": "urlkey", "limit": str(limite * 20)}
    if contient:
        params["filter"].append(f"original:(?i).*{contient}.*")
    q = urllib.parse.urlencode(params, doseq=True)
    lignes = json.loads(telecharger(f"{CDX}?{q}") or "[]")
    return [tuple(l) for l in lignes[1:]][:limite]


def resume_captures(telecharger, url, jours=730):
    """(nombre de captures sur la période, première date, dernière date, timestamps) d'une page."""
    q = urllib.parse.urlencode({"url": url.split("#")[0], "output": "json", "filter": "statuscode:200",
                                "collapse": "timestamp:8", "fl": "timestamp"})
    lignes = json.loads(telecharger(f"{CDX}?{q}") or "[]")
    ts = [l[0] for l in lignes[1:]]
    import datetime as dt
    limite = (dt.date.today() - dt.timedelta(days=jours)).strftime("%Y%m%d")
    ts = [t for t in ts if t[:8] >= limite]
    return len(ts), (ts[0][:8] if ts else None), (ts[-1][:8] if ts else None), ts
