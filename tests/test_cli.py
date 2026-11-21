import re

import pytest

from nemeton_canopee import __version__
from nemeton_canopee.cli import main


def test_version_est_une_version_pep440():
    # Version calendaire AAAA.MM.N en release, suffixe .devN entre deux tags, 0.0.0 sans tag.
    assert re.fullmatch(r"\d+\.\d+\.\d+(\.dev\d+)?", __version__)


def test_option_version_affiche_la_version(capsys):
    with pytest.raises(SystemExit) as sortie:
        main(["--version"])
    assert sortie.value.code == 0
    assert capsys.readouterr().out.strip() == f"canopee {__version__}"


def test_sans_argument_affiche_l_aide(capsys):
    assert main([]) == 0
    assert "canopee" in capsys.readouterr().out
