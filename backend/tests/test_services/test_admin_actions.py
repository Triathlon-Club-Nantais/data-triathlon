"""Les gestes correctifs d'un administrateur (#117).

Le fil de tous ces tests : **un refus ne laisse aucune trace, ni en base ni au
journal** (FR-015), et **une demande sans effet n'est pas un geste** (FR-012).
"""
from datetime import date

import pytest

from app.core.exceptions import NotFoundError
from app.repositories import (
    admin_action_log_repository,
    athlete_repository,
    course_repository,
    participation_repository,
    user_repository,
)
from app.services import admin_actions


@pytest.fixture
def auteur(db_session):
    user = user_repository.create(db_session, email="admin@exemple.fr")
    db_session.flush()
    return user


def _epreuve(db_session, nom="Triathlon de Nantes", event_date=date(2026, 5, 17)):
    course = course_repository.get_or_create(
        db_session,
        name=nom,
        event_date=event_date,
        event_type="triathlon-m",
        source_url=f"https://k/{nom}",
        provider="klikego",
    )
    db_session.flush()
    return course


def _coureur(db_session, nom, prenom="Coureur", birth_date=None):
    athlete = athlete_repository.get_or_create(
        db_session, nom=nom, prenom=prenom, birth_date=birth_date
    )
    db_session.flush()
    return athlete


def _inscrit(db_session, athlete, course, dossard="1"):
    ligne = participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number=dossard
    )
    db_session.flush()
    return ligne


def _journal(db_session, entity_type, entity_id):
    return admin_action_log_repository.list_for_entity(
        db_session, entity_type=entity_type, entity_id=entity_id
    )


# --- Supprimer une épreuve (US1) --------------------------------------------


def test_delete_course_emporte_ses_resultats(db_session, auteur):
    course = _epreuve(db_session)
    _inscrit(db_session, _coureur(db_session, "UN"), course, "1")
    _inscrit(db_session, _coureur(db_session, "DEUX"), course, "2")
    course_id = course.id

    admin_actions.delete_course(db_session, course_id=course_id, user_id=auteur.id)

    assert course_repository.get(db_session, course_id) is None
    assert participation_repository.count_for_course(db_session, course_id) == 0


def test_delete_course_purge_les_fiches_devenues_vides(db_session, auteur):
    """FR-022 — mais **seulement** celles qui perdent leur dernier résultat."""
    cible = _epreuve(db_session, "Cible")
    autre = _epreuve(db_session, "Autre", date(2026, 6, 1))
    exclusif = _coureur(db_session, "EXCLUSIF")
    partage = _coureur(db_session, "PARTAGE")
    _inscrit(db_session, exclusif, cible, "1")
    _inscrit(db_session, partage, cible, "2")
    _inscrit(db_session, partage, autre, "2")

    admin_actions.delete_course(db_session, course_id=cible.id, user_id=auteur.id)

    assert athlete_repository.get(db_session, exclusif.id) is None
    assert athlete_repository.get(db_session, partage.id) is not None


def test_delete_course_consigne_le_geste(db_session, auteur):
    """FR-013 — la trace nomme l'épreuve : un identifiant mort ne désigne rien."""
    course = _epreuve(db_session)
    exclusif = _coureur(db_session, "EXCLUSIF")
    _inscrit(db_session, exclusif, course, "1")
    course_id, exclusif_id = course.id, exclusif.id

    admin_actions.delete_course(db_session, course_id=course_id, user_id=auteur.id)

    entrees = _journal(db_session, "course", course_id)
    assert len(entrees) == 1
    entree = entrees[0]
    assert entree.action == "course.delete"
    assert entree.user_id == auteur.id
    assert entree.payload["name"] == "Triathlon de Nantes"
    assert entree.payload["participations_deleted"] == 1
    assert entree.payload["athletes_purged"] == [exclusif_id]


def test_delete_course_sur_epreuve_inexistante_refuse_et_n_ecrit_rien(db_session, auteur):
    from app.models.admin_action_log import AdminActionLog

    with pytest.raises(NotFoundError):
        admin_actions.delete_course(db_session, course_id=4242, user_id=auteur.id)

    assert db_session.query(AdminActionLog).count() == 0


def test_delete_course_n_emporte_aucun_orphelin_preexistant(db_session, auteur):
    """Le geste reste dans son périmètre : il ne fait pas le ménage de la base.

    Un orphelin antérieur, sans rapport avec l'épreuve, doit survivre — sinon la
    trace du geste devient fausse et la suppression déborde de ce qu'elle annonce.
    """
    course = _epreuve(db_session)
    _inscrit(db_session, _coureur(db_session, "INSCRIT"), course, "1")
    orphelin_anterieur = _coureur(db_session, "ORPHELIN-ANTERIEUR")

    admin_actions.delete_course(db_session, course_id=course.id, user_id=auteur.id)

    assert athlete_repository.get(db_session, orphelin_anterieur.id) is not None


# --- L'ampleur annoncée est l'ampleur réelle (SC-007) ------------------------


def test_l_impact_annonce_est_exactement_ce_qui_est_supprime(db_session, auteur):
    """SC-007 — le test qui empêche les deux définitions de diverger.

    L'impact et la purge doivent venir de la même fonction de repository. S'ils
    divergent, la modale de confirmation ment sur un geste sans retour arrière.
    """
    cible = _epreuve(db_session, "Cible")
    autre = _epreuve(db_session, "Autre", date(2026, 6, 1))
    for indice in range(3):
        _inscrit(db_session, _coureur(db_session, f"EXCLUSIF{indice}"), cible, str(indice))
    partage = _coureur(db_session, "PARTAGE")
    _inscrit(db_session, partage, cible, "9")
    _inscrit(db_session, partage, autre, "9")
    avant = athlete_repository.search(db_session, page_size=500)

    impact = admin_actions.course_deletion_impact(db_session, course_id=cible.id)
    admin_actions.delete_course(db_session, course_id=cible.id, user_id=auteur.id)

    apres = athlete_repository.search(db_session, page_size=500)
    assert impact["participations"] == 4
    assert impact["athletes"] == 3
    assert len(avant) - len(apres) == impact["athletes"]


def test_l_impact_ne_modifie_rien(db_session, auteur):
    course = _epreuve(db_session)
    coureur = _coureur(db_session, "INTACT")
    _inscrit(db_session, coureur, course, "1")

    admin_actions.course_deletion_impact(db_session, course_id=course.id)

    assert course_repository.get(db_session, course.id) is not None
    assert athlete_repository.get(db_session, coureur.id) is not None
    assert participation_repository.count_for_course(db_session, course.id) == 1


def test_l_impact_sur_epreuve_inexistante_refuse(db_session):
    with pytest.raises(NotFoundError):
        admin_actions.course_deletion_impact(db_session, course_id=4242)


# --- Rattacher un résultat (US2) --------------------------------------------


def _duo(db_session):
    course = _epreuve(db_session, "Rattachement")
    source = _coureur(db_session, "SOURCE")
    cible = _coureur(db_session, "CIBLE")
    ligne = _inscrit(db_session, source, course, "1")
    return course, source, cible, ligne


def test_reassign_deplace_le_resultat(db_session, auteur):
    course, source, cible, ligne = _duo(db_session)

    admin_actions.reassign_participation(
        db_session, participation_id=ligne.id, athlete_id=cible.id, user_id=auteur.id
    )

    assert participation_repository.get(db_session, ligne.id).athlete_id == cible.id
    assert [p.id for p in participation_repository.list_for_athlete(db_session, cible.id)] == [
        ligne.id
    ]


def test_reassign_purge_la_fiche_source_devenue_vide(db_session, auteur):
    course, source, cible, ligne = _duo(db_session)
    source_id = source.id

    admin_actions.reassign_participation(
        db_session, participation_id=ligne.id, athlete_id=cible.id, user_id=auteur.id
    )

    assert athlete_repository.get(db_session, source_id) is None


def test_reassign_epargne_une_source_encore_pourvue(db_session, auteur):
    course, source, cible, ligne = _duo(db_session)
    autre = _epreuve(db_session, "Autre", date(2026, 7, 1))
    _inscrit(db_session, source, autre, "1")
    source_id = source.id

    admin_actions.reassign_participation(
        db_session, participation_id=ligne.id, athlete_id=cible.id, user_id=auteur.id
    )

    assert athlete_repository.get(db_session, source_id) is not None


def test_reassign_consigne_l_origine_et_la_destination(db_session, auteur):
    """AC3 — une trace qui ne dirait pas d'où vient le résultat serait illisible."""
    course, source, cible, ligne = _duo(db_session)
    source_id, cible_id = source.id, cible.id

    admin_actions.reassign_participation(
        db_session, participation_id=ligne.id, athlete_id=cible_id, user_id=auteur.id
    )

    entrees = _journal(db_session, "participation", ligne.id)
    assert len(entrees) == 1
    assert entrees[0].action == "participation.reassign"
    assert entrees[0].payload["from_athlete_id"] == source_id
    assert entrees[0].payload["to_athlete_id"] == cible_id
    assert entrees[0].payload["athletes_purged"] == [source_id]


def test_reassign_vers_un_coureur_deja_classe_refuse(db_session, auteur):
    """FR-006 — sinon la même personne apparaît deux fois au classement."""
    from app.core.exceptions import DuplicateError

    course, source, cible, ligne = _duo(db_session)
    _inscrit(db_session, cible, course, "2")

    with pytest.raises(DuplicateError):
        admin_actions.reassign_participation(
            db_session, participation_id=ligne.id, athlete_id=cible.id, user_id=auteur.id
        )

    assert participation_repository.get(db_session, ligne.id).athlete_id == source.id


def test_reassign_vers_un_coureur_inconnu_refuse(db_session, auteur):
    course, source, cible, ligne = _duo(db_session)

    with pytest.raises(NotFoundError):
        admin_actions.reassign_participation(
            db_session, participation_id=ligne.id, athlete_id=4242, user_id=auteur.id
        )

    assert participation_repository.get(db_session, ligne.id).athlete_id == source.id


def test_reassign_d_un_resultat_inconnu_refuse(db_session, auteur):
    with pytest.raises(NotFoundError):
        admin_actions.reassign_participation(
            db_session, participation_id=4242, athlete_id=1, user_id=auteur.id
        )


def test_reassign_vers_le_coureur_deja_porteur_ne_consigne_rien(db_session, auteur):
    """FR-012 — une demande qui ne change rien n'est pas un geste.

    Elle réussit (l'état voulu est l'état atteint), mais le journal ne se
    remplit pas de non-événements.
    """
    course, source, cible, ligne = _duo(db_session)

    admin_actions.reassign_participation(
        db_session, participation_id=ligne.id, athlete_id=source.id, user_id=auteur.id
    )

    assert participation_repository.get(db_session, ligne.id).athlete_id == source.id
    assert _journal(db_session, "participation", ligne.id) == []


# --- Corriger un coureur (US3) ----------------------------------------------


def test_update_athlete_ecrit_les_champs_fournis(db_session, auteur):
    coureur = _coureur(db_session, "DUPOND", "jean")

    admin_actions.update_athlete(
        db_session,
        athlete_id=coureur.id,
        champs={"nom": "DUPONT", "birth_date": date(1988, 3, 2)},
        user_id=auteur.id,
    )

    relu = athlete_repository.get(db_session, coureur.id)
    assert relu.nom == "DUPONT"
    assert relu.birth_date == date(1988, 3, 2)
    assert relu.prenom == "jean"  # non fourni, donc non touché (PATCH strict)


def test_update_athlete_preserve_l_historique(db_session, auteur):
    course = _epreuve(db_session)
    coureur = _coureur(db_session, "DUPOND")
    _inscrit(db_session, coureur, course, "1")

    admin_actions.update_athlete(
        db_session, athlete_id=coureur.id, champs={"nom": "DUPONT"}, user_id=auteur.id
    )

    assert len(participation_repository.list_for_athlete(db_session, coureur.id)) == 1


def test_update_athlete_consigne_l_avant_et_l_apres(db_session, auteur):
    coureur = _coureur(db_session, "DUPOND")

    admin_actions.update_athlete(
        db_session, athlete_id=coureur.id, champs={"nom": "DUPONT"}, user_id=auteur.id
    )

    entrees = _journal(db_session, "athlete", coureur.id)
    assert entrees[0].action == "athlete.update"
    assert entrees[0].payload["before"]["nom"] == "DUPOND"
    assert entrees[0].payload["after"]["nom"] == "DUPONT"


def test_update_athlete_refuse_un_doublon_en_le_nommant(db_session, auteur):
    """AC2 — le message désigne la fiche en conflit, et rien n'est modifié."""
    from app.core.exceptions import DuplicateError

    existant = _coureur(db_session, "DUPONT", "Jean", birth_date=date(1988, 3, 2))
    a_corriger = _coureur(db_session, "DUPOND", "Jean", birth_date=date(1988, 3, 2))

    with pytest.raises(DuplicateError) as capture:
        admin_actions.update_athlete(
            db_session, athlete_id=a_corriger.id, champs={"nom": "DUPONT"}, user_id=auteur.id
        )

    assert str(existant.id) in str(capture.value)
    assert athlete_repository.get(db_session, a_corriger.id).nom == "DUPOND"
    assert _journal(db_session, "athlete", a_corriger.id) == []


def test_update_athlete_sur_coureur_inconnu_refuse(db_session, auteur):
    with pytest.raises(NotFoundError):
        admin_actions.update_athlete(
            db_session, athlete_id=4242, champs={"nom": "X"}, user_id=auteur.id
        )


def test_update_athlete_sans_changement_ne_consigne_rien(db_session, auteur):
    """Même règle que le rattachement : une demande sans effet n'est pas un geste."""
    coureur = _coureur(db_session, "DUPONT", "Jean")

    admin_actions.update_athlete(
        db_session, athlete_id=coureur.id, champs={"nom": "DUPONT"}, user_id=auteur.id
    )

    assert _journal(db_session, "athlete", coureur.id) == []


# --- Corriger une épreuve (US4) ---------------------------------------------


def test_update_course_ecrit_les_champs_fournis(db_session, auteur):
    course = _epreuve(db_session, "Tri de Nates")

    admin_actions.update_course(
        db_session,
        course_id=course.id,
        champs={"name": "Triathlon de Nantes"},
        user_id=auteur.id,
    )

    assert course_repository.get(db_session, course.id).name == "Triathlon de Nantes"


def test_update_course_ne_touche_aucun_resultat(db_session, auteur):
    """FR-023 — temps, rangs, statut et rattachements identiques avant/après."""
    course = _epreuve(db_session, "Tri de Nates")
    coureur = _coureur(db_session, "COUREUR")
    ligne = _inscrit(db_session, coureur, course, "1")
    ligne.total_time = "01:23:45"
    ligne.rank_overall = 7
    db_session.flush()

    admin_actions.update_course(
        db_session,
        course_id=course.id,
        champs={"name": "Triathlon de Nantes", "event_type": "triathlon-s"},
        user_id=auteur.id,
    )

    relu = participation_repository.get(db_session, ligne.id)
    assert relu.athlete_id == coureur.id
    assert relu.total_time == "01:23:45"
    assert relu.rank_overall == 7
    assert relu.status == "finisher"


def test_update_course_refuse_un_doublon_en_le_nommant(db_session, auteur):
    """FR-021 — le quadruplet (nom, date, type, relais) est la clé d'unicité."""
    from app.core.exceptions import DuplicateError

    existante = _epreuve(db_session, "Triathlon de Nantes", date(2026, 5, 17))
    a_corriger = _epreuve(db_session, "Tri de Nates", date(2026, 5, 17))

    with pytest.raises(DuplicateError) as capture:
        admin_actions.update_course(
            db_session,
            course_id=a_corriger.id,
            champs={"name": "Triathlon de Nantes"},
            user_id=auteur.id,
        )

    assert str(existante.id) in str(capture.value)
    assert course_repository.get(db_session, a_corriger.id).name == "Tri de Nates"


def test_update_course_consigne_l_avant_et_l_apres(db_session, auteur):
    course = _epreuve(db_session, "Tri de Nates")

    admin_actions.update_course(
        db_session,
        course_id=course.id,
        champs={"name": "Triathlon de Nantes"},
        user_id=auteur.id,
    )

    entrees = _journal(db_session, "course", course.id)
    assert entrees[0].action == "course.update"
    assert entrees[0].payload["before"]["name"] == "Tri de Nates"
    assert entrees[0].payload["after"]["name"] == "Triathlon de Nantes"


def test_update_course_sur_epreuve_inconnue_refuse(db_session, auteur):
    with pytest.raises(NotFoundError):
        admin_actions.update_course(
            db_session, course_id=4242, champs={"name": "X"}, user_id=auteur.id
        )
