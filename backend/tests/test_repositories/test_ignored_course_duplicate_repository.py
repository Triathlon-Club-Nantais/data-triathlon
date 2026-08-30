"""Paires de doublons suspects écartées (#754).

L'existence de la ligne porte la décision, patron de `test_season_validation_repository.py`.
La paire est normalisée (`course_id_low` < `course_id_high`) : `create`/`exists`
acceptent les deux ids dans n'importe quel ordre, et `all_pairs` les rend triés.
"""
from datetime import date

from app.repositories import course_repository, ignored_course_duplicate_repository, user_repository


def _auteur(db_session, email="admin@exemple.fr"):
    user = user_repository.create(db_session, email=email)
    db_session.flush()
    return user


def _course(db_session, name="A", url="https://www.chronosmetron.com/a"):
    course = course_repository.get_or_create(
        db_session,
        name=name,
        event_date=date(2026, 5, 3),
        event_type="triathlon-s",
        source_url=url,
        provider="wiclax",
    )
    db_session.flush()
    return course


def test_create_consigne_la_paire_normalisee_et_l_auteur(db_session):
    auteur = _auteur(db_session)

    ignoree = ignored_course_duplicate_repository.create(
        db_session, course_id_a=50, course_id_b=38, user_id=auteur.id
    )
    db_session.flush()

    assert (ignoree.course_id_low, ignoree.course_id_high) == (38, 50)
    assert ignoree.ignored_by_user_id == auteur.id
    assert ignoree.ignored_at is not None


def test_exists_est_vrai_quel_que_soit_l_ordre_des_ids(db_session):
    auteur = _auteur(db_session)
    ignored_course_duplicate_repository.create(
        db_session, course_id_a=38, course_id_b=50, user_id=auteur.id
    )
    db_session.flush()

    assert ignored_course_duplicate_repository.exists(db_session, course_id_a=38, course_id_b=50)
    assert ignored_course_duplicate_repository.exists(db_session, course_id_a=50, course_id_b=38)


def test_exists_est_faux_sans_ligne(db_session):
    assert not ignored_course_duplicate_repository.exists(db_session, course_id_a=38, course_id_b=50)


def test_exists_ne_confond_pas_deux_paires_distinctes(db_session):
    auteur = _auteur(db_session)
    ignored_course_duplicate_repository.create(
        db_session, course_id_a=38, course_id_b=50, user_id=auteur.id
    )
    db_session.flush()

    assert not ignored_course_duplicate_repository.exists(db_session, course_id_a=38, course_id_b=51)


def test_all_pairs_rend_toutes_les_paires_normalisees_en_une_requete(db_session):
    auteur = _auteur(db_session)
    ignored_course_duplicate_repository.create(
        db_session, course_id_a=50, course_id_b=38, user_id=auteur.id
    )
    ignored_course_duplicate_repository.create(
        db_session, course_id_a=1, course_id_b=2, user_id=auteur.id
    )
    db_session.flush()

    assert ignored_course_duplicate_repository.all_pairs(db_session) == {(38, 50), (1, 2)}


def test_all_pairs_est_vide_sans_ligne(db_session):
    assert ignored_course_duplicate_repository.all_pairs(db_session) == set()


# --- Nettoyage avant suppression d'une épreuve (#754) ------------------------
#
# `ignored_course_duplicates` n'a ni cascade ORM ni `ondelete` vers
# `courses.id` (patron de `course_sources.course_id`, cf. le docstring de
# `course_repository.delete`) : sans ce nettoyage, une ligne survivrait à
# l'épreuve qu'elle référence — invisible en SQLite, un `ForeignKeyViolation`
# en PostgreSQL.


def test_delete_for_course_retire_les_lignes_ou_l_id_apparait_des_deux_cotes(db_session):
    auteur = _auteur(db_session)
    a, b, c = _course(db_session, "A", "https://x/a"), _course(db_session, "B", "https://x/b"), _course(db_session, "C", "https://x/c")
    ignored_course_duplicate_repository.create(
        db_session, course_id_a=a.id, course_id_b=b.id, user_id=auteur.id
    )
    ignored_course_duplicate_repository.create(
        db_session, course_id_a=c.id, course_id_b=a.id, user_id=auteur.id
    )
    db_session.flush()

    ignored_course_duplicate_repository.delete_for_course(db_session, a.id)
    db_session.flush()

    assert ignored_course_duplicate_repository.all_pairs(db_session) == set()


def test_delete_for_course_ne_touche_pas_les_paires_qui_ne_le_concernent_pas(db_session):
    auteur = _auteur(db_session)
    a, b, c = _course(db_session, "A", "https://x/a"), _course(db_session, "B", "https://x/b"), _course(db_session, "C", "https://x/c")
    ignored_course_duplicate_repository.create(
        db_session, course_id_a=a.id, course_id_b=b.id, user_id=auteur.id
    )
    ignored_course_duplicate_repository.create(
        db_session, course_id_a=b.id, course_id_b=c.id, user_id=auteur.id
    )
    db_session.flush()

    ignored_course_duplicate_repository.delete_for_course(db_session, a.id)
    db_session.flush()

    assert ignored_course_duplicate_repository.all_pairs(db_session) == {
        (min(b.id, c.id), max(b.id, c.id))
    }


def test_course_repository_delete_retire_les_paires_ignorees_de_l_epreuve(db_session):
    """Comportemental et non structurel : SQLite n'impose aucune FK, donc seul
    le comportement de `course_repository.delete` prouve que le nettoyage a
    bien lieu, pas la contrainte."""
    auteur = _auteur(db_session)
    a, b = _course(db_session, "A", "https://x/a"), _course(db_session, "B", "https://x/b")
    ignored_course_duplicate_repository.create(
        db_session, course_id_a=a.id, course_id_b=b.id, user_id=auteur.id
    )
    db_session.flush()

    course_repository.delete(db_session, a)
    db_session.flush()

    assert ignored_course_duplicate_repository.all_pairs(db_session) == set()


def test_course_repository_delete_all_vide_aussi_les_paires_ignorees(db_session):
    auteur = _auteur(db_session)
    a, b = _course(db_session, "A", "https://x/a"), _course(db_session, "B", "https://x/b")
    ignored_course_duplicate_repository.create(
        db_session, course_id_a=a.id, course_id_b=b.id, user_id=auteur.id
    )
    db_session.flush()

    course_repository.delete_all(db_session)

    assert ignored_course_duplicate_repository.all_pairs(db_session) == set()
