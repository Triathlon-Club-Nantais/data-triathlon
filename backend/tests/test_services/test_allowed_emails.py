"""Gestion de la liste d'autorisation depuis le back-office (#170).

Le service porte ce que le repository ne peut pas porter : l'auteur de
l'inscription, l'effet du retrait sur les comptes, et l'invariant du dernier
administrateur.
"""
from app.repositories import user_repository
from app.services.auth import allowed_emails


def _acteur(db_session, email="admin@exemple.fr"):
    acteur = user_repository.create(db_session, email=email, display_name="Camille")
    db_session.flush()
    return acteur


def test_add_normalise_l_adresse(db_session):
    acteur = _acteur(db_session)

    entree, creee, _ = allowed_emails.add(db_session, acteur, email=" Vous@Exemple.FR ")

    assert creee is True
    assert entree.email == "vous@exemple.fr"


def test_add_nomme_celui_qui_accorde(db_session):
    acteur = _acteur(db_session)

    entree, _, _ = allowed_emails.add(db_session, acteur, email="vous@exemple.fr")

    assert entree.created_by_user_id == acteur.id


def test_add_est_idempotent(db_session):
    acteur = _acteur(db_session)

    premiere, creee, _ = allowed_emails.add(db_session, acteur, email="vous@exemple.fr")
    seconde, recreee, _ = allowed_emails.add(db_session, acteur, email="VOUS@exemple.fr")

    assert (creee, recreee) == (True, False)
    assert seconde.id == premiere.id
    assert len(allowed_emails.list_all(db_session)) == 1


def test_list_all_est_triee_par_adresse(db_session):
    acteur = _acteur(db_session)
    allowed_emails.add(db_session, acteur, email="zoe@exemple.fr")
    allowed_emails.add(db_session, acteur, email="alex@exemple.fr")

    assert [ligne.email for ligne in allowed_emails.list_all(db_session)] == [
        "alex@exemple.fr",
        "zoe@exemple.fr",
    ]


# --- Le retrait, et ce qu'il ferme (US2) ------------------------------------


def _autoriser_et_compter(db_session, acteur, email):
    entree, _, _ = allowed_emails.add(db_session, acteur, email=email)
    return entree


def test_remove_ferme_tous_les_comptes_portant_l_adresse(db_session):
    """`users.email` n'est pas unique : deux identités externes de même adresse
    donnent deux comptes distincts (#114, FR-003). Le retrait les ferme **tous**."""
    acteur = _acteur(db_session)
    premier = user_repository.create(db_session, email="Cible@Exemple.FR")
    second = user_repository.create(db_session, email="cible@exemple.fr")
    entree = _autoriser_et_compter(db_session, acteur, "cible@exemple.fr")

    fermes = allowed_emails.remove(db_session, acteur, entree)

    assert fermes == 2
    assert (premier.is_active, second.is_active) == (False, False)


def test_remove_ne_supprime_ni_utilisateur_ni_role(db_session):
    """FR-017 : le retrait ferme l'accès, il n'efface pas la personne."""
    from app.models.user import User

    acteur = _acteur(db_session)
    cible = user_repository.create(db_session, email="cible@exemple.fr")
    entree = _autoriser_et_compter(db_session, acteur, "cible@exemple.fr")

    allowed_emails.remove(db_session, acteur, entree)

    assert db_session.get(User, cible.id) is not None
    assert allowed_emails.list_all(db_session) == []


def test_reinscrire_rouvre_les_comptes(db_session):
    """La symétrie n'est pas optionnelle : sans elle, réinscrire n'ouvre rien.

    Un compte désactivé est refusé en `account_not_allowed` **avant** que la
    liste ne soit consultée — l'exploitant verrait l'adresse dans le tableau et
    la personne resterait dehors, sans message qui l'explique.
    """
    acteur = _acteur(db_session)
    cible = user_repository.create(db_session, email="cible@exemple.fr")
    entree = _autoriser_et_compter(db_session, acteur, "cible@exemple.fr")
    allowed_emails.remove(db_session, acteur, entree)
    assert cible.is_active is False

    allowed_emails.add(db_session, acteur, email="CIBLE@exemple.fr")

    assert cible.is_active is True
