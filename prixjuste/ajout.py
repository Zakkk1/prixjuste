"""Ajout d'un objet ou d'un prix vu, à partir d'une issue GitHub (sans IA).

Le site ouvre une issue pré-remplie dont le corps ressemble à :

    Objet : Timberland 6-Inch Premium jaune
    Taille : 40
    Coloris : jaune
    Urgence : pas_urgent
    Budget : 230
    Liens :
    https://www.exemple.fr/produit-123

- avec des liens marchands : l'article est créé directement ;
- sans lien : l'article est créé « en attente d'identification » (Claude prendra le relais si activé).

Issue « prix » (prix vu en magasin ou sur un site bloqué) :

    Article : timberland
    Prix : 199
    Prix barré : 230
    Marchand : Courir Lyon
    Date : 2026-11-20
    Rupture : non
"""
import datetime as dt
import re
import unicodedata
import urllib.parse

from . import analyse
from .donnees import aujourdhui

URL_RE = re.compile(r"https?://[^\s<>()\"']+", re.I)
CHAMP_RE = re.compile(r"^\s*(?:[-*]\s*)?(?:\*\*)?([A-Za-zÀ-ÿ' ]{2,30}?)(?:\*\*)?\s*[:：]\s*(.*)$")
TITRE_SECTION_RE = re.compile(r"^#{1,6}\s*(.+?)\s*$")

URGENCES = {"urgent": "urgent", "bientot": "bientot", "bientôt": "bientot", "pas_urgent": "pas_urgent",
            "pas urgent": "pas_urgent", "pas-urgent": "pas_urgent"}

CATEGORIES_MOTS = [
    ("chaussures", r"chaussure|basket|sneaker|boot|botte|bottine|mocassin|derby|sandale|escarpin|running|timberland|pointure"),
    ("vetement_hiver", r"parka|doudoune|manteau|anorak|pull|polaire|bonnet|écharpe|echarpe|gants?\b|veste d'hiver|duvet"),
    ("vetement_ete", r"maillot|short|bermuda|tee-?shirt|t-shirt|robe d'été|sandales?|lunettes de soleil"),
    ("composants_pc", r"\bgpu\b|carte graphique|rtx|radeon|processeur|\bcpu\b|ryzen|\bssd\b|\bram\b|ddr[45]|carte mère|alimentation pc"),
    ("electronique", r"iphone|smartphone|téléphone|telephone|tablette|ipad|ordinateur|laptop|macbook|télé|tele\b|tv\b|"
                     r"console|playstation|ps5|switch|xbox|casque|écouteurs|ecouteurs|airpods|montre connectée|appareil photo|enceinte"),
]


def _cle(t):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower().strip()
    return re.sub(r"\s+", " ", t)


def lire_champs(corps):
    """Lit les lignes « Clé : valeur » (ou les sections « ### Clé » d'un formulaire GitHub)."""
    champs, section = {}, None
    for ligne in (corps or "").replace("\r", "").split("\n"):
        if ligne.strip().startswith("<!--"):
            continue
        m = TITRE_SECTION_RE.match(ligne)
        if m:
            section = _cle(m.group(1))
            continue
        m = CHAMP_RE.match(ligne)
        if m and not ligne.lstrip().lower().startswith("http"):
            section = _cle(m.group(1))
            val = m.group(2).strip()
            if val:
                champs[section] = val
            continue
        if section and ligne.strip() and not URL_RE.match(ligne.strip()):
            champs.setdefault(section, ligne.strip())
    for k, v in list(champs.items()):
        if v.strip().lower() in ("_no response_", "aucun", "aucune", "-", "—"):
            del champs[k]
    return champs


def liens_du_texte(corps):
    vus, res = set(), []
    for u in URL_RE.findall(corps or ""):
        u = u.rstrip(".,;)]>")
        host = urllib.parse.urlsplit(u).netloc.lower()
        if not host or host.endswith("github.com") or u in vus:
            continue
        vus.add(u)
        res.append(u)
    return res


def nom_marchand(url):
    host = urllib.parse.urlsplit(url).netloc.lower()
    host = re.sub(r"^(www\d?|m|shop|fr)\.", "", host)
    base = host.rsplit(".", 1)[0] if host.count(".") >= 1 else host
    if base.startswith("e.") or base == "e":  # e.leclerc
        return "E.Leclerc"
    return base.replace("-", " ").replace(".", " ").title()


def deviner_categorie(texte):
    t = texte.lower()
    for cat, motif in CATEGORIES_MOTS:
        if re.search(motif, t):
            return cat
    return "autre"


def _nombre(v):
    if v is None:
        return None
    m = re.search(r"\d+(?:[.,]\d+)?", v.replace(" ", "").replace(" ", ""))
    return float(m.group(0).replace(",", ".")) if m else None


def _date_iso(v):
    if not v:
        return None
    v = v.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return dt.datetime.strptime(v, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def objet_depuis_titre(titre):
    return re.sub(r"^\s*\[?(ajout|ajouter|prix)\]?\s*[:：-]?\s*", "", titre or "", flags=re.I).strip()


def lire_demande(titre, corps):
    """Demande d'ajout -> dict normalisé."""
    ch = lire_champs(corps)
    objet = ch.get("objet") or ch.get("qu'est-ce que tu veux acheter ?") or objet_depuis_titre(titre)
    urg = URGENCES.get((ch.get("urgence") or "").strip().lower(), None)
    return {
        "objet": (objet or "").strip()[:140],
        "taille": ch.get("taille") or ch.get("pointure"),
        "coloris": ch.get("coloris") or ch.get("couleur"),
        "urgence": urg or "pas_urgent",
        "acheter_avant": _date_iso(ch.get("avant le") or ch.get("date limite")),
        "budget_max": _nombre(ch.get("budget")),
        "liens": liens_du_texte(corps),
    }


def creer_article(depot, demande, issue=None):
    """Crée data/articles/<id>.json. Renvoie l'article."""
    objet = demande["objet"] or "Objet sans nom"
    variante = " · ".join(x for x in (demande.get("coloris"), demande.get("taille") and f"taille {demande['taille']}") if x)
    art = {
        "id": depot.nouvel_id(objet),
        "statut": "suivi" if demande["liens"] else "a_identifier",
        "cree_le": aujourdhui().isoformat(),
        "issue": issue,
        "demande": objet,
        "nom": objet,
        "variante": variante or None,
        "categorie": deviner_categorie(objet),
        "urgence": demande["urgence"],
        "acheter_avant": demande.get("acheter_avant"),
        "budget_max": demande.get("budget_max"),
        "taille": demande.get("taille"),
        "coloris": demande.get("coloris"),
        "autres_coloris_ok": not demande.get("coloris"),
        "liens": [],
        "liens_historiques": [],
    }
    art["liens"] = [_lien(u, demande) for u in demande["liens"]]
    art = {k: v for k, v in art.items() if v is not None}
    depot.ecrire_article(art)
    return art


def _lien(url, demande):
    lien = {"marchand": nom_marchand(url), "url": url, "exact": True}
    if demande.get("coloris"):
        lien["coloris"] = demande["coloris"]
    if demande.get("taille"):
        lien["taille"] = demande["taille"].replace(",", ".")
    return lien


def completer_liens(depot, art, demande):
    """Ajoute à un article en attente les liens apparus dans sa demande ; il passe « suivi »."""
    connus = {l["url"] for l in art.get("liens", [])}
    art.setdefault("liens", []).extend(_lien(u, demande) for u in demande["liens"] if u not in connus)
    art["statut"] = "suivi"
    depot.ecrire_article(art)
    return art


def lire_prix_vu(titre, corps, articles):
    """Issue « prix » -> dict {article, prix, barre, marchand, date, rupture} ou ValueError."""
    ch = lire_champs(corps)
    ident = (ch.get("article") or "").strip()
    ids = {a["id"]: a for a in articles}
    if ident not in ids:  # on accepte aussi le nom affiché
        par_nom = [a for a in articles if _cle(a.get("nom", "")) == _cle(ident)]
        if len(par_nom) == 1:
            ident = par_nom[0]["id"]
        else:
            raise ValueError(f"Article inconnu : « {ident} ». Articles suivis : {', '.join(ids) or 'aucun'}.")
    prix = _nombre(ch.get("prix"))
    if not prix or prix <= 0:
        raise ValueError("Prix manquant ou illisible (exemple attendu : « Prix : 199,90 »).")
    rupture = (ch.get("rupture") or ch.get("en rupture") or "").strip().lower() in ("oui", "yes", "x", "vrai", "true")
    return {"article": ident, "prix": prix, "barre": _nombre(ch.get("prix barre") or ch.get("prix barré")),
            "marchand": ch.get("marchand") or ch.get("magasin") or "vu par toi",
            "date": _date_iso(ch.get("date")), "rupture": rupture, "note": ch.get("note")}


# ---------------------------------------------------------------- comptes rendus (commentaires d'issue)

LIBELLES = {"acheter": "ACHÈTE", "attendre": "ATTENDS", "surveiller": "SURVEILLE", "bidon": "BIDON",
            "donnees": "PAS ASSEZ DE DONNÉES"}


def euros(x):
    if x is None:
        return "—"
    s = f"{x:,.2f}".replace(",", " ").replace(".", ",")
    return (s[:-3] if s.endswith(",00") else s) + " €"


def compte_rendu(art, releves, journal, aujourdhui_=None):
    """Texte Markdown court posté en commentaire : verdict + état de lecture de chaque lien."""
    res = analyse.analyser(art, releves, aujourdhui_)
    code, titre, expli = res["verdict"]
    c = res["chiffres"]
    lignes = [f"**{LIBELLES[code]}** — {titre}", "", expli, ""]
    if res.get("actuel"):
        lignes.append(f"- Meilleur prix actuel : {euros(res['actuel']['prix'])} ({res['actuel'].get('marchand')})")
    if c.get("min_12m"):
        lignes.append(f"- Plus bas sur 12 mois : {euros(c['min_12m'])} le {c['min_12m_date']:%d/%m/%Y}")
    if c.get("alerte"):
        lignes.append(f"- Alerte conseillée : {euros(c['alerte'])}")
    lignes.append(f"- Fiabilité {c.get('fiabilite', 'faible')} : {c.get('n_releves', 0)} jour(s) de prix connus")
    lignes += ["", "| Marchand | Lecture |", "|---|---|"]
    from .collecte import cle
    dernier = {}
    for j in journal:
        if j["action"] == "direct":
            dernier[j["lien"]] = j
    for lien in art.get("liens", []):
        j = dernier.get(cle(lien))
        etat = f"{j['statut']} ({j['detail']})" if j else "pas encore lu"
        lignes.append(f"| {lien.get('marchand')} | {etat} |")
    return "\n".join(lignes)
