"""Être prévenu sans ouvrir le site : un commentaire sur une issue « Suivi : <article> ».

L'app GitHub du téléphone affiche la notification. Un message seulement quand quelque chose
change vraiment (passage à ACHÈTE, prix sous l'alerte, promo bidon), jamais un message par jour.
L'état déjà signalé est gardé dans data/signaux.json.
"""
import datetime as dt
import json
import os
import urllib.request

from . import analyse, etranger
from .ajout import LIBELLES, euros

ETIQUETTE = "suivi"


def signal(art, res):
    """Ce qui mérite une notification aujourd'hui (ensemble de motifs)."""
    code = res["verdict"][0]
    c = res["chiffres"]
    act = res.get("actuel")
    motifs = set()
    if code == "acheter":
        motifs.add("acheter")
    if code == "bidon":
        motifs.add("bidon")
    if act and c.get("alerte") and act["prix"] <= c["alerte"] and not art.get("achat"):
        motifs.add("alerte")
    if res.get("baisse_apres_achat"):
        motifs.add("baisse_achat")
    if art.get("achat"):
        motifs -= {"acheter", "bidon"}
    return motifs


def message(art, res, nouveaux):
    code, titre, expli = res["verdict"]
    act = res.get("actuel")
    lignes = [f"**{LIBELLES[code]}** — {titre}", "", expli]
    quebec = ""
    if "quebec" in nouveaux:
        q = res["_quebec"]
        quebec = (f"**Au Québec, sous ton alerte** : {q['prix_local']:.2f} $ CA chez {q['marchand']}, soit environ "
                  f"{euros(q['eur_ttc'])} taxes comprises (alerte {euros(res['chiffres']['alerte'])}).")
        if nouveaux == {"quebec"}:
            return quebec
        return message(art, res, nouveaux - {"quebec"}) + "\n\n" + quebec
    if "baisse_achat" in nouveaux:
        b, pr = res["baisse_apres_achat"], res["protection"]
        return (f"**Il a baissé depuis ton achat** : {euros(b['prix'])} chez {b['marchand']}, soit {euros(b['ecart'])} "
                f"de moins que les {euros(pr['prix'])} payés. Tu peux le renvoyer et le racheter, ou demander un geste "
                f"commercial, jusqu'au {pr['fin_retractation']:%d/%m/%Y} (rétractation de 14 jours).")
    if "alerte" in nouveaux and act:
        lignes += ["", f"Le prix est passé sous ton alerte de {euros(res['chiffres']['alerte'])} : "
                       f"{euros(act['prix'])} chez {act.get('marchand')}."]
    return "\n".join(lignes)


def _url_minuscule(url):
    """https://Zakkk1.github.io/x -> https://zakkk1.github.io/x (le nom d'hôte seulement)."""
    if "://" not in url:
        return url
    schema, reste = url.split("://", 1)
    hote, _, chemin = reste.partition("/")
    return f"{schema}://{hote.lower()}" + (f"/{chemin}" if chemin else "")


class GitHub:
    def __init__(self, depot, jeton, api="https://api.github.com"):
        self.depot, self.jeton, self.api = depot, jeton, api

    def _req(self, methode, chemin, donnees=None):
        req = urllib.request.Request(f"{self.api}/repos/{self.depot}{chemin}", method=methode,
                                     data=json.dumps(donnees).encode() if donnees is not None else None,
                                     headers={"Authorization": f"Bearer {self.jeton}",
                                              "Accept": "application/vnd.github+json",
                                              "User-Agent": "PrixJuste-notifications"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read() or b"null")

    def ouvrir(self, titre, corps):
        return self._req("POST", "/issues", {"title": titre, "body": corps, "labels": [ETIQUETTE]})["number"]

    def commenter(self, numero, corps):
        self._req("POST", f"/issues/{numero}/comments", {"body": corps})


def notifier(depot, github, pages_url="", aujourdhui=None, log=print, mention=None):
    pages_url = _url_minuscule(pages_url)
    f = depot.racine / "signaux.json"
    etat = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    envoyes = 0
    for art in depot.articles():
        if art.get("statut", "suivi") != "suivi" or not analyse.a_relever(art, aujourdhui or dt.date.today()):
            continue
        tous = depot.releves(art["id"])
        res = analyse.analyser(art, tous, aujourdhui)
        motifs = signal(art, res)
        comp = etranger.comparaison(tous, (res.get("actuel") or {}).get("prix"), etranger.charger_change(depot),
                                    aujourdhui or dt.date.today())
        if comp and res["chiffres"].get("alerte") and comp["eur_ttc"] <= res["chiffres"]["alerte"] \
                and not art.get("achat"):
            motifs.add("quebec")
            res["_quebec"] = comp
        e = etat.setdefault(art["id"], {})
        nouveaux = motifs - set(e.get("motifs", []))
        if nouveaux:
            corps = message(art, res, nouveaux)
            if pages_url:
                corps += f"\n\nFiche : {pages_url}/a/{art['id']}.html"
            if mention:  # garantit la notification sur le téléphone du propriétaire
                corps += f"\n\n@{mention}"
            if github:
                if not e.get("issue"):
                    e["issue"] = github.ouvrir(f"Suivi : {art['nom']}",
                                               "Les changements importants de cet article sont commentés ici "
                                               "(passage à ACHÈTE, prix sous l'alerte, promo bidon). "
                                               "Abonne-toi à cette issue pour recevoir les notifications.")
                github.commenter(e["issue"], corps)
            log(f"[notification] {art['id']} : {', '.join(sorted(nouveaux))}")
            envoyes += 1
        e["motifs"] = sorted(motifs)
    f.write_text(json.dumps(etat, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return envoyes


def depuis_environnement():
    jeton, depot = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not (jeton and depot):
        return None
    return GitHub(depot, jeton, os.environ.get("GITHUB_API_URL", "https://api.github.com"))
