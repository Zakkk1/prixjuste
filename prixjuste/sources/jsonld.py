"""Lecture générique des offres publiées en JSON-LD schema.org (Product / Offer / AggregateOffer).

Couvre aussi les variantes (`hasVariant` / ProductGroup) qui portent une taille (`size`),
et, en dernier recours, les balises meta `product:price:amount`.
"""
import json
import re

LD_RE = re.compile(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', re.S | re.I)
META_PRICE_RE = re.compile(
    r'<meta[^>]+(?:property|itemprop|name)=["\'](?:product:price:amount|og:price:amount|price)["\'][^>]*'
    r'content=["\']([\d.,\s]+)["\']', re.I)
EN_STOCK = ("InStock", "LimitedAvailability", "OnlineOnly", "PreOrder", "InStoreOnly")


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
    return any(nom in str(x) for x in _liste(node.get("@type")))


def prix_nombre(v):
    """'1 299,90' / '1299.90' / 1299.9 -> 1299.9 ; None si illisible."""
    if v is None:
        return None
    s = re.sub(r"[\s  €]", "", str(v))
    if "," in s and "." in s:  # 1.299,90 (style européen) ou 1,299.90
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def normaliser_taille(t):
    return str(t or "").strip().replace(",", ".").lower()


def _charger(bloc):
    bloc = bloc.strip()
    try:
        return json.loads(bloc, strict=False)
    except json.JSONDecodeError:
        try:  # certains sites laissent des retours à la ligne bruts dans les chaînes
            return json.loads(bloc.replace("\n", " "), strict=False)
        except json.JSONDecodeError:
            return None


def livraison(offre, pays="FR"):
    """Frais de livraison publiés (OfferShippingDetails) : vers la France si précisé, sinon le moins cher."""
    tarifs = []
    for d in _liste(offre.get("shippingDetails")):
        if not isinstance(d, dict):
            continue
        rate = d.get("shippingRate")
        rate = rate[0] if isinstance(rate, list) and rate else rate
        v = prix_nombre(rate.get("value") if isinstance(rate, dict) else None)
        if v is None:
            continue
        dest = [x.get("addressCountry") for x in _liste(d.get("shippingDestination")) if isinstance(x, dict)]
        dest = [c for x in dest for c in _liste(x)]
        tarifs.append((0 if pays in dest else 1, v))
    return min(tarifs)[1] if tarifs else None


def extraire_offres(html):
    """Renvoie (nom_produit, [{prix, devise, en_stock, sku, nom, taille}, ...])."""
    offres, nom_produit = [], None
    for bloc in LD_RE.findall(html):
        data = _charger(bloc)
        if data is None:
            continue
        for node in _parcourir(data):
            if not (_est_type(node, "Product") or _est_type(node, "ProductGroup")):
                continue
            nom_produit = nom_produit or node.get("name")
            taille = str(node.get("size") or "").strip()
            sku_produit = str(node.get("sku") or "")
            for o in _liste(node.get("offers")):
                if not isinstance(o, dict):
                    continue
                agg = _est_type(o, "AggregateOffer")
                sous = _liste(o.get("offers")) if agg else [o]
                if agg and not o.get("offers"):
                    sous = [{"price": o.get("lowPrice") or o.get("price"),
                             "priceCurrency": o.get("priceCurrency"), "availability": o.get("availability")}]
                for s in sous:
                    if not isinstance(s, dict):
                        continue
                    prix = prix_nombre(s.get("price"))
                    if prix is None:
                        spec = s.get("priceSpecification")
                        for sp in _liste(spec):
                            if isinstance(sp, dict) and prix_nombre(sp.get("price")):
                                prix = prix_nombre(sp.get("price"))
                                break
                    if prix is None or prix <= 0:
                        continue
                    dispo = str(s.get("availability") or "")
                    en_stock = any(k in dispo for k in EN_STOCK) if dispo else None
                    offres.append({
                        "prix": prix,
                        "devise": s.get("priceCurrency") or "EUR",
                        "en_stock": en_stock,
                        "sku": str(s.get("sku") or sku_produit),
                        "nom": str(s.get("name") or ""),
                        "taille": normaliser_taille(s.get("size") or taille),
                        "livraison": livraison(s) if livraison(s) is not None else livraison(o),
                    })
    if not offres:
        m = META_PRICE_RE.search(html)
        if m and prix_nombre(m.group(1)):
            offres.append({"prix": prix_nombre(m.group(1)), "devise": "EUR", "en_stock": None,
                           "sku": "", "nom": "", "taille": "", "livraison": None})
    return nom_produit, _dedoublonner(offres)


OG_IMAGE_RE = re.compile(r'<meta[^>]+property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', re.I)


def image_produit(html):
    """Photo du produit telle que la page la publie (JSON-LD `image`, sinon og:image). None si absente."""
    def url_de(v):
        for x in _liste(v):
            if isinstance(x, dict):
                x = x.get("url") or x.get("contentUrl")
            if isinstance(x, str) and x.startswith(("https://", "//")):
                return "https:" + x if x.startswith("//") else x
        return None
    for bloc in LD_RE.findall(html):
        data = _charger(bloc)
        if data is None:
            continue
        for node in _parcourir(data):
            if _est_type(node, "Product") or _est_type(node, "ProductGroup"):
                u = url_de(node.get("image"))
                if u:
                    return u
    m = OG_IMAGE_RE.search(html)
    return url_de(m.group(1)) if m else None


def _dedoublonner(offres):
    """Un même Product est souvent décrit deux fois (bloc principal + variantes) : on garde chaque offre une fois."""
    vues, res = set(), []
    for o in offres:
        k = (o["prix"], o["sku"], o["nom"], o["taille"], o["en_stock"])
        if k not in vues:
            vues.add(k)
            res.append(o)
    return res
