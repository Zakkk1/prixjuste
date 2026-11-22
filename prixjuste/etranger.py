"""Comparer avec un prix relevé à l'étranger (aujourd'hui : le Canada, pour un achat sur place à Québec).

Les prix étrangers ne se mélangent JAMAIS à l'historique français (autre devise, autres taxes) : ils sont
relevés sur des liens marqués `"pays": "CA"` et affichés à part, convertis en euros au taux de la BCE.

Au Canada, les prix affichés sont hors taxes : à Québec, on paie en caisse la TPS (5 %) et la TVQ (9,975 %).
Les touristes ne se font plus rembourser ces taxes (programme fédéral supprimé en 2007).
Au retour en France, les achats faits hors UE sont exonérés jusqu'à 430 € par voyageur arrivant en avion ;
au-delà, droits de douane et TVA sont dus sur l'objet.
"""
import datetime as dt
import json
import re

BCE = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"

PAYS = {
    "CA": {"nom": "au Québec", "devise": "CAD", "symbole": "$ CA", "taxes": 0.14975,
           "taxes_txt": "TPS 5 % + TVQ 9,975 %, ajoutées en caisse",
           "franchise": 430,
           "rappels": ["Au Canada, le prix affiché est hors taxes ; les touristes ne sont pas remboursés de ces taxes.",
                       "Retour en France : jusqu'à 430 € d'achats par voyageur (avion), rien à payer ; au-delà, "
                       "droits de douane et TVA sur l'objet."]},
}


# ---------------------------------------------------------------- taux de change (BCE)

def lire_bce(xml):
    """Fichier quotidien de la BCE -> (date ISO, {devise: unités pour 1 €})."""
    m = re.search(r"time=['\"](\d{4}-\d{2}-\d{2})['\"]", xml)
    taux = {d: float(v) for d, v in re.findall(r"currency=['\"]([A-Z]{3})['\"]\s+rate=['\"]([\d.]+)['\"]", xml)}
    if not m or not taux:
        raise ValueError("fichier de la BCE illisible")
    return m.group(1), taux


def mettre_a_jour(depot, telecharger):
    date, taux = lire_bce(telecharger(BCE))
    f = depot.racine / "change.json"
    f.write_text(json.dumps({"date": date, "source": "Banque centrale européenne (taux de référence)",
                             "taux": {k: taux[k] for k in sorted(taux)}}, ensure_ascii=False, indent=1) + "\n",
                 encoding="utf-8")
    return date, taux


def charger_change(depot):
    f = depot.racine / "change.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


# ---------------------------------------------------------------- comparaison

def est_etranger(o):
    return bool(o.get("pays"))


def comparaison(releves, prix_france, change, auj, jours=7):
    """Meilleure offre étrangère récente, convertie en euros, taxes locales comprises.
    Renvoie None s'il n'y a ni prix étranger récent ni taux de change."""
    if not change:
        return None
    recents = {}
    for o in releves:
        if not est_etranger(o) or o.get("source") == "historique":
            continue
        d = dt.date.fromisoformat(o["ts"][:10])
        if (auj - d).days > jours:
            continue
        if o["lien"] not in recents or o["ts"] >= recents[o["lien"]]["ts"]:
            recents[o["lien"]] = o  # le relevé le plus récent de chaque page décide (rupture comprise)
    meilleurs = []
    for o in recents.values():
        if o.get("en_stock") == 0:
            continue
        p = PAYS.get(o["pays"])
        t = change["taux"].get(p["devise"]) if p else None
        if not t:
            continue
        ht = o["prix"] / t
        ttc = ht * (1 + p["taxes"])
        meilleurs.append({"pays": o["pays"], "marchand": o.get("marchand"), "prix_local": o["prix"],
                          "devise": p["devise"], "symbole": p["symbole"], "le": o["ts"][:10], "taux": t,
                          "taux_date": change["date"], "eur_ht": round(ht, 2), "eur_ttc": round(ttc, 2),
                          "ecart": round(ttc - prix_france, 2) if prix_france else None,
                          "nom_pays": p["nom"], "taxes_txt": p["taxes_txt"], "rappels": p["rappels"],
                          "lien": o["lien"]})
    return min(meilleurs, key=lambda m: m["eur_ttc"]) if meilleurs else None
