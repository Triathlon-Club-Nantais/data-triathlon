"""Tests de l'initialisation du client PostHog (issue #339).

Ces tests couvrent le seul chemin qui n'était joué **nulle part** avant eux :
celui où un token est présent, donc où le client est réellement construit. En
développement comme en CI la variable `POSTHOG_PROJECT_TOKEN` est vide, donc
`init_posthog` retournait tôt et le constructeur n'était jamais appelé — un
mauvais nom d'argument y a survécu jusqu'à casser le démarrage en production.

Aucun réseau : construire un client n'émet rien (la file est vide), et
`shutdown()` arrête son thread et restaure le `sys.excepthook` que
l'autocapture d'exceptions installe.
"""
import pytest

FAKE_TOKEN = "phc_fake_token_for_tests"
#: Hôte jamais contacté — le test ne capture aucun événement. Le port 9
#: (discard) rendrait l'échec immédiat et bruyant si cela changeait.
FAKE_HOST = "http://127.0.0.1:9"


@pytest.fixture(autouse=True)
def _etat_propre():
    """L'instance est un état de module : la laisser en place ferait enfiler des
    événements aux tests d'API qui suivent, donc on la démonte des deux côtés."""
    from app.core import analytics

    analytics.shutdown_posthog()
    analytics.posthog_client = None
    yield
    analytics.shutdown_posthog()
    analytics.posthog_client = None


def test_init_posthog_construit_le_client_avec_le_token():
    """Régression : les arguments passés au constructeur doivent être ceux que
    le SDK accepte. `Posthog(api_key=...)` levait `TypeError` au démarrage."""
    from app.core import analytics

    analytics.init_posthog(token=FAKE_TOKEN, host=FAKE_HOST, debug=False)

    assert analytics.posthog_client is not None
    assert analytics.posthog_client.api_key == FAKE_TOKEN
    assert analytics.posthog_client.host == FAKE_HOST


def test_init_posthog_active_l_autocapture_des_exceptions():
    """Le produit « Error Tracking » est la raison d'être de la variable : sans
    ce drapeau, aucune exception non gérée ne remonte."""
    from app.core import analytics

    analytics.init_posthog(token=FAKE_TOKEN, host=FAKE_HOST, debug=False)

    assert analytics.posthog_client.enable_exception_autocapture is True


def test_init_posthog_sans_token_ne_construit_rien():
    """Un token vide est un état légitime : pas de client, pas d'exception."""
    from app.core import analytics

    analytics.init_posthog(token="", host=FAKE_HOST, debug=False)

    assert analytics.posthog_client is None


def test_capture_event_sans_client_ne_leve_pas():
    """Les sites d'appel n'ont aucune garde : `capture_event` doit être inerte
    quand PostHog n'est pas configuré."""
    from app.core import analytics

    analytics.capture_event("test_event", distinct_id="anonymous", properties={"a": 1})
    analytics.set_person_properties("anonymous", {"is_staff": False})
