"""Les ressources d'administration des données (#117) — six gestes, quatre lectures.

Ce fichier vit sous `tests/test_api/`, donc sous la session **superutilisateur**
du `conftest` local. Les tests de refus ouvrent leur propre session, plus
étroite, et écrasent le cookie posé par la fixture.

Les trois issues de chaque ressource — 401 anonyme, 403 connecté sans le
pouvoir, succès avec — suivent le patron de `test_course_reliability_api.py`.
"""
from datetime import date

import pytest

from app.api.v1.auth import session_cookie_name
from app.core.config import get_settings
from app.core.permissions import P
from app.models.admin_action_log import AdminActionLog
from app.models.organisation import Organisation
from app.models.role_permission import RolePermission
from app.repositories import (
    athlete_repository,
    course_repository,
    participation_repository,
    role_repository,
    user_repository,
    user_role_repository,
)
from app.services.auth import session as session_service


def _session_etroite(client, db_session, *codes, email="etroit@exemple.fr"):
    """Remplace la session large du conftest par une session à pouvoirs comptés."""
    organisation = db_session.query(Organisation).first()
    user = user_repository.create(db_session, email=email)
    db_session.flush()
    if codes:
        role = role_repository.create(db_session, slug="etroit", name="Étroit")
        for code in codes:
            role.permissions.append(RolePermission(permission_code=str(code)))
        db_session.flush()
        user_role_repository.grant(
            db_session, user_id=user.id, role_id=role.id, organisation_id=organisation.id
        )
    jeton = session_service.open_for(db_session, user)
    db_session.commit()
    client.cookies.set(session_cookie_name(get_settings()), jeton)
    return user


@pytest.fixture
def epreuve(db_session):
    """Une épreuve, deux résultats : un coureur exclusif, un coureur présent ailleurs."""
    cible = course_repository.get_or_create(
        db_session, name="Triathlon de Nantes", event_date=date(2026, 5, 17),
        event_type="triathlon-m", source_url="https://k/nantes", provider="klikego",
    )
    autre = course_repository.get_or_create(
        db_session, name="Autre épreuve", event_date=date(2026, 6, 1),
        event_type="triathlon-m", source_url="https://k/autre", provider="klikego",
    )
    db_session.flush()
    exclusif = athlete_repository.get_or_create(db_session, nom="EXCLUSIF", prenom="Eva")
    partage = athlete_repository.get_or_create(db_session, nom="PARTAGE", prenom="Paul")
    db_session.flush()
    participation_repository.create(
        db_session, athlete_id=exclusif.id, course_id=cible.id, bib_number="1"
    )
    participation_repository.create(
        db_session, athlete_id=partage.id, course_id=cible.id, bib_number="2"
    )
    participation_repository.create(
        db_session, athlete_id=partage.id, course_id=autre.id, bib_number="2"
    )
    db_session.commit()
    return cible


# --- GET /admin/courses/{id}/deletion-impact --------------------------------


def test_l_impact_chiffre_les_deux_destructions(client, epreuve):
    reponse = client.get(f"/api/v1/admin/courses/{epreuve.id}/deletion-impact")

    assert reponse.status_code == 200
    charge = reponse.json()
    assert charge["name"] == "Triathlon de Nantes"
    assert charge["participations"] == 2
    assert charge["athletes"] == 1


def test_l_impact_ne_modifie_rien(client, epreuve, db_session):
    client.get(f"/api/v1/admin/courses/{epreuve.id}/deletion-impact")

    assert course_repository.get(db_session, epreuve.id) is not None
    assert participation_repository.count_for_course(db_session, epreuve.id) == 2


def test_l_impact_sur_epreuve_inconnue_rend_404(client):
    reponse = client.get("/api/v1/admin/courses/4242/deletion-impact")

    assert reponse.status_code == 404
    assert reponse.json()["detail"] == "Épreuve introuvable."


def test_l_impact_sans_session_rend_401(client, epreuve):
    client.cookies.clear()

    assert client.get(f"/api/v1/admin/courses/{epreuve.id}/deletion-impact").status_code == 401


def test_l_impact_sans_le_pouvoir_rend_403(client, db_session, epreuve):
    _session_etroite(client, db_session)

    assert client.get(f"/api/v1/admin/courses/{epreuve.id}/deletion-impact").status_code == 403


# --- DELETE /admin/courses/{id} ---------------------------------------------


def test_supprimer_une_epreuve_rend_204_et_emporte_ses_resultats(client, db_session, epreuve):
    course_id = epreuve.id

    reponse = client.delete(f"/api/v1/admin/courses/{course_id}")

    assert reponse.status_code == 204
    assert reponse.content == b""
    assert course_repository.get(db_session, course_id) is None
    assert participation_repository.count_for_course(db_session, course_id) == 0


def test_supprimer_une_epreuve_purge_les_fiches_devenues_vides(client, db_session, epreuve):
    exclusif = athlete_repository.get_by_identity(
        db_session, nom="EXCLUSIF", prenom="Eva", birth_date=None
    )
    partage = athlete_repository.get_by_identity(
        db_session, nom="PARTAGE", prenom="Paul", birth_date=None
    )
    exclusif_id, partage_id = exclusif.id, partage.id

    client.delete(f"/api/v1/admin/courses/{epreuve.id}")

    assert athlete_repository.get(db_session, exclusif_id) is None
    assert athlete_repository.get(db_session, partage_id) is not None


def test_supprimer_une_epreuve_consigne_le_geste(client, db_session, epreuve):
    from app.repositories import admin_action_log_repository

    course_id = epreuve.id

    client.delete(f"/api/v1/admin/courses/{course_id}")

    entrees = admin_action_log_repository.list_for_entity(
        db_session, entity_type="course", entity_id=course_id
    )
    assert [e.action for e in entrees] == ["course.delete"]
    assert entrees[0].payload["participations_deleted"] == 2


def test_supprimer_une_epreuve_inconnue_rend_404(client):
    reponse = client.delete("/api/v1/admin/courses/4242")

    assert reponse.status_code == 404
    assert reponse.json()["detail"] == "Épreuve introuvable."


def test_supprimer_une_epreuve_sans_session_rend_401(client, epreuve):
    client.cookies.clear()

    assert client.delete(f"/api/v1/admin/courses/{epreuve.id}").status_code == 401


def test_supprimer_une_epreuve_sans_le_pouvoir_rend_403(client, db_session, epreuve):
    _session_etroite(client, db_session)

    assert client.delete(f"/api/v1/admin/courses/{epreuve.id}").status_code == 403


def test_supprimer_une_epreuve_avec_le_seul_pouvoir_utile_reussit(client, db_session, epreuve):
    """La garde nomme un pouvoir, pas un rôle : celui-ci suffit, et lui seul."""
    _session_etroite(client, db_session, P.COURSES_DELETE)

    assert client.delete(f"/api/v1/admin/courses/{epreuve.id}").status_code == 204


def test_un_refus_de_pouvoir_ne_supprime_rien(client, db_session, epreuve):
    """FR-015 — un 403 laisse la base strictement inchangée."""
    _session_etroite(client, db_session)
    course_id = epreuve.id

    client.delete(f"/api/v1/admin/courses/{course_id}")

    assert course_repository.get(db_session, course_id) is not None
    assert participation_repository.count_for_course(db_session, course_id) == 2


# --- L'inventaire des pouvoirs ----------------------------------------------


def test_le_pouvoir_de_suppression_est_offert_a_la_composition_des_roles(client):
    """FR-010 — un pouvoir qui garde une ressource sans figurer à l'inventaire
    serait inattribuable, donc mort."""
    groupes = client.get("/api/v1/admin/permissions").json()

    epreuves = next(g for g in groupes if g["feature"] == "Épreuves")
    codes = {p["code"] for p in epreuves["permissions"]}
    assert "courses:delete" in codes
    libelle = next(p for p in epreuves["permissions"] if p["code"] == "courses:delete")
    assert libelle["label"] == "Supprimer une épreuve"


def test_le_pouvoir_de_purge_totale_est_offert_a_la_composition_des_roles(client):
    """#384 — même garde-fou que pour `courses:delete`."""
    groupes = client.get("/api/v1/admin/permissions").json()

    resultats = next(g for g in groupes if g["feature"] == "Résultats")
    codes = {p["code"] for p in resultats["permissions"]}
    assert "participations:wipe_all" in codes
    libelle = next(p for p in resultats["permissions"] if p["code"] == "participations:wipe_all")
    assert libelle["label"] == "Purger tous les résultats"


def test_le_pouvoir_de_purge_des_epreuves_est_offert_a_la_composition_des_roles(client):
    """Suite de #384 — un second bouton, un second pouvoir, même garde-fou."""
    groupes = client.get("/api/v1/admin/permissions").json()

    epreuves = next(g for g in groupes if g["feature"] == "Épreuves")
    codes = {p["code"] for p in epreuves["permissions"]}
    assert "courses:wipe_all" in codes
    libelle = next(p for p in epreuves["permissions"] if p["code"] == "courses:wipe_all")
    assert libelle["label"] == "Purger toutes les épreuves"


@pytest.fixture
def base_avec_resultats(db_session):
    """Deux épreuves, chacune un résultat — pour chiffrer et purger la base entière."""
    a = course_repository.get_or_create(
        db_session, name="Tri A", event_date=date(2026, 5, 1),
        event_type="triathlon-m", source_url="https://k/a", provider="klikego",
    )
    b = course_repository.get_or_create(
        db_session, name="Tri B", event_date=date(2026, 5, 2),
        event_type="triathlon-m", source_url="https://k/b", provider="klikego",
    )
    db_session.flush()
    jean = athlete_repository.get_or_create(db_session, nom="COUREUR", prenom="Jean")
    paul = athlete_repository.get_or_create(db_session, nom="COUREUR", prenom="Paul")
    db_session.flush()
    participation_repository.create(db_session, athlete_id=jean.id, course_id=a.id, bib_number="1")
    participation_repository.create(db_session, athlete_id=paul.id, course_id=b.id, bib_number="1")
    course_repository.touch_scraped_at(db_session, a)
    course_repository.touch_scraped_at(db_session, b)
    db_session.commit()
    return a, b


# --- GET /admin/participations/wipe-impact -----------------------------------


def test_l_impact_de_purge_chiffre_participations_et_athletes(client, base_avec_resultats):
    reponse = client.get("/api/v1/admin/participations/wipe-impact")

    assert reponse.status_code == 200
    assert reponse.json() == {"participations": 2, "athletes": 2}


def test_l_impact_de_purge_ne_modifie_rien(client, base_avec_resultats, db_session):
    client.get("/api/v1/admin/participations/wipe-impact")

    assert participation_repository.count_all(db_session) == 2


def test_l_impact_de_purge_sans_session_rend_401(client, base_avec_resultats):
    client.cookies.clear()

    assert client.get("/api/v1/admin/participations/wipe-impact").status_code == 401


def test_l_impact_de_purge_sans_le_pouvoir_rend_403(client, db_session, base_avec_resultats):
    _session_etroite(client, db_session)

    assert client.get("/api/v1/admin/participations/wipe-impact").status_code == 403


# --- DELETE /admin/participations ---------------------------------------------


def test_purger_rend_le_decompte_reel_et_vide_la_table(client, db_session, base_avec_resultats):
    reponse = client.delete("/api/v1/admin/participations")

    assert reponse.status_code == 200
    assert reponse.json() == {
        "participations_deleted": 2,
        "athletes_purged": 2,
        "courses_reset": 2,
    }
    assert participation_repository.count_all(db_session) == 0


def test_purger_laisse_courses_et_sources_intacts(client, db_session, base_avec_resultats):
    from app.repositories import course_source_repository

    a, b = base_avec_resultats

    client.delete("/api/v1/admin/participations")

    assert course_repository.get(db_session, a.id) is not None
    assert course_repository.get(db_session, b.id) is not None
    assert len(course_source_repository.list_for_course(db_session, a.id)) == 1
    assert len(course_source_repository.list_for_course(db_session, b.id)) == 1


def test_purger_remet_scraped_at_a_null_sur_toutes_les_epreuves(
    client, db_session, base_avec_resultats
):
    a, b = base_avec_resultats

    client.delete("/api/v1/admin/participations")

    db_session.expire(a)
    db_session.expire(b)
    assert course_repository.get(db_session, a.id).scraped_at is None
    assert course_repository.get(db_session, b.id).scraped_at is None


def test_purger_supprime_les_fiches_devenues_orphelines(client, db_session, base_avec_resultats):
    jean = athlete_repository.get_by_identity(db_session, nom="COUREUR", prenom="Jean", birth_date=None)
    jean_id = jean.id

    client.delete("/api/v1/admin/participations")

    assert athlete_repository.get(db_session, jean_id) is None


def test_purger_consigne_le_geste(client, db_session, base_avec_resultats):
    from app.repositories import admin_action_log_repository

    client.delete("/api/v1/admin/participations")

    entrees = admin_action_log_repository.list_for_entity(
        db_session, entity_type="participations", entity_id=0
    )
    assert [e.action for e in entrees] == ["participations.wipe_all"]
    assert entrees[0].payload["participations_deleted"] == 2


def test_purger_sans_session_rend_401(client, base_avec_resultats):
    client.cookies.clear()

    assert client.delete("/api/v1/admin/participations").status_code == 401


def test_purger_sans_le_pouvoir_rend_403(client, db_session, base_avec_resultats):
    _session_etroite(client, db_session)

    assert client.delete("/api/v1/admin/participations").status_code == 403


def test_purger_avec_le_seul_pouvoir_utile_reussit(client, db_session, base_avec_resultats):
    _session_etroite(client, db_session, P.PARTICIPATIONS_WIPE_ALL)

    assert client.delete("/api/v1/admin/participations").status_code == 200


def test_un_refus_de_pouvoir_ne_purge_rien(client, db_session, base_avec_resultats):
    """FR-015 — un 403 laisse la base strictement inchangée."""
    _session_etroite(client, db_session)

    client.delete("/api/v1/admin/participations")

    assert participation_repository.count_all(db_session) == 2


# --- GET /admin/courses/wipe-impact -------------------------------------------


def test_l_impact_de_purge_des_epreuves_chiffre_courses_participations_et_athletes(
    client, base_avec_resultats
):
    reponse = client.get("/api/v1/admin/courses/wipe-impact")

    assert reponse.status_code == 200
    assert reponse.json() == {"courses": 2, "participations": 2, "athletes": 2}


def test_l_impact_de_purge_des_epreuves_ne_modifie_rien(client, base_avec_resultats, db_session):
    client.get("/api/v1/admin/courses/wipe-impact")

    assert course_repository.count_all(db_session) == 2
    assert participation_repository.count_all(db_session) == 2


def test_l_impact_de_purge_des_epreuves_sans_session_rend_401(client, base_avec_resultats):
    client.cookies.clear()

    assert client.get("/api/v1/admin/courses/wipe-impact").status_code == 401


def test_l_impact_de_purge_des_epreuves_sans_le_pouvoir_rend_403(
    client, db_session, base_avec_resultats
):
    _session_etroite(client, db_session)

    assert client.get("/api/v1/admin/courses/wipe-impact").status_code == 403


# --- DELETE /admin/courses -----------------------------------------------------


def test_purger_les_epreuves_rend_le_decompte_reel_et_vide_le_catalogue(
    client, db_session, base_avec_resultats
):
    reponse = client.delete("/api/v1/admin/courses")

    assert reponse.status_code == 200
    assert reponse.json() == {"courses_deleted": 2, "athletes_purged": 2}
    assert course_repository.count_all(db_session) == 0
    assert participation_repository.count_all(db_session) == 0
    assert athlete_repository.count_all(db_session) == 0


def test_purger_les_epreuves_emporte_bien_les_sources(client, db_session, base_avec_resultats):
    from app.repositories import course_source_repository

    a, b = base_avec_resultats
    # Ids capturés avant le geste : `delete_all` est un DELETE de masse, pas
    # une cascade ORM instance par instance — relire `a`/`b` après coup
    # lèverait sur une identity map périmée (même patron que
    # `test_supprimer_une_epreuve_purge_les_fiches_devenues_vides`).
    id_a, id_b = a.id, b.id

    client.delete("/api/v1/admin/courses")

    assert course_source_repository.list_for_course(db_session, id_a) == []
    assert course_source_repository.list_for_course(db_session, id_b) == []


def test_purger_les_epreuves_consigne_le_geste(client, db_session, base_avec_resultats):
    from app.repositories import admin_action_log_repository

    client.delete("/api/v1/admin/courses")

    entrees = admin_action_log_repository.list_for_entity(
        db_session, entity_type="courses", entity_id=0
    )
    assert [e.action for e in entrees] == ["courses.wipe_all"]
    assert entrees[0].payload == {"courses_deleted": 2, "athletes_purged": 2}


def test_purger_les_epreuves_sans_session_rend_401(client, base_avec_resultats):
    client.cookies.clear()

    assert client.delete("/api/v1/admin/courses").status_code == 401


def test_purger_les_epreuves_sans_le_pouvoir_rend_403(client, db_session, base_avec_resultats):
    _session_etroite(client, db_session)

    assert client.delete("/api/v1/admin/courses").status_code == 403


def test_purger_les_epreuves_avec_le_seul_pouvoir_utile_reussit(
    client, db_session, base_avec_resultats
):
    _session_etroite(client, db_session, P.COURSES_WIPE_ALL)

    assert client.delete("/api/v1/admin/courses").status_code == 200


def test_un_refus_de_pouvoir_ne_purge_pas_les_epreuves(client, db_session, base_avec_resultats):
    """FR-015 — un 403 laisse la base strictement inchangée."""
    _session_etroite(client, db_session)

    client.delete("/api/v1/admin/courses")

    assert course_repository.count_all(db_session) == 2
    assert participation_repository.count_all(db_session) == 2


# --- POST /admin/participations/{id}/reassign -------------------------------


@pytest.fixture
def rattachement(db_session):
    """Un résultat sur un coureur « source », un coureur « cible » libre."""
    course = course_repository.get_or_create(
        db_session, name="Course rattachement", event_date=date(2026, 4, 5),
        event_type="triathlon-m", source_url="https://k/rat", provider="klikego",
    )
    db_session.flush()
    source = athlete_repository.get_or_create(db_session, nom="SOURCE", prenom="Sam")
    cible = athlete_repository.get_or_create(db_session, nom="CIBLE", prenom="Cam")
    db_session.flush()
    ligne = participation_repository.create(
        db_session, athlete_id=source.id, course_id=course.id, bib_number="1"
    )
    db_session.commit()
    return {"course": course, "source": source, "cible": cible, "participation": ligne}


def test_rattacher_un_resultat_change_de_coureur(client, db_session, rattachement):
    ligne = rattachement["participation"]
    cible_id = rattachement["cible"].id

    reponse = client.post(
        f"/api/v1/admin/participations/{ligne.id}/reassign", json={"athlete_id": cible_id}
    )

    assert reponse.status_code == 200
    assert reponse.json()["athlete"]["id"] == cible_id
    assert participation_repository.get(db_session, ligne.id).athlete_id == cible_id


def test_rattacher_vers_un_coureur_deja_classe_rend_409(client, db_session, rattachement):
    ligne = rattachement["participation"]
    participation_repository.create(
        db_session,
        athlete_id=rattachement["cible"].id,
        course_id=rattachement["course"].id,
        bib_number="2",
    )
    db_session.commit()

    reponse = client.post(
        f"/api/v1/admin/participations/{ligne.id}/reassign",
        json={"athlete_id": rattachement["cible"].id},
    )

    assert reponse.status_code == 409
    assert reponse.json()["detail"] == "Ce coureur a déjà un résultat sur cette épreuve."


def test_rattacher_vers_un_coureur_inconnu_rend_404(client, rattachement):
    ligne = rattachement["participation"]

    reponse = client.post(
        f"/api/v1/admin/participations/{ligne.id}/reassign", json={"athlete_id": 4242}
    )

    assert reponse.status_code == 404
    assert reponse.json()["detail"] == "Coureur introuvable."


def test_rattacher_un_resultat_inconnu_rend_404(client, rattachement):
    reponse = client.post(
        "/api/v1/admin/participations/4242/reassign",
        json={"athlete_id": rattachement["cible"].id},
    )

    assert reponse.status_code == 404
    assert reponse.json()["detail"] == "Résultat introuvable."


def test_rattacher_sans_session_rend_401(client, rattachement):
    client.cookies.clear()

    reponse = client.post(
        f"/api/v1/admin/participations/{rattachement['participation'].id}/reassign",
        json={"athlete_id": rattachement["cible"].id},
    )

    assert reponse.status_code == 401


def test_rattacher_sans_le_pouvoir_rend_403(client, db_session, rattachement):
    _session_etroite(client, db_session)

    reponse = client.post(
        f"/api/v1/admin/participations/{rattachement['participation'].id}/reassign",
        json={"athlete_id": rattachement["cible"].id},
    )

    assert reponse.status_code == 403


def test_un_refus_de_rattachement_ne_change_ni_la_donnee_ni_le_journal(
    client, db_session, rattachement
):
    """#439, FR-009 — le refus est total : le résultat reste sur son coureur, et
    le journal ne garde aucune trace d'une tentative."""
    ligne = rattachement["participation"]
    source_id = rattachement["source"].id
    _session_etroite(client, db_session)

    client.post(
        f"/api/v1/admin/participations/{ligne.id}/reassign",
        json={"athlete_id": rattachement["cible"].id},
    )

    db_session.expire_all()
    assert participation_repository.get(db_session, ligne.id).athlete_id == source_id
    assert db_session.query(AdminActionLog).count() == 0


# --- GET /admin/athletes ----------------------------------------------------


def test_la_recherche_admin_rend_l_identite_complete(client, db_session, rattachement):
    reponse = client.get("/api/v1/admin/athletes", params={"search": "source"})

    assert reponse.status_code == 200
    fiches = reponse.json()
    assert len(fiches) == 1
    assert fiches[0]["nom"] == "SOURCE"
    assert "birth_date" in fiches[0]
    assert fiches[0]["participations"] == 1


def test_une_recherche_sans_resultat_rend_une_liste_vide(client, rattachement):
    reponse = client.get("/api/v1/admin/athletes", params={"search": "zzzz"})

    assert reponse.status_code == 200
    assert reponse.json() == []


def test_la_recherche_admin_sans_session_rend_401(client):
    client.cookies.clear()

    assert client.get("/api/v1/admin/athletes").status_code == 401


def test_la_recherche_admin_sans_le_pouvoir_rend_403(client, db_session):
    _session_etroite(client, db_session)

    assert client.get("/api/v1/admin/athletes").status_code == 403


def test_les_pouvoirs_de_us2_sont_offerts_a_la_composition_des_roles(client):
    groupes = client.get("/api/v1/admin/permissions").json()
    codes = {p["code"] for groupe in groupes for p in groupe["permissions"]}

    assert {"athletes:read", "participations:reassign"} <= codes


# --- PATCH /admin/athletes/{id} et /admin/courses/{id} ----------------------


@pytest.fixture
def coureur(db_session):
    athlete = athlete_repository.get_or_create(
        db_session, nom="DUPOND", prenom="Jean", birth_date=date(1988, 3, 2)
    )
    db_session.commit()
    return athlete


def test_corriger_un_coureur_rend_sa_fiche_complete(client, coureur):
    reponse = client.patch(
        f"/api/v1/admin/athletes/{coureur.id}", json={"nom": "DUPONT"}
    )

    assert reponse.status_code == 200
    assert reponse.json()["nom"] == "DUPONT"
    assert reponse.json()["birth_date"] == "1988-03-02"


def test_corriger_un_coureur_vers_une_identite_prise_rend_409(client, db_session, coureur):
    athlete_repository.get_or_create(
        db_session, nom="DUPONT", prenom="Jean", birth_date=date(1988, 3, 2)
    )
    db_session.commit()

    reponse = client.patch(
        f"/api/v1/admin/athletes/{coureur.id}", json={"nom": "DUPONT"}
    )

    assert reponse.status_code == 409
    assert "identité" in reponse.json()["detail"]


def test_corriger_le_club_actuel_laisse_les_clubs_des_resultats(client, db_session, coureur):
    """#439, FR-013 — le club d'un résultat est celui de l'époque, pas le club actuel."""
    course = course_repository.get_or_create(
        db_session,
        name="Triathlon de Nantes",
        event_date=date(2026, 5, 17),
        event_type="triathlon-m",
        source_url="https://k/nantes",
        provider="klikego",
    )
    ligne = participation_repository.create(
        db_session,
        athlete_id=coureur.id,
        course_id=course.id,
        bib_number="7",
        club="ASPTT NANTES",
    )
    db_session.commit()

    reponse = client.patch(
        f"/api/v1/admin/athletes/{coureur.id}", json={"club": "TRI CLUB NANTAIS"}
    )

    assert reponse.status_code == 200
    assert reponse.json()["club"] == "TRI CLUB NANTAIS"
    db_session.expire_all()
    assert participation_repository.get(db_session, ligne.id).club == "ASPTT NANTES"


def test_vider_le_club_actuel_le_met_a_null(client, db_session, coureur):
    """US3-AC2 — `null` et non `""` : « sans club » n'est pas un club au libellé vide."""
    client.patch(f"/api/v1/admin/athletes/{coureur.id}", json={"club": "ASPTT NANTES"})

    reponse = client.patch(f"/api/v1/admin/athletes/{coureur.id}", json={"club": None})

    assert reponse.status_code == 200
    assert reponse.json()["club"] is None
    db_session.expire_all()
    assert athlete_repository.get(db_session, coureur.id).club is None


def test_un_club_detrempe_est_refuse(client, db_session, coureur):
    """Le pendant d'AC2 : « sans club » s'écrit `null`, un `""` n'est pas un club.

    `str_strip_whitespace` détrempe `"   "` en `""` ; sans le `min_length`, la
    chaîne vide serait rangée comme un libellé à part entière et apparaîtrait dans
    les regroupements par club.
    """
    client.patch(f"/api/v1/admin/athletes/{coureur.id}", json={"club": "ASPTT NANTES"})

    reponse = client.patch(f"/api/v1/admin/athletes/{coureur.id}", json={"club": "   "})

    assert reponse.status_code == 422
    db_session.expire_all()
    assert athlete_repository.get(db_session, coureur.id).club == "ASPTT NANTES"


def test_le_verrou_du_club_n_est_expose_par_aucune_reponse(client, db_session, coureur):
    """#439, INV-5, D2 — c'est un rouage interne, pas une donnée du contrat.

    L'exposer inviterait un écran à s'en servir, alors qu'il ne se pilote que par
    le geste de correction : aucune API ne le pose ni ne le lève directement.
    """
    fiche = client.patch(
        f"/api/v1/admin/athletes/{coureur.id}", json={"club": "TRI CLUB NANTAIS"}
    ).json()
    assert "club_locked" not in fiche
    assert "club_locked" not in client.get(f"/api/v1/admin/athletes/{coureur.id}").json()

    # `AthleteBrief`, le DTO public embarqué dans chaque résultat, non plus.
    course = course_repository.get_or_create(
        db_session,
        name="Duathlon de Nantes",
        event_date=date(2026, 6, 7),
        event_type="duathlon-s",
        source_url="https://k/duathlon",
        provider="klikego",
    )
    participation_repository.create(
        db_session, athlete_id=coureur.id, course_id=course.id, bib_number="3"
    )
    db_session.commit()

    resultats = client.get("/api/v1/participations").json()
    assert resultats
    assert all("club_locked" not in r["athlete"] for r in resultats)


def test_corriger_un_coureur_sans_champ_rend_422(client, coureur):
    assert client.patch(f"/api/v1/admin/athletes/{coureur.id}", json={}).status_code == 422


@pytest.mark.parametrize("corps", [{"nom": ""}, {"nom": "   "}, {"prenom": "  "}])
def test_corriger_un_coureur_au_nom_blanc_rend_422(client, coureur, corps):
    """`min_length=1` compte les caractères, pas les non-blancs : sans
    `str_strip_whitespace`, « ␣␣␣ » passait jusqu'en base (spec §Edge Cases)."""
    assert client.patch(f"/api/v1/admin/athletes/{coureur.id}", json=corps).status_code == 422


@pytest.mark.parametrize("corps", [{"nom": None}, {"prenom": None}])
def test_vider_un_champ_obligatoire_d_un_coureur_rend_422(client, coureur, corps):
    """Le `null` de ces champs voulait dire « absent » côté schéma, et
    ressortait en **500** (`IntegrityError`) au lieu du 422 du contrat."""
    assert client.patch(f"/api/v1/admin/athletes/{coureur.id}", json=corps).status_code == 422


@pytest.mark.parametrize("corps", [{"name": None}, {"event_type": None}, {"is_relay": None}])
def test_vider_un_champ_obligatoire_d_une_epreuve_rend_422(client, epreuve, corps):
    assert client.patch(f"/api/v1/admin/courses/{epreuve.id}", json=corps).status_code == 422


def test_un_type_d_epreuve_hors_nomenclature_rend_422(client, epreuve):
    """`event_type` pilote le partage fédéral, les stats et les splits : une
    faute de frappe retirerait l'épreuve des filtres **en silence**."""
    reponse = client.patch(
        f"/api/v1/admin/courses/{epreuve.id}", json={"event_type": "triathlon_m"}
    )

    assert reponse.status_code == 422


def test_un_type_d_epreuve_de_la_nomenclature_est_accepte(client, epreuve):
    reponse = client.patch(
        f"/api/v1/admin/courses/{epreuve.id}", json={"event_type": "duathlon-s"}
    )

    assert reponse.status_code == 200
    assert reponse.json()["event_type"] == "duathlon-s"


def test_un_conflit_d_epreuve_n_ecrit_rien_au_journal(client, db_session, epreuve):
    """FR-015 à l'étage HTTP : un 409 ne laisse ni donnée ni trace."""
    avant = db_session.query(AdminActionLog).count()

    client.patch(
        f"/api/v1/admin/courses/{epreuve.id}",
        json={"name": "Autre épreuve", "event_date": "2026-06-01"},
    )

    assert db_session.query(AdminActionLog).count() == avant


def test_corriger_un_coureur_inconnu_rend_404(client):
    reponse = client.patch("/api/v1/admin/athletes/4242", json={"nom": "X"})

    assert reponse.status_code == 404
    assert reponse.json()["detail"] == "Coureur introuvable."


def test_corriger_un_coureur_sans_session_rend_401(client, coureur):
    client.cookies.clear()

    assert client.patch(
        f"/api/v1/admin/athletes/{coureur.id}", json={"nom": "X"}
    ).status_code == 401


def test_corriger_un_coureur_sans_le_pouvoir_rend_403(client, db_session, coureur):
    _session_etroite(client, db_session)

    assert client.patch(
        f"/api/v1/admin/athletes/{coureur.id}", json={"nom": "X"}
    ).status_code == 403


def test_un_refus_de_correction_ne_change_ni_la_donnee_ni_le_journal(
    client, db_session, coureur
):
    """#439, FR-009 — même exigence que sur le rattachement : rien n'est écrit,
    ni dans la fiche, ni dans le journal."""
    coureur_id = coureur.id
    _session_etroite(client, db_session)

    client.patch(f"/api/v1/admin/athletes/{coureur_id}", json={"nom": "X"})

    db_session.expire_all()
    assert athlete_repository.get(db_session, coureur_id).nom == "DUPOND"
    assert db_session.query(AdminActionLog).count() == 0


def test_corriger_une_epreuve_rend_le_libelle_a_jour(client, epreuve):
    reponse = client.patch(
        f"/api/v1/admin/courses/{epreuve.id}", json={"name": "Triathlon de Nantes 2026"}
    )

    assert reponse.status_code == 200
    assert reponse.json()["name"] == "Triathlon de Nantes 2026"


def test_corriger_une_epreuve_ne_touche_aucun_resultat(client, db_session, epreuve):
    """FR-023 — le nombre de résultats et leur rattachement sont inchangés."""
    avant = participation_repository.count_for_course(db_session, epreuve.id)

    client.patch(f"/api/v1/admin/courses/{epreuve.id}", json={"event_type": "triathlon-s"})

    assert participation_repository.count_for_course(db_session, epreuve.id) == avant


def test_corriger_une_epreuve_vers_une_identite_prise_rend_409(client, db_session, epreuve):
    reponse = client.patch(
        f"/api/v1/admin/courses/{epreuve.id}",
        json={"name": "Autre épreuve", "event_date": "2026-06-01"},
    )

    assert reponse.status_code == 409
    assert "épreuve" in reponse.json()["detail"].lower()


def test_corriger_une_epreuve_accepte_une_date_mise_a_null(client, epreuve):
    """`event_date: null` est une valeur, pas une absence — et le PATCH la distingue."""
    reponse = client.patch(
        f"/api/v1/admin/courses/{epreuve.id}", json={"event_date": None}
    )

    assert reponse.status_code == 200
    assert reponse.json()["event_date"] is None


def test_corriger_une_epreuve_sans_champ_rend_422(client, epreuve):
    assert client.patch(f"/api/v1/admin/courses/{epreuve.id}", json={}).status_code == 422


def test_corriger_une_epreuve_inconnue_rend_404(client):
    assert client.patch("/api/v1/admin/courses/4242", json={"name": "X"}).status_code == 404


def test_corriger_une_epreuve_sans_session_rend_401(client, epreuve):
    client.cookies.clear()

    assert client.patch(
        f"/api/v1/admin/courses/{epreuve.id}", json={"name": "X"}
    ).status_code == 401


def test_corriger_une_epreuve_sans_le_pouvoir_rend_403(client, db_session, epreuve):
    _session_etroite(client, db_session)

    assert client.patch(
        f"/api/v1/admin/courses/{epreuve.id}", json={"name": "X"}
    ).status_code == 403


def test_les_pouvoirs_de_correction_sont_offerts_a_la_composition_des_roles(client):
    groupes = client.get("/api/v1/admin/permissions").json()
    codes = {p["code"] for groupe in groupes for p in groupe["permissions"]}

    assert {"courses:write", "athletes:write"} <= codes


def test_lire_une_fiche_coureur_rend_sa_date_de_naissance(client, coureur):
    """Sans cette route, l'écran d'édition ouvert depuis un résultat n'aurait
    pas la date de naissance — et l'enregistrement l'effacerait."""
    reponse = client.get(f"/api/v1/admin/athletes/{coureur.id}")

    assert reponse.status_code == 200
    assert reponse.json()["birth_date"] == "1988-03-02"


def test_lire_une_fiche_coureur_inconnue_rend_404(client):
    assert client.get("/api/v1/admin/athletes/4242").status_code == 404


def test_lire_une_fiche_coureur_sans_le_pouvoir_rend_403(client, db_session, coureur):
    _session_etroite(client, db_session)

    assert client.get(f"/api/v1/admin/athletes/{coureur.id}").status_code == 403
