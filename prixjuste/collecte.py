"""Collecte des prix : pages marchands (en direct) et archives Wayback Machine.

Règles de conduite (non négociables) :
- l'outil s'annonce honnêtement comme un robot (User-Agent explicite) ;
- il respecte robots.txt ;
- un relevé direct par jour maximum et par page ;
- si un site bloque (401, 403, 429, captcha...), on n'essaie PAS de contourner :
  on note « bloqué » et on se rabat sur les archives ou la saisie manuelle.
"""
import datetime as dt
import gzip
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import zlib

from . import VERSION
from .donnees import maintenant
from .sources import jsonld, wayback

try:  # certificats du système : évite les erreurs SSL sur certains postes
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

USER_AGENT = f"PrixJuste/{VERSION} (outil personnel de suivi de prix; 1 visite/jour max)"
TIMEOUT = 40
PAUSE = 2  # secondes entre deux pages

_robots_cache = {}

# réexports pratiques
extraire_offres = jsonld.extraire_offres


class Bloque(Exception):
    """Le site refuse l'accès (ou robots.txt l'interdit). On ne contourne pas."""


def cle(lien):
    """Identifiant d'un lien suivi : l'URL, plus la taille si on suit une taille précise."""
    t = lien.get("taille")
    return lien.get("url", "") + (f"#taille={t}" if t else "")


def _decode(raw, headers):
    enc = (headers.get("Content-Encoding") or "").lower()
    if enc == "gzip" or raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    elif enc == "deflate":
        raw = zlib.decompress(raw)
    charset = None
    m = re.search(r"charset=([\w-]+)", headers.get("Content-Type") or "")
    if m:
        charset = m.group(1)
    if not charset:
        m = re.search(rb'<meta[^>]+charset=["\']?([\w-]+)', raw[:3000], re.I)
        if m:
            charset = m.group(1).decode("ascii", "ignore")
    for cs in (charset, "utf-8", "latin-1"):
        if not cs:
            continue
        try:
            return raw.decode(cs)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", "replace")


def telecharger(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "fr-FR,fr;q=0.9",
        "Accept-Encoding": "gzip, deflate",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return _decode(r.read(), r.headers)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 429, 503):
            raise Bloque(f"le site refuse l'accès aux robots (HTTP {e.code})")
        raise


def robots_autorise(url):
    p = urllib.parse.urlsplit(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        try:
            rp.parse(telecharger(base + "/robots.txt").splitlines())
        except Bloque:
            rp = "bloque"
        except Exception:
            rp = None  # pas de robots.txt lisible : autorisé par convention
        _robots_cache[base] = rp
    rp = _robots_cache[base]
    if rp == "bloque":
        return False
    return True if rp is None else rp.can_fetch(USER_AGENT, url)


# ---------------------------------------------------------------- résumé d'une page

def resumer(offres, filtre=None, taille=None):
    """Agrège les offres d'une page (une par taille en général) en un relevé.

    `taille` : ne garder que cette pointure/taille exacte (si la page détaille les tailles).
    `filtre` : texte à trouver dans la référence ou le nom de l'offre ; préfixe `re:` pour une
    expression régulière (ex. `re:US 7$` garde US 7 mais pas US 7,5).
    """
    taille_inconnue = False
    if taille:
        t = jsonld.normaliser_taille(taille)
        if any(o.get("taille") for o in offres):
            offres = [o for o in offres if jsonld.normaliser_taille(o.get("taille")) == t]
        else:  # la page ne détaille pas les tailles : prix gardé, stock de la taille inconnu
            taille_inconnue = True
    if filtre:
        if filtre.startswith("re:"):
            motif = re.compile(filtre[3:], re.I)
            offres = [o for o in offres if motif.search(o["sku"] + " " + o["nom"])]
        else:
            f = filtre.lower()
            offres = [o for o in offres if f in (o["sku"] + " " + o["nom"]).lower()]
    if not offres:
        return None
    dispo = [o for o in offres if o["en_stock"]]
    stock_connu = any(o["en_stock"] is not None for o in offres) and not taille_inconnue
    base = dispo if dispo else offres
    return {
        "prix": min(o["prix"] for o in base),
        "devise": base[0]["devise"],
        "en_stock": (1 if dispo else 0) if stock_connu else None,
        "n_offres": len(offres),
        "n_dispo": len(dispo) if stock_connu else None,
    }


CAPTCHA_RE = re.compile(r"captcha|cf-chl|challenge-platform|Access Denied|px-captcha|datadome", re.I)


def lire_page(html, filtre=None, taille=None):
    _, offres = extraire_offres(html)
    if not offres:
        if CAPTCHA_RE.search(html):
            raise Bloque("page anti-robot (captcha)")
        return None
    return resumer(offres, filtre, taille)


def releve_direct(url, filtre=None, taille=None):
    if not robots_autorise(url):
        raise Bloque("robots.txt interdit cette page (ou le site bloque les robots)")
    return lire_page(telecharger(url), filtre, taille)


# ---------------------------------------------------------------- orchestration

def _ligne(art, lien, source, ts, r, prix_barre=None, note=None):
    return {"ts": ts, "lien": cle(lien), "marchand": lien.get("marchand", "?"),
            "exact": bool(lien.get("exact", True)), "source": source, "prix": r["prix"],
            "devise": r.get("devise", "EUR"), "en_stock": r.get("en_stock"), "n_offres": r.get("n_offres"),
            "n_dispo": r.get("n_dispo"), "prix_barre": prix_barre, "note": note}


def deja_lu_aujourdhui(depot, ident, k, jour):
    return any(j["lien"] == k and j["action"] == "direct" and j["ts"][:10] == jour for j in depot.journal(ident))


def collecter_article(depot, art, log=print, pause=PAUSE):
    """Relevé direct de chaque lien suivi (une fois par jour max). Renvoie le nombre de prix lus."""
    n, jour = 0, maintenant()[:10]
    for lien in art.get("liens", []):
        url, k = lien["url"], cle(lien)
        if deja_lu_aujourdhui(depot, art["id"], k, jour):
            log(f"  [déjà lu aujourd'hui] {lien.get('marchand')}")
            continue
        try:
            r = releve_direct(url, lien.get("filtre"), lien.get("taille"))
        except Bloque as e:
            depot.noter(art["id"], k, "direct", "bloqué", str(e))
            log(f"  [bloqué] {lien.get('marchand')} : {e}")
            continue
        except Exception as e:
            depot.noter(art["id"], k, "direct", "erreur", repr(e)[:200])
            log(f"  [erreur] {lien.get('marchand')} : {e!r:.120}")
            continue
        finally:
            time.sleep(pause)
        if r:
            depot.ajouter_releve(art["id"], _ligne(art, lien, "direct", maintenant(), r))
            depot.noter(art["id"], k, "direct", "ok", f"{r['prix']:.2f} €")
            log(f"  [ok] {lien.get('marchand')} : {r['prix']:.2f} € ({r.get('n_dispo')} dispo)")
            n += 1
        else:
            depot.noter(art["id"], k, "direct", "vide", "aucun prix lisible sur la page")
            log(f"  [vide] {lien.get('marchand')} : aucun prix lisible")
    return n


def historique_article(depot, art, max_captures=40, log=print, pause=1.5, fin=None):
    """Import des captures Wayback non encore lues, pour tous les liens (suivis et historiques).
    `fin` : heure (time.time()) à ne pas dépasser ; le reste sera lu à la prochaine passe."""
    total = 0
    vues = depot.captures_vues(art["id"])
    for lien in art.get("liens", []) + art.get("liens_historiques", []):
        if fin and time.time() > fin:
            log("  [archives] temps écoulé : la suite à la prochaine passe")
            break
        k = cle(lien)
        try:
            caps = wayback.captures(telecharger, lien["url"], max_captures)
        except Exception as e:
            depot.noter(art["id"], k, "wayback", "erreur", str(e)[:200])
            log(f"  [archives indisponibles] {lien.get('marchand')} : {e}")
            continue
        nouvelles = [c for c in caps if (k, c[0]) not in vues]
        n_ok = 0
        for ts, original in nouvelles:
            if fin and time.time() > fin:
                break
            try:
                r = lire_page(telecharger(wayback.url_capture(ts, original)), lien.get("filtre"), lien.get("taille"))
            except Exception as e:
                log(f"    {ts[:8]} illisible ({e!r:.60})")
                time.sleep(pause * 2)
                continue
            depot.marquer_capture(art["id"], k, ts)
            if r:
                iso = dt.datetime.strptime(ts, "%Y%m%d%H%M%S").isoformat()
                if depot.ajouter_releve(art["id"], _ligne(art, lien, "archive", iso, r)):
                    n_ok += 1
            time.sleep(pause)
        depot.noter(art["id"], k, "wayback", "ok", f"{n_ok} prix récupérés sur {len(nouvelles)} capture(s) nouvelle(s)")
        log(f"  [archives] {lien.get('marchand')} : {len(caps)} capture(s), {n_ok} prix nouveaux")
        total += n_ok
    return total


def prix_manuel(depot, art, prix, marchand=None, barre=None, date=None, rupture=False, note=None):
    ts = (date + "T12:00:00") if date else maintenant()
    lien = {"url": "", "marchand": marchand or "saisie manuelle", "exact": True}
    r = {"prix": prix, "en_stock": 0 if rupture else 1}
    ligne = _ligne(art, lien, "manuel", ts, r, prix_barre=barre, note=note)
    ligne["lien"] = "manuel"
    return depot.ajouter_releve(art["id"], ligne)
