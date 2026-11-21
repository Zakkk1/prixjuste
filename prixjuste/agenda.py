"""Le calendrier d'achat : site/agenda.ics, à ajouter (abonnement) dans le calendrier du téléphone.

Pour chaque article : fenêtre d'achat conseillée, date limite, fin de rétractation et de garantie après achat.
Grandes dates commerciales françaises dont la date est fixée par une règle connue :
- soldes d'hiver : 2e mercredi de janvier, avancé au 1er si le 2e tombe après le 12 ; 4 semaines ;
- soldes d'été : dernier mercredi de juin, avancé à l'avant-dernier s'il tombe après le 28 ; 4 semaines
  (article D310-15-2 du code de commerce, durée de 4 semaines depuis 2020) ;
- Black Friday : lendemain de Thanksgiving (4e jeudi de novembre).
Les autres opérations (French Days, Prime Day) changent chaque année : non inventées ici.
"""
import datetime as dt

MERCREDI, JEUDI = 2, 3


def _mercredis(an, mois):
    d = dt.date(an, mois, 1)
    d += dt.timedelta(days=(MERCREDI - d.weekday()) % 7)
    res = []
    while d.month == mois:
        res.append(d)
        d += dt.timedelta(days=7)
    return res


def soldes_hiver(an):
    m = _mercredis(an, 1)
    return m[0] if m[1].day > 12 else m[1]


def soldes_ete(an):
    m = _mercredis(an, 6)
    return m[-2] if m[-1].day > 28 else m[-1]


def black_friday(an):
    d = dt.date(an, 11, 1)
    d += dt.timedelta(days=(JEUDI - d.weekday()) % 7)
    return d + dt.timedelta(days=21 + 1)


def evenements_commerciaux(debut, fin):
    """[(date_debut, date_fin_incluse, titre)] entre deux dates."""
    res = []
    for an in range(debut.year, fin.year + 1):
        for d, duree, titre in ((soldes_hiver(an), 28, "Soldes d'hiver"), (soldes_ete(an), 28, "Soldes d'été"),
                                (black_friday(an), 4, "Black Friday (jusqu'au Cyber Monday)")):
            if debut <= d <= fin:
                res.append((d, d + dt.timedelta(days=duree - 1), titre))
    return sorted(res)


def _echapper(t):
    return str(t).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _plier(ligne):
    """Lignes de 75 octets max (RFC 5545)."""
    b = ligne.encode("utf-8")
    if len(b) <= 75:
        return ligne
    morceaux, cour = [], ""
    for ch in ligne:
        if len((cour + ch).encode("utf-8")) > (75 if not morceaux else 74):
            morceaux.append(cour)
            cour = ""
        cour += ch
    morceaux.append(cour)
    return "\r\n ".join(morceaux)


def evenements_articles(articles_et_resultats):
    """[(début, fin incluse, titre, description, uid, id_article)] pour chaque article."""
    ev = []
    for art, res in articles_et_resultats:
        if art.get("statut", "suivi") != "suivi":
            continue
        nom = art["nom"]
        c = res["chiffres"]
        pr = res.get("protection")
        if pr:
            ev.append((pr["fin_retractation"], pr["fin_retractation"], f"Fin de rétractation : {nom}",
                       f"Dernier jour (compté depuis l'achat) pour renvoyer {nom} acheté le {pr['date']:%d/%m/%Y}.",
                       f"retract-{art['id']}", art["id"]))
            ev.append((pr["fin_garantie"], pr["fin_garantie"], f"Fin de garantie légale : {nom}",
                       "Garantie légale de conformité de 2 ans : un défaut avant cette date se règle avec le vendeur.",
                       f"garantie-{art['id']}", art["id"]))
            continue
        if c.get("fenetre_dates"):
            a, b = c["fenetre_dates"]
            ev.append((a, b, f"Fenêtre d'achat : {nom}",
                       f"Historiquement vers {c['meilleur_mois_prix']:.0f} € à cette période. {res['verdict'][2]}",
                       f"fenetre-{art['id']}-{a:%Y%m}", art["id"]))
        ev.append((res["limite"], res["limite"], f"Date limite : {nom}", "Date limite d'achat que tu as choisie.",
                   f"limite-{art['id']}", art["id"]))
    return ev


def ics(articles_et_resultats, auj, url_site=""):
    lignes = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//PrixJuste//Agenda d'achat//FR", "CALSCALE:GREGORIAN",
              "METHOD:PUBLISH", "X-WR-CALNAME:PrixJuste", "X-WR-TIMEZONE:Europe/Paris"]
    stamp = f"{auj:%Y%m%d}T000000Z"

    def vevent(a, b, titre, desc, uid, url=""):
        lignes.extend(["BEGIN:VEVENT", f"UID:{uid}@prixjuste", f"DTSTAMP:{stamp}",
                       f"DTSTART;VALUE=DATE:{a:%Y%m%d}", f"DTEND;VALUE=DATE:{b + dt.timedelta(days=1):%Y%m%d}",
                       _plier(f"SUMMARY:{_echapper(titre)}"), _plier(f"DESCRIPTION:{_echapper(desc)}")]
                      + ([_plier(f"URL:{url}")] if url else []) + ["TRANSP:TRANSPARENT", "END:VEVENT"])

    for a, b, titre, desc, uid, ident in evenements_articles(articles_et_resultats):
        vevent(a, b, titre, desc, uid, f"{url_site}/a/{ident}.html" if url_site else "")
    for a, b, titre in evenements_commerciaux(auj - dt.timedelta(days=30), auj + dt.timedelta(days=400)):
        vevent(a, b, titre, "Grande date commerciale en France (date fixée par la loi ou l'usage).",
               f"commerce-{a:%Y%m%d}")
    lignes.append("END:VCALENDAR")
    return "\r\n".join(lignes) + "\r\n"


def prochain(articles_et_resultats, auj):
    """Le prochain moment utile (pour une ligne sur le comptoir) : (date, texte) ou None."""
    cands = [(a, t) for a, b, t, *_ in evenements_articles(articles_et_resultats) if b >= auj and t.startswith("Fenêtre")]
    cands += [(a, t) for a, b, t in evenements_commerciaux(auj, auj + dt.timedelta(days=200)) if b >= auj]
    return min(cands) if cands else None
