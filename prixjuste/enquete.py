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
    res = {"article": None, "historique": [], "historique_ca": [], "prix": [], "canada": [], "note": None,
           "sources": None, "modeles": [], "equivalents": []}
    for ligne in (corps or "").replace("\r", "").split("\n"):
        m = re.match(r"^\s*(?:[-*]\s*)?([A-Za-zÀ-ÿ ]{4,20}?)\s*[:：]\s*(.+)$", ligne)
        if not m:
            continue
        cle, val = _cle(m.group(1)), m.group(2).strip()
        champs = [c.strip() for c in val.split("|")]
        if cle == "article":
            res["article"] = val
        elif cle in ("historique", "historique canada") and len(champs) >= 2:
            d, p = _date_iso(champs[0]), _nombre(champs[1])
            if d and p:
                h = {"date": d, "prix": p, "source": champs[2] if len(champs) > 2 else "comparateur"}
                res["historique" if cle == "historique" else "historique_ca"].append(h)
        elif cle in ("prix", "canada") and len(champs) >= 2:
            p = _nombre(champs[0])
            if not p:
                continue
            url = next((c for c in champs if c.startswith("http")), "")
            autres = [c for c in champs[2:] if c and not c.startswith("http")]
            res[cle].append({"prix": p, "marchand": champs[1] or "?", "url": url,
                             "en_stock": (1 if _oui(autres[0]) else 0) if autres else None,
                             "barre": _nombre(autres[1]) if len(autres) > 1 else None})
        elif cle == "modele" and len(champs) >= 3:
            n, p = _nombre(champs[0]), _nombre(champs[1])
            if n and p:
                url = next((c for c in champs if c.startswith("http")), "")
                autres = [c for c in champs[3:] if c and not c.startswith("http")]
                res["modeles"].append({"n": int(n), "prix": p, "marchand": champs[2], "url": url,
                                       "en_stock": (1 if _oui(autres[0]) else 0) if autres else None,
                                       "commentaire": " | ".join(autres[1:])[:200] if len(autres) > 1 else ""})
        elif cle == "equivalent" and len(champs) >= 2:
            url = next((c for c in champs if c.startswith("http")), "")
            autres = [c for c in champs[1:] if c and not c.startswith("http")]
            prix = _nombre(autres[0]) if autres else None
            res["equivalents"].append({"nom": champs[0][:120], "prix": prix,
                                       "marchand": autres[1] if len(autres) > 1 else "", "url": url,
                                       "pourquoi": " | ".join(autres[2:])[:240]})
        elif cle == "note":
            res["note"] = val[:300]
        elif cle == "sources":
            res["sources"] = val[:400]
    ids = {a["id"] for a in articles}
    if res["article"] not in ids:
        raise ValueError(f"Article inconnu : « {res['article']} ». Articles : {', '.join(sorted(ids))}.")
    if not (res["historique"] or res["historique_ca"] or res["prix"] or res["canada"] or res["modeles"]
            or res["equivalents"]):
        raise ValueError("Aucune ligne « Historique », « Prix », « Canada », « Modèle » ou « Équivalent » lisible.")
    return res


def enregistrer(depot, art, enq, ts=None):
    """Ajoute les relevés de l'enquête. Renvoie (n_historique, n_prix, n_canada) réellement ajoutés."""
    ts = ts or maintenant()
    n = [0, 0, 0]
    modif = False
    if enq.get("modeles") and art.get("candidats"):
        for m in enq["modeles"]:
            if 1 <= m["n"] <= len(art["candidats"]):
                art["candidats"][m["n"] - 1]["enquete"] = {**m, "le": ts[:10]}
                modif = True
    if enq.get("equivalents"):
        art["equivalents"] = [{**q, "le": ts[:10]} for q in enq["equivalents"]][:4]
        modif = True
    if modif:
        depot.ecrire_article(art)
    if art.get("statut") == "a_choisir":
        return tuple(n)  # plusieurs modèles possibles : pas de relevés tant que le choix n'est pas fait
    for cle_h, extra in (("historique", {}), ("historique_ca", {"pays": "CA", "devise": "CAD"})):
        for h in enq.get(cle_h, []):
            src = h["source"]
            ligne = {"ts": h["date"] + "T12:00:00", "lien": f"historique:{_cle(src)}", "marchand": f"{src} (historique)",
                     "exact": True, "source": "historique", "prix": h["prix"], "devise": "EUR", "en_stock": None,
                     "note": "prix lu dans l'historique d'un comparateur ou d'un site de bons plans", **extra}
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
    cands = art.get("candidats") or []
    if cands:
        modeles = "\n".join(f"   {i}. {c.get('nom')} — {c.get('variante') or ''} — {c.get('url') or ''}"
                             for i, c in enumerate(cands, 1))
        bloc_modeles = (f"0. JE N'AI PAS ENCORE CHOISI entre ces modèles. Pour CHACUN, trouve le prix le plus bas du jour "
                        f"dans ma taille et mon coloris, et le plus bas vu sur 12 mois (comparateurs) :\n{modeles}\n"
                        "   Une ligne par modèle : « Modèle : numéro | prix | boutique | adresse | oui ou non | "
                        "plus bas vu (prix, date, source) et ton avis en une phrase ».\n")
        modele_l = ("Modèle : 1 | prix | boutique | adresse | oui ou non | plus bas vu et avis\n")
    else:
        bloc_modeles, modele_l = "", ""
    modele = ("Article : {id}\n" + modele_l + "Historique : AAAA-MM-JJ | prix en € | source (idealo, Dealabs…)\n"
              "Prix : prix | boutique | adresse | oui ou non | prix barré si affiché\n"
              "Historique Canada : AAAA-MM-JJ | prix en $ CA | source (RedFlagDeals…)\n"
              "Canada : prix en $ CA | boutique | adresse | oui ou non\n"
              "Équivalent : nom | prix | boutique | adresse | pourquoi\n"
              "Sources : tous les sites consultés, séparés par des virgules\nNote : une phrase"
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

Tu navigues dans mon Chrome, pour moi, une seule fois. Les sites cités ne sont que des EXEMPLES : cherche toi-même (Google, Google Shopping) tous ceux qui ont ce produit. Règles : une visite par page ; si un site affiche un captcha ou refuse l'accès, passe au suivant sans contourner ; n'achète rien, ne te connecte à rien.

{bloc_modeles}1. HISTORIQUE EN FRANCE (le plus important) : trouve les comparateurs et sites qui gardent l'historique de ce modèle exact — par exemple idealo, Le Dénicheur, Google Shopping, Kelkoo, et les bons plans datés de Dealabs ; pour Amazon.fr, Keepa ou camelcamelcamel ; cherche aussi « {nom} historique prix ». Relève 6 à 15 points datés sur 1 à 2 ans : le plus bas, le plus haut, Black Friday, soldes de janvier et d'été, aujourd'hui (en notant la source de chaque point).
2. PRIX DU JOUR dans ma taille, en France et en Europe : pars des comparateurs pour lister TOUTES les boutiques qui l'ont, puis garde les 6 moins chères en stock dans ma taille (prix, en stock ou non, prix barré s'il y en a un). Déjà suivies (à revérifier) :
{fr_txt}
3. CANADA (je vais à Québec, achat sur place ou en ligne) : même démarche avec les équivalents canadiens — par exemple Google Shopping Canada et Shopbot (prix du jour), bons plans datés de RedFlagDeals (le plus proche d'un historique multi-boutiques au Canada), circulaires des magasins (Flipp), Keepa ou camelcamelcamel pour l'historique Amazon.ca ; ignore les courbes « estimées » (ex. Shopli), qui ne sont pas de vrais prix passés — et toutes les boutiques (site officiel .ca, grands magasins, chaînes de sport et de chaussures, magasins de la ville de Québec). Relève l'historique s'il existe, et les prix du jour en $ CA tels qu'affichés (hors taxes), en stock ou non dans ma taille{us_txt}. Si une promo « au panier » est annoncée (ex. -30 % appliqué au panier), ajoute l'article au panier SANS te connecter ni payer pour lire le prix réellement facturé, et indique-le dans la note. Déjà suivies :
{ca_txt}
3 bis. ÉQUIVALENTS : propose 2 ou 3 autres produits tout aussi bien (même usage, qualité et chaleur comparables, bons avis), idéalement moins chers, avec leur prix dans ma taille et une phrase factuelle sur ce qu'on gagne ou perd.
4. ENREGISTRE : ouvre cette adresse, remplace le texte par tes résultats (une ligne par information, en gardant exactement ce format), puis clique sur « Create » :
{issue}

Format :
{modele}
"""
