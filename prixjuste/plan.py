"""Plan d'achat sous budget (docs/IDEES.md, idée 6).

Le build prépare, pour chaque article suivi et pas encore acheté, le prix attendu mois par mois
jusqu'à sa date limite (ou jusqu'à la date « pas après le » quand ta taille risque de manquer).
Le budget mensuel, lui, ne quitte jamais le navigateur : site.js répartit les achats avec `repartir`
(même algorithme qu'ici, écrit en JS) et le garde en localStorage. Rien de personnel n'est publié.

Prix attendu d'un mois : le prix actuel pour le mois en cours ; ensuite la médiane historique de ce
mois-là quand l'historique a assez de mois différents (comme le « meilleur mois » de l'analyse),
sinon le prix actuel : on n'invente pas d'économie.
"""
import datetime as dt
import statistics

MOIS_MAX = 12


def _mois_suivants(auj, fin, n_max=MOIS_MAX):
    an, m, res = auj.year, auj.month, []
    while (an, m) <= (fin.year, fin.month) and len(res) < n_max:
        res.append((an, m))
        an, m = (an + 1, 1) if m == 12 else (an, m + 1)
    return res or [(auj.year, auj.month)]


def candidats(articles_et_resultats, auj):
    """{"debut": "AAAA-MM", "articles": [{id, nom, maintenant, limite, mois: [["AAAA-MM", prix], ...]}]}"""
    items = []
    for art, res in articles_et_resultats:
        if art.get("statut", "suivi") != "suivi" or art.get("achat"):
            continue
        c = res["chiffres"]
        act = res.get("actuel")
        base = act["prix"] if act else c.get("mediane")
        if base is None:
            continue
        med = {}
        if c.get("meilleur_mois"):  # historique jugé suffisant par l'analyse
            par_mois = {}
            for d, v in res["serie"].items():
                par_mois.setdefault(d.month, []).append(v["prix"])
            med = {m: statistics.median(p) for m, p in par_mois.items()}
        fin = min(res["limite"], res.get("jusqu_a") or dt.date.max)
        mois = []
        for i, (an, m) in enumerate(_mois_suivants(auj, fin)):
            prix = base if i == 0 else med.get(m, base)
            mois.append([f"{an}-{m:02d}", round(prix, 2)])
        items.append({"id": art["id"], "nom": art["nom"], "maintenant": round(base, 2),
                      "limite": fin.isoformat(), "mois": mois})
    return {"debut": f"{auj:%Y-%m}", "articles": items}


def repartir(cands, budget=None):
    """Glouton explicable : les articles les plus contraints (moins de mois possibles) d'abord ; chacun
    va dans son mois le moins cher où il reste du budget, à prix égal le plus tôt.
    Renvoie {"mois": {"AAAA-MM": [(id, prix)]}, "hors": [id], "total": x, "economie": y}."""
    plafond = budget if budget and budget > 0 else float("inf")
    depense, plan, hors, total, maintenant = {}, {}, [], 0.0, 0.0
    ordre = sorted(cands["articles"], key=lambda a: (len(a["mois"]), -(a["maintenant"] - min(p for _, p in a["mois"]))))
    for a in ordre:
        choix = sorted(a["mois"], key=lambda mp: (mp[1], mp[0]))
        ok = next((mp for mp in choix if depense.get(mp[0], 0) + mp[1] <= plafond), None)
        if ok is None:
            hors.append(a["id"])
            continue
        depense[ok[0]] = depense.get(ok[0], 0) + ok[1]
        plan.setdefault(ok[0], []).append((a["id"], ok[1]))
        total += ok[1]
        maintenant += a["maintenant"]
    return {"mois": dict(sorted(plan.items())), "hors": hors, "total": round(total, 2),
            "economie": round(maintenant - total, 2)}
