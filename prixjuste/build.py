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
import urllib.parse
from pathlib import Path

from . import VERSION, agenda, ajout, analyse, dossiers, enquete, etranger, plan
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
    "choisir": ("attends", ["À CHOISIR"]),
    "paye": ("donnees", ["PAYÉ"]),
}
ORDRE = {"choisir": -1, "acheter": 0, "bidon": 1, "surveiller": 2, "attendre": 3, "donnees": 4, "attente": 5, "paye": 6}
SOURCES = {"direct": "relevé en direct", "archive": "archive web", "manuel": "saisie manuelle",
           "historique": "courbe d'un comparateur, lue lors d'une enquête", "navigateur": "vu en naviguant (enquête)"}
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


# ---------------------------------------------------------------- météo des prix

def jauge(res, auj):
    """Où se situe le prix du jour entre le plus bas et le plus haut des 12 derniers mois."""
    act = res.get("actuel")
    prix = [v["prix"] for d, v in res["serie"].items() if 0 <= (auj - d).days <= 365]
    if not act or len(prix) < 2 or max(prix) - min(prix) < 1:
        return None
    lo, hi = min(prix), max(prix)
    pos = min(max((act["prix"] - lo) / (hi - lo), 0), 1)
    if pos <= .25:
        niveau, classe = "bas", "bas"
    elif pos <= .6:
        niveau, classe = "dans la moyenne", "moyen"
    else:
        niveau, classe = "plutôt élevé", "haut"
    return {"pos": pos, "lo": lo, "hi": hi, "niveau": niveau, "classe": classe}


def bloc_jauge(j, compact=False):
    if not j:
        if compact:
            return ""
        return ('<section class="carte jauge"><p class="carte-lbl">Ce prix est</p>'
                '<p class="niveau n-vide">pas encore situable</p>'
                '<p class="aide">Il faut au moins deux jours de prix différents sur 12 mois.</p></section>')
    barre = (f'<span class="jauge-barre" aria-hidden="true"><i style="left:{j["pos"] * 100:.1f}%"></i></span>')
    if compact:
        return f'<span class="jauge-mini j-{j["classe"]}">{barre}<b>{e(j["niveau"])}</b></span>'
    return (f'<section class="carte jauge"><div class="jauge-tete"><p class="carte-lbl">Ce prix est</p>'
            f'<p class="aide">sur 12 mois</p></div>'
            f'<p class="niveau n-{j["classe"]}">{e(j["niveau"])}</p>{barre}'
            f'<p class="jauge-bornes"><span>{euros(j["lo"], False)} · plus bas</span>'
            f'<span>{euros(j["hi"], False)} · plus haut</span></p></section>')


def prevision_mois(res, auj, n=4):
    """Les n prochains mois, avec le prix médian relevé ces mois-là les années passées."""
    par_mois = {}
    for d, v in res["serie"].items():
        if (auj - d).days > 30:
            par_mois.setdefault(d.month, []).append(v["prix"])
    tuiles = []
    for i in range(1, n + 1):
        m = (auj.month - 1 + i) % 12 + 1
        vals = sorted(par_mois.get(m, []))
        med = vals[len(vals) // 2] if len(vals) >= 2 else None  # un seul prix ne fait pas une prévision
        tuiles.append({"mois": MOIS_COURT[m - 1], "prix": med})
    connus = [t for t in tuiles if t["prix"] is not None]
    if connus:
        min(connus, key=lambda t: t["prix"])["meilleur"] = True
    return tuiles


TITRES_PREVISION = {"acheter": "Bon moment pour acheter", "surveiller": "Prix à surveiller",
                    "bidon": "Promo trompeuse", "donnees": "Pas encore de prévision", "paye": "Acheté"}


def bloc_prevision(art, res, code, auj):
    titre = TITRES_PREVISION.get(code, res["verdict"][1])
    if code == "attendre":
        titre = res["verdict"][1].replace("Attends", "Baisse probable en")
    expli = phrase_achat(res) if code == "paye" else res["verdict"][2]
    tuiles = prevision_mois(res, auj)
    tu = ""
    if any(t["prix"] is not None for t in tuiles) and code != "paye":
        tu = '<ol class="mois">' + "".join(
            f'<li class="{"meilleur" if t.get("meilleur") else ""}"><span>{e(t["mois"])}</span>'
            f'<b>{"~" + str(round(t["prix"])) if t["prix"] is not None else "—"}</b></li>' for t in tuiles) + "</ol>"
    c = res["chiffres"]
    n = c.get("n_releves", 0)
    notes = "".join(f"<li>{e(x)}</li>" for x in res["notes"])
    return (f'<section class="carte prevision v-{e(code)}"><div class="prev-tete"><p class="carte-lbl">Prévision</p>'
            f'{tampon(code, sous_tampon_code(code, res), "grand")}</div>'
            f'<p class="prev-titre">{e(titre)}</p><p class="prev-expli">{e(expli)}</p>{tu}'
            + (f'<ul class="notes">{notes}</ul>' if notes else "")
            + f'<p class="prev-fiab">Prix médians relevés les années passées · fiabilité {e(c.get("fiabilite", "faible"))} '
            f'({n} jour{"s" if n > 1 else ""} de prix)</p></section>')


def vignette(art, classe="vignette"):
    img = art.get("image") or next((c.get("image") for c in art.get("candidats") or [] if c.get("image")), None)
    if img:
        return (f'<span class="{classe}"><img src="{e(img)}" alt="" referrerpolicy="no-referrer" '
                'onerror="this.remove()"></span>')
    initiale = (art.get("nom") or "?").strip()[:1].upper()
    return f'<span class="{classe} sans-photo" aria-hidden="true">{e(initiale)}</span>'


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
    """Une seule chose à lire : le meilleur prix de chaque jour sur les 12 derniers mois.
    Le prix d'aujourd'hui et le plus bas sont écrits sur la courbe ; l'alerte est une ligne. Rien d'autre."""
    c = res["chiffres"]
    jours = sorted((d, v) for d, v in res["serie"].items() if 0 <= (auj - d).days <= 365)
    if not jours:
        return ""
    fs = 12.5 if suffixe == "etroite" else 13
    ml, mr, mt, mb = 50, 10, 30, 30
    d0, d1 = auj - dt.timedelta(days=365), auj  # toujours 12 mois pleins : chaque point tombe à son vrai mois
    span = (d1 - d0).days or 1
    prix = [v["prix"] for _, v in jours] + ([c["alerte"]] if c.get("alerte") else [])
    lo, hi = min(prix), max(prix)
    pad = max((hi - lo) * 0.18, hi * 0.04)
    lo, hi = max(0, lo - pad), hi + pad
    X = lambda d: ml + (d - d0).days / span * (W - ml - mr)
    Y = lambda v: mt + (hi - v) / (hi - lo) * (H - mt - mb)
    largeur = lambda t: len(t) * fs * 0.6

    s = [f'<svg class="courbe-svg courbe-{suffixe}" viewBox="0 0 {W} {H}" role="img" '
         f'aria-label="Meilleur prix de chaque jour, du {date_fr(d0)} au {date_fr(d1)}" style="--fs:{fs}px">']

    # repères de prix : 3 lignes fines, la valeur dans la marge de gauche
    for v in _graduations(lo, hi, 3):
        y = Y(v)
        s.append(f'<line x1="{ml}" x2="{W - mr}" y1="{y:.1f}" y2="{y:.1f}" class="grille"/>'
                 f'<text x="{ml - 8}" y="{y + fs * 0.35:.1f}" text-anchor="end" class="t-axe">{v:.0f} €</text>')

    # mois : un sur deux si la place manque ; l'année sur janvier et sur le premier mois
    m, dernier_fin, premier = dt.date(d0.year, d0.month, 1), -1e9, True
    if m < d0:
        m = dt.date(m.year + (m.month == 12), m.month % 12 + 1, 1)
    while m <= d1:
        x = X(m)
        lab = MOIS_COURT[m.month - 1] + (f" {m.year}" if m.month == 1 or premier else "")
        if x - dernier_fin >= 12 and x + largeur(lab) <= W:
            s.append(f'<text x="{x:.1f}" y="{H - 9}" class="t-axe">{e(lab)}</text>')
            dernier_fin, premier = x + largeur(lab), False
        m = dt.date(m.year + (m.month == 12), m.month % 12 + 1, 1)
    s.append(f'<line x1="{ml}" x2="{W - mr}" y1="{H - mb}" y2="{H - mb}" class="axe"/>')

    # zones occupées par le tracé (points et marches verticales) : les libellés les évitent
    serie = [(d, v["prix"]) for d, v in jours]
    occupe = [(X(d) - 6, Y(p) - 6, X(d) + 6, Y(p) + 6) for d, p in serie]
    for (da, pa), (db, pb) in zip(serie, serie[1:]):
        if (db - da).days <= 45:
            occupe.append((X(db) - 4, min(Y(pa), Y(pb)), X(db) + 4, max(Y(pa), Y(pb))))
            occupe.append((X(da), Y(pa) - 3, X(db), Y(pa) + 3))

    def place(candidats, w):
        """Premier emplacement (x de début, ligne de base) dont le texte ne touche pas le tracé."""
        for tx, ty in candidats:
            tx = min(max(tx, ml), W - mr - w)
            boite = (tx - 3, ty - fs, tx + w + 3, ty + 4)
            if not any(a < boite[2] and boite[0] < c_ and b < boite[3] and boite[1] < d_ for a, b, c_, d_ in occupe):
                occupe.append(boite)
                return tx, ty
        tx, ty = candidats[0] if candidats else (ml, mt + fs)
        return min(max(tx, ml), W - mr - w), ty

    # alerte : la ligne sous laquelle il faut acheter
    if c.get("alerte") and lo < c["alerte"] < hi:
        ya = Y(c["alerte"])
        t = f'acheter sous {c["alerte"]:.0f} €'
        w = largeur(t)
        s.append(f'<line x1="{ml}" x2="{W - mr}" y1="{ya:.1f}" y2="{ya:.1f}" class="alerte"/>')
        cands = [(x, y) for y in (ya - 6, ya + fs + 4) for x in (W - mr - w, ml + 6, (W - w) / 2, ml + (W - ml) * .25, ml + (W - ml) * .6)]
        tx, ty = place(cands, w)
        s.append(f'<text x="{tx:.1f}" y="{ty:.1f}" class="t-alerte">{t}</text>')

    # le trait : un palier par jour connu, interrompu quand on n'a pas de prix pendant plus de 45 jours ;
    # le trou est dessiné en pointillé discret et dit « aucun prix connu » (on n'invente pas le prix entre-temps)
    chemin = _chemin_escalier(serie, X, Y)
    for (da, pa), (db, pb) in zip(serie, serie[1:]):
        if (db - da).days > 45:
            xa, xb, ya_ = X(da), X(db), Y(pa)
            s.append(f'<line x1="{xa + 6:.1f}" x2="{xb - 6:.1f}" y1="{ya_:.1f}" y2="{ya_:.1f}" class="trou"/>')
            t = "aucun prix connu"
            if xb - xa > largeur(t) + 30:
                tx, ty = place([((xa + xb - largeur(t)) / 2, ya_ - 8), ((xa + xb - largeur(t)) / 2, ya_ + fs + 6)],
                               largeur(t))
                s.append(f'<text x="{tx:.1f}" y="{ty:.1f}" class="t-trou">{t}</text>')
    s.append(f'<path d="{chemin}" class="trait"/>')

    donnees = []
    for d, v in jours:
        x, y = X(d), Y(v["prix"])
        s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" class="pt"/>')
        donnees.append([round(x / W * 100, 2), round(y / H * 100, 2),
                        f"{date_fr(d)} : {euros(v['prix'])} chez {v.get('marchand') or '?'} "
                        f"({SOURCES.get(v.get('source'), v.get('source'))})"])

    # étiquettes : le prix du dernier jour connu, et le plus bas s'il est différent
    def etiquette(d, p, texte, classe):
        x, y = X(d), Y(p)
        w = largeur(texte)
        cands = [(x - w / 2, y - 11), (x - w / 2, y + fs + 10), (x + 10, y + fs * .35), (x - w - 10, y + fs * .35),
                 (x + 10, y - 11), (x + 10, y + fs + 10)]
        tx, ty = place([(cx, cy) for cx, cy in cands if cy - fs > 0 and cy < H - mb], w)
        return f'<text x="{tx:.1f}" y="{ty:.1f}" class="{classe}">{e(texte)}</text>'

    d_der, v_der = jours[-1]
    xd, yd = X(d_der), Y(v_der["prix"])
    s.append(f'<circle cx="{xd:.1f}" cy="{yd:.1f}" r="5.5" class="pt-fort"/>')
    t = euros(v_der["prix"], False).replace(" €", " €")
    w = largeur(t) * 1.1
    tx, ty = place([(xd - w - 12, yd + fs * .35), (xd - w / 2, yd - 12), (xd - w / 2, yd + fs + 12),
                    (xd - w - 12, yd - 12), (xd - w - 12, yd + fs + 12)], w)
    s.append(f'<text x="{tx:.1f}" y="{ty:.1f}" class="t-fort">{e(t)}</text>')
    d_min, v_min = min(jours, key=lambda t: t[1]["prix"])
    if v_min["prix"] < v_der["prix"] - 0.5 and abs(X(d_min) - X(d_der)) > 70:
        s.append(etiquette(d_min, v_min["prix"], f'plus bas {euros(v_min["prix"], False)}'.replace(" €", " €"), "t-min"))

    s.append('<circle r="7" class="curseur" cx="-10" cy="-10"/>')
    s.append("</svg>")
    return "".join(s), donnees


def figure_courbe(art, res, obs, auj):
    etroite = courbe(art["id"], res, obs, auj, 360, 230, "etroite")
    if not etroite:
        return '<p class="vide-txt">Pas encore de courbe : aucun prix en stock relevé.</p>'
    large = courbe(art["id"], res, obs, auj, 720, 280, "large")
    pts = json.dumps({"etroite": etroite[1], "large": large[1]}, ensure_ascii=False, separators=(",", ":"))
    return (f'<figure class="courbe" data-points="{e(pts)}">{etroite[0]}{large[0]}'
            f'<figcaption class="origine">{e(origine_historique(obs, auj))}</figcaption>'
            '<output class="lecture" aria-live="polite">Meilleur prix de chaque jour, tous marchands confondus. '
            'Touche un point pour le détail.</output></figure>' + historique_ailleurs(art))


def historique_ailleurs(art):
    """Les comparateurs gardent des années d'historique, mais refusent les robots : on y renvoie l'utilisateur
    (un toucher), et un prix daté qu'il y lit rejoint la courbe via « J'ai vu un prix »."""
    import re
    import urllib.parse
    q = urllib.parse.quote(art.get("recherche") or re.sub(r"\s*\(.*?\)", "", art["nom"]).strip())
    liens = [(f"https://www.idealo.fr/prechcat.html?q={q}", "idealo"),
             (f"https://ledenicheur.fr/search?search={q}", "Le Dénicheur"),
             (f"https://keepa.com/#!search/4-{q}", "Keepa (Amazon)")]
    l = " · ".join(f'<a href="{e(u)}" target="_blank" rel="noopener">{t}</a>' for u, t in liens)
    return (f'<p class="ailleurs">Historique plus ancien : {l}. Un prix daté vu là-bas ? Recopie-le avec '
            '« J’ai vu un prix » en choisissant sa date : il rejoint la courbe, marqué « saisie ».</p>')


def origine_historique(obs, auj):
    """D'où vient la courbe : depuis quand le prix est relevé chaque jour, et combien de prix d'archives avant."""
    directs = sorted(o["ts"][:10] for o in obs if o.get("source") in ("direct", "manuel"))
    debut = directs[0] if directs else None
    archives = {o["ts"][:10] for o in obs if o.get("source") == "archive"
                and 0 <= (auj - dt.date.fromisoformat(o["ts"][:10])).days <= 365
                and (debut is None or o["ts"][:10] < debut)}
    txt = f"Relevé chaque matin depuis le {date_fr(debut)}" if debut else "Pas encore de relevé direct"
    hist = [o for o in obs if o.get("source") == "historique"]
    if hist:
        sources = sorted({o.get("marchand", "").replace(" (historique)", "") for o in hist})
        derniere = max(o["ts"][:10] for o in obs if o.get("source") in ("historique", "navigateur"))
        txt += (f" ; {len(hist)} prix d'historique lus sur {', '.join(sources)} lors de l'enquête du "
                f"{date_fr(derniere)}")
    if archives:
        txt += (f" ; avant, {len(archives)} prix retrouvé{'s' if len(archives) > 1 else ''} dans les archives du web"
                " (elles gardent peu de copies des pages produit)")
    else:
        txt += " ; aucune copie plus ancienne de ces pages dans les archives du web"
    return txt + ". La courbe se remplit jour après jour."


# ---------------------------------------------------------------- morceaux de page

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800'
         '&display=swap">')

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
<meta name="color-scheme" content="light">
<meta name="theme-color" content="#F4F0E7">
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
    return f'<header class="tete">{lien}<p class="releve">prix du {e(quand)}</p></header>'


def pied(prefixe):
    return ('<footer class="pied">'
            f'<p>Verdicts calculés uniquement à partir de prix réellement relevés : en direct, dans les archives '
            f'publiques du web, ou saisis à la main. L\'outil s\'annonce comme robot (PrixJuste/{VERSION}), '
            'respecte robots.txt, lit chaque page une fois par jour au plus, et ne contourne jamais un site qui refuse.</p>'
            f'<p><a href="https://github.com/{DEPOT_GITHUB}">code et données</a></p></footer>')


def etat_article(art, res):
    if art.get("statut") == "a_identifier":
        return "attente"
    if art.get("statut") == "a_choisir":
        return "choisir"
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

def ligne_comptoir(art, res, obs, auj, comp=None):
    code = etat_article(art, res)
    href = f'a/{e(art["id"])}.html'
    variante = art.get("variante") or art.get("reference") or ""
    jg = ""
    if code == "attente":
        prix = '<span class="prix-ligne nul">—</span><span class="chez">identification en cours</span>'
        phrase = "Claude cherche le produit et des marchands : des propositions avec photo arrivent ici."
    elif code == "choisir":
        n = len(art.get("candidats") or [])
        prix = f'<span class="prix-ligne">{n} proposition{"s" if n > 1 else ""}</span>'
        phrase = "Touche pour choisir le bon produit : le suivi des prix démarre aussitôt."
    else:
        act = res.get("actuel")
        prix = (f'<span class="prix-ligne">{euros(act["prix"])}</span><span class="chez">chez {e(act.get("marchand"))}</span>'
                if act else '<span class="prix-ligne nul">—</span><span class="chez">aucun prix lisible ces 3 jours</span>')
        phrase = phrase_achat(res) if code == "paye" else res["verdict"][2]
        jg = bloc_jauge(jauge(res, auj), compact=True)
        if comp:
            prix += f'<span class="chez etr-ligne">{e(comp["nom_pays"])} ≈ {euros(comp["eur_ttc"])} taxes comprises</span>'
    return (f'<li><a class="etiquette" href="{href}">'
            f'{vignette(art)}'
            f'<span class="ligne-corps"><span class="nom">{e(art["nom"])}</span>'
            f'<span class="var">{e(variante)}</span>'
            f'<span class="prix-bloc">{prix}</span>{jg}</span>'
            f'<span class="tampon-bloc">{tampon(code, sous_tampon_code(code, res), "petit")}</span>'
            f'<span class="phrase">{e(phrase)}</span>'
            '</a></li>')


def bloc_plan(cands):
    """Frise repliable : le budget mensuel reste dans le navigateur (site.js), rien n'est publié."""
    if not cands or not cands["articles"]:
        return ""
    data = json.dumps(cands, ensure_ascii=False, separators=(",", ":"))
    return (f'<details class="archives plan" data-plan="{e(data)}"><summary>Plan d\'achat sous budget</summary>'
            '<label class="plan-budget">Budget par mois <i>€, reste sur cet appareil</i>'
            '<input name="budget-mois" inputmode="decimal" placeholder="sans limite"></label>'
            '<ol class="frise"></ol><p class="aide plan-bilan"></p>'
            '<p class="aide">Chaque article va dans son mois historiquement le moins cher, avant sa date limite, '
            'sans dépasser le budget ; les plus pressés passent d\'abord.</p></details>')


def comptoir(lignes, quand, prochain=None, plan_html="", noms=None, dossiers_html=None):
    corps = [entete("", quand, accueil=True), '<main>', bloc_assistant()]
    if prochain:
        d, txt = prochain
        corps.append(f'<p class="prochain"><span>Prochain moment</span> {e(txt)} — {date_fr(d)} · '
                     '<a href="agenda.ics">ajouter à mon agenda</a></p>')
    if dossiers_html:
        corps.append('<h2 class="rubrique">Mes dossiers</h2><ol class="etiquettes">' + "".join(dossiers_html) + "</ol>")
    corps.append('<div class="rubrique-ligne"><h2 class="rubrique">Prix suivis chaque jour</h2>'
                 '<a href="ajouter.html">+ suivre un article</a></div>')
    if lignes:
        corps.append('<ol class="etiquettes">' + "".join(lignes) + "</ol>" + plan_html)
    else:
        corps.append('<p class="vide-txt">Rien n\'est suivi pour l\'instant.</p>')
    corps.append("</main>")
    corps.append(pied(""))
    return page("PrixJuste — assistant d'achat", "".join(corps), classe="p-comptoir")


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
        L.append(_ligne_ticket("Mois le moins cher", e(nom), f'vers {euros(c["meilleur_mois_prix"], False)}'))
    if c.get("alerte"):
        L.append(_ligne_ticket("Alerte", f'sous {euros(c["alerte"], False)}', "achète si le prix passe dessous"))
    pr = res.get("protection")
    if pr:
        L.append(_ligne_ticket("Payé", euros(pr["prix"]), f'{e(pr["marchand"])} · {date_fr(pr["date"])}'))
        L.append(_ligne_ticket("Rétractation", f'jusqu\'au {date_fr(pr["fin_retractation"])}',
                               "14 jours pour renvoyer un achat en ligne (depuis la réception)"))
        L.append(_ligne_ticket("Garantie légale", f'jusqu\'au {date_fr(pr["fin_garantie"])}',
                               "2 ans de garantie de conformité, à demander au vendeur"))
    n = c.get("n_releves", 0)
    L.append(_ligne_ticket("Fiabilité", e(c.get("fiabilite", "faible")),
                           f'{n} jour{"s" if n > 1 else ""} de prix connus sur 12 mois'))
    return '<dl class="ticket">' + "".join(L) + "</dl>"


def bloc_promos(res):
    if not res["promos"]:
        return ""
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
    for o in obs:  # le relevé le plus RÉCENT de chaque page (les archives arrivent après les relevés du jour)
        if o["lien"] not in dernier_prix or o["ts"] >= dernier_prix[o["lien"]]["ts"]:
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
        if lien.get("pays"):
            continue  # comparé à part (bloc « Au Québec »)
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
    manuels, navig = {}, {}
    for o in obs:
        if o.get("source") == "manuel":
            manuels[o.get("marchand")] = o
        elif o.get("source") == "navigateur" and not any(cle(l) == o["lien"] for l in art.get("liens", [])):
            navig[o.get("marchand")] = o
    for m, o in navig.items():
        url = o["lien"] if o["lien"].startswith("http") else None
        L.append(ligne(m, url, "vu en naviguant lors d'une enquête", "enquête", "archive", o))
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


def bloc_enquete(art):
    """Consigne prête à coller dans Claude dans Chrome (sur ordinateur) : l'enquête complète, à la demande."""
    txt = enquete.consigne(art, DEPOT_GITHUB)
    return ('<details class="vu enquete"><summary>Enquête complète (Claude dans Chrome)</summary>'
            '<p class="aide">Sur ton ordinateur : copie cette consigne, ouvre Claude dans Chrome et colle-la. Claude '
            'lit l\'historique d\'idealo ou de Le Dénicheur, les prix dans ta taille et au Canada, puis enregistre tout '
            'ici (quelques minutes). À faire quand tu envisages d\'acheter.</p>'
            f'<textarea class="consigne" readonly rows="8">{e(txt)}</textarea>'
            '<button type="button" class="copier">Copier la consigne</button></details>')


def form_prix(art):
    return (f'<details class="vu"><summary>J\'ai vu un prix</summary>'
            f'<form class="form-prix" data-article="{e(art["id"])}" data-nom="{e(art["nom"])}" data-depot="{e(DEPOT_GITHUB)}">'
            '<p class="aide">En magasin, dans une pub, sur un site que l\'outil ne peut pas lire, ou sur la courbe '
            'd\'un comparateur (mets alors la date du prix lu). '
            'Le bouton ouvre une demande pré-remplie sur GitHub : il reste à l\'envoyer.</p>'
            '<div class="grille2"><label>Prix vu<input name="prix" inputmode="decimal" required placeholder="199,90"></label>'
            '<label>Prix barré <i>si affiché</i><input name="barre" inputmode="decimal" placeholder="230"></label></div>'
            '<div class="grille2"><label>Où<input name="marchand" placeholder="magasin, site…"></label>'
            '<label>Le<input name="date" type="date"></label></div>'
            '<label class="case"><input name="rupture" type="checkbox"> en rupture dans ma taille</label>'
            '<button type="submit">Envoyer ce prix →</button></form></details>')


def bloc_etranger(comp):
    """Le même article à l'étranger, converti en euros, taxes locales comprises (un achat sur place)."""
    if not comp:
        return ""
    if comp["ecart"] is None:
        verdict = ""
    elif comp["ecart"] < -1:
        verdict = f'<p class="etr-verdict moins">{euros(-comp["ecart"])} de moins qu’en France</p>'
    elif comp["ecart"] > 1:
        verdict = f'<p class="etr-verdict plus">{euros(comp["ecart"])} de plus qu’en France</p>'
    else:
        verdict = '<p class="etr-verdict">Même prix qu’en France</p>'
    local = f'{comp["prix_local"]:,.2f}'.replace(",", "\u202f").replace(".", ",") + "\u00a0" + comp["symbole"]
    rappels = "".join(f"<li>{e(r)}</li>" for r in comp["rappels"])
    return (f'<section class="carte etranger"><h2 class="rubrique">{e(comp["nom_pays"][:1].upper() + comp["nom_pays"][1:])}</h2>'
            f'<p class="etr-prix"><b>≈ {euros(comp["eur_ttc"])}</b> taxes comprises</p>{verdict}'
            f'<p class="etr-detail">{e(local)} chez {e(comp["marchand"])} (relevé le {date_fr(comp["le"])}), '
            f'soit {euros(comp["eur_ht"])} hors taxes + {e(comp["taxes_txt"])}. Change BCE du '
            f'{date_fr(comp["taux_date"])} : 1 € = {str(comp["taux"]).replace(".", ",")} {e(comp["symbole"])}'
            ' ; ta banque ajoute souvent 1 à 3 % de frais.</p>'
            f'<ul class="notes">{rappels}</ul></section>')


def fiche(art, res, obs, journal, quand, auj, voisins=None, comp=None):
    code = etat_article(art, res)
    act = res.get("actuel")
    variante = art.get("variante") or art.get("reference") or ""
    cadre = [f'à acheter avant le {date_fr(res["limite"])}']
    if art.get("budget_max"):
        cadre.append(f'budget {euros(art["budget_max"], False)}')

    if act:
        barre = ""
        promo = next((p for p in res["promos"] if p["ts"] == act["ts"] and p["marchand"] == act.get("marchand")), None)
        if promo and not promo["douteuse"]:  # ancien prix barré affiché seulement s'il est réel
            barre = f' <s class="barre">{euros(promo["barre"])}</s> <span class="remise">{pct(promo["remise_affichee"])}</span>'
        prix_html = (f'<p class="lbl">Aujourd’hui · {e(act.get("marchand"))}</p>'
                     f'<p class="prix-geant">{euros(act["prix"])}{barre}</p>')
    elif code == "attente":
        prix_html = '<p class="lbl">Identification en cours</p>'
    elif code == "choisir":
        prix_html = '<p class="lbl">Choisis le bon produit ci-dessous : le suivi des prix démarre aussitôt.</p>'
    else:
        prix_html = ('<p class="lbl">Aucun site lisible ces 3 derniers jours</p><p class="prix-geant nul">—</p>')

    corps = [entete("../", quand), '<main class="fiche">',
             '<a class="retour" href="../index.html">← Ma liste</a>',
             '<section class="bandeau">',
             f'<div class="produit">{vignette(art, "photo")}<div class="produit-txt">'
             f'<h1 class="nom-fiche">{e(art["nom"])}</h1>'
             + (f'<p class="var-fiche">{e(variante)}</p>' if variante else "")
             + f'<p class="cadre-fiche">{e(" · ".join(cadre))}</p></div></div>',
             prix_html, '</section>', liens_parentes(art, voisins or {})]

    if code == "attente":
        num = art.get("issue")
        lien_issue = (f'<a href="https://github.com/{DEPOT_GITHUB}/issues/{num}">la demande n°{num}</a>' if num else "la demande")
        corps.append(f'<section class="carte prevision v-donnees"><div class="prev-tete"><p class="carte-lbl">Prévision</p>'
                     f'{tampon("attente", None, "grand")}</div>'
                     f'<p class="prev-titre">Identification en cours</p>'
                     f'<p class="prev-expli">Demande : « {e(art.get("demande", art["nom"]))} ». Claude cherche la référence '
                     f'exacte et des pages marchands lisibles, puis le suivi démarre. Pour aller plus vite, colle un lien '
                     f'produit dans {lien_issue}.</p></section>')
        corps += ["</main>", pied("../")]
        return page(f"{art['nom']} — PrixJuste", "".join(corps), "../", classe="p-fiche")

    if code == "choisir":
        corps.append(bloc_candidats(art))
        corps.append(bloc_equivalents(art))
        corps.append('<div class="actions">' + bloc_enquete(art) + '</div>')
        corps += ["</main>", pied("../")]
        return page(f"{art['nom']} — PrixJuste", "".join(corps), "../", classe="p-fiche")

    titre = res["verdict"][1] if code != "paye" else "Acheté"
    corps.append(bloc_jauge(jauge(res, auj)))
    corps.append(bloc_prevision(art, res, code, auj))
    corps.append('<section class="carte"><h2 class="rubrique">Les 12 derniers mois</h2>'
                 + figure_courbe(art, res, obs, auj) + '</section>')
    corps.append('<section class="carte"><h2 class="rubrique">Repères</h2>' + ticket(art, res)
                 + (f'<p class="repere">Encore peu de prix connus. En général : {e(res["repere"])}</p>'
                    if res["chiffres"].get("fiabilite", "faible") == "faible" else "") + '</section>')
    promos = bloc_promos(res)
    if promos:
        corps.append('<section class="carte"><h2 class="rubrique">Contrôle des promos</h2>' + promos + '</section>')
    corps.append('<section class="carte"><h2 class="rubrique">Où l’acheter</h2>'
                 + bloc_marchands(art, obs, journal) + '</section>')
    corps.append(bloc_etranger(comp))
    corps.append(bloc_equivalents(art))
    corps.append('<div class="actions">' + bloc_enquete(art) + form_prix(art) + ("" if art.get("achat") else form_achat(art, act))
                 + carte(art, res, code, auj) + '</div>' + lien_equivalent(art))
    corps += ["</main>", pied("../")]
    return page(f"{art['nom']} — PrixJuste", "".join(corps), "../",
                description=f"{TAMPONS[code][1][0]} — {titre}", classe="p-fiche")


def enquete_candidat(c):
    q = c.get("enquete")
    if not q:
        return ""
    stock = {1: "en stock dans ta taille", 0: "pas en stock dans ta taille"}.get(q.get("en_stock"), "")
    lien = (f'<a href="{e(q["url"])}" rel="noopener nofollow">{e(q["marchand"])}</a>' if q.get("url")
            else e(q.get("marchand")))
    return (f'<p class="c-enquete"><b>Enquête du {date_fr(q["le"])} :</b> {euros(q["prix"])} chez {lien}'
            + (f", {stock}" if stock else "") + (f". {e(q['commentaire'])}" if q.get("commentaire") else "") + "</p>")


def bloc_equivalents(art):
    """Produits « tout aussi bien » trouvés par la dernière enquête ; on peut les suivre d'un toucher."""
    eqs = art.get("equivalents") or []
    if not eqs:
        return ""
    L = []
    for q in eqs:
        corps = "\n".join([f"Objet : {q['nom']}"] + ([f"Taille : {art['taille']}"] if art.get("taille") else [])
                          + ["Urgence : " + art.get("urgence", "pas_urgent"), "Liens :", q.get("url") or "(aucun)",
                             "", "<!-- prixjuste:ajout -->"])
        u = urllib.parse.urlencode({"title": f"Ajout : {q['nom']}", "body": corps, "labels": "ajout"},
                                   quote_via=urllib.parse.quote)
        prix = f" — {euros(q['prix'])}" + (f" chez {e(q['marchand'])}" if q.get("marchand") else "") if q.get("prix") else ""
        nom = (f'<a href="{e(q["url"])}" rel="noopener nofollow">{e(q["nom"])}</a>' if q.get("url") else e(q["nom"]))
        L.append(f'<li><p class="eq-nom">{nom}{prix}</p>'
                 + (f'<p class="eq-pourquoi">{e(q["pourquoi"])}</p>' if q.get("pourquoi") else "")
                 + f'<a class="eq-suivre" href="https://github.com/{DEPOT_GITHUB}/issues/new?{e(u)}">Le suivre aussi</a></li>')
    return (f'<section class="carte equivalents"><h2 class="rubrique">Aussi bien, à comparer</h2>'
            f'<p class="aide">Trouvés lors de l’enquête du {date_fr(eqs[0]["le"])}.</p><ul>{"".join(L)}</ul></section>')


def bloc_candidats(art):
    """Propositions trouvées pour une demande en texte libre : on choisit d'un geste, le suivi démarre sans IA."""
    L = []
    for i, c in enumerate(art.get("candidats") or [], 1):
        corps = "\n".join([f"Article : {art['id']}", f"Choix : {i}", "", "<!-- prixjuste:choix -->"])
        q = urllib.parse.urlencode({"title": f"Choix : {c.get('nom', art['nom'])}", "body": corps, "labels": "choix"},
                                   quote_via=urllib.parse.quote)
        prix = (f'{euros(c["prix"])} chez {e(c.get("marchand") or "?")}' if c.get("prix") is not None
                else e(c.get("marchand") or ""))
        voir = (f'<a class="c-voir" href="{e(c["url"])}" rel="noopener nofollow">voir la page</a>' if c.get("url") else "")
        L.append(f'<li class="candidat">{vignette(c, "c-photo")}<div class="c-txt">'
                 f'<p class="c-nom">{e(c.get("nom", "?"))}</p>'
                 + (f'<p class="c-var">{e(c["variante"])}</p>' if c.get("variante") else "")
                 + f'<p class="c-prix">{prix}</p>'
                 + (f'<p class="c-note">{e(c["note"])}</p>' if c.get("note") else "")
                 + enquete_candidat(c)
                 + f'</div><div class="c-actions"><a class="c-choisir" href="https://github.com/{DEPOT_GITHUB}/issues/new?{e(q)}">'
                 f'C’est celui-là</a>{voir}</div></li>')
    num = art.get("issue")
    autre = (f' Aucun ne va ? Précise ta <a href="https://github.com/{DEPOT_GITHUB}/issues/{num}">demande n°{num}</a> '
             'en y collant un lien produit.' if num else "")
    return (f'<section class="carte choix"><h2 class="rubrique">Lequel veux-tu suivre ?</h2>'
            f'<p class="aide">Trouvés pour « {e(art.get("demande", art["nom"]))} ». Touche le bon : la demande s’ouvre '
            f'sur GitHub, il reste à appuyer sur « Create », et le suivi démarre.{autre}</p>'
            f'<ol class="candidats">{"".join(L)}</ol></section>')


def lien_equivalent(art):
    """Lien discret : ouvre une demande « ajout » pré-remplie ; Claude (si activé) cherche 2 ou 3 équivalents
    moins chers, suivis ensuite comme les autres articles (docs/IDEES.md, idée 10)."""
    if art.get("achat") or art.get("equivalent_de"):
        return ""
    taille = art.get("taille") or next((l["taille"] for l in art.get("liens", []) if l.get("taille")), None)
    lignes = [f"Objet : équivalent moins cher de {art['nom']}", f"Équivalent de : {art['id']}"]
    if taille:
        lignes.append(f"Taille : {taille}")
    lignes.append(f"Urgence : {art.get('urgence', 'pas_urgent')}")
    if art.get("acheter_avant"):
        lignes.append(f"Avant le : {art['acheter_avant']}")
    lignes += ["Liens :", "(aucun : à identifier)", "", "<!-- prixjuste:equivalent -->"]
    q = urllib.parse.urlencode({"title": f"Ajout : équivalent de {art['nom']}", "body": "\n".join(lignes),
                                "labels": "ajout"}, quote_via=urllib.parse.quote)
    return (f'<p class="equivalent"><a href="https://github.com/{DEPOT_GITHUB}/issues/new?{e(q)}">'
            'Trouver un équivalent moins cher →</a> <span>par Claude, s\'il est activé (voir LISEZMOI)</span></p>')


def liens_parentes(art, voisins):
    """Une ligne sous le titre : l'original d'un équivalent, ou les équivalents d'un original."""
    if art.get("equivalent_de"):
        o = voisins.get(art["equivalent_de"])
        if not o:
            return ""
        pourquoi = f" — {e(art['pourquoi'])}" if art.get("pourquoi") else ""
        return (f'<p class="parente">Équivalent proposé pour <a href="{e(o["id"])}.html">{e(o["nom"])}</a>'
                f'{pourquoi}</p>')
    alts = [a for a in voisins.values() if a.get("equivalent_de") == art["id"] and a.get("statut") == "suivi"]
    if not alts:
        return ""
    return ('<p class="parente">À comparer : ' + ", ".join(
        f'<a href="{e(a["id"])}.html">{e(a["nom"])}</a>' for a in sorted(alts, key=lambda a: a["nom"])) + "</p>")


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


# ---------------------------------------------------------------- l'assistant : dossiers

def tampon_dossier(code, sous=None, taille="petit"):
    classe, lbl = dossiers.VERDICTS[code]
    corps = e(lbl) + (f'<small>{e(sous)}</small>' if sous else "")
    return f'<strong class="tampon t-{classe} {taille}"><span>{corps}</span></strong>'


def prix_piece(p, change):
    """« 168,36 € » ; pour un prix étranger : « 230 $ CA ≈ 168,36 € taxes comprises »."""
    if p.get("prix") is None:
        return '<span class="prix-ligne nul">—</span>'
    v = dossiers.en_euros(p, change)
    if p.get("devise", "EUR") == "EUR":
        h = f'<span class="prix-ligne">{euros(v)}</span>'
    else:
        sym = (etranger.PAYS.get(p.get("pays") or "") or {}).get("symbole") or p["devise"]
        h = (f'<span class="prix-ligne">{p["prix"]:.2f} {e(sym)}</span>'.replace(".", ",")
             + (f'<span class="chez">≈ {euros(v)} taxes comprises</span>' if v is not None else ""))
    if p.get("prix_avant") and p["prix_avant"] > p["prix"]:
        h += f'<s class="avant">{p["prix_avant"]:.2f}</s>'.replace(".", ",")
    return h


def lien_suivre(p, taille=None):
    corps = "\n".join([f"Objet : {p['nom']}"] + ([f"Taille : {taille}"] if taille else [])
                      + ["Urgence : pas_urgent", "Liens :", p.get("url") or "(aucun)", "", "<!-- prixjuste:ajout -->"])
    u = urllib.parse.urlencode({"title": f"Ajout : {p['nom']}", "body": corps, "labels": "ajout"},
                               quote_via=urllib.parse.quote)
    return f"https://github.com/{DEPOT_GITHUB}/issues/new?{u}"


def carte_piece(p, change, suivis, taille=None):
    code = p.get("verdict")
    sous = p.get("quand_court")
    vign = vignette({"nom": p.get("role") or p["nom"], "image": p.get("image")})
    titre = e(p["nom"])
    if p.get("url"):
        titre = f'<a href="{e(p["url"])}" rel="noopener nofollow" target="_blank">{titre}</a>'
    var = " · ".join(x for x in (p.get("role"), p.get("reference"), p.get("taille") and f"taille {p['taille']}") if x)
    chez = []
    if p.get("marchand"):
        chez.append(f'chez {e(p["marchand"])}')
    if p.get("en_stock") is False:
        chez.append("pas dans ta taille")
    if p.get("fin"):
        chez.append(f'jusqu\'au {date_fr(p["fin"])}')
    phrase = " ".join(x for x in (p.get("pourquoi"), p.get("quand")) if x)
    actions = []
    if p.get("article") and p["article"] in suivis:
        actions.append(f'<a href="../a/{e(p["article"])}.html">Prix suivi chaque jour →</a>')
    elif p.get("url") and code in ("attendre", "surveiller"):
        actions.append(f'<a href="{e(lien_suivre(p, p.get("taille") or taille))}">Suivre son prix</a>')
    if p.get("seconde_main"):
        actions.append(f'<a href="{e(p["seconde_main"])}" rel="noopener nofollow" target="_blank">En seconde main</a>')
    return ('<li class="piece">'
            f'{vign}<span class="ligne-corps"><span class="nom">{titre}</span>'
            + (f'<span class="var">{e(var)}</span>' if var else "")
            + f'<span class="prix-bloc">{prix_piece(p, change)}'
            + (f'<span class="chez">{" · ".join(chez)}</span>' if chez else "") + '</span></span>'
            + (f'<span class="tampon-bloc">{tampon_dossier(code, sous)}</span>' if code else "")
            + (f'<p class="phrase-piece">{e(phrase)}</p>' if phrase else "")
            + (f'<p class="actions-piece">{" · ".join(actions)}</p>' if actions else "")
            + '</li>')


def _sources(d):
    s = d.get("sources") or []
    if not s:
        return ""
    L = "".join(f'<li><a href="{e(x["url"])}" rel="noopener nofollow" target="_blank">{e(x.get("nom") or x["url"])}</a>'
                + (f' <i>{e(x["note"])}</i>' if x.get("note") else "") + "</li>" for x in s)
    return f'<details class="archives"><summary>Sources <i>({len(s)})</i></summary><ul class="sources">{L}</ul></details>'


def _liste(titre, items):
    return (f'<section class="carte"><h2 class="rubrique">{e(titre)}</h2><ul class="puces">'
            + "".join(f"<li>{e(x)}</li>" for x in items) + "</ul></section>") if items else ""


def page_dossier(d, change, suivis, quand):
    taille = d.get("taille")
    t = d["type"]
    tete = [f'<p class="sur-titre">{e(dossiers.TYPES[t])} · {date_fr(d["le"])}'
            + (f' · taille {e(taille)}' if taille else "") + '</p>',
            f'<h1>{e(d["titre"])}</h1>']
    if t == "achat":
        tete.append(f'<div class="verdict-dossier">{tampon_dossier(d["verdict"], d.get("quand_court"), "")}'
                    + (f'<span>Prix cible <b>{euros(d["prix_cible"])}</b></span>' if d.get("prix_cible") else "")
                    + "</div>")
    tete.append(f'<p class="resume">{e(d["resume"])}</p>')
    if d.get("demande"):
        tete.append(f'<p class="aide">Ta demande : « {e(d["demande"])} »</p>')
    corps = [entete("../", quand), '<main class="dossier">', '<a class="retour" href="../index.html">← Accueil</a>',
             f'<section class="bandeau">{"".join(tete)}</section>']
    if t == "tenue":
        if d.get("look"):
            corps.append(f'<p class="look">{e(d["look"])}</p>')
        for o in d["options"]:
            tot = dossiers.total(o["pieces"], change)
            corps.append(f'<section class="option"><div class="option-tete"><h2 class="rubrique">{e(o["nom"])}</h2>'
                         + (f'<span class="total">{euros(tot)}</span>' if tot is not None else "") + '</div>'
                         + (f'<p class="aide">{e(o["idee"])}</p>' if o.get("idee") else "")
                         + (f'<p class="aide"><a href="{e(o["pinterest"])}" rel="noopener nofollow" target="_blank">'
                            'Voir ce look en photos sur Pinterest →</a></p>' if o.get("pinterest") else "")
                         + '<ol class="pieces">' + "".join(carte_piece(p, change, suivis, taille) for p in o["pieces"])
                         + "</ol></section>")
    elif t == "achat":
        offres = sorted(d["offres"], key=lambda p: (p.get("en_stock") is False, dossiers.en_euros(p, change) or 9e9))
        corps.append('<section class="option"><h2 class="rubrique">Où l\'acheter, du moins cher au plus cher</h2>'
                     '<ol class="pieces">' + "".join(carte_piece(p, change, suivis, taille) for p in offres)
                     + "</ol></section>")
        if d.get("historique"):
            corps.append(_liste("L'historique", d["historique"]))
        if d.get("canada"):
            corps.append(_liste("Au Canada", d["canada"]))
        if d.get("equivalents"):
            corps.append('<section class="option"><h2 class="rubrique">Aussi bien, moins cher</h2><ol class="pieces">'
                         + "".join(carte_piece(p, change, suivis, taille) for p in d["equivalents"]) + "</ol></section>")
    else:
        corps.append('<section class="option"><ol class="pieces">'
                     + "".join(carte_piece(p, change, suivis, taille) for p in d["plans"]) + "</ol></section>")
    corps.append(_liste("Pièges à éviter" if t == "bons-plans" else "Conseils", d.get("conseils") or d.get("pieges")))
    if d.get("article") and d["article"] in suivis:
        corps.append(f'<p class="aide suivi-lien"><a href="../a/{e(d["article"])}.html">Voir son prix suivi chaque jour '
                     'et la courbe →</a></p>')
    fin = d.get("valable_jusqu_au")
    corps.append(f'<p class="aide">Prix vus le {date_fr(d["le"])}'
                 + (f', conseil valable jusqu\'au {date_fr(fin)}' if fin else "")
                 + ". Les prix bougent : vérifie sur la page de la boutique avant de payer.</p>")
    corps.append(_sources(d))
    corps.append("</main>")
    corps.append(pied("../"))
    return page(f"{d['titre']} — PrixJuste", "".join(corps), "../", d.get("resume", ""), classe="p-dossier")


def ligne_dossier(d, change):
    t = d["type"]
    if t == "achat":
        tp = tampon_dossier(d["verdict"], d.get("quand_court"))
    elif t == "tenue":
        n = len(d["options"])
        tp = f'<strong class="tampon t-donnees petit"><span>{n} OPTION{"S" if n > 1 else ""}</span></strong>'
    else:
        n = len(d["plans"])
        tp = f'<strong class="tampon t-achete petit"><span>{n} PLAN{"S" if n > 1 else ""}</span></strong>'
    img = next((p.get("image") for p in dossiers.pieces(d) if p.get("image")), None)
    return (f'<li><a class="etiquette" href="d/{e(d["id"])}.html">{vignette({"nom": d["titre"], "image": img})}'
            f'<span class="ligne-corps"><span class="nom">{e(d["titre"])}</span>'
            f'<span class="var">{e(dossiers.TYPES[t])} · {date_fr(d["le"])}</span></span>'
            f'<span class="tampon-bloc">{tp}</span><span class="phrase">{e(d["resume"])}</span></a></li>')


ASSISTANT = ("https://claude.ai/code")


def bloc_assistant():
    return ('<section class="demande assistant"><h1>Ton assistant d\'achat</h1>'
            '<ul class="demandes">'
            '<li><b>Une tenue</b> Envoie la photo d\'un look à Claude : pièces exactes, versions moins chères, '
            'prix et verdict pour chacune.</li>'
            '<li><b>Un achat</b> « Je veux les Timberland, pointure 40 » : toutes les boutiques, France et Canada, '
            'puis achète maintenant ou attends, avec la date.</li>'
            '<li><b>Les bons plans</b> « Trouve-moi des bons plans » : les vraies promos du moment pour toi, '
            'fausses promos écartées.</li></ul>'
            f'<a class="bouton" href="{ASSISTANT}" rel="noopener">Demander à Claude</a>'
            '<p class="aide">Ouvre une session sur le dépôt prixjuste et écris ta demande : la réponse arrive dans '
            'la conversation, et le dossier s\'ajoute ici.</p></section>')


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
             '<p class="aide"><b>Combien de temps ?</b> Avec un lien produit : le premier prix et le verdict arrivent '
             'en 2 minutes environ. Sans lien : des propositions avec photo arrivent au plus tard dans les 3 heures '
             '(quelques minutes si Claude est activé sur le dépôt). Ce n\'est pas instantané parce que le site n\'a '
             'pas de serveur : c\'est GitHub qui fait le travail, à ta demande.</p>',
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
    (sortie / "d").mkdir()
    for f in ("style.css", "site.js"):
        shutil.copy(STATIQUE / f, sortie / f)
    (sortie / ".nojekyll").write_text("")

    lignes, exports, pour_agenda = [], [], []
    voisins = {a["id"]: a for a in depot.articles()}
    change = etranger.charger_change(depot)
    for art in voisins.values():
        tous = depot.releves(art["id"])
        obs = analyse.filtrer_obs(art, tous)
        res = analyse.analyser(art, obs, auj)
        comp = etranger.comparaison(tous, (res.get("actuel") or {}).get("prix"), change, auj)
        pour_agenda.append((art, res))
        code = etat_article(art, res)
        jusqu = res.get("jusqu_a") or dt.date.max
        lignes.append(((ORDRE[code], jusqu, art["nom"].lower()), ligne_comptoir(art, res, obs, auj, comp)))
        (sortie / "a" / f"{art['id']}.html").write_text(
            fiche(art, res, obs, depot.journal(art["id"]), quand, auj, voisins, comp), encoding="utf-8")
        exports.append(export(art, res, code))
    lignes.sort(key=lambda x: x[0])
    proprio, nom_depot = DEPOT_GITHUB.split("/")
    url_site = os.environ.get("PAGES_URL") or f"https://{proprio.lower()}.github.io/{nom_depot}"
    (sortie / "agenda.ics").write_text(agenda.ics(pour_agenda, auj, url_site), encoding="utf-8", newline="")
    les_dossiers = dossiers.charger(depot)
    for d in les_dossiers:
        (sortie / "d" / f"{d['id']}.html").write_text(page_dossier(d, change, voisins, quand), encoding="utf-8")
    (sortie / "index.html").write_text(comptoir([l for _, l in lignes], quand, agenda.prochain(pour_agenda, auj),
                                                bloc_plan(plan.candidats(pour_agenda, auj)),
                                                [{"id": a["id"], "nom": a["nom"]} for a, _ in pour_agenda],
                                                [ligne_dossier(d, change) for d in les_dossiers]),
                                       encoding="utf-8")
    profil = ajout.charger_profil(depot)
    (sortie / "ajouter.html").write_text(  # seulement les tailles : le reste du profil n'est pas publié
        ajouter(quand, {k: profil[k] for k in ("pointure", "taille", "marques") if k in profil}), encoding="utf-8")
    (sortie / "data.json").write_text(json.dumps({"genere": maintenant(), "articles": exports, "dossiers": les_dossiers}, default=_json,
                                                 ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Site : {sortie}/ ({len(exports)} article(s))")
    return sortie
