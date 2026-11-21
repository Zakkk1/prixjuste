"""Moteur de verdict : acheter maintenant, attendre, ou fausse promo ?

Tout est calcule a partir de vrais prix releves. Pas d'IA ici : des stats simples,
explicables en une phrase, pour que chaque verdict soit verifiable.
"""
import datetime as dt
import statistics

MOIS = ["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet",
        "aout", "septembre", "octobre", "novembre", "decembre"]
MOIS_AFFICHE = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
                "août", "septembre", "octobre", "novembre", "décembre"]

# Reperes generaux par categorie, utilises seulement quand l'historique est trop court.
# Ce sont des habitudes du commerce en France, pas des donnees sur TON produit.
REPERES = {
    "vetement_hiver": ("Habituellement le plus bas : soldes d'hiver (mi-janvier → mi-février) puis "
                       "déstockage de fin de saison (mars). Risque : les tailles courantes partent vite.", [1, 2, 3]),
    "vetement_ete": ("Habituellement le plus bas : soldes d'été (fin juin → fin juillet) et fin août.", [7, 8]),
    "chaussures": ("Habituellement le plus bas : soldes (janvier et juillet) et changement de coloris en fin de saison.", [1, 7]),
    "electronique": ("Habituellement le plus bas : Black Friday (fin novembre), Prime Day (juillet), "
                     "et juste après la sortie du modèle suivant.", [11, 7]),
    "composants_pc": ("Pas de saison fiable : ce sont surtout la tendance de fond (pénuries, demande IA) "
                      "et les sorties de nouvelles générations qui comptent. Ne te fie pas au minimum de l'année.", []),
    "autre": ("Pas de repère de saison pour cette catégorie.", []),
}

URGENCE_JOURS = {"urgent": 7, "bientot": 45, "pas_urgent": 365}


def _date(s):
    return dt.date.fromisoformat(s[:10])


def serie_journaliere(obs):
    """{date: {prix, n_dispo, sources}} : meilleur prix disponible chaque jour, tous marchands confondus."""
    jours = {}
    for o in obs:
        if o["en_stock"] == 0:
            continue
        d = _date(o["ts"])
        j = jours.get(d)
        if j is None or o["prix"] < j["prix"]:
            jours[d] = {"prix": o["prix"], "n_dispo": o["n_dispo"], "marchand": o["marchand"],
                        "source": o["source"], "exact": o["exact"]}
    return dict(sorted(jours.items()))


def _quantile(vals, q):
    vals = sorted(vals)
    if not vals:
        return None
    i = (len(vals) - 1) * q
    lo, hi = int(i), min(int(i) + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (i - lo)


def _prochaine(mois, apres):
    """Milieu du prochain `mois` strictement apres la date `apres`."""
    an = apres.year if mois > apres.month else apres.year + 1
    return dt.date(an, mois, 15)


def _pente_pct(points):
    """Tendance sur la periode : variation en % estimee par regression lineaire."""
    if len(points) < 4:
        return None
    xs = [(d - points[0][0]).days for d, _ in points]
    ys = [p for _, p in points]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0 or my == 0:
        return None
    a = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
    return a * (xs[-1] - xs[0]) / my * 100


def analyser(article, obs, aujourdhui=None):
    auj = aujourdhui or dt.date.today()
    serie = serie_journaliere(obs)
    cat = article.get("categorie", "autre")
    repere_txt, repere_mois = REPERES.get(cat, REPERES["autre"])

    # Date limite d'achat
    if article.get("acheter_avant"):
        limite = _date(article["acheter_avant"])
    else:
        limite = auj + dt.timedelta(days=URGENCE_JOURS.get(article.get("urgence", "pas_urgent"), 365))

    res = {"serie": serie, "limite": limite, "repere": repere_txt, "notes": [], "chiffres": {}}

    # Prix actuel = meilleur releve des 3 derniers jours
    recents = [o for o in obs if (auj - _date(o["ts"])).days <= 3 and o["en_stock"] != 0]
    actuel = min(recents, key=lambda o: o["prix"]) if recents else None
    res["actuel"] = actuel

    hist = {d: v for d, v in serie.items() if (auj - d).days <= 400}
    prix_hist = [v["prix"] for v in hist.values()]
    c = res["chiffres"]

    if actuel:
        c["actuel"] = actuel["prix"]
    if prix_hist:
        d_min = min(hist, key=lambda d: hist[d]["prix"])
        c["min_12m"] = hist[d_min]["prix"]
        c["min_12m_date"] = d_min
        c["min_12m_dispo"] = hist[d_min]["n_dispo"]
        c["p25"] = _quantile(prix_hist, 0.25)
        c["mediane"] = statistics.median(prix_hist)

    # Meme periode l'an dernier (+/- 3 semaines)
    centre = auj - dt.timedelta(days=365)
    meme = [v["prix"] for d, v in serie.items() if abs((d - centre).days) <= 21]
    if meme:
        c["meme_periode_an_dernier"] = min(meme)

    # Meilleur mois d'apres l'historique
    par_mois = {}
    for d, v in serie.items():
        par_mois.setdefault(d.month, []).append(v)
    meilleur_mois = None
    if len(par_mois) >= 3:
        meilleur_mois = min(par_mois, key=lambda m: statistics.median(x["prix"] for x in par_mois[m]))
        vals = par_mois[meilleur_mois]
        c["meilleur_mois"] = meilleur_mois
        c["meilleur_mois_prix"] = statistics.median(x["prix"] for x in vals)
        dispos = [x["n_dispo"] for x in vals if x["n_dispo"] is not None]
        c["meilleur_mois_dispo"] = min(dispos) if dispos else None
        # fenetre : mois consecutifs a moins de 5 % du meilleur
        seuil = c["meilleur_mois_prix"] * 1.05
        ok = lambda m: m in par_mois and statistics.median(x["prix"] for x in par_mois[m]) <= seuil
        debut = fin = meilleur_mois
        while ok((debut - 2) % 12 + 1) and (debut - 2) % 12 + 1 != meilleur_mois:
            debut = (debut - 2) % 12 + 1
        while ok(fin % 12 + 1) and fin % 12 + 1 != debut:
            fin = fin % 12 + 1
        c["fenetre"] = (debut, fin)

    # Meilleur prix vu l'an dernier entre "aujourd'hui" et la date limite (decale d'un an)
    a0 = auj - dt.timedelta(days=365)
    a1 = min(limite - dt.timedelta(days=365), auj - dt.timedelta(days=30))
    avant_limite = [v["prix"] for d, v in serie.items() if a0 <= d <= a1]
    if avant_limite:
        c["min_avant_limite_an_dernier"] = min(avant_limite)

    # Tendance de fond sur 90 jours
    pts90 = [(d, v["prix"]) for d, v in serie.items() if (auj - d).days <= 90]
    tendance = _pente_pct(pts90)
    c["tendance_90j"] = tendance

    # Fausse promo : prix barre affiche vs ce qu'on a vraiment observe
    # (on verifie chaque promo recente, pas seulement l'offre la moins chere)
    promos = []
    for o in sorted(recents, key=lambda o: o["ts"], reverse=True):
        if not o.get("prix_barre"):
            continue
        barre = o["prix_barre"]
        promo = {"barre": barre, "prix": o["prix"], "marchand": o["marchand"],
                 "remise_affichee": (1 - o["prix"] / barre) * 100}
        # Regle des 30 jours : le prix barre doit etre le plus bas pratique PAR CE MARCHAND sur 30 jours
        meme_marchand = [x["prix"] for x in obs if x["marchand"] == o["marchand"] and x is not o
                         and 0 <= (_date(o["ts"]) - _date(x["ts"])).days <= 30]
        if meme_marchand and min(meme_marchand) < barre - 0.5:
            promo["alerte"] = (f"Prix barré {barre:.0f} € alors que ce marchand l'a vendu {min(meme_marchand):.0f} € "
                               f"dans les 30 jours précédents : réduction trompeuse (signalable sur SignalConso).")
        if c.get("min_12m") and o["prix"] > c["min_12m"] * 1.15:
            promo["contexte"] = (f"La remise de {promo['remise_affichee']:.0f} % est calculée sur {barre:.0f} €, "
                                 f"mais on a vu ce modèle à {c['min_12m']:.0f} € le {c['min_12m_date']:%d/%m/%Y}"
                                 + (f", et à {c['actuel']:.0f} € ailleurs en ce moment" if c.get("actuel", o["prix"]) < o["prix"] - 1 else "")
                                 + ". Ce n'est pas une bonne affaire.")
        promos.append(promo)
    res["promos"] = promos

    # Fiabilite du verdict
    n = len(prix_hist)
    c["n_releves"] = n
    c["fiabilite"] = "faible" if n < 15 else ("moyenne" if n < 60 else "bonne")

    # ------------------------------------------------------------ verdict
    budget = article.get("budget_max")
    if not actuel and not prix_hist:
        res["verdict"] = ("inconnu", "Aucun prix relevé pour l'instant",
                          "Lance la collecte ou ajoute un prix vu en magasin.")
        return res

    if len(prix_hist) < 5:
        res["verdict"] = ("donnees", "Pas encore assez d'historique",
                          f"{len(prix_hist)} relevé(s) seulement. {repere_txt}")
        _alerte(res, c, budget)
        return res

    p = actuel["prix"] if actuel else None
    if p is None:
        res["verdict"] = ("donnees", "Pas de prix actuel",
                          "Le site bloque la lecture automatique : ajoute le prix que tu vois avec la commande `prix`.")
        _alerte(res, c, budget)
        return res

    if tendance is not None and tendance > 8:
        res["notes"].append(f"Tendance haussière (+{tendance:.0f} % sur 90 jours) : attendre peut coûter plus cher.")
    elif tendance is not None and tendance < -8:
        res["notes"].append(f"Tendance baissière ({tendance:.0f} % sur 90 jours).")

    if p <= c["p25"] * 1.02 or p <= c["min_12m"] * 1.05:
        res["verdict"] = ("acheter", "Bon prix : tu peux acheter",
                          f"{p:.0f} € fait partie des prix les plus bas vus sur 12 mois (plus bas : {c['min_12m']:.0f} €).")
    elif meilleur_mois:
        debut, fin = c["fenetre"]
        prochain = _prochaine(debut, auj)
        gain = (p - c["meilleur_mois_prix"]) / p * 100
        nom_mois = MOIS_AFFICHE[debut - 1] + ("" if debut == fin else "–" + MOIS_AFFICHE[fin - 1])
        if gain >= 10 and prochain <= limite:
            txt = (f"Historiquement autour de {c['meilleur_mois_prix']:.0f} € en {nom_mois} "
                   f"(−{gain:.0f} % par rapport à aujourd'hui).")
            if c.get("meilleur_mois_dispo") is not None and c["meilleur_mois_dispo"] <= 2:
                txt += " Attention : à ce moment-là il ne restait que peu de tailles en stock."
            if tendance is not None and tendance > 8:
                res["verdict"] = ("surveiller", f"Plutôt attendre {nom_mois}, mais le prix monte", txt)
            else:
                res["verdict"] = ("attendre", f"Attends {nom_mois}", txt)
        elif gain >= 10:
            txt = (f"Le prix baisse surtout en {nom_mois} (~{c['meilleur_mois_prix']:.0f} €), "
                   f"après le {limite:%d/%m/%Y}.")
            m = c.get("min_avant_limite_an_dernier")
            if m:
                txt += f" L'an dernier sur la même période, le plus bas était {m:.0f} €."
                c["alerte_limite"] = round(m)
            res["verdict"] = ("surveiller", "Le meilleur moment tombe après ta date limite",
                              txt + " Mets une alerte et achète au premier bon prix.")
        else:
            res["verdict"] = ("surveiller", "Prix correct, sans plus",
                              f"Peu d'écart avec le meilleur mois ({c['meilleur_mois_prix']:.0f} €).")
    else:
        res["verdict"] = ("surveiller", "Prix au-dessus des plus bas de l'année",
                          f"Plus bas vu : {c['min_12m']:.0f} € le {c['min_12m_date']:%d/%m/%Y}. {repere_txt}")

    if budget and p > budget:
        res["notes"].append(f"Au-dessus de ton budget ({budget:.0f} €).")
    _alerte(res, c, budget)
    return res


def _alerte(res, c, budget):
    if c.get("alerte_limite"):  # date limite courte : seuil realiste plutot que le plus bas absolu
        c["alerte"] = c["alerte_limite"]
        return
    p25 = c.get("p25") if c.get("n_releves", 0) >= 5 else None  # pas de seuil invente sur 2 prix
    seuils = [x for x in (p25, budget) if x]
    if seuils:
        c["alerte"] = round(min(seuils))
