"""Collecte des prix : pages marchands (en direct) et archives Wayback Machine.

Regles de conduite (non negociables) :
- l'outil s'annonce honnetement comme un robot (User-Agent explicite) ;
- il respecte robots.txt ;
- si un site bloque (403, 429, captcha...), on n'essaie PAS de contourner :
  on note "bloque" et on se rabat sur les archives ou la saisie manuelle.
"""
import gzip
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import zlib

try:  # certificats du systeme (Windows) : evite les erreurs SSL sur certains sites mal configures
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

USER_AGENT = "PrixJuste/0.1 (outil personnel de suivi de prix; 1 visite/jour max)"
TIMEOUT = 40

_robots_cache = {}

LD_RE = re.compile(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', re.S | re.I)
META_PRICE_RE = re.compile(
    r'<meta[^>]+(?:property|itemprop|name)=["\'](?:product:price:amount|og:price:amount|price)["\'][^>]*content=["\']([\d.,]+)["\']',
    re.I)


def cle(lien):
    """Identifiant d'un lien suivi : l'URL, plus la taille si on suit une taille precise."""
    t = lien.get("taille")
    return lien.get("url", "") + (f"#taille={t}" if t else "")


class Bloque(Exception):
    """Le site refuse l'acces (ou robots.txt l'interdit). On ne contourne pas."""


def _decode(raw, headers):
    enc = (headers.get("Content-Encoding") or "").lower()
    if enc == "gzip" or raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    elif enc == "deflate":
        raw = zlib.decompress(raw)
    charset = None
    ctype = headers.get("Content-Type") or ""
    m = re.search(r"charset=([\w-]+)", ctype)
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
            raise Bloque(f"le site refuse l'acces aux robots (HTTP {e.code})")
        raise


def robots_autorise(url):
    p = urllib.parse.urlsplit(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        try:
            txt = telecharger(base + "/robots.txt")
            rp.parse(txt.splitlines())
        except Bloque:
            rp = "bloque"
        except Exception:
            rp = None  # pas de robots.txt lisible : on considere autorise
        _robots_cache[base] = rp
    rp = _robots_cache[base]
    if rp == "bloque":
        return False
    return True if rp is None else rp.can_fetch(USER_AGENT, url)


# ---------------------------------------------------------------- extraction

def _liste(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _parcourir(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _parcourir(v)
    elif isinstance(node, list):
        for v in node:
            yield from _parcourir(v)


def _est_type(node, nom):
    t = node.get("@type")
    return any(nom in str(x) for x in _liste(t))


def _prix(v):
    if v is None:
        return None
    try:
        return float(str(v).replace(" ", "").replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def extraire_offres(html):
    """Renvoie (nom_produit, [ {prix, devise, en_stock, sku, nom} ... ])."""
    offres, nom_produit = [], None
    for bloc in LD_RE.findall(html):
        bloc = bloc.strip().replace("\n", " ")
        try:
            data = json.loads(bloc, strict=False)
        except json.JSONDecodeError:
            continue
        for node in _parcourir(data):
            if not _est_type(node, "Product"):
                continue
            nom_produit = nom_produit or node.get("name")
            taille = str(node.get("size") or "").strip()
            sku_produit = str(node.get("sku") or "")
            for o in _liste(node.get("offers")):
                if not isinstance(o, dict):
                    continue
                sous = _liste(o.get("offers")) if _est_type(o, "AggregateOffer") else [o]
                if _est_type(o, "AggregateOffer") and not o.get("offers"):
                    sous = [{"price": o.get("lowPrice"), "priceCurrency": o.get("priceCurrency"),
                             "availability": o.get("availability")}]
                for s in sous:
                    if not isinstance(s, dict):
                        continue
                    prix = _prix(s.get("price"))
                    if prix is None and isinstance(s.get("priceSpecification"), dict):
                        prix = _prix(s["priceSpecification"].get("price"))
                    if prix is None or prix <= 0:
                        continue
                    dispo = str(s.get("availability") or "")
                    en_stock = None
                    if dispo:
                        en_stock = any(k in dispo for k in ("InStock", "LimitedAvailability", "OnlineOnly", "PreOrder"))
                    offres.append({
                        "prix": prix,
                        "devise": s.get("priceCurrency") or "EUR",
                        "en_stock": en_stock,
                        "sku": str(s.get("sku") or sku_produit),
                        "nom": str(s.get("name") or ""),
                        "taille": str(s.get("size") or taille).replace(",", "."),
                    })
    if not offres:
        m = META_PRICE_RE.search(html)
        if m and _prix(m.group(1)):
            offres.append({"prix": _prix(m.group(1)), "devise": "EUR", "en_stock": None, "sku": "", "nom": ""})
    return nom_produit, offres


def resumer(offres, filtre=None, taille=None):
    """Agrege les offres d'une page (une par taille en general) en un releve.
    `taille` : ne garder que cette pointure/taille exacte (si la page la decrit)."""
    taille_inconnue = False
    if taille:
        t = str(taille).replace(",", ".").strip().lower()
        if any(o.get("taille") for o in offres):
            offres = [o for o in offres if o.get("taille", "").lower() == t]
        else:  # la page ne detaille pas les tailles : prix garde, stock de la taille inconnu
            taille_inconnue = True
    if filtre:
        if filtre.startswith("re:"):  # expression reguliere, ex. "re:US 7$" (US 7 mais pas US 7,5)
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


def releve_direct(url, filtre=None, taille=None):
    if not robots_autorise(url):
        raise Bloque("robots.txt interdit cette page (ou le site bloque les robots)")
    html = telecharger(url)
    _, offres = extraire_offres(html)
    if not offres:
        if re.search(r"captcha|cf-chl|challenge-platform|Access Denied", html, re.I):
            raise Bloque("page anti-robot (captcha)")
        return None
    return resumer(offres, filtre, taille)


# ---------------------------------------------------------------- wayback

CDX = "https://web.archive.org/cdx/search/cdx"


def captures_wayback(url, max_captures=40):
    """Liste des captures (timestamp, url) d'une page, une par jour max, reparties dans le temps."""
    q = urllib.parse.urlencode({
        "url": url.split("#")[0],
        "output": "json",
        "filter": "statuscode:200",
        "collapse": "timestamp:8",
        "fl": "timestamp,original",
    })
    for essai in range(3):
        try:
            txt = telecharger(f"{CDX}?{q}")
            lignes = json.loads(txt)
            break
        except (json.JSONDecodeError, Bloque, urllib.error.URLError, TimeoutError):
            time.sleep(5 * (essai + 1))
    else:
        raise Bloque("Wayback Machine indisponible pour le moment")
    caps = [tuple(l) for l in lignes[1:]]
    if len(caps) > max_captures:  # echantillonnage regulier, on garde toujours la plus recente
        pas = len(caps) / max_captures
        caps = [caps[int(i * pas)] for i in range(max_captures - 1)] + [caps[-1]]
    return caps


def releve_wayback(ts, original, filtre=None, taille=None):
    html = telecharger(f"https://web.archive.org/web/{ts}id_/{original}")
    _, offres = extraire_offres(html)
    return resumer(offres, filtre, taille) if offres else None
