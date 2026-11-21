"""Stockage en fichiers texte lisibles dans le dépôt.

data/articles/<id>.json    un article (objet, variante, urgence, liens marchands)
data/releves/<id>.jsonl    un relevé de prix par ligne, append-only (jamais réécrit)
data/journal/<id>.jsonl    chaque tentative de lecture (ok / bloqué / vide / erreur), append-only
data/wayback/<id>.jsonl    captures d'archives déjà lues (pour ne pas les relire), append-only
"""
import datetime as dt
import json
import os
import re
import unicodedata
from pathlib import Path

RACINE = Path(os.environ.get("PRIXJUSTE_DATA") or Path(__file__).resolve().parent.parent / "data")

# ordre des champs d'un relevé (lisible en diff)
CHAMPS_RELEVE = ["ts", "lien", "marchand", "exact", "source", "prix", "devise", "livraison", "en_stock",
                 "n_offres", "n_dispo", "prix_barre", "note"]


try:
    from zoneinfo import ZoneInfo
    _PARIS = ZoneInfo("Europe/Paris")
except Exception:  # pragma: no cover - base de fuseaux absente
    _PARIS = None


def maintenant():
    """Heure de Paris, sans fuseau (les relevés V1 étaient en heure locale française)."""
    return dt.datetime.now(dt.timezone.utc).astimezone(_PARIS).replace(microsecond=0, tzinfo=None).isoformat()


def aujourdhui():
    return dt.date.fromisoformat(maintenant()[:10])


class Depot:
    def __init__(self, racine=None):
        self.racine = Path(racine or RACINE)

    def _f(self, dossier, ident, ext):
        return self.racine / dossier / f"{ident}.{ext}"

    # ------------------------------------------------------------ articles
    def articles(self):
        d = self.racine / "articles"
        if not d.exists():
            return []
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json"))]

    def article(self, ident):
        p = self._f("articles", ident, "json")
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def ecrire_article(self, art):
        p = self._f("articles", art["id"], "json")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(art, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return p

    def nouvel_id(self, nom):
        base = slug(nom) or "article"
        ident, i = base, 2
        while self._f("articles", ident, "json").exists():
            ident, i = f"{base}-{i}", i + 1
        return ident

    # ------------------------------------------------------------ fichiers append-only
    def _lire_jsonl(self, dossier, ident):
        p = self._f(dossier, ident, "jsonl")
        if not p.exists():
            return []
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]

    def _ajouter_jsonl(self, dossier, ident, lignes):
        if not lignes:
            return
        p = self._f(dossier, ident, "jsonl")
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            for l in lignes:
                f.write(json.dumps(l, ensure_ascii=False, separators=(",", ":")) + "\n")

    def releves(self, ident):
        return self._lire_jsonl("releves", ident)

    def ajouter_releve(self, ident, r):
        """Ajoute un relevé, sauf doublon exact (même lien, même source, même horodatage)."""
        ligne = {k: r[k] for k in CHAMPS_RELEVE if r.get(k) is not None}
        cle = (ligne.get("lien"), ligne.get("source"), ligne.get("ts"))
        if any((x.get("lien"), x.get("source"), x.get("ts")) == cle for x in self.releves(ident)):
            return False
        self._ajouter_jsonl("releves", ident, [ligne])
        return True

    def journal(self, ident):
        return self._lire_jsonl("journal", ident)

    def noter(self, ident, lien, action, statut, detail="", ts=None):
        self._ajouter_jsonl("journal", ident, [{"ts": ts or maintenant(), "lien": lien, "action": action,
                                                "statut": statut, "detail": detail}])

    def captures_vues(self, ident):
        return {(x["lien"], x["ts"]) for x in self._lire_jsonl("wayback", ident)}

    def marquer_capture(self, ident, lien, ts):
        self._ajouter_jsonl("wayback", ident, [{"lien": lien, "ts": ts}])


def slug(texte):
    t = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    mots = [m for m in t.split("-") if m not in {"le", "la", "les", "de", "du", "des", "pour", "un", "une", "en", "et"}]
    return "-".join(mots)[:40].strip("-")
