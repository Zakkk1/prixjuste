import datetime as dt

from prixjuste import notifier
from tests.test_analyse import AUJ, annee, o


class FauxGitHub:
    def __init__(self):
        self.issues, self.commentaires = [], []

    def ouvrir(self, titre, corps):
        self.issues.append(titre)
        return len(self.issues)

    def commenter(self, numero, corps):
        self.commentaires.append((numero, corps))


def preparer(depot, obs):
    depot.ecrire_article({"id": "x", "nom": "Parka X", "categorie": "autre", "urgence": "pas_urgent", "liens": []})
    for r in obs:
        depot.ajouter_releve("x", r)


def test_un_seul_message_par_changement(depot):
    preparer(depot, annee(lambda m: 250) + [o(AUJ, 199)])
    gh = FauxGitHub()
    assert notifier.notifier(depot, gh, "https://ex.io/pj", AUJ, log=lambda *a: None, mention="moi") == 1
    assert gh.issues == ["Suivi : Parka X"]
    num, corps = gh.commentaires[0]
    assert corps.startswith("**ACHÈTE**") and "https://ex.io/pj/a/x.html" in corps and corps.endswith("@moi")
    # le lendemain, rien de neuf : pas de message
    assert notifier.notifier(depot, gh, "", AUJ + dt.timedelta(days=1), log=lambda *a: None) == 0
    assert len(gh.commentaires) == 1


def test_pas_de_message_sans_signal(depot):
    preparer(depot, [o(AUJ, 199)])
    gh = FauxGitHub()
    assert notifier.notifier(depot, gh, "", AUJ, log=lambda *a: None) == 0
    assert gh.issues == []
    assert (depot.racine / "signaux.json").exists()
