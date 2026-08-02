"""Contrat d'un fournisseur d'identité.

**La signature n'énumère aucun mécanisme** (FR-032). C'est la seule forme qui
survit au second fournisseur : un `authorize(..., verifier: str)` calqué sur PKCE
obligerait, à l'arrivée d'OIDC, à ajouter un `nonce` aux deux méthodes — donc à
modifier le contrat, le flux **et** le fournisseur GitHub existant. Avec un
aller-retour opaque, GitHub y range `{"verifier": …}`, un futur OIDC y rangera
`{"verifier": …, "nonce": …}`, et rien au-dessus ne bouge.

Le `state` CSRF, lui, reste **commun** : il est produit et comparé par le flux,
jamais par un fournisseur — c'est une garantie du socle, pas une variation.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ExternalIdentity:
    """Ce qu'un fournisseur affirme d'une personne, au retour du parcours.

    `email_verified` fait partie du **contrat**, et non du code du fournisseur
    GitHub : c'est ce qui rend l'exigence de certification opposable au
    fournisseur suivant (FR-005).
    """

    provider: str
    subject: str
    email: str
    email_verified: bool
    display_name: str = ""


@dataclass(frozen=True)
class AuthorizationRequest:
    """Où envoyer la personne, et ce qu'il faudra retrouver à son retour.

    `round_trip` est **opaque** : le flux le signe et le restitue sans jamais le
    lire.
    """

    url: str
    round_trip: Mapping[str, str]


class IdentityProvider(Protocol):
    """Un moyen de se connecter.

    `slug` sert de segment d'URL et de valeur en base (`identities.provider`) ;
    `label` est le libellé d'affichage rendu par `GET /auth/methods`.
    """

    slug: str
    label: str

    def is_configured(self) -> bool:
        """Vrai si ce moyen de connexion peut aboutir sur cette installation."""
        ...

    def authorize(self, *, state: str) -> AuthorizationRequest:
        """Prépare le départ. Ne fait **aucune** sortie réseau."""
        ...

    def fetch_identity(
        self, *, code: str, round_trip: Mapping[str, str]
    ) -> ExternalIdentity:
        """Échange le code contre une identité. Lève `LoginError` en cas d'échec."""
        ...
