"""Genere rapport.html : un tableau de bord sobre, lisible, sans fioritures."""
import datetime as dt
import html

import collecte

from analyse import MOIS_AFFICHE

MOIS_COURT = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
LIBELLES = {"acheter": "Acheter", "attendre": "Attendre", "surveiller": "Surveiller",
            "donnees": "Historique insuffisant", "inconnu": "Aucune donnée"}
SOURCES = {"direct": "Relevé en direct", "archive": "Archive web", "manuel": "Saisie manuelle"}

CSS = """
:root{--bg:#f6f5f2;--card:#fff;--ink:#1d1d1b;--muted:#6b6a66;--line:#e4e2dc;--grid:#eeece7;
--acheter:#1f7a4d;--attendre:#2f5fa8;--surveiller:#a8650f;--donnees:#76746e;
--serie:#1d1d1b;--archive:#8a8780;--direct:#2f5fa8;--manuel:#a8650f;--repere:#c9c6bd}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--card:#1f1f1d;--ink:#ecebe7;--muted:#9a9891;
--line:#33322f;--grid:#2a2927;--acheter:#4cb07c;--attendre:#6f9be0;--surveiller:#d99a45;--donnees:#9a9891;
--serie:#ecebe7;--archive:#8a8780;--direct:#6f9be0;--manuel:#d99a45;--repere:#4a4945}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:880px;margin:0 auto;padding:32px 16px 64px}
header.top{display:flex;justify-content:space-between;align-items:baseline;gap:16px;flex-wrap:wrap;margin-bottom:24px}
h1{font-size:22px;margin:0;letter-spacing:-.01em}
.sub{color:var(--muted);font-size:13px}
article{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:24px;margin-bottom:24px}
h2{font-size:18px;margin:0 0 4px}
.meta{color:var(--muted);font-size:13px;margin-bottom:18px}
.verdict{border-left:4px solid var(--c);padding:10px 14px;background:color-mix(in srgb,var(--c) 8%,transparent);border-radius:0 6px 6px 0;margin-bottom:18px}
.verdict .tag{font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--c)}
.verdict .titre{font-size:17px;font-weight:600;margin:2px 0}
.verdict p{margin:0;color:var(--ink)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:1px;background:var(--line);border:1px solid var(--line);border-radius:8px;overflow:hidden;margin-bottom:18px}
.kpi{background:var(--card);padding:12px 14px}
.kpi .l{font-size:12px;color:var(--muted)}
.kpi .v{font-size:20px;font-weight:600;font-variant-numeric:tabular-nums}
.kpi .d{font-size:12px;color:var(--muted)}
.box{border:1px solid var(--line);border-radius:8px;padding:10px 14px;margin-bottom:12px;font-size:14px}
.box.alerte{border-color:var(--surveiller)}
ul.notes{margin:0 0 14px;padding-left:18px;font-size:14px}
svg{width:100%;height:auto;display:block}
.legende{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:var(--muted);margin:6px 0 18px}
.legende span::before{content:"";display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px;background:var(--k)}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;color:var(--muted);font-weight:500;border-bottom:1px solid var(--line);padding:6px 8px 6px 0}
td{border-bottom:1px solid var(--grid);padding:7px 8px 7px 0;vertical-align:top}
td.num{font-variant-numeric:tabular-nums;white-space:nowrap}
.st-ok{color:var(--acheter)}.st-bloqué{color:var(--surveiller)}.st-erreur,.st-vide{color:var(--muted)}
a{color:inherit}
details{margin-top:14px;font-size:13px;color:var(--muted)}
footer{color:var(--muted);font-size:12px;margin-top:32px}
"""


def e(x):
    return html.escape(str(x))


def euros(x):
    return "—" if x is None else f"{x:,.2f} €".replace(",", " ").replace(".", ",").replace(",00 €", " €")


def graphique(serie, rows, chiffres, aujourdhui):
    if not rows:
        return '<p class="sub">Pas encore de courbe : aucun prix relevé.</p>'
    pts = []
    for r in rows:
        if r["en_stock"] == 0:
            continue
        d = dt.date.fromisoformat(r["ts"][:10])
        if (aujourdhui - d).days <= 430:  # ~14 mois : au-dela ca n'aide plus a decider
            pts.append((d, r["prix"], r["source"]))
    serie = {d: v for d, v in serie.items() if (aujourdhui - d).days <= 430}
    if not pts:
        return '<p class="sub">Aucun prix en stock relevé.</p>'
    W, H, ml, mr, mt, mb = 760, 260, 52, 14, 14, 30
    d0 = min(p[0] for p in pts)
    d1 = max(aujourdhui, max(p[0] for p in pts))
    if (d1 - d0).days < 60:
        d0 = d1 - dt.timedelta(days=60)
    prix = [p[1] for p in pts] + [x for x in (chiffres.get("alerte"),) if x]
    lo, hi = min(prix), max(prix)
    pad = max((hi - lo) * 0.12, 10)
    lo, hi = max(0, lo - pad), hi + pad
    span = (d1 - d0).days or 1

    def X(d):
        return ml + (d - d0).days / span * (W - ml - mr)

    def Y(v):
        return mt + (hi - v) / (hi - lo) * (H - mt - mb)

    s = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Historique des prix">']
    # grille horizontale
    pas = max(10, round((hi - lo) / 4 / 10) * 10)
    v = (int(lo // pas) + 1) * pas
    while v < hi:
        s.append(f'<line x1="{ml}" x2="{W-mr}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="var(--grid)"/>'
                 f'<text x="{ml-8}" y="{Y(v)+4:.1f}" text-anchor="end" font-size="11" fill="var(--muted)">{v:.0f} €</text>')
        v += pas
    # mois
    m = dt.date(d0.year, d0.month, 1)
    n_mois = span / 30
    saut = 1 if n_mois <= 14 else (2 if n_mois <= 28 else 3)
    i = 0
    while m <= d1:
        if m >= d0 and i % saut == 0:
            lab = MOIS_COURT[m.month - 1] + (f" {m.year % 100:02d}" if m.month == 1 or i == 0 else "")
            s.append(f'<line x1="{X(m):.1f}" x2="{X(m):.1f}" y1="{mt}" y2="{H-mb}" stroke="var(--grid)"/>'
                     f'<text x="{X(m)+3:.1f}" y="{H-mb+16}" font-size="11" fill="var(--muted)">{lab}</text>')
        m = dt.date(m.year + (m.month == 12), m.month % 12 + 1, 1)
        i += 1
    # seuil d'alerte
    if chiffres.get("alerte"):
        ya = Y(chiffres["alerte"])
        s.append(f'<line x1="{ml}" x2="{W-mr}" y1="{ya:.1f}" y2="{ya:.1f}" stroke="var(--acheter)" stroke-dasharray="4 4"/>'
                 f'<text x="{W-mr}" y="{ya-5:.1f}" text-anchor="end" font-size="11" fill="var(--acheter)">alerte {chiffres["alerte"]} €</text>')
    # aujourd'hui
    xt = X(aujourdhui)
    s.append(f'<line x1="{xt:.1f}" x2="{xt:.1f}" y1="{mt}" y2="{H-mb}" stroke="var(--muted)" stroke-dasharray="2 3"/>')
    # meilleur prix du jour (ligne en escalier)
    jours = sorted(serie.items())
    if len(jours) > 1:
        chemin = []
        prec = None
        for d, val in jours:
            x, y = X(d), Y(val["prix"])
            if prec is None or (d - prec).days > 45:  # trou dans les donnees : on ne relie pas
                chemin.append(f"M{x:.1f},{y:.1f}")
            else:
                chemin.append(f"H{x:.1f}V{y:.1f}")
            prec = d
        s.append(f'<path d="{" ".join(chemin)}" fill="none" stroke="var(--serie)" stroke-width="1.5" opacity=".55"/>')
    for d, p, src in pts:
        s.append(f'<circle cx="{X(d):.1f}" cy="{Y(p):.1f}" r="3.5" fill="var(--{src})">'
                 f'<title>{d:%d/%m/%Y} · {euros(p)} · {SOURCES.get(src, src)}</title></circle>')
    s.append("</svg>")
    return "".join(s)


def carte(art, rows, res, journal, auj):
    code, titre, expli = res["verdict"]
    c = res["chiffres"]
    o = []
    o.append("<article>")
    o.append(f"<h2>{e(art['nom'])}</h2>")
    meta = [art.get("reference"), art.get("variante"),
            f"à acheter avant le {res['limite']:%d/%m/%Y}",
            f"budget {euros(art['budget_max'])}" if art.get("budget_max") else None]
    o.append(f'<div class="meta">{" · ".join(e(m) for m in meta if m)}</div>')
    o.append(f'<div class="verdict" style="--c:var(--{code})"><div class="tag">{LIBELLES[code]}</div>'
             f'<div class="titre">{e(titre)}</div><p>{e(expli)}</p>'
             + (f'<p class="sub" style="margin-top:6px">Fiabilité {e(c["fiabilite"])} : basé sur '
                f'{c["n_releves"]} jour(s) de prix relevés.</p>' if c.get("n_releves") else "")
             + '</div>')

    act = res.get("actuel")
    k = []
    k.append(("Prix actuel le plus bas", euros(act["prix"]) if act else "non lisible",
              e(act["marchand"]) if act else "sites bloqués : saisie manuelle"))
    if c.get("min_12m"):
        dispo = c.get("min_12m_dispo")
        k.append(("Plus bas sur 12 mois", euros(c["min_12m"]),
                  f"{c['min_12m_date']:%d/%m/%Y}" + (f" · {dispo} taille(s) dispo" if dispo is not None else "")))
    if c.get("meme_periode_an_dernier"):
        k.append(("Même période l'an dernier", euros(c["meme_periode_an_dernier"]), "± 3 semaines"))
    if c.get("meilleur_mois"):
        k.append(("Mois le moins cher", MOIS_AFFICHE[c["meilleur_mois"] - 1], f"médiane {euros(c['meilleur_mois_prix'])}"))
    if c.get("alerte"):
        k.append(("Alerte conseillée", euros(c["alerte"]), "achète si le prix passe dessous"))
    o.append('<div class="kpis">' + "".join(
        f'<div class="kpi"><div class="l">{l}</div><div class="v">{v}</div><div class="d">{d}</div></div>'
        for l, v, d in k) + "</div>")

    for pr in res.get("promos", []):
        lignes = [f"<strong>Promo vérifiée</strong> · {e(pr['marchand'])} : {euros(pr['prix'])} au lieu de "
                  f"{euros(pr['barre'])} (−{pr['remise_affichee']:.0f} % annoncé)"]
        if pr.get("alerte"):
            lignes.append(e(pr["alerte"]))
        if pr.get("contexte"):
            lignes.append(e(pr["contexte"]))
        if len(lignes) == 1:
            lignes.append("Rien d'anormal détecté avec les données disponibles.")
        cls = "box alerte" if pr.get("alerte") or pr.get("contexte") else "box"
        o.append(f'<div class="{cls}">' + "<br>".join(lignes) + "</div>")
    if res["notes"]:
        o.append('<ul class="notes">' + "".join(f"<li>{e(n)}</li>" for n in res["notes"]) + "</ul>")

    o.append(graphique(res["serie"], rows, c, auj))
    o.append('<div class="legende">'
             '<span style="--k:var(--direct)">relevé en direct</span>'
             '<span style="--k:var(--archive)">archive web (Wayback Machine)</span>'
             '<span style="--k:var(--manuel)">saisie manuelle</span>'
             '<span style="--k:var(--serie)">meilleur prix du jour</span></div>')

    # sources
    dernier = {}
    for j in journal:
        dernier.setdefault((j["url"], j["action"]), j)
    der_prix = {}
    for r in rows:
        der_prix[r["url"]] = r
    o.append("<table><tr><th>Marchand</th><th>Coloris</th><th>Lecture directe</th><th>Dernier prix</th></tr>")
    for lien in art.get("liens", []) + art.get("liens_historiques", []):
        j = dernier.get((collecte.cle(lien), "direct"))
        hist = lien in art.get("liens_historiques", [])
        statut = "archives seulement" if hist else (f'<span class="st-{e(j["statut"])}" title="{e(j["detail"])}">'
                                                    f'{e(j["statut"])}</span>' if j else "pas encore essayé")
        dp = der_prix.get(collecte.cle(lien))
        dp_txt = f"{euros(dp['prix'])} <span class='sub'>({dp['ts'][:10]})</span>" if dp else "—"
        o.append(f'<tr><td><a href="{e(lien["url"])}">{e(lien.get("marchand", "?"))}</a></td>'
                 f'<td>{e(lien.get("coloris", ""))}</td><td>{statut}</td><td class="num">{dp_txt}</td></tr>')
    o.append("</table>")
    o.append(f"<details><summary>Repère de saison (règle générale)</summary><p>{e(res['repere'])}</p></details>")
    o.append("</article>")
    return "".join(o)


def generer(analyses, aujourdhui=None):
    auj = aujourdhui or dt.date.today()
    corps = "".join(carte(a, r, res, j, auj) for a, r, res, j in analyses)
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>PrixJuste</title>
<style>{CSS}</style></head><body><main>
<header class="top"><h1>PrixJuste</h1><div class="sub">Mis à jour le {dt.datetime.now():%d/%m/%Y à %H:%M}</div></header>
{corps}
<footer>Verdicts calculés uniquement à partir de prix réellement relevés (en direct, archives web publiques ou saisis à la main).
Les sites qui refusent les robots ne sont jamais contournés.</footer>
</main></body></html>"""
