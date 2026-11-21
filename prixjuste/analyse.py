"""Moteur de verdict : acheter maintenant, attendre, ou fausse promo ?

Tout est calculé à partir de vrais prix relevés. Pas d'IA ici : des stats simples,
explicables en une phrase, pour que chaque verdict soit vérifiable.

Codes de verdict (= tampons du site) :
  acheter     ACHÈTE      bon prix au regard de l'historique
  attendre    ATTENDS     le prix baisse habituellement avant ta date limite
  surveiller  SURVEILLE   ni bon ni mauvais : alerte conseillée
  bidon       BIDON       la meilleure offre affiche une réduction trompeuse
  donnees     PAS ASSEZ DE DONNÉES
"""
import datetime as dt
import statistics

MOIS_AFFICHE = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
                "août", "septembre", "octobre", "novembre", "décembre"]

# Repères généraux par catégorie, affichés seulement comme contexte quand l'historique est court.
# Ce sont des habitudes du commerce en France, pas des données sur TON produit.
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
    """{date: {prix, n_dispo, marchand, source, exact}} : meilleur prix disponible chaque jour, tous marchands confondus."""
    jours = {}
    for o in obs:
        if o.get("en_stock") == 0:
            continue
        d = _date(o["ts"])
        j = jours.get(d)
        if j is None or o["prix"] < j["prix"]:
            jours[d] = {"prix": o["prix"], "n_dispo": o.get("n_dispo"), "marchand": o.get("marchand"),
                        "source": o.get("source"), "exact": o.get("exact", True)}
    return dict(sorted(jours.items()))


def _quantile(vals, q):
    vals = sorted(vals)
    if not vals:
        return None
    i = (len(vals) - 1) * q
    lo, hi = int(i), min(int(i) + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (i - lo)


def _pente_pct(points):
    """Tendance sur la période : variation en % estimée par régression linéaire."""
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



def _fin_de_mois(an, mois):
    suivant = dt.date(an + (mois == 12), mois % 12 + 1, 1)
    return suivant - dt.timedelta(days=1)


def prochaine_fenetre(debut, fin, auj):
    """(premier jour, dernier jour) de la prochaine fenêtre de mois debut→fin ; commence
    aujourd'hui si on est déjà dedans."""
    mois, m = [debut], debut
    while m != fin:
        m = m % 12 + 1
        mois.append(m)
    if auj.month in mois:
        reste = mois[mois.index(auj.month):]
        an_fin = auj.year + (1 if reste[-1] < auj.month else 0)
        return auj, _fin_de_mois(an_fin, reste[-1])
    an_debut = auj.year if debut > auj.month else auj.year + 1
    an_fin = an_debut + (1 if fin < debut else 0)
    return dt.date(an_debut, debut, 1), _fin_de_mois(an_fin, fin)


def filtrer_obs(article, obs):
    """Relevés pris en compte pour le verdict : seulement le coloris exact si l'article l'exige."""
    if article.get("autres_coloris_ok", True):
        return list(obs)
    return [o for o in obs if o.get("exact", True)]


def fiabilite(n):
    """Fiabilité d'un verdict selon le nombre de jours de prix connus sur ~12 mois."""
    return "faible" if n < 15 else ("moyenne" if n < 60 else "bonne")


def analyser(article, obs, aujourdhui=None):
    auj = aujourdhui or dt.date.today()
    obs = filtrer_obs(article, obs)
    serie = serie_journaliere(obs)
    cat = article.get("categorie", "autre")
    repere_txt, _ = REPERES.get(cat, REPERES["autre"])

    # Date limite d'achat
    if article.get("acheter_avant"):
        limite = _date(article["acheter_avant"])
    else:
        limite = auj + dt.timedelta(days=URGENCE_JOURS.get(article.get("urgence", "pas_urgent"), 365))

    res = {"serie": serie, "limite": limite, "repere": repere_txt, "notes": [], "chiffres": {},
           "jusqu_a": None}
    c = res["chiffres"]

    # Prix actuel = meilleur relevé des 3 derniers jours (en stock ou stock inconnu)
    recents = [o for o in obs if 0 <= (auj - _date(o["ts"])).days <= 3 and o.get("en_stock") != 0]
    actuel = min(recents, key=lambda o: o["prix"]) if recents else None
    res["actuel"] = actuel
    if actuel:
        c["actuel"] = actuel["prix"]

    hist = {d: v for d, v in serie.items() if 0 <= (auj - d).days <= 400}
    prix_hist = [v["prix"] for v in hist.values()]
    if prix_hist:
        d_min = min(hist, key=lambda d: hist[d]["prix"])
        c["min_12m"] = hist[d_min]["prix"]
        c["min_12m_date"] = d_min
        c["min_12m_dispo"] = hist[d_min]["n_dispo"]
        c["min_12m_marchand"] = hist[d_min]["marchand"]
        c["p25"] = _quantile(prix_hist, 0.25)
        c["mediane"] = statistics.median(prix_hist)

    # Même période l'an dernier (± 3 semaines)
    centre = auj - dt.timedelta(days=365)
    meme = [v["prix"] for d, v in serie.items() if abs((d - centre).days) <= 21]
    if meme:
        c["meme_periode_an_dernier"] = min(meme)

    # Meilleur mois d'après l'historique (au moins 3 mois différents observés)
    par_mois = {}
    for d, v in serie.items():
        par_mois.setdefault(d.month, []).append(v)
    meilleur_mois = None
    # au moins 3 mois différents et 5 jours de prix : pas de « meilleur mois » inventé sur 4 points
    if len(par_mois) >= 3 and len(serie) >= 5:
        med = {m: statistics.median(x["prix"] for x in vs) for m, vs in par_mois.items()}
        meilleur_mois = min(med, key=med.get)
        c["meilleur_mois"] = meilleur_mois
        c["meilleur_mois_prix"] = med[meilleur_mois]
        dispos = [x["n_dispo"] for x in par_mois[meilleur_mois] if x["n_dispo"] is not None]
        c["meilleur_mois_dispo"] = min(dispos) if dispos else None
        # fenêtre : mois consécutifs à moins de 5 % du meilleur
        seuil = med[meilleur_mois] * 1.05
        ok = lambda m: m in med and med[m] <= seuil
        debut = fin = meilleur_mois
        while ok((debut - 2) % 12 + 1) and (debut - 2) % 12 + 1 != meilleur_mois:
            debut = (debut - 2) % 12 + 1
        while ok(fin % 12 + 1) and fin % 12 + 1 != debut:
            fin = fin % 12 + 1
        c["fenetre"] = (debut, fin)
        c["fenetre_dates"] = prochaine_fenetre(debut, fin, auj)

    # Meilleur prix vu l'an dernier entre « aujourd'hui » et la date limite (décalés d'un an)
    a0 = auj - dt.timedelta(days=365)
    a1 = min(limite - dt.timedelta(days=365), auj - dt.timedelta(days=30))
    avant_limite = [v["prix"] for d, v in serie.items() if a0 <= d <= a1]
    if avant_limite:
        c["min_avant_limite_an_dernier"] = min(avant_limite)

    # Tendance de fond sur 90 jours
    pts90 = [(d, v["prix"]) for d, v in serie.items() if 0 <= (auj - d).days <= 90]
    tendance = _pente_pct(pts90)
    c["tendance_90j"] = tendance

    # Contrôle des promos : chaque prix barré récent, comparé à ce qu'on a vraiment observé
    res["promos"] = controler_promos(obs, recents, c)

    # Fiabilité
    n = len(prix_hist)
    c["n_releves"] = n
    c["n_sources"] = len({o.get("marchand") for o in obs})
    c["fiabilite"] = fiabilite(n)

    _verdict(res, article, c, actuel, prix_hist, meilleur_mois, tendance, limite, auj, repere_txt)
    _alerte(c, article.get("budget_max"))
    _bidon(res)
    return res


def controler_promos(obs, recents, c):
    """Règle française des 30 jours (art. L112-1-1 du code de la consommation) : le prix de
    référence d'une réduction doit être le prix le plus bas pratiqué par CE marchand dans les
    30 jours précédents. On signale aussi une remise calculée sur un prix jamais pratiqué ailleurs."""
    promos = []
    for o in sorted(recents, key=lambda o: o["ts"], reverse=True):
        barre = o.get("prix_barre")
        if not barre or barre <= o["prix"]:
            continue
        promo = {"barre": barre, "prix": o["prix"], "marchand": o.get("marchand"), "ts": o["ts"],
                 "remise_affichee": (1 - o["prix"] / barre) * 100}
        d_o = _date(o["ts"])
        meme_marchand = [x["prix"] for x in obs if x.get("marchand") == o.get("marchand") and x is not o
                         and 0 < (d_o - _date(x["ts"])).days <= 30]
        if meme_marchand and min(meme_marchand) < barre - 0.5:
            promo["alerte"] = (f"Prix barré {barre:.0f} € alors que ce marchand l'a vendu {min(meme_marchand):.0f} € "
                               f"dans les 30 jours précédents : réduction trompeuse (signalable sur SignalConso).")
        if c.get("min_12m") and o["prix"] > c["min_12m"] * 1.15:
            ailleurs = c.get("actuel") is not None and c["actuel"] < o["prix"] - 1
            promo["contexte"] = (f"La remise de {promo['remise_affichee']:.0f} % est calculée sur {barre:.0f} €, "
                                 f"mais ce modèle a été vu à {c['min_12m']:.0f} € le {c['min_12m_date']:%d/%m/%Y}"
                                 + (f", et il est à {c['actuel']:.0f} € ailleurs en ce moment" if ailleurs else "")
                                 + ". Ce n'est pas une bonne affaire.")
        promo["douteuse"] = bool(promo.get("alerte") or promo.get("contexte"))
        promos.append(promo)
    return promos


def _verdict(res, article, c, actuel, prix_hist, meilleur_mois, tendance, limite, auj, repere_txt):
    budget = article.get("budget_max")
    if not actuel and not prix_hist:
        res["verdict"] = ("donnees", "Aucun prix relevé pour l'instant",
                          "Le premier relevé arrive avec la prochaine collecte, ou ajoute un prix vu.")
        return
    if len(prix_hist) < 5:
        res["verdict"] = ("donnees", "Pas encore assez d'historique",
                          f"{len(prix_hist)} jour(s) de prix connus seulement. {repere_txt}")
        return
    p = actuel["prix"] if actuel else None
    if p is None:
        res["verdict"] = ("donnees", "Pas de prix actuel",
                          "Aucun site n'a pu être lu ces 3 derniers jours : ajoute le prix que tu vois.")
        return

    if tendance is not None and tendance > 8:
        res["notes"].append(f"Tendance haussière (+{tendance:.0f} % sur 90 jours) : attendre peut coûter plus cher.")
    elif tendance is not None and tendance < -8:
        res["notes"].append(f"Tendance baissière ({tendance:.0f} % sur 90 jours).")

    # « bon prix » : proche du plus bas, ou dans le quart le moins cher ET sous le prix habituel
    # (sur un historique plat, le 1er quartile vaut le prix habituel : ce n'est pas une affaire)
    if p <= c["min_12m"] * 1.05 or (p <= c["p25"] * 1.02 and p < c["mediane"]):
        res["verdict"] = ("acheter", "Bon prix : tu peux acheter",
                          f"{p:.0f} € fait partie des prix les plus bas vus sur 12 mois (plus bas : {c['min_12m']:.0f} €).")
    elif meilleur_mois:
        debut, fin = c["fenetre"]
        d0, d1 = c["fenetre_dates"]
        gain = (p - c["meilleur_mois_prix"]) / p * 100
        nom_mois = MOIS_AFFICHE[debut - 1] + ("" if debut == fin else "–" + MOIS_AFFICHE[fin - 1])
        if gain >= 10 and d0 <= limite:
            txt = (f"Historiquement autour de {c['meilleur_mois_prix']:.0f} € en {nom_mois} "
                   f"(−{gain:.0f} % par rapport à aujourd'hui).")
            if c.get("meilleur_mois_dispo") is not None and c["meilleur_mois_dispo"] <= 2:
                txt += " Attention : à ce moment-là il ne restait que peu de tailles en stock."
            res["jusqu_a"] = min(d1, limite)
            if tendance is not None and tendance > 8:
                res["verdict"] = ("surveiller", f"Plutôt attendre {nom_mois}, mais le prix monte", txt)
            else:
                res["verdict"] = ("attendre", f"Attends {nom_mois}", txt)
        elif gain >= 10:
            txt = (f"Le prix baisse surtout en {nom_mois} (~{c['meilleur_mois_prix']:.0f} €), "
                   f"après ta date limite du {limite:%d/%m/%Y}.")
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


def _alerte(c, budget):
    """Seuil d'alerte : jamais calculé sur moins de 5 jours de prix (on n'invente rien)."""
    if c.get("alerte_limite"):  # date limite courte : seuil réaliste plutôt que le plus bas absolu
        c["alerte"] = c["alerte_limite"]
        return
    p25 = c.get("p25") if c.get("n_releves", 0) >= 5 else None
    seuils = [x for x in (p25, budget) if x]
    if seuils:
        c["alerte"] = round(min(seuils))


def _bidon(res):
    """Si la meilleure offre du moment affiche une réduction trompeuse, le tampon devient BIDON :
    c'est la première chose à savoir avant d'acheter. Le conseil d'origine reste en note."""
    act = res.get("actuel")
    if not act or not act.get("prix_barre"):
        return
    for pr in res["promos"]:
        if pr["douteuse"] and pr["ts"] == act["ts"] and pr["marchand"] == act.get("marchand"):
            code, titre, expli = res["verdict"]
            res["verdict_initial"] = res["verdict"]
            res["verdict"] = ("bidon", f"Promo bidon chez {pr['marchand']}",
                              pr.get("alerte") or pr.get("contexte"))
            if code != "donnees":
                res["notes"].insert(0, f"Sans tenir compte de la promo : {titre.lower()}. {expli}")
            return
