import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PAGES = Path(__file__).resolve().parent / "pages"


@pytest.fixture
def page():
    return lambda nom: (PAGES / nom).read_text(encoding="utf-8")


@pytest.fixture
def depot(tmp_path):
    from prixjuste.donnees import Depot
    return Depot(tmp_path / "data")
