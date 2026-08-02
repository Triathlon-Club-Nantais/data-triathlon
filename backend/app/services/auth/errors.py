"""Codes d'échec du parcours de connexion — **ensemble fermé** (FR-028).

Un code, et rien d'autre, franchit la frontière vers l'interface : jamais un
message venu du fournisseur, jamais une donnée d'entrée. La PR #159 rendait une
page JSON brute à un navigateur en pleine navigation ; corriger ce défaut ne doit
pas ouvrir une injection dans la page de connexion.

Les valeurs sont **anglaises**, comme tous les paramètres de query du dépôt
(`scope`, `federal_only`, `seasons`) ; leur libellé français vit dans
l'interface, sur le modèle de `PROVIDER_LABELS`.
"""

#: Codes émis dans `/login?error=…`. Cette liste est le contrat public.
ERROR_CODES = frozenset({
    "state_mismatch",        # preuve absente, altérée, expirée, rejouée, ou d'un autre fournisseur
    "email_unverified",      # le fournisseur ne certifie aucune adresse
    "account_not_allowed",   # adresse hors de la liste des comptes autorisés
    "provider_error",        # refus du fournisseur, ou réponse inexploitable
    "provider_unavailable",  # fournisseur injoignable
})

#: Refus qui ne franchissent **pas** la frontière : ils se traduisent en code de
#: statut HTTP (404, 503) plutôt qu'en redirection vers la page de connexion.
INTERNAL_CODES = frozenset({"unknown_provider", "not_configured"})


class LoginError(Exception):
    """Échec du parcours, porteur d'un code appartenant à l'ensemble fermé.

    Ne dérive **pas** de `DomainError` : ces échecs ne se rendent pas en JSON à
    un appelant d'API, ils se rendent en **redirection** vers la page de
    connexion (FR-027). Les laisser remonter au handler de `DomainError`
    afficherait précisément la page de données techniques que le contrat
    proscrit.
    """

    def __init__(self, code: str) -> None:
        if code not in ERROR_CODES | INTERNAL_CODES:
            raise ValueError(f"unknown login error code: {code}")
        self.code = code
        super().__init__(code)
