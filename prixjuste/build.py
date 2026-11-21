"""Génère le site statique dans site/ : le comptoir, une fiche par article, la page « ajouter ».

HTML + CSS + JS vanilla, rendu côté build (les pages s'ouvrent aussi hors ligne) ; data.json
reprend les mêmes chiffres pour qui veut les réutiliser. Direction artistique « Étiquette » :
papier, encre, tampon.
"""
import datetime as dt
import html
import json
import os
import shutil
from pathlib import Path

from . import VERSION, agenda, ajout, analyse
from .collecte import cle, hors_ue
from .donnees import Depot, maintenant

ICI = Path(__file__).resolve().parent
STATIQUE = ICI / "statique"
DEPOT_GITHUB = os.environ.get("GITHUB_REPOSITORY") or "Zakkk1/prixjuste"

MOIS_COURT = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
MOIS = analyse.MOIS_AFFICHE

TAMPONS = {  # code -> (classe, lignes du tampon)
    "acheter": ("achete", ["ACHÈTE"]),
    "attendre": ("attends", ["ATTENDS"]),
    "surveiller": ("surveille", ["SURVEILLE"]),
    "bidon": ("bidon", ["BIDON"]),
    "donnees": ("donnees", ["PAS ASSEZ", "DE DONNÉES"]),
    "attente": ("donnees", ["EN ATTENTE"]),
    "paye": ("donnees", ["PAYÉ"]),
}
ORDRE = {"acheter": 0, "bidon": 1, "surveiller": 2, "attendre": 3, "donnees": 4, "attente": 5, "paye": 6}
SOURCES = {"direct": "relevé en direct", "archive": "archive web", "manuel": "saisie manuelle"}
LECTURE = {"ok": ("lu", "ok"), "bloqué": ("bloqué", "bloque"), "vide": ("pas de prix lisible", "vide"),
           "erreur": ("erreur de lecture", "vide")}


# ---------------------------------------------------------------- formats

def e(x):
    return html.escape("" if x is None else str(x), quote=True)


def euros(x, centimes=True):
    if x is None:
        return "—"
    s = f"{x:,.2f}" if centimes else f"{round(x):,}"
    return s.replace(",", " ").replace(".", ",") + " €"


def date_fr(d):
    if isinstance(d, str):
        d = dt.date.fromisoformat(d[:10])
    return f"{d:%d/%m/%Y}" if d else "—"


def pct(x):
    return f"−{abs(x):.0f} %"


# ---------------------------------------------------------------- tampon

def tampon(code, sous=None, taille=""):
    classe, lignes = TAMPONS[code]
    corps = "<br>".join(e(l) for l in lignes)
    if sous:
        corps += f'<small>{e(sous)}</small>'
    return f'<strong class="tampon t-{classe} {taille}"><span>{corps}</span></strong>'


def sous_tampon(res):
    if res["verdict"][0] == "attendre" and res["chiffres"].get("fenetre_dates"):
        d0 = res["chiffres"]["fenetre_dates"][0]
        return f"→ {MOIS[d0.month - 1].upper()} {d0.year}"
    return None


# ---------------------------------------------------------------- courbes

def _points(obs, auj, jours=430):
    pts = []
    for o in obs:
        if o.get("en_stock") == 0:
            continue
        d = dt.date.fromisoformat(o["ts"][:10])
        if 0 <= (auj - d).days <= jours:
            pts.append((d, o["prix"], o.get("source", "direct"), o.get("marchand", "")))
    return sorted(pts)


def _chemin_escalier(serie, X, Y, trou=45):
    """Trait en escalier (le prix reste valable jusqu'au relevé suivant) ; pas de liaison sur un trou."""
    morceaux, prec = [], None
    for d, v in serie:
        x, y = X(d), Y(v)
        if prec is None or (d - prec).days > trou:
            morceaux.append(f"M{x:.1f} {y:.1f}")
        else:
            morceaux.append(f"H{x:.1f}V{y:.1f}")
        prec = d
    return " ".join(morceaux)


def sparkline(res, obs, auj, w=88, h=28):
    serie = [(d, v["prix"]) for d, v in res["serie"].items() if 0 <= (auj - d).days <= 400]
    if len(serie) < 2:
        return '<span class="spark vide" aria-hidden="true"></span>'
    d0, d1 = serie[0][0], max(auj, serie[-1][0])
    lo, hi = min(p for _, p in serie), max(p for _, p in serie)
    marge = max(hi * 0.25 - (hi - lo), 0) / 2  # amplitude mini : un écart de 4 % ne doit pas sembler énorme
    lo, hi = lo - marge, hi + marge
    span = max((d1 - d0).days, 1)
    X = lambda d: 2 + (d - d0).days / span * (w - 6)
    Y = lambda v: 3 + (hi - v) / (hi - lo) * (h - 6)
    chemin = _chemin_escalier(serie, X, Y, trou=10 ** 6)
    xd, yd = X(serie[-1][0]), Y(serie[-1][1])
    return (f'<svg class="spark" viewBox="0 0 {w} {h}" width="{w}" height="{h}" aria-hidden="true">'
            f'<path d="{chemin}" fill="none" stroke="currentColor" stroke-width="1.25"/>'
            f'<circle cx="{xd:.1f}" cy="{yd:.1f}" r="2.4" fill="currentColor"/></svg>')


def _graduations(lo, hi, n=4):
    brut = (hi - lo) / n
    for pas in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000):
        if pas >= brut:
            break
    v = (int(lo // pas) + 1) * pas
    res = []
    while v < hi:
        res.append(v)
        v += pas
    return res


def courbe(ident, res, obs, auj, W, H, suffixe):
    pts = _points(obs, auj)
    if not pts:
        return ""
    c = res["chiffres"]
    ml, mr, mt, mb = 44, 10, 22, 26
    d0 = min(p[0] for p in pts)
    d1 = max(auj, max(p[0] for p in pts))
    fen = c.get("fenetre_dates")
    if fen and (fen[1] - auj).days <= 200:
        d1 = max(d1, fen[1])
    if (d1 - d0).days < 60:
        d0 = d1 - dt.timedelta(days=60)
    prix = [p[1] for p in pts] + ([c["alerte"]] if c.get("alerte") else [])
    lo, hi = min(prix), max(prix)
    pad = max((hi - lo) * 0.14, 8)
    lo, hi = max(0, lo - pad), hi + pad
    span = (d1 - d0).days or 1
    X = lambda d: ml + (d - d0).days / span * (W - ml - mr)
    Y = lambda v: mt + (hi - v) / (hi - lo) * (H - mt - mb)
    hid = f"hachure-{ident}-{suffixe}"
    s = [f'<svg class="courbe-svg courbe-{suffixe}" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="Historique du meilleur prix, du {date_fr(d0)} au {date_fr(min(d1, auj))}">',
         f'<defs><pattern id="{hid}" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
         f'<line x1="0" y1="0" x2="0" y2="6" class="hachure"/></pattern></defs>']

    # fenêtre d'achat conseillée : chaque occurrence des mois de la fenêtre, hachurée
    if c.get("fenetre"):
        debut, fin = c["fenetre"]
        mois = [debut]
        while mois[-1] != fin:
            mois.append(mois[-1] % 12 + 1)
        an = d0.year - 1
        while an <= d1.year:
            a = dt.date(an, debut, 1)
            an_fin = an + (1 if fin < debut else 0)
            b = analyse._fin_de_mois(an_fin, fin)
            x0, x1 = max(a, d0), min(b, d1)
            if x0 < x1:
                s.append(f'<rect x="{X(x0):.1f}" y="{mt}" width="{X(x1) - X(x0):.1f}" height="{H - mt - mb}" '
                         f'fill="url(#{hid})" class="fenetre"/>')
                if (a > auj or (a <= auj <= b)) and abs(X(x0) - X(auj)) > 64 and abs(X(x1) - X(auj)) > 64:
                    if X(x0) + 60 > W:
                        s.append(f'<text x="{X(x1):.1f}" y="{mt - 8}" text-anchor="end" class="t-fen">fenêtre</text>')
                    else:
                        s.append(f'<text x="{X(x0) + 3:.1f}" y="{mt - 8}" class="t-fen">fenêtre</text>')
            an += 1

    # axe des prix : quelques repères, pas de grille lourde
    for v in _graduations(lo, hi):
        y = Y(v)
        s.append(f'<line x1="{ml - 4}" x2="{ml}" y1="{y:.1f}" y2="{y:.1f}" class="tic"/>'
                 f'<text x="{ml - 7}" y="{y + 3.5:.1f}" text-anchor="end" class="t-axe">{v:.0f}</text>')
    s.append(f'<line x1="{ml}" x2="{ml}" y1="{mt}" y2="{H - mb}" class="axe"/>'
             f'<line x1="{ml}" x2="{W - mr}" y1="{H - mb}" y2="{H - mb}" class="axe"/>')

    # mois
    m, vus, dernier_x, dernier_l = dt.date(d0.year, d0.month, 1), 0, -99, 0
    while m <= d1:
        x = X(m)
        if m >= d0:
            s.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{H - mb}" y2="{H - mb + 4}" class="tic"/>')
            lab = MOIS_COURT[m.month - 1]
            if m.month == 1 or vus == 0:
                lab += f" {m.year % 100:02d}"
            if x - dernier_x >= dernier_l * 6.4 + 10 and x + len(lab) * 6.4 < W:
                s.append(f'<text x="{x + 2:.1f}" y="{H - mb + 16}" class="t-axe">{e(lab)}</text>')
                dernier_x, dernier_l = x, len(lab)
                vus += 1
        m = dt.date(m.year + (m.month == 12), m.month % 12 + 1, 1)

    # alerte : pointillé
    if c.get("alerte") and lo < c["alerte"] < hi:
        ya = Y(c["alerte"])
        s.append(f'<line x1="{ml}" x2="{W - mr}" y1="{ya:.1f}" y2="{ya:.1f}" class="alerte"/>'
                 f'<text x="{W - mr}" y="{ya - 5:.1f}" text-anchor="end" class="t-alerte">alerte {c["alerte"]:.0f} €</text>')

    # aujourd'hui
    if auj < d1:
        xt = X(auj)
        s.append(f'<line x1="{xt:.1f}" x2="{xt:.1f}" y1="{mt}" y2="{H - mb}" class="auj"/>'
                 f'<text x="{xt:.1f}" y="{mt - 8}" text-anchor="middle" class="t-axe">auj.</text>')

    # meilleur prix du jour : trait d'encre en escalier, prolongé jusqu'à aujourd'hui s'il est récent
    serie = [(d, v["prix"]) for d, v in res["serie"].items() if d >= d0 and d <= auj]
    if serie:
        chemin = _chemin_escalier(serie, X, Y)
        if (auj - serie[-1][0]).days <= 3:
            chemin += f" H{X(auj):.1f}"
        s.append(f'<path d="{chemin}" class="trait"/>')

    # relevés : plein = direct, creux = archive, carré = saisie manuelle
    donnees = []
    for d, p, src, marchand in pts:
        x, y = X(d), Y(p)
        if src == "archive":
            s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" class="pt-creux"/>')
        elif src == "manuel":
            s.append(f'<rect x="{x - 3.2:.1f}" y="{y - 3.2:.1f}" width="6.4" height="6.4" class="pt-plein"/>')
        else:
            s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" class="pt-plein"/>')
        donnees.append([round(x / W * 100, 2), round(y / H * 100, 2),
                        f"{date_fr(d)} · {euros(p)} · {marchand} · {SOURCES.get(src, src)}"])
    s.append(f'<circle r="6" class="curseur" cx="-10" cy="-10"/>')
    s.append("</svg>")
    return "".join(s), donnees


def figure_courbe(art, res, obs, auj):
    etroite = courbe(art["id"], res, obs, auj, 360, 220, "etroite")
    if not etroite:
        return '<p class="vide-txt">Pas encore de courbe : aucun prix en stock relevé.</p>'
    large = courbe(art["id"], res, obs, auj, 720, 270, "large")
    pts = json.dumps({"etroite": etroite[1], "large": large[1]}, ensure_ascii=False, separators=(",", ":"))
    return (f'<figure class="courbe" data-points="{e(pts)}">{etroite[0]}{large[0]}'
            '<figcaption class="legende"><span class="k-plein">relevé direct</span>'
            '<span class="k-creux">archive web</span><span class="k-carre">saisie</span>'
            '<span class="k-hach">fenêtre conseillée</span><span class="k-alerte">alerte</span></figcaption>'
            '<output class="lecture" aria-live="polite">Touche la courbe pour lire un relevé.</output></figure>')


# ---------------------------------------------------------------- morceaux de page

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700'
         '&family=JetBrains+Mono:wght@400;500;700&display=swap">')

FILTRE_ENCRE = ('<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false">'
                '<filter id="encre" x="-5%" y="-10%" width="110%" height="120%">'
                '<feTurbulence type="fractalNoise" baseFrequency="0.04" numOctaves="2" seed="7" result="ondes"/>'
                '<feDisplacementMap in="SourceGraphic" in2="ondes" scale="2.5" xChannelSelector="R" '
                'yChannelSelector="G" result="bave"/>'
                '<feTurbulence type="fractalNoise" baseFrequency="0.7" numOctaves="2" seed="3" result="grain"/>'
                '<feColorMatrix in="grain" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -7 5.1" '
                'result="trous"/><feComposite in="bave" in2="trous" operator="in"/></filter></svg>')


def page(titre, corps, prefixe="", description="", classe=""):
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#F3EFE6" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#141312" media="(prefers-color-scheme: dark)">
<meta name="description" content="{e(description or 'Achète, attends ou méfie-toi : verdicts tirés de vrais prix relevés.')}">
<title>{e(titre)}</title>
{FONTS}
<link rel="stylesheet" href="{prefixe}style.css?v={VERSION}">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect x='3' y='3' width='26' height='26' fill='none' stroke='%23B3261E' stroke-width='3'/%3E%3Ctext x='16' y='22' font-family='monospace' font-weight='700' font-size='16' text-anchor='middle' fill='%23B3261E'%3E€%3C/text%3E%3C/svg%3E">
</head>
<body class="{classe}">
{FILTRE_ENCRE}
<div class="page">
{corps}
</div>
<script src="{prefixe}site.js?v={VERSION}" defer></script>
</body>
</html>
"""


def entete(prefixe, quand, accueil=False):
    marque = '<span class="marque">Prix<b>Juste</b></span>'
    lien = marque if accueil else f'<a class="marque-lien" href="{prefixe}index.html">{marque}</a>'
    return (f'<header class="tete">{lien}<p class="releve">relevé du {e(quand)}</p></header>'
            '<div class="perfore" aria-hidden="true"></div>')


def pied(prefixe):
    return ('<div class="perfore" aria-hidden="true"></div><footer class="pied">'
            f'<p>Verdicts calculés uniquement à partir de prix réellement relevés : en direct, dans les archives '
            f'publiques du web, ou saisis à la main. L\'outil s\'annonce comme robot (PrixJuste/{VERSION}), '
            'respecte robots.txt, lit chaque page une fois par jour au plus, et ne contourne jamais un site qui refuse.</p>'
            f'<p><a href="https://github.com/{DEPOT_GITHUB}">code et données</a></p></footer>')


def etat_article(art, res):
    if art.get("statut") == "a_identifier":
        return "attente"
    if art.get("achat"):
        return "paye"
    return res["verdict"][0]


def phrase_achat(res):
    pr = res["protection"]
    txt = f"Payé {euros(pr['prix'])} chez {pr['marchand']} le {date_fr(pr['date'])}. "
    b = res.get("baisse_apres_achat")
    if b:
        return txt + (f"Il a baissé de {euros(b['ecart'])} chez {b['marchand']} : retourne-le et rachète-le, ou demande "
                      f"un geste commercial, avant le {date_fr(pr['fin_retractation'])}.")
    if pr["en_retractation"]:
        return txt + f"Prix surveillé jusqu'au {date_fr(pr['fin_retractation'])} (rétractation)."
    return txt + f"Garantie légale de conformité jusqu'au {date_fr(pr['fin_garantie'])}."


def sous_tampon_code(code, res):
    if code == "attendre":
        return sous_tampon(res)
    if code == "paye":
        return f"{res['protection']['date']:%d/%m/%Y}"
    return None


# ---------------------------------------------------------------- le comptoir

def ligne_comptoir(art, res, obs, auj):
    code = etat_article(art, res)
    href = f'a/{e(art["id"])}.html'
    variante = art.get("variante") or art.get("reference") or ""
    if code == "attente":
        prix = '<span class="prix-ligne nul">—</span><span class="chez">pas encore de prix</span>'
        phrase = "En attente d'identification : ajoute un lien marchand à la demande pour le suivre tout de suite."
        spark = '<span class="spark vide" aria-hidden="true"></span>'
    else:
        act = res.get("actuel")
        prix = (f'<span class="prix-ligne">{euros(act["prix"])}</span><span class="chez">chez {e(act.get("marchand"))}</span>'
                if act else '<span class="prix-ligne nul">—</span><span class="chez">aucun prix lisible ces 3 jours</span>')
        phrase = phrase_achat(res) if code == "paye" else res["verdict"][2]
        spark = sparkline(res, obs, auj)
    return (f'<li><a class="etiquette" href="{href}">'
            f'<span class="nom">{e(art["nom"])}</span>'
            f'<span class="var">{e(variante)}</span>'
            f'<span class="prix-bloc">{prix}</span>'
            f'<span class="spark-bloc">{spark}</span>'
            f'<span class="tampon-bloc">{tampon(code, sous_tampon_code(code, res), "petit")}</span>'
            f'<span class="phrase">{e(phrase)}</span>'
            '</a></li>')


def comptoir(lignes, quand, prochain=None):
    corps = [entete("", quand, accueil=True),
             '<main>',
             '<form class="demande" action="ajouter.html" method="get">'
             '<h1><label for="objet">Qu\'est-ce que tu veux acheter&nbsp;?</label></h1>'
             '<div class="champ-ligne"><input id="objet" name="objet" type="text" autocomplete="off" required '
             'placeholder="ex. parka McMurdo, taille L"><button type="submit">Suivre</button></div></form>']
    if prochain:
        d, txt = prochain
        corps.append(f'<p class="prochain"><span>Prochain moment</span> {e(txt)} — {date_fr(d)} · '
                     '<a href="agenda.ics">ajouter à mon agenda</a></p>')
    if lignes:
        corps.append('<h2 class="rubrique">Au comptoir</h2><ol class="etiquettes">' + "".join(lignes) + "</ol>")
    else:
        corps.append('<p class="vide-txt">Rien au comptoir pour l\'instant.</p>')
    corps.append("</main>")
    corps.append(pied(""))
    return page("PrixJuste — le comptoir", "".join(corps), classe="p-comptoir")


# ---------------------------------------------------------------- la fiche

def _ligne_ticket(lbl, val, detail=None):
    d = f'<dd class="detail">{detail}</dd>' if detail else ""
    return f'<div class="t-ligne"><dt>{lbl}</dt><dd class="val">{val}</dd>{d}</div>'


def ticket(art, res):
    c = res["chiffres"]
    L = []
    if c.get("min_12m") is not None:
        det = [date_fr(c["min_12m_date"])]
        if c.get("min_12m_marchand"):
            det.append(e(c["min_12m_marchand"]))
        if c.get("min_12m_dispo") is not None:
            det.append(f'{c["min_12m_dispo"]} taille(s) dispo')
        L.append(_ligne_ticket("Plus bas sur 12 mois", euros(c["min_12m"]), " · ".join(det)))
    else:
        L.append(_ligne_ticket("Plus bas sur 12 mois", "—", "aucun relevé"))
    if c.get("meme_periode_an_dernier") is not None:
        L.append(_ligne_ticket("Même période l'an dernier", euros(c["meme_periode_an_dernier"]), "± 3 semaines"))
    else:
        L.append(_ligne_ticket("Même période l'an dernier", "—", "pas de relevé à cette période"))
    if c.get("fenetre"):
        debut, fin = c["fenetre"]
        nom = MOIS[debut - 1] + ("" if debut == fin else "–" + MOIS[fin - 1])
        a, b = c["fenetre_dates"]
        L.append(_ligne_ticket("Fenêtre d'achat conseillée", e(nom),
                               f'du {date_fr(a)} au {date_fr(b)} · vers {euros(c["meilleur_mois_prix"], False)}'))
    else:
        L.append(_ligne_ticket("Fenêtre d'achat conseillée", "—", "il faut des prix sur au moins 3 mois différents"))
    if c.get("alerte"):
        L.append(_ligne_ticket("Alerte", f'sous {euros(c["alerte"], False)}', "achète si le prix passe dessous"))
    else:
        L.append(_ligne_ticket("Alerte", "—", "pas calculée sur moins de 5 jours de prix"))
    L.append(_ligne_ticket("À acheter avant", date_fr(res["limite"]),
                           "date choisie" if art.get("acheter_avant") else f"urgence : {e(art.get('urgence', 'pas_urgent').replace('_', ' '))}"))
    if art.get("budget_max"):
        L.append(_ligne_ticket("Budget", euros(art["budget_max"], False)))
    pr = res.get("protection")
    if pr:
        L.append(_ligne_ticket("Payé", euros(pr["prix"]), f'{e(pr["marchand"])} · {date_fr(pr["date"])}'))
        L.append(_ligne_ticket("Rétractation", f'jusqu\'au {date_fr(pr["fin_retractation"])}',
                               "14 jours pour renvoyer un achat en ligne (depuis la réception)"))
        L.append(_ligne_ticket("Garantie légale", f'jusqu\'au {date_fr(pr["fin_garantie"])}',
                               "2 ans de garantie de conformité, à demander au vendeur"))
    n = c.get("n_releves", 0)
    L.append(_ligne_ticket("Fiabilité", e(c.get("fiabilite", "faible")),
                           f'{n} jour{"s" if n > 1 else ""} de prix sur 12 mois · {c.get("n_sources", 0)} source(s)'))
    return '<dl class="ticket">' + "".join(L) + "</dl>"


def bloc_promos(res):
    if not res["promos"]:
        return ('<p class="vide-txt">Aucun prix barré relevé ces 3 derniers jours. Quand un marchand affiche une '
                'réduction, elle est comparée à ce qu\'il pratiquait vraiment dans les 30 jours d\'avant.</p>')
    L = []
    for pr in res["promos"]:
        etat = "trompeuse" if pr["douteuse"] else "conforme"
        txt = pr.get("alerte") or pr.get("contexte") or "Rien d'anormal avec les prix connus de ce marchand."
        if pr.get("alerte") and pr.get("contexte"):
            txt = pr["alerte"] + " " + pr["contexte"]
        L.append(f'<li class="promo {"douteuse" if pr["douteuse"] else ""}"><p class="promo-tete">'
                 f'<span>{e(pr["marchand"])}</span><span class="promo-prix">{euros(pr["prix"])} '
                 f'<s>{euros(pr["barre"])}</s> <span class="remise">{pct(pr["remise_affichee"])}</span></span></p>'
                 f'<p class="promo-etat"><b>{etat}</b> — {e(txt)}</p></li>')
    return '<ul class="promos">' + "".join(L) + "</ul>"


def bloc_marchands(art, obs, journal):
    dernier_essai, dernier_prix = {}, {}
    for j in journal:
        if j["action"] == "direct":
            dernier_essai[j["lien"]] = j
    for o in obs:
        dernier_prix[o["lien"]] = o
    L = []

    def ligne(nom, url, detail, statut, classe, o):
        if o:
            livr = o.get("livraison")
            frais = ("" if livr is None else " · livraison offerte" if livr == 0
                     else f" · +{euros(livr)} livraison")
            rupture = " · rupture" if o.get("en_stock") == 0 else ""
            prix = f'<span class="m-prix">{euros(o["prix"])}<small>{date_fr(o["ts"])}{rupture}{frais}</small></span>'
        else:
            prix = '<span class="m-prix nul">—</span>'
        if url and hors_ue(url):
            detail = " · ".join(x for x in (detail, "hors UE : droits et TVA à l'import possibles") if x)
        nom_html = f'<a href="{e(url)}" rel="noopener nofollow">{e(nom)}</a>' if url else e(nom)
        return (f'<li><span class="m-nom">{nom_html}</span>{prix}'
                f'<span class="m-det">{e(detail)}</span><span class="m-statut s-{classe}">{e(statut)}</span></li>')

    for lien in art.get("liens", []):
        k = cle(lien)
        j = dernier_essai.get(k)
        if j:
            statut, classe = LECTURE.get(j["statut"], (j["statut"], "vide"))
            if j["statut"] == "bloqué":
                statut = "bloqué — " + j["detail"].replace(" (ou le site bloque les robots)", "")
        else:
            statut, classe = "pas encore lu", "vide"
        taille = lien.get("taille")
        if taille and taille.replace(".", ",") in (lien.get("coloris") or "").replace(".", ","):
            taille = None  # déjà dit dans le coloris (« Jaune · 39,5 »)
        detail = " · ".join(x for x in (lien.get("coloris"), taille and f"taille {taille}") if x and x.strip() != "?")
        o = dernier_prix.get(k)
        cout = (o.get("en_stock") == 0, o["prix"] + (o.get("livraison") or 0)) if o else (True, float("inf"))
        L.append((cout, ligne(lien.get("marchand", "?"), lien["url"], detail, statut, classe, o)))
    L = [x for _, x in sorted(L, key=lambda t: t[0])]  # du coût réel le plus bas au plus haut
    manuels = {}
    for o in obs:
        if o.get("source") == "manuel":
            manuels[o.get("marchand")] = o
    for m, o in manuels.items():
        L.append(ligne(m, None, "prix vu et saisi à la main", "saisie manuelle", "archive", o))
    H = [ligne(lien.get("marchand", "?"), lien["url"], lien.get("coloris", ""), "archives seulement",
               "archive", dernier_prix.get(cle(lien))) for lien in art.get("liens_historiques", [])]
    res = '<ul class="marchands">' + "".join(L) + "</ul>"
    if H:
        res += (f'<details class="archives"><summary>{len(H)} page{"s" if len(H) > 1 else ""} lue{"s" if len(H) > 1 else ""} '
                f'dans les archives seulement <i>(anciens coloris, anciennes références)</i></summary>'
                f'<ul class="marchands">{"".join(H)}</ul></details>')
    return res


def form_prix(art):
    return (f'<details class="vu"><summary>J\'ai vu un prix</summary>'
            f'<form class="form-prix" data-article="{e(art["id"])}" data-nom="{e(art["nom"])}" data-depot="{e(DEPOT_GITHUB)}">'
            '<p class="aide">En magasin, dans une pub, ou sur un site que l\'outil ne peut pas lire. '
            'Le bouton ouvre une demande pré-remplie sur GitHub : il reste à l\'envoyer.</p>'
            '<div class="grille2"><label>Prix vu<input name="prix" inputmode="decimal" required placeholder="199,90"></label>'
            '<label>Prix barré <i>si affiché</i><input name="barre" inputmode="decimal" placeholder="230"></label></div>'
            '<div class="grille2"><label>Où<input name="marchand" placeholder="magasin, site…"></label>'
            '<label>Le<input name="date" type="date"></label></div>'
            '<label class="case"><input name="rupture" type="checkbox"> en rupture dans ma taille</label>'
            '<button type="submit">Envoyer ce prix →</button></form></details>')


def fiche(art, res, obs, journal, quand, auj):
    code = etat_article(art, res)
    act = res.get("actuel")
    sous = sous_tampon_code(code, res)
    variante = " · ".join(x for x in (art.get("reference"), art.get("variante")) if x)
    corps = [entete("../", quand), '<main class="fiche">',
             '<a class="retour" href="../index.html">← Le comptoir</a>',
             f'<h1 class="nom-fiche">{e(art["nom"])}</h1>',
             f'<p class="var-fiche">{e(variante)}</p>' if variante else ""]

    if code == "attente":
        num = art.get("issue")
        lien_issue = (f'<a href="https://github.com/{DEPOT_GITHUB}/issues/{num}">la demande n°{num}</a>' if num else "la demande")
        corps.append(f'<section class="decision"><div class="tampon-zone">{tampon("attente", None, "grand")}</div>'
                     f'<p class="verdict-titre">En attente d\'identification</p>'
                     f'<p class="verdict-expli">Demande : « {e(art.get("demande", art["nom"]))} ». Claude doit d\'abord '
                     f'trouver la référence exacte et des pages marchands lisibles. Pour aller plus vite, ajoute un lien '
                     f'produit dans {lien_issue} : le suivi démarre au relevé suivant.</p></section>')
        corps += ["</main>", pied("../")]
        return page(f"{art['nom']} — PrixJuste", "".join(corps), "../", classe="p-fiche")

    titre, expli = res["verdict"][1], res["verdict"][2]
    if code == "paye":
        titre, expli = "Acheté", phrase_achat(res)
    if act:
        barre = ""
        promo = next((p for p in res["promos"] if p["ts"] == act["ts"] and p["marchand"] == act.get("marchand")), None)
        if promo and not promo["douteuse"]:  # ancien prix barré affiché seulement s'il est réel
            barre = f'<s class="barre">{euros(promo["barre"])}</s> <span class="remise">{pct(promo["remise_affichee"])}</span>'
        prix_html = (f'<p class="lbl">Meilleur prix actuel</p>'
                     f'<p class="prix-geant">{euros(act["prix"])}</p>'
                     f'<p class="ou">{barre}{" · " if barre else ""}chez {e(act.get("marchand"))} · '
                     f'{SOURCES.get(act.get("source"), "")} du {date_fr(act["ts"])}</p>')
    else:
        prix_html = ('<p class="lbl">Meilleur prix actuel</p><p class="prix-geant nul">—</p>'
                     '<p class="ou">aucun site lisible ces 3 derniers jours</p>')
    notes = "".join(f"<li>{e(n)}</li>" for n in res["notes"])
    corps.append(f'<section class="decision">'
                 f'<div class="prix-zone">{prix_html}</div>'
                 f'<div class="tampon-zone">{tampon(code, sous, "grand")}</div>'
                 f'<div class="verdict-zone"><p class="verdict-titre">{e(titre)}</p>'
                 f'<p class="verdict-expli">{e(expli)}</p>'
                 + (f'<ul class="notes">{notes}</ul>' if notes else "") + '</div></section>')
    corps.append('<h2 class="rubrique">Le ticket</h2>' + ticket(art, res))
    corps.append('<h2 class="rubrique">La courbe</h2>' + figure_courbe(art, res, obs, auj))
    corps.append('<h2 class="rubrique">Contrôle des promos</h2>' + bloc_promos(res))
    corps.append('<h2 class="rubrique">Où c\'est relevé</h2>' + bloc_marchands(art, obs, journal))
    corps.append(f'<p class="repere"><b>Repère de saison</b> (règle générale, pas une donnée sur cet article) : {e(res["repere"])}</p>')
    corps.append(form_prix(art) + ("" if art.get("achat") else form_achat(art, act)) + carte(art, res, code, auj))
    corps += ["</main>", pied("../")]
    return page(f"{art['nom']} — PrixJuste", "".join(corps), "../",
                description=f"{TAMPONS[code][1][0]} — {titre}", classe="p-fiche")


def form_achat(art, act):
    return (f'<details class="vu achat"><summary>Je l\'ai acheté</summary>'
            f'<form class="form-achat" data-article="{e(art["id"])}" data-nom="{e(art["nom"])}" data-depot="{e(DEPOT_GITHUB)}">'
            '<p class="aide">Le prix reste surveillé pendant les 14 jours de rétractation : s\'il baisse nettement, tu es '
            'prévenu, pour renvoyer et racheter ou demander un geste. La fin de la garantie légale est notée.</p>'
            f'<div class="grille2"><label>Prix payé<input name="prix" inputmode="decimal" required '
            f'value="{e(f"{act["prix"]:.2f}".replace(".", ",")) if act else ""}"></label>'
            f'<label>Où<input name="marchand" value="{e(act.get("marchand", "")) if act else ""}"></label></div>'
            '<label>Le<input name="date" type="date"></label>'
            '<button type="submit">Noter l\'achat →</button></form></details>')


def carte(art, res, code, auj):
    """Bouton « Carte 9:16 » : image verticale factuelle (prix, historique, tampon, sources), dessinée
    dans le navigateur, sans service tiers ni nom de personne."""
    act = res.get("actuel")
    if not act:
        return ""
    c = res["chiffres"]
    promo = next((p for p in res["promos"] if p["ts"] == act["ts"] and p["marchand"] == act.get("marchand")), None)
    donnees = {
        "nom": art["nom"], "variante": art.get("variante") or "", "prix": euros(act["prix"]),
        "chez": act.get("marchand"), "le": date_fr(act["ts"]),
        "tampon": TAMPONS[code][1], "classe": TAMPONS[code][0], "sous": sous_tampon_code(code, res) or "",
        "titre": res["verdict"][1] if code != "paye" else "Acheté", "explication": res["verdict"][2],
        "barre": euros(promo["barre"]) if promo else "", "remise": pct(promo["remise_affichee"]) if promo else "",
        "douteuse": bool(promo and promo["douteuse"]),
        "min": euros(c["min_12m"]) if c.get("min_12m") is not None else "",
        "min_le": date_fr(c["min_12m_date"]) if c.get("min_12m_date") else "",
        "serie": [[(d - auj).days, v["prix"], v["source"]] for d, v in res["serie"].items() if 0 <= (auj - d).days <= 400],
        "fiabilite": f'fiabilité {c.get("fiabilite")} · {c.get("n_releves", 0)} jours de prix · {c.get("n_sources", 0)} sources',
        "date": date_fr(auj),
    }
    return (f'<div class="carte-zone"><button type="button" class="bouton-carte" '
            f'data-carte="{e(json.dumps(donnees, ensure_ascii=False, separators=(",", ":")))}">Carte 9:16</button>'
            '<p class="aide">Image verticale à partager : le prix, l\'historique réel et le tampon, avec la date.</p></div>')


# ---------------------------------------------------------------- ajouter

def ajouter(quand, profil=None):
    prof = json.dumps(profil or {}, ensure_ascii=False, separators=(",", ":"))
    corps = [entete("", quand), '<main class="ajouter">',
             '<a class="retour" href="index.html">← Le comptoir</a>',
             f'<form class="form-ajout" data-depot="{e(DEPOT_GITHUB)}" data-profil="{e(prof)}">',
             '<h1><label for="a-objet">Qu\'est-ce que tu veux acheter&nbsp;?</label></h1>',
             '<input id="a-objet" name="objet" type="text" required autocomplete="off" '
             'placeholder="ex. Timberland 6-Inch Premium jaune">',
             '<div class="grille2"><label>Taille, pointure<input name="taille" placeholder="40, L, 32/34…"></label>'
             '<label>Coloris<input name="coloris" placeholder="jaune, noir…"></label></div>',
             '<p class="aide conseil-taille" hidden></p>',
             '<fieldset class="urgence"><legend>C\'est pour quand ?</legend>'
             '<label><input type="radio" name="urgence" value="urgent"><span>urgent<small>7 jours</small></span></label>'
             '<label><input type="radio" name="urgence" value="bientot"><span>bientôt<small>45 jours</small></span></label>'
             '<label><input type="radio" name="urgence" value="pas_urgent" checked><span>pas urgent<small>1 an</small></span></label>'
             '</fieldset>',
             '<div class="grille2"><label>Avant le<input name="avant" type="date"></label>'
             '<label>Budget max <i>€</i><input name="budget" inputmode="decimal" placeholder="250"></label></div>',
             '<label>Liens produit <i>si tu en as, un par ligne</i>'
             '<textarea name="liens" rows="3" placeholder="https://…"></textarea></label>',
             '<p class="aide">Avec des liens, le suivi démarre tout de suite (sans IA). Sans lien, la demande attend '
             'que Claude identifie la référence exacte et des pages marchands lisibles.</p>',
             '<button type="submit">Ouvrir la demande sur GitHub →</button>',
             '<p class="aide">Tu arrives sur GitHub avec la demande déjà écrite : il reste à appuyer sur '
             '« Create ». Aucun mot de passe ni jeton n\'est stocké ici.</p>',
             '</form></main>', pied("")]
    return page("Ajouter — PrixJuste", "".join(corps), classe="p-ajouter")


# ---------------------------------------------------------------- data.json

def _json(x):
    if isinstance(x, (dt.date, dt.datetime)):
        return x.isoformat()
    if isinstance(x, tuple):
        return list(x)
    raise TypeError(type(x))


def export(art, res, code):
    c = {k: v for k, v in res["chiffres"].items()}
    return {
        "id": art["id"], "nom": art["nom"], "variante": art.get("variante"), "statut": art.get("statut", "suivi"),
        "tampon": code, "titre": res["verdict"][1], "explication": res["verdict"][2],
        "jusqu_a": res.get("jusqu_a"), "limite": res["limite"], "notes": res["notes"],
        "actuel": res.get("actuel"), "chiffres": c, "promos": res["promos"],
        "serie": [[d.isoformat(), v["prix"], v["source"], v["marchand"]] for d, v in res["serie"].items()],
    }


# ---------------------------------------------------------------- construction

def construire(depot=None, sortie=Path("site"), aujourdhui=None, quand=None):
    depot = depot or Depot()
    auj = aujourdhui or dt.date.fromisoformat(maintenant()[:10])
    if quand is None:
        m = maintenant()
        quand = f"{date_fr(m[:10])} à {m[11:16]}"
    sortie = Path(sortie)
    if sortie.exists():
        shutil.rmtree(sortie)
    (sortie / "a").mkdir(parents=True)
    for f in ("style.css", "site.js"):
        shutil.copy(STATIQUE / f, sortie / f)
    (sortie / ".nojekyll").write_text("")

    lignes, exports, pour_agenda = [], [], []
    for art in depot.articles():
        obs = analyse.filtrer_obs(art, depot.releves(art["id"]))
        res = analyse.analyser(art, obs, auj)
        pour_agenda.append((art, res))
        code = etat_article(art, res)
        jusqu = res.get("jusqu_a") or dt.date.max
        lignes.append(((ORDRE[code], jusqu, art["nom"].lower()), ligne_comptoir(art, res, obs, auj)))
        (sortie / "a" / f"{art['id']}.html").write_text(
            fiche(art, res, obs, depot.journal(art["id"]), quand, auj), encoding="utf-8")
        exports.append(export(art, res, code))
    lignes.sort(key=lambda x: x[0])
    proprio, nom_depot = DEPOT_GITHUB.split("/")
    url_site = os.environ.get("PAGES_URL") or f"https://{proprio.lower()}.github.io/{nom_depot}"
    (sortie / "agenda.ics").write_text(agenda.ics(pour_agenda, auj, url_site), encoding="utf-8", newline="")
    (sortie / "index.html").write_text(comptoir([l for _, l in lignes], quand, agenda.prochain(pour_agenda, auj)),
                                       encoding="utf-8")
    profil = ajout.charger_profil(depot)
    (sortie / "ajouter.html").write_text(ajouter(quand, profil), encoding="utf-8")
    (sortie / "data.json").write_text(json.dumps({"genere": maintenant(), "articles": exports}, default=_json,
                                                 ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Site : {sortie}/ ({len(exports)} article(s))")
    return sortie
