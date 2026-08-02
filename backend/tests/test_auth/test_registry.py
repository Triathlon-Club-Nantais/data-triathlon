"""Registre des fournisseurs d'identité — extensibilité et inaccessibilité des doublures."""
import subprocess
import sys
from pathlib import Path

from app.services.auth.idp import registry
from app.services.auth.idp.base import AuthorizationRequest, ExternalIdentity

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def test_github_est_le_seul_fournisseur_livre():
    assert registry.slugs() == ["github"]


def test_le_registre_importe_a_froid_ne_contient_que_github():
    """SC-012 : aucune doublure de test n'est atteignable en production (FR-034).

    Vérifié dans un **processus neuf** : dans celui-ci, une fixture a pu
    enregistrer une doublure, et le registre tient des singletons de module. Une
    doublure atteignable en production serait un contournement d'authentification
    complet — elle fabriquerait une identité arbitraire.
    """
    sortie = subprocess.run(
        [
            sys.executable,
            "-c",
            "from app.services.auth.idp import registry; print(registry.slugs())",
        ],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert sortie.stdout.strip() == "['github']"


def test_une_doublure_enregistree_par_fixture_est_visible(doublure):
    assert registry.get(doublure.slug) is doublure
    assert doublure.slug in registry.slugs()


def test_un_slug_inconnu_ne_resout_rien():
    assert registry.get("inexistant") is None


def test_les_methodes_actives_excluent_un_fournisseur_non_configure(doublure):
    """`enabled_methods()` est la source de l'écran de connexion (FR-031)."""
    actifs = {methode.slug for methode in registry.enabled_methods()}
    assert doublure.slug in actifs

    doublure.configure = False
    assert doublure.slug not in {methode.slug for methode in registry.enabled_methods()}


def test_le_flux_complet_se_deroule_sur_la_doublure(db_session, doublure):
    """SC-011 : ajouter un fournisseur ne touche ni le contrat, ni le flux, ni GitHub.

    Le contrat n'énumérant aucun mécanisme, la doublure range ce qu'elle veut
    dans son aller-retour opaque — ici une clé que GitHub n'a pas.
    """
    from app.services.auth import flow

    url, jeton_etat = flow.start_login(doublure.slug)
    assert url.startswith("https://doublure.exemple/authorize")

    from app.services.auth import state

    charge = state.read(jeton_etat)
    assert charge.provider == doublure.slug
    assert charge.round_trip == {"cle-inventee": "valeur"}

    jeton_session, user = flow.complete_login(
        db_session,
        provider_slug=doublure.slug,
        state_token=jeton_etat,
        state_param=charge.state,
        code="code-de-retour",
        error=None,
    )
    db_session.commit()

    assert user.email == "contributeur@exemple.fr"
    assert len(jeton_session) >= 43


def test_le_contrat_ne_nomme_aucun_mecanisme_de_fournisseur():
    """FR-032 : la signature ne doit pas fuiter PKCE, ni rien qui lui ressemble.

    Un `verifier: str` en dur obligerait, à l'arrivée d'OIDC, à ajouter un
    `nonce` aux deux méthodes — donc à modifier le contrat, le flux **et** le
    fournisseur GitHub existant.
    """
    import inspect

    from app.services.auth.idp.base import IdentityProvider

    signatures = "".join(
        str(inspect.signature(getattr(IdentityProvider, nom)))
        for nom in ("authorize", "fetch_identity")
    )
    for mecanisme in ("verifier", "pkce", "challenge", "nonce", "token"):
        assert mecanisme not in signatures.lower()

    assert AuthorizationRequest and ExternalIdentity  # exportés par le contrat
