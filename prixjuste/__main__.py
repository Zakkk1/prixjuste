"""PrixJuste — ligne de commande (utilisée par les workflows GitHub Actions, utilisable en local).

  python -m prixjuste collecter [--article ID]        relevé direct du jour (1 par page et par jour max)
  python -m prixjuste historique [--article ID]       import des archives Wayback non encore lues
  python -m prixjuste prix ID PRIX [--barre 500] [--marchand X] [--date AAAA-MM-JJ] [--rupture]
  python -m prixjuste verdicts                        affiche le verdict de chaque article
  python -m prixjuste site [--sortie site]            génère le site statique
  python -m prixjuste issue --numero N                traite une issue « ajout » ou « prix »
                                                      (titre/corps lus dans ISSUE_TITLE / ISSUE_BODY)
  python -m prixjuste premier-releve ID               relevé + archives + compte rendu (après un ajout)
"""
import argparse
import os
import sys
from pathlib import Path

from . import ajout, analyse, collecte
from .donnees import Depot


def _articles(depot, ident=None, statut="suivi"):
    arts = [a for a in depot.articles() if a.get("statut", "suivi") == statut or statut is None]
    if ident:
        arts = [a for a in arts if a["id"] == ident]
        if not arts:
            sys.exit(f"Article inconnu ou pas encore suivi : {ident}")
    return arts


def _sortie_github(**kv):
    """Valeurs lues par le workflow (fichier GITHUB_OUTPUT), affichées sinon."""
    f = os.environ.get("GITHUB_OUTPUT")
    lignes = []
    for k, v in kv.items():
        v = "" if v is None else str(v)
        if "\n" in v:
            lignes.append(f"{k}<<FIN_PRIXJUSTE\n{v}\nFIN_PRIXJUSTE")
        else:
            lignes.append(f"{k}={v}")
    if f:
        with open(f, "a", encoding="utf-8") as h:
            h.write("\n".join(lignes) + "\n")
    else:
        print("\n".join(lignes))


def cmd_issue(depot, a):
    titre = os.environ.get("ISSUE_TITLE", "")
    corps = os.environ.get("ISSUE_BODY", "")
    labels = {x.strip() for x in os.environ.get("ISSUE_LABELS", "").split(",") if x.strip()}
    if "prix" in labels:
        try:
            p = ajout.lire_prix_vu(titre, corps, depot.articles())
        except ValueError as e:
            _sortie_github(mode="erreur", message=str(e))
            return
        art = depot.article(p["article"])
        collecte.prix_manuel(depot, art, p["prix"], p["marchand"], p["barre"], p["date"], p["rupture"], p["note"])
        texte = (f"Prix enregistré : {ajout.euros(p['prix'])} chez {p['marchand']}"
                 + (f" (barré {ajout.euros(p['barre'])})" if p["barre"] else "") + ".\n\n"
                 + ajout.compte_rendu(art, depot.releves(art["id"]), depot.journal(art["id"])))
        _sortie_github(mode="prix", id=art["id"], message=texte)
        return
    # ajout : une issue déjà traitée ne crée pas de doublon
    for art in depot.articles():
        if str(art.get("issue")) == str(a.numero):
            _sortie_github(mode="deja", id=art["id"], statut=art.get("statut"))
            return
    demande = ajout.lire_demande(titre, corps)
    if not demande["objet"] and not demande["liens"]:
        _sortie_github(mode="erreur", message="Je n'ai trouvé ni objet ni lien dans cette demande.")
        return
    art = ajout.creer_article(depot, demande, issue=a.numero)
    _sortie_github(mode="liens" if art["statut"] == "suivi" else "a_identifier", id=art["id"])


def cmd_premier_releve(depot, ident, max_captures):
    art = depot.article(ident)
    if not art:
        sys.exit(f"Article inconnu : {ident}")
    if art.get("statut") != "suivi" and art.get("liens"):
        art["statut"] = "suivi"
        depot.ecrire_article(art)
    print(f"# {art['nom']}")
    collecte.collecter_article(depot, art)
    collecte.historique_article(depot, art, max_captures)
    texte = ajout.compte_rendu(art, depot.releves(ident), depot.journal(ident))
    print(texte)
    _sortie_github(message=texte)


def cmd_verdicts(depot):
    for art in _articles(depot):
        res = analyse.analyser(art, depot.releves(art["id"]))
        code, titre, expli = res["verdict"]
        c = res["chiffres"]
        print(f"{art['id']:<24} {ajout.LIBELLES[code]:<22} {titre} — {expli} "
              f"[fiabilité {c.get('fiabilite')}, {c.get('n_releves', 0)} j]")


def main(argv=None):
    p = argparse.ArgumentParser(prog="prixjuste", description="PrixJuste")
    p.add_argument("--data", help="dossier des données (défaut : data/)")
    sp = p.add_subparsers(dest="cmd", required=True)
    co = sp.add_parser("collecter")
    co.add_argument("--article")
    h = sp.add_parser("historique")
    h.add_argument("--max", type=int, default=40)
    h.add_argument("--article")
    pr = sp.add_parser("prix")
    pr.add_argument("id")
    pr.add_argument("prix", type=float)
    pr.add_argument("--barre", type=float)
    pr.add_argument("--marchand")
    pr.add_argument("--date")
    pr.add_argument("--rupture", action="store_true")
    sp.add_parser("verdicts")
    si = sp.add_parser("site")
    si.add_argument("--sortie", default="site")
    iss = sp.add_parser("issue")
    iss.add_argument("--numero", type=int, required=True)
    prr = sp.add_parser("premier-releve")
    prr.add_argument("id")
    prr.add_argument("--max", type=int, default=40)
    a = p.parse_args(argv)
    depot = Depot(a.data) if a.data else Depot()

    if a.cmd == "collecter":
        for art in _articles(depot, a.article):
            print(f"# {art['nom']}")
            collecte.collecter_article(depot, art)
    elif a.cmd == "historique":
        for art in _articles(depot, a.article):
            print(f"# {art['nom']}")
            collecte.historique_article(depot, art, a.max)
    elif a.cmd == "prix":
        art = depot.article(a.id)
        if not art:
            sys.exit(f"Article inconnu : {a.id}")
        collecte.prix_manuel(depot, art, a.prix, a.marchand, a.barre, a.date, a.rupture)
        print(f"Ajouté : {a.id} à {a.prix:.2f} €")
    elif a.cmd == "verdicts":
        cmd_verdicts(depot)
    elif a.cmd == "site":
        from . import build
        build.construire(depot, Path(a.sortie))
    elif a.cmd == "issue":
        cmd_issue(depot, a)
    elif a.cmd == "premier-releve":
        cmd_premier_releve(depot, a.id, a.max)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
