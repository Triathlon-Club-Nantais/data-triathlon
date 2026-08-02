"""Registre des fournisseurs d'identité.

Peuplé **à l'import**, comme le registre des scrapers. C'est précisément pour
cela qu'une doublure de test ne s'y enregistre jamais au niveau module : elle
existerait en production (FR-034), et `is_configured()` ne la masquerait que par
configuration — c'est un garde de configuration, pas un garde de sécurité, et il
ne survit pas à une variable d'environnement traînante. Une doublure atteignable
en production est un contournement d'authentification complet.

Les tests l'enregistrent donc par `monkeypatch.setitem(registry.PROVIDERS, …)`,
et un test normatif vérifie dans un **processus neuf** que le registre chargé à
froid ne contient que GitHub.
"""
from app.services.auth.idp.base import IdentityProvider
from app.services.auth.idp.github import GithubIdentityProvider

#: Slug -> fournisseur. Public parce que les tests y substituent une entrée ;
#: le reste du code passe par `get()` et `enabled_methods()`.
PROVIDERS: dict[str, IdentityProvider] = {}


def register(provider: IdentityProvider) -> None:
    PROVIDERS[provider.slug] = provider


def get(slug: str) -> IdentityProvider | None:
    return PROVIDERS.get(slug)


def slugs() -> list[str]:
    return sorted(PROVIDERS)


def enabled_methods() -> list[IdentityProvider]:
    """Moyens de connexion **effectivement disponibles** (FR-031).

    C'est la source de l'écran de connexion : l'interface n'en code aucun en dur,
    et une liste vide est une réponse valide qui signifie « aucune connexion
    possible ».
    """
    return [provider for provider in (PROVIDERS[slug] for slug in slugs()) if provider.is_configured()]


register(GithubIdentityProvider())
