"""Révocation d'urgence des sessions (#169).

Le geste que la procédure SQL rendait impraticable sous stress : fermer d'un coup
les sessions ouvertes, toutes ou celles d'une adresse. À distinguer du retrait
d'une adresse autorisée (#170), qui pose `is_active = False` et laisse les lignes
de `user_sessions` en place — une réinscription dans la fenêtre de TTL
ressuscitait alors les jetons exacts. La révocation, elle, **supprime**.
"""
from datetime import timedelta

from app.core.time import utcnow
from app.repositories import session_repository, user_repository
from app.services.auth import session as session_service


def _compte(db, email, *, sessions=1):
    """Un compte et N sessions ouvertes ; rend les jetons **bruts**."""
    user = user_repository.create(db, email=email, display_name="Prénom Nom")
    db.flush()
    return user, [session_service.open_for(db, user) for _ in range(sessions)]


def test_revoquer_tout_ferme_les_sessions_de_tous_les_comptes(db_session):
    _, jetons_un = _compte(db_session, "une@exemple.fr", sessions=2)
    _, jetons_deux = _compte(db_session, "deux@exemple.fr")

    sessions, comptes = session_service.revoke_all(db_session)

    assert (sessions, comptes) == (3, 2)
    for jeton in jetons_un + jetons_deux:
        assert session_service.resolve(db_session, jeton) is None


def test_revoquer_tout_sans_session_ouverte_ne_pretend_pas_le_contraire(db_session):
    """« 0 session fermée » est une réponse, pas un échec — l'exploitant doit
    pouvoir distinguer un geste utile d'un geste dans le vide."""
    assert session_service.revoke_all(db_session) == (0, 0)


def test_revoquer_une_adresse_epargne_les_autres_comptes(db_session):
    _, cible = _compte(db_session, "fuite@exemple.fr")
    _, epargne = _compte(db_session, "autre@exemple.fr")

    sessions, comptes = session_service.revoke_for_email(db_session, "fuite@exemple.fr")

    assert (sessions, comptes) == (1, 1)
    assert session_service.resolve(db_session, cible[0]) is None
    assert session_service.resolve(db_session, epargne[0]) is not None


def test_revoquer_une_adresse_ferme_tous_les_comptes_qui_la_portent(db_session):
    """`users.email` n'est pas unique (#114, FR-003), délibérément.

    Là où `grant-role` refuse de trancher entre les candidats, la révocation les
    prend **tous** : sous incident, en épargner un serait l'erreur coûteuse.
    """
    _, premier = _compte(db_session, "double@exemple.fr")
    _, second = _compte(db_session, "Double@Exemple.fr")

    sessions, comptes = session_service.revoke_for_email(db_session, "double@exemple.fr")

    assert (sessions, comptes) == (2, 2)
    assert session_service.resolve(db_session, premier[0]) is None
    assert session_service.resolve(db_session, second[0]) is None


def test_revoquer_un_compte_epargne_les_homonymes_d_adresse(db_session):
    """Le geste de l'écran cible **un compte**, jamais une adresse.

    `users.email` n'est pas unique (FR-003) : révoquer par adresse depuis un
    tableau qui liste des comptes en frapperait plusieurs sans le dire. La CLI
    prend l'adresse parce qu'elle n'a pas d'écran pour choisir ; ici on choisit.
    """
    cible, jetons_cible = _compte(db_session, "double@exemple.fr", sessions=2)
    _, jeton_homonyme = _compte(db_session, "double@exemple.fr")

    sessions, comptes = session_service.revoke_for_user(db_session, cible)

    assert (sessions, comptes) == (2, 1)
    assert session_service.resolve(db_session, jetons_cible[0]) is None
    assert session_service.resolve(db_session, jeton_homonyme[0]) is not None


def test_revoquer_un_compte_ne_le_desactive_pas(db_session):
    """Même invariant que la révocation globale : on coupe des jetons."""
    user, _ = _compte(db_session, "revoque@exemple.fr")

    session_service.revoke_for_user(db_session, user)

    assert user.is_active is True


def test_revoquer_un_compte_sans_session_ouverte_ne_ferme_rien(db_session):
    user = user_repository.create(db_session, email="dort@exemple.fr")
    db_session.flush()

    assert session_service.revoke_for_user(db_session, user) == (0, 0)


def test_revoquer_une_adresse_inconnue_ne_ferme_rien(db_session):
    _, epargne = _compte(db_session, "connue@exemple.fr")

    assert session_service.revoke_for_email(db_session, "inconnue@exemple.fr") == (0, 0)
    assert session_service.resolve(db_session, epargne[0]) is not None


def test_le_bilan_ne_compte_que_les_sessions_reellement_ouvertes(db_session):
    """Le chiffre que l'exploitant lit en incident doit être le vrai.

    Une session **expirée** est déjà refusée par `resolve` — la compter comme
    « fermée » gonfle le bilan de lignes mortes. Et faute d'ordonnanceur, ces
    lignes s'accumulent : elles ne sont purgées qu'à la connexion de leur
    titulaire, donc une base réelle en est pleine. « 5 sessions fermées » quand
    une seule était vivante empêche de répondre à la seule question qui compte.
    """
    dormeur = user_repository.create(db_session, email="dormeur@exemple.fr")
    db_session.flush()
    session_repository.create(
        db_session,
        user_id=dormeur.id,
        token_hash="expiré",
        expires_at=utcnow() - timedelta(days=90),
    )
    _compte(db_session, "vivant@exemple.fr")

    sessions, comptes = session_service.revoke_all(db_session)

    assert (sessions, comptes) == (1, 1)


def test_le_bilan_ignore_les_sessions_d_un_compte_deja_ferme(db_session):
    """Un compte désactivé (#170) voit déjà ses sessions refusées par la jointure.

    Les compter comme « fermées » ferait passer un retrait d'adresse pour défait.
    Elles sont **supprimées** quand même — l'hygiène est gratuite —, simplement
    pas annoncées.
    """
    retire, _ = _compte(db_session, "retire@exemple.fr")
    retire.is_active = False
    _compte(db_session, "vivant@exemple.fr")
    db_session.flush()

    sessions, comptes = session_service.revoke_all(db_session)

    assert (sessions, comptes) == (1, 1)
    assert session_repository.get_by_token_hash(db_session, "peu importe") is None
    assert db_session.query(session_repository.UserSession).count() == 0


def test_la_revocation_ne_desactive_aucun_compte(db_session):
    """C'est ce qui la distingue du retrait d'adresse (#170).

    Retirer ferme par la **jointure** (`is_active = False`) et laisse les lignes ;
    révoquer supprime les lignes et laisse le compte ouvert. La personne se
    reconnecte — ce qu'on voulait, après une fuite de jetons.
    """
    user, jetons = _compte(db_session, "revoque@exemple.fr")

    session_service.revoke_all(db_session)

    assert user.is_active is True
    assert session_service.resolve(db_session, session_service.open_for(db_session, user))
    assert session_service.resolve(db_session, jetons[0]) is None
