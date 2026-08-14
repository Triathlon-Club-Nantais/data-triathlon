"""Fixtures de l'API de lecture.

**Pourquoi une session ici.** `POST /participations` et
`DELETE /participations/{id}` étaient ouvertes à Internet ; #115 les ferme
(FR-023). Or ces fichiers s'en servaient comme **raccourci de peuplement** :
ils éprouvent le comportement de l'API de lecture — filtres, saisons, portée
club, agrégats —, jamais son ouverture.

La session posée ci-dessous rend donc ce raccourci de nouveau utilisable sans
réécrire vingt tests autour de leur outillage.

**Ce que cette fixture ne doit jamais servir à établir** : qu'une route est
ouverte. Cette propriété-là appartient en propre à
`tests/test_auth/test_public_routes_still_open.py`, qui parcourt **toutes** les
routes de l'application avec un client sans le moindre cookie, et à
`tests/test_auth/test_admin_guards.py` pour les trois issues de chaque ressource
fermée. Un test d'ouverture écrit ici passerait pour la mauvaise raison.
"""
import pytest

from app.api.v1.auth import session_cookie_name
from app.core.config import get_settings
from app.models.organisation import Organisation
from app.models.role import Role
from app.repositories import user_repository, user_role_repository
from app.services.auth import session as session_service


@pytest.fixture(autouse=True)
def session_de_saisie(client, db_session, monkeypatch):
    """Ouvre une session **superutilisateur** sur le client de ces tests.

    Superutilisateur plutôt qu'un rôle composé : ce qui est éprouvé ici n'est
    pas la composition des pouvoirs, et un rôle à deux codes se périmerait à la
    prochaine route fermée.
    """
    # Sans cela, le cookie porte le préfixe `__Host-`, qui exige `Secure` : httpx
    # refuserait de l'émettre vers `http://testserver`. Même motif qu'en #114.
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    get_settings.cache_clear()

    organisation = Organisation(slug="tcn", name="Triathlon Club Nantais")
    role = Role(slug="admin", name="Administrateur", is_system=True, is_superuser=True)
    db_session.add_all([organisation, role])
    db_session.flush()
    user = user_repository.create(db_session, email="saisie@exemple.fr")
    db_session.flush()
    user_role_repository.grant(
        db_session, user_id=user.id, role_id=role.id, organisation_id=organisation.id
    )
    jeton = session_service.open_for(db_session, user)
    db_session.commit()

    client.cookies.set(session_cookie_name(get_settings()), jeton)
    yield
    get_settings.cache_clear()


def valider_toutes_les_participations(db_session):
    """Bascule toute participation créée via l'API à l'état validé.

    #270 rend un résultat créé par `POST /participations` non vérifié par
    défaut (FR-016), donc exclu des agrégats publics (FR-021). Les tests de ce
    dossier utilisent cette route comme raccourci de peuplement pour des
    lectures qui ne portent pas sur la validation elle-même — filtres,
    saisons, portée club, badge `is_tcn`, taille du classement — et doivent
    donc lever cet état pour retrouver leur donnée dans ces agrégats.
    """
    from app.models.participation import Participation

    db_session.query(Participation).update({"is_pending_validation": False})
    db_session.commit()
