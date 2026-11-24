"""Les dossiers de l'assistant d'achat : ce que Claude a trouvé à ta demande, gardé et publié sur le site.

Trois sortes de dossiers, un fichier JSON chacun dans data/dossiers/ :
  - « tenue »      : une photo de look -> les pièces exactes, des versions moins chères, le meilleur du style ;
  - « achat »      : « je veux ce produit, voilà ma taille » -> partout en France et au Canada, achète ou attends ;
  - « bons-plans » : les vraies bonnes affaires du moment pour toi (Black Friday, soldes…), pièges compris.

Claude écrit le fichier (procédure : docs/ASSISTANT.md), `python -m prixjuste dossier FICHIER` le vérifie,
le site l'affiche. Aucune photo de personne n'est publiée : seulement les photos produit des boutiques.
"""
import datetime as dt
import json
import re

from . import etranger

TYPES = {"tenue": "Tenue", "achat": "Achat", "bons-plans": "Bons plans"}
VERDICTS = {  # code -> (classe du tampon, libellé)
    "acheter": ("achete", "ACHÈTE"),
    "attendre": ("attends", "ATTENDS"),
    "surveiller": ("surveille", "SURVEILLE"),
    "eviter": ("bidon", "ÉVITE"),
    "deja": ("donnees", "TU L'AS"),
}
URL_RE = re.compile(r"^https?://[^\s]+$")


def charger(depot):
    dos = depot.racine / "dossiers"
    if not dos.exists():
        return []
    L = []
    for f in sorted(dos.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        d.setdefault("id", f.stem)
        L.append(d)
    return sorted(L, key=lambda d: (d.get("le", ""), d["id"]), reverse=True)


# ---------------------------------------------------------------- prix

def en_euros(piece, change):
    """Prix en euros, taxes du pays comprises (au Québec : TPS + TVQ ajoutées en caisse)."""
    p = piece.get("prix")
    if p is None:
        return None
    devise = piece.get("devise", "EUR")
    if devise == "EUR":
        return float(p)
    if not change or devise not in change.get("taux", {}):
        return None
    ht = p / change["taux"][devise]
    pays = etranger.PAYS.get(piece.get("pays") or "")
    taxes = pays["taxes"] if pays and pays["devise"] == devise else 0
    return round(ht * (1 + taxes), 2)


def total(pieces, change):
    """Somme des pièces à acheter (celles que tu as déjà ne comptent pas). None si un prix manque."""
    s = 0.0
    for p in pieces:
        if p.get("verdict") == "deja":
            continue
        v = en_euros(p, change)
        if v is None:
            return None
        s += v
    return round(s, 2)


def pieces(d):
    if d.get("type") == "tenue":
        return [p for o in d.get("options", []) for p in o.get("pieces", [])]
    if d.get("type") == "achat":
        return [d["produit"]] + d.get("offres", []) + d.get("equivalents", []) if d.get("produit") else d.get("offres", [])
    return d.get("plans", [])


# ---------------------------------------------------------------- vérification

def _date(v):
    try:
        dt.date.fromisoformat(str(v))
        return True
    except ValueError:
        return False


def _verifier_piece(p, ou, err, verdict_requis=True):
    if not p.get("nom"):
        err.append(f"{ou} : « nom » manquant")
    if p.get("prix") is not None and not isinstance(p["prix"], (int, float)):
        err.append(f"{ou} : « prix » doit être un nombre")
    if p.get("prix_avant") is not None and not isinstance(p["prix_avant"], (int, float)):
        err.append(f"{ou} : « prix_avant » doit être un nombre")
    if p.get("devise", "EUR") not in ("EUR", "CAD", "USD", "GBP", "CHF"):
        err.append(f"{ou} : devise inconnue {p.get('devise')!r}")
    if p.get("devise", "EUR") != "EUR" and not p.get("pays"):
        err.append(f"{ou} : prix en {p.get('devise')} sans « pays » (ex. \"CA\")")
    for k in ("url", "image"):
        if p.get(k) and not URL_RE.match(p[k]):
            err.append(f"{ou} : « {k} » n'est pas une adresse web")
    if p.get("prix") is not None and not p.get("url"):
        err.append(f"{ou} : un prix sans « url » n'est pas vérifiable")
    if verdict_requis and p.get("verdict") not in VERDICTS:
        err.append(f"{ou} : « verdict » doit être l'un de {', '.join(VERDICTS)}")
    for k in ("fin", "vu_le"):
        if p.get(k) and not _date(p[k]):
            err.append(f"{ou} : « {k} » doit être une date AAAA-MM-JJ")


def verifier(d, articles=()):
    """Liste des problèmes (vide si le dossier est publiable)."""
    err = []
    t = d.get("type")
    if t not in TYPES:
        return [f"« type » doit être l'un de {', '.join(TYPES)}"]
    for k in ("titre", "le", "resume"):
        if not d.get(k):
            err.append(f"« {k} » manquant")
    if d.get("le") and not _date(d["le"]):
        err.append("« le » doit être une date AAAA-MM-JJ")
    if d.get("valable_jusqu_au") and not _date(d["valable_jusqu_au"]):
        err.append("« valable_jusqu_au » doit être une date AAAA-MM-JJ")
    if t == "tenue":
        if not d.get("options"):
            err.append("une tenue a au moins une option")
        for i, o in enumerate(d.get("options", []), 1):
            if not o.get("nom"):
                err.append(f"option {i} : « nom » manquant")
            if not o.get("pieces"):
                err.append(f"option {i} : aucune pièce")
            for j, p in enumerate(o.get("pieces", []), 1):
                _verifier_piece(p, f"option {i}, pièce {j}", err)
    elif t == "achat":
        if d.get("verdict") not in VERDICTS:
            err.append(f"« verdict » doit être l'un de {', '.join(VERDICTS)}")
        if not d.get("produit"):
            err.append("« produit » manquant")
        else:
            _verifier_piece(d["produit"], "produit", err, verdict_requis=False)
        if not d.get("offres"):
            err.append("un achat compare au moins une offre")
        for j, p in enumerate(d.get("offres", []), 1):
            _verifier_piece(p, f"offre {j}", err, verdict_requis=False)
        for j, p in enumerate(d.get("equivalents", []), 1):
            _verifier_piece(p, f"équivalent {j}", err)
        if d.get("quand") and not _date(d["quand"]):
            err.append("« quand » doit être une date AAAA-MM-JJ")
    else:
        if not d.get("plans"):
            err.append("aucun bon plan")
        for j, p in enumerate(d.get("plans", []), 1):
            _verifier_piece(p, f"plan {j}", err)
    ids = {a["id"] for a in articles}
    for p in pieces(d) + ([d] if d.get("article") else []):
        if p.get("article") and ids and p["article"] not in ids:
            err.append(f"« article » {p['article']!r} : aucun article suivi de ce nom")
    for s in d.get("sources", []):
        if not (isinstance(s, dict) and s.get("url") and URL_RE.match(s["url"])):
            err.append(f"source invalide : {s!r:.80}")
    return err


def resume_texte(d, change=None):
    """Résumé lisible en terminal (ce que Claude relit avant de répondre)."""
    L = [f"{TYPES[d['type']]} — {d['titre']} ({d['le']})", d.get("resume", "")]
    if d["type"] == "tenue":
        for o in d["options"]:
            t = total(o["pieces"], change)
            L.append(f"  {o['nom']} : " + (f"{t:.2f} €" if t is not None else "total incomplet"))
            for p in o["pieces"]:
                v = en_euros(p, change)
                L.append(f"    [{VERDICTS[p['verdict']][1]}] {p['nom']} " + (f"{v:.2f} €" if v is not None else "—"))
    elif d["type"] == "achat":
        L.append(f"  Verdict : {VERDICTS[d['verdict']][1]}" + (f" — cible {d['prix_cible']} €" if d.get("prix_cible") else ""))
        for p in sorted(d["offres"], key=lambda p: en_euros(p, change) or 9e9):
            v = en_euros(p, change)
            L.append(f"    {p.get('marchand', '?')} : " + (f"{v:.2f} €" if v is not None else "—")
                     + ("" if p.get("en_stock", True) else " (pas dans ta taille)"))
    else:
        for p in d["plans"]:
            v = en_euros(p, change)
            L.append(f"    [{VERDICTS[p['verdict']][1]}] {p['nom']} " + (f"{v:.2f} €" if v is not None else "—"))
    return "\n".join(L)
