"""Enquête à la demande, faite par Claude dans TON Chrome (extension « Claude in Chrome »).

Le robot quotidien ne lit que les sites qui acceptent les robots, et n'a pas d'historique. Quand tu envisages
un achat, tu lances une enquête : Claude navigue pour toi, ponctuellement, comme tu le ferais (courbe
d'historique d'idealo / Le Dénicheur / Keepa, prix dans ta taille chez les boutiques, prix au Canada), puis
dépose le résultat dans une issue « enquete » au format ci-dessous, intégrée sans IA par ajout.yml :

    Article : timberland
    Historique : 2025-11-28 | 160 | idealo
    Prix : 190.79 | E.Leclerc | https://... | oui | 229.99
    Canada : 230 | JD Sports Canada | https://... | oui
    Note : une phrase

Les points d'historique rejoignent la courbe (source « historique »), les prix du jour aussi
(source « navigateur »), les prix canadiens vont au comparatif « Au Québec ».
"""
import re
import urllib.parse

from .ajout import _cle, _date_iso, _nombre
from .donnees import maintenant

SOURCES_HISTORIQUE = ("idealo", "le dénicheur", "ledenicheur", "keepa", "camelcamelcamel", "pricespy")


def _oui(v):
    return (v or "").strip().lower() in ("oui", "yes", "o", "en stock", "dispo", "disponible", "1", "true")


def lire(corps, articles):
    """Corps d'issue -> {article, historique:[(date, prix, source)], prix:[...], canada:[...], note} ou ValueError."""
    res = {"article": None, "historique": [], "prix": [], "canada": [], "note": None}
    for ligne in (corps or "").replace("\r", "").split("\n"):
        m = re.match(r"^\s*(?:[-*]\s*)?([A-Za-zÀ-ÿ ]{4,20}?)\s*[:：]\s*(.+)$", ligne)
        if not m:
            continue
        cle, val = _cle(m.group(1)), m.group(2).strip()
        champs = [c.strip() for c in val.split("|")]
        if cle == "article":
            res["article"] = val
        elif cle == "historique" and len(champs) >= 2:
            d, p = _date_iso(champs[0]), _nombre(champs[1])
            if d and p:
                res["historique"].append({"date": d, "prix": p, "source": champs[2] if len(champs) > 2 else "comparateur"})
        elif cle in ("prix", "canada") and len(champs) >= 2:
            p = _nombre(champs[0])
            if not p:
                continue
            url = next((c for c in champs if c.startswith("http")), "")
            autres = [c for c in champs[2:] if c and not c.startswith("http")]
            res[cle].append({"prix": p, "marchand": champs[1] or "?", "url": url,
                             "en_stock": (1 if _oui(autres[0]) else 0) if autres else None,
                             "barre": _nombre(autres[1]) if len(autres) > 1 else None})
        elif cle == "note":
            res["note"] = val[:300]
    ids = {a["id"] for a in articles}
    if res["article"] not in ids:
        raise ValueError(f"Article inconnu : « {res['article']} ». Articles : {', '.join(sorted(ids))}.")
    if not (res["historique"] or res["prix"] or res["canada"]):
        raise ValueError("Aucune ligne « Historique », « Prix » ou « Canada » lisible dans l'enquête.")
    return res


def enregistrer(depot, art, enq, ts=None):
    """Ajoute les relevés de l'enquête. Renvoie (n_historique, n_prix, n_canada) réellement ajoutés."""
    ts = ts or maintenant()
    n = [0, 0, 0]
    for h in enq["historique"]:
        src = h["source"]
        ligne = {"ts": h["date"] + "T12:00:00", "lien": f"historique:{_cle(src)}", "marchand": f"{src} (historique)",
                 "exact": True, "source": "historique", "prix": h["prix"], "devise": "EUR", "en_stock": None,
                 "note": "plus bas tous vendeurs lu sur la courbe du comparateur"}
        n[0] += depot.ajouter_releve(art["id"], ligne)
    for cle, i, extra in (("prix", 1, {}), ("canada", 2, {"pays": "CA", "devise": "CAD"})):
        for p in enq[cle]:
            ligne = {"ts": ts, "lien": p["url"] or f"navigateur:{_cle(p['marchand'])}", "marchand": p["marchand"],
                     "exact": True, "source": "navigateur", "prix": p["prix"], "devise": "EUR",
                     "en_stock": p["en_stock"], "prix_barre": p["barre"], **extra}
            n[i] += depot.ajouter_releve(art["id"], ligne)
    return tuple(n)


# ---------------------------------------------------------------- la consigne donnée à Claude dans Chrome

def _pointure_us(taille):
    """Pointure EU homme -> US homme (correspondance usuelle : EU 40 = US 7, demi-pointures intercalées)."""
    t = _nombre(str(taille or ""))
    if not t or t < 35 or t > 50:
        return None
    table = {39: 6, 39.5: 6.5, 40: 7, 40.5: 7.5, 41: 7.5, 41.5: 8, 42: 8.5, 42.5: 9, 43: 9.5, 44: 10, 44.5: 10.5,
             45: 11, 45.5: 11.5, 46: 12, 47: 12.5, 47.5: 13}
    v = table.get(t)
    return None if v is None else f"{v:g}"


def consigne(art, depot_github):
    nom = art.get("nom", "")
    ref = art.get("reference") or ""
    tailles = [art["taille"]] if art.get("taille") else []
    for l in art.get("liens", []):
        if l.get("taille") and l["taille"] not in tailles:
            tailles.append(l["taille"])
    taille = " ou ".join(str(t).replace(".", ",") for t in tailles) or None
    coloris = art.get("coloris") or ("celui de la référence" if art.get("reference") else "")
    us = None
    if art.get("categorie") == "chaussures" and tailles:
        conv = [_pointure_us(t) for t in tailles]
        us = " ou ".join(c for c in conv if c) or None
    connus, vus = [], set()
    for l in art.get("liens", []):
        if l.get("url") and l["url"] not in vus:
            vus.add(l["url"])
            connus.append(l)
    fr = "\n".join(f"   - {l.get('marchand')} : {l['url']}" for l in connus if not l.get("pays"))
    ca = "\n".join(f"   - {l.get('marchand')} : {l['url']}" for l in connus if l.get("pays") == "CA")
    modele = ("Article : {id}\nHistorique : AAAA-MM-JJ | prix | idealo\nPrix : prix | boutique | adresse | oui ou non "
              "| prix barré si affiché\nCanada : prix en $ CA | boutique | adresse | oui ou non\nNote : une phrase"
              ).format(id=art["id"])
    issue = (f"https://github.com/{depot_github}/issues/new?labels=enquete&title="
             + urllib.parse.quote(f"Enquête : {nom}") + "&body=" + urllib.parse.quote(modele))
    t_txt = (f"taille {taille}" + (f" (US {us} en pointure américaine)" if us else "")) if taille else "taille non précisée"
    ref_txt = f" ({ref})" if ref else ""
    col_txt = coloris or "indifférent"
    us_txt = f" (US {us})" if us else ""
    fr_txt = fr or "   (aucune)"
    ca_txt = ca or "   (aucune)"
    return f"""Enquête de prix PrixJuste — {nom}{ref_txt}, {t_txt}, coloris {col_txt}.

Tu navigues dans mon Chrome, pour moi, une seule fois. Règles : une visite par site ; si un site affiche un captcha ou refuse l'accès, passe au suivant sans contourner ; n'achète rien, ne te connecte à rien.

1. HISTORIQUE (le plus important) : sur idealo.fr, cherche ce modèle exact, ouvre sa fiche, puis sa courbe « historique des prix » sur 1 an. Relève 6 à 12 points datés : le plus bas, le plus haut, le Black Friday, les soldes de janvier et d'été, et aujourd'hui. Si idealo ne l'a pas, fais-le sur ledenicheur.fr. Si le produit est vendu sur Amazon, regarde aussi sa courbe sur keepa.com.
2. PRIX DU JOUR dans ma taille : 4 à 6 boutiques françaises ou européennes (prix, en stock ou non dans ma taille, prix barré s'il y en a un). Celles que je suis déjà :
{fr_txt}
3. CANADA (je vais à Québec) : 1 à 3 boutiques canadiennes (site officiel .ca, Sporting Life, Sports Experts, JD Sports Canada…) : prix en $ CA tel qu'affiché (hors taxes), en stock ou non dans ma taille{us_txt}. Déjà suivies :
{ca_txt}
4. ENREGISTRE : ouvre cette adresse, remplace le texte par tes résultats (une ligne par information, en gardant exactement ce format), puis clique sur « Create » :
{issue}

Format :
{modele}
"""
