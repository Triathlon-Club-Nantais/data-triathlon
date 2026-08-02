"""Fixtures du socle d'authentification (#114).

`get_settings()` est `@lru_cache` et `Settings` lit `backend/.env` : sans
isolation, un développeur ayant de vrais secrets locaux verrait ces tests passer
**pour la mauvaise raison**, pendant que l'intégration continue — qui n'a pas de
`.env` — diverge. Le dépôt a déjà ce motif exact dans `tests/test_migrations.py`.
"""
import pytest

from app.core.config import get_settings
from app.services.auth.idp import registry
from app.services.auth.idp.base import AuthorizationRequest, ExternalIdentity

#: Configuration nominale : authentification pleinement configurée. Un test qui
#: éprouve l'absence de configuration surcharge ce qu'il lui faut, jamais
#: l'inverse — c'est le cas nominal qui doit être le défaut.
REGLAGES = {
    "AUTH_SESSION_SECRET_KEY": "k" * 48,
    "AUTH_GITHUB_CLIENT_ID": "Iv1.test-client-id",
    "AUTH_GITHUB_CLIENT_SECRET": "test-client-secret",
    "AUTH_ALLOWED_EMAILS": "contributeur@exemple.fr",
    "AUTH_REDIRECT_BASE_URL": "http://127.0.0.1:3000",
    "AUTH_COOKIE_SECURE": "false",
    "AUTH_SESSION_TTL_DAYS": "7",
    "AUTH_STATE_TTL_SECONDS": "600",
}


@pytest.fixture(autouse=True)
def reglages_auth(monkeypatch):
    """Pose les réglages d'authentification et vide le cache **avant et après**.

    Après aussi : le cache est un état de processus, et une instance construite
    ici survivrait au test pour être servie au suivant — y compris hors de ce
    paquet.
    """
    for cle, valeur in REGLAGES.items():
        monkeypatch.setenv(cle, valeur)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings(reglages_auth):
    """Réglages effectifs du test courant, après d'éventuelles surcharges."""
    return get_settings()


class DoublureProvider:
    """Fournisseur d'identité factice — **jamais** enregistré au niveau module.

    Le registre tient des singletons de module peuplés à l'import : une doublure
    enregistrée de la même façon existerait **en production** (FR-034), et
    `is_configured()` ne la masquerait que par configuration — c'est un garde de
    configuration, pas un garde de sécurité.

    Son aller-retour porte une clé que GitHub n'a pas : c'est ce qui prouve que
    le flux ne l'interprète pas (FR-032).
    """

    slug = "doublure"
    label = "Doublure de test"

    def __init__(self) -> None:
        self.configure = True
        self.identite = ExternalIdentity(
            provider=self.slug,
            subject="doublure-1",
            email="contributeur@exemple.fr",
            email_verified=True,
            display_name="contributeur",
        )
        self.appels: list[dict] = []

    def is_configured(self) -> bool:
        return self.configure

    def authorize(self, *, state: str) -> AuthorizationRequest:
        return AuthorizationRequest(
            url=f"https://doublure.exemple/authorize?state={state}",
            round_trip={"cle-inventee": "valeur"},
        )

    def fetch_identity(self, *, code: str, round_trip) -> ExternalIdentity:
        self.appels.append({"code": code, "round_trip": dict(round_trip)})
        return self.identite


@pytest.fixture
def doublure(monkeypatch) -> DoublureProvider:
    """Enregistre une doublure **le temps du test**, par `monkeypatch.setitem`."""
    faux = DoublureProvider()
    monkeypatch.setitem(registry.PROVIDERS, faux.slug, faux)
    return faux
