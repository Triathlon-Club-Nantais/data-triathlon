"""Un démarrage sans authentification le **dit**, sur une base de développement.

Le silence est le contrat en production (FR-036 : le site public reste intact, et
une installation sans secrets est un état légitime). Mais ce silence a un coût
mesuré : un `backend/.env` absent — ou nommé `.env.local`, la convention du
frontend — donne un backend qui démarre normalement, un `/auth/methods` à `[]` et
un écran de connexion qui annonce « aucun moyen de connexion » sans dire pourquoi.
Rien, nulle part, ne nommait la cause.

Le discriminant est `is_sqlite`, et non un neuvième réglage `AUTH_*` : le dépôt
s'en sert déjà comme garde « environnement jetable » dans `scripts/reset_db.py`,
qui refuse de tourner sur une base non-SQLite. Limite assumée de ce choix : un
développement branché sur PostgreSQL n'aura pas l'avertissement.
"""
import logging

from app.core.config import get_settings
from app.main import _warn_if_auth_unconfigured


def _sans(monkeypatch, *reglages: str) -> None:
    """Retire des réglages de la configuration nominale posée par `reglages_auth`."""
    for reglage in reglages:
        monkeypatch.setenv(reglage, "")
    get_settings.cache_clear()


def _journal(caplog) -> str:
    return "\n".join(
        e.getMessage() for e in caplog.records if e.levelno >= logging.WARNING
    )


def test_un_socle_non_configure_nomme_les_deux_reglages_manquants(caplog, monkeypatch):
    """Deux, et non plus trois : la liste d'autorisation a quitté la configuration (#170)."""
    _sans(monkeypatch, "AUTH_SESSION_SECRET_KEY", "AUTH_REDIRECT_BASE_URL")

    with caplog.at_level(logging.WARNING):
        _warn_if_auth_unconfigured()

    journal = _journal(caplog)
    assert "AUTH_SESSION_SECRET_KEY" in journal
    assert "AUTH_REDIRECT_BASE_URL" in journal
    assert "AUTH_ALLOWED_EMAILS" not in journal


def test_seul_le_reglage_reellement_absent_est_nomme(caplog, monkeypatch):
    """Nommer les trois quand un seul manque envoie chercher au mauvais endroit."""
    _sans(monkeypatch, "AUTH_REDIRECT_BASE_URL")

    with caplog.at_level(logging.WARNING):
        _warn_if_auth_unconfigured()

    journal = _journal(caplog)
    assert "AUTH_REDIRECT_BASE_URL" in journal
    assert "AUTH_SESSION_SECRET_KEY" not in journal


def test_un_fournisseur_non_configure_est_nomme_par_son_slug(caplog, monkeypatch):
    """Le socle est complet ici : c'est le fournisseur seul qui manque.

    Distinction structurante — c'est le cas d'un déploiement qui a la clé et la
    liste mais a oublié les identifiants OAuth, où `/auth/methods` rend `[]`
    exactement comme si rien n'était configuré.

    **Le slug, et pas les noms de réglages du fournisseur** : le contrat
    `IdentityProvider` n'énumère aucun mécanisme, et `authorize()` rend un
    `round_trip` opaque précisément pour qu'un futur OIDC n'ait rien à changer
    au flux. Dériver `AUTH_<SLUG>_CLIENT_ID` ici replacerait dans `main.py` la
    connaissance du mécanisme que le contrat refuse — pour un message de journal.
    """
    _sans(monkeypatch, "AUTH_GITHUB_CLIENT_SECRET")

    with caplog.at_level(logging.WARNING):
        _warn_if_auth_unconfigured()

    assert "github" in _journal(caplog)


def test_un_socle_complet_et_un_fournisseur_configure_ne_disent_rien(caplog):
    """La configuration nominale de `conftest` : aucun avertissement."""
    with caplog.at_level(logging.WARNING):
        _warn_if_auth_unconfigured()

    assert _journal(caplog) == ""


def test_une_base_de_production_reste_silencieuse(caplog, monkeypatch):
    """Le silence en production est un choix : pas de bruit dans Sentry pour une
    installation qui n'utilise délibérément pas l'authentification."""
    _sans(monkeypatch, "AUTH_SESSION_SECRET_KEY", "AUTH_REDIRECT_BASE_URL")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user@host/db")
    get_settings.cache_clear()

    with caplog.at_level(logging.WARNING):
        _warn_if_auth_unconfigured()

    assert _journal(caplog) == ""


def test_aucune_valeur_presente_n_est_journalisee(caplog, monkeypatch):
    """FR-038 : l'avertissement nomme ce qui manque, jamais ce qui est là.

    La clé de signature et le secret du fournisseur sont renseignés ; seule
    l'origine de retour manque. Aucune des deux valeurs ne doit apparaître.
    """
    temoin = "valeur-temoin-qui-ne-doit-pas-fuiter-0123456789"
    monkeypatch.setenv("AUTH_SESSION_SECRET_KEY", temoin)
    monkeypatch.setenv("AUTH_GITHUB_CLIENT_SECRET", temoin)
    _sans(monkeypatch, "AUTH_REDIRECT_BASE_URL")

    with caplog.at_level(logging.WARNING):
        _warn_if_auth_unconfigured()

    assert temoin not in _journal(caplog)
    assert "AUTH_REDIRECT_BASE_URL" in _journal(caplog)
