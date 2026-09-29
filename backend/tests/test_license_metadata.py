"""La licence déclarée est la même partout : AGPL v3 « ou ultérieure » (#1007)."""
import json
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPDX = "AGPL-3.0-or-later"


def test_backend_and_frontend_declare_the_same_spdx_identifier():
    pyproject = tomllib.loads((REPO / "backend" / "pyproject.toml").read_text(encoding="utf-8"))
    package = json.loads((REPO / "frontend" / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((REPO / "frontend" / "package-lock.json").read_text(encoding="utf-8"))

    assert pyproject["project"]["license"] == SPDX
    assert package["license"] == SPDX
    assert lock["packages"][""]["license"] == SPDX


def test_the_license_notice_states_the_or_later_choice():
    head = (REPO / "LICENSE").read_text(encoding="utf-8").split("GNU AFFERO GENERAL PUBLIC LICENSE")[0]
    notice = " ".join(head.split())

    assert "Triathlon Club Nantais" in notice
    assert "any later version" in notice
    assert SPDX in (REPO / "README.md").read_text(encoding="utf-8")
