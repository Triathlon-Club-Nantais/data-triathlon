"""Les textes légaux du front (#333) nomment ce que l'API pose réellement.

Un cookie renommé ici rendrait la politique de confidentialité fausse sans
qu'aucun test front ne bronche : le front ne connaît pas ces constantes.
"""
from pathlib import Path

import pytest

from app.api.v1.auth import LOGGED_IN_COOKIE, SESSION_COOKIE, STATE_COOKIE
from app.services.benevole_access import BENEVOLE_SESSION_COOKIE
from app.services.site_access import SITE_SESSION_COOKIE

LEGAL = Path(__file__).resolve().parents[2] / "frontend" / "components" / "legal" / "content"


@pytest.mark.parametrize(
    "cookie",
    [SESSION_COOKIE, STATE_COOKIE, LOGGED_IN_COOKIE, SITE_SESSION_COOKIE, BENEVOLE_SESSION_COOKIE],
)
def test_privacy_policy_lists_every_api_cookie(cookie):
    assert f'"{cookie}"' in (LEGAL / "confidentialite.tsx").read_text(encoding="utf-8")


def test_legal_notice_states_the_declared_license():
    assert "AGPL-3.0-or-later" in (LEGAL / "mentions-legales.tsx").read_text(encoding="utf-8")
