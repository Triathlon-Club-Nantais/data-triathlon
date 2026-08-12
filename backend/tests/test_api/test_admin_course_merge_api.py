"""Contrat de `GET /admin/courses/{id}/merge-impact` — l'aperçu d'avant pair (#286).

Fusionner supprime l'épreuve absorbée **et ses résultats** : ceux qui n'ont pas
d'équivalent dans la cible disparaissent. Ce fichier éprouve que le chiffre qui
décide — combien de **membres du club** on perdrait — est exact avant le geste,
et non découvert après.

**Sur la session.** Le conftest de ce dossier ouvre une session
superutilisateur ; les tests de refus ouvrent la leur, plus étroite, et écrasent
le cookie posé par la fixture — patron de `test_admin_data_api.py`.
"""
from datetime import date

import pytest

from app.core.permissions import P
from app.repositories import (
    athlete_repository,
    course_repository,
    course_source_repository,
    participation_repository,
)
from tests.test_api.test_admin_data_api import _session_etroite

TARGET_URL = "https://www.klikego.com/resultats/mesquer-2026"
ABSORBED_URL = "https://www.breizhchrono.com/resultats/mesquer-2026"


def _result(db_session, course, *, nom, bib, club=None):
    athlete = athlete_repository.get_or_create(db_session, nom=nom, prenom="Test", club=club)
    db_session.flush()
    return participation_repository.create(
        db_session,
        athlete_id=athlete.id,
        course_id=course.id,
        bib_number=bib,
        club=club,
    )


@pytest.fixture
def pair(db_session):
    """Deux épreuves publiées par deux chronométreurs, aux dossards partiellement communs.

    Le nom, la date et le type **diffèrent** des deux côtés : c'est le cas
    nominal (AC2), pas une anomalie — deux chronométreurs ne nomment ni ne
    classent la même épreuve de la même façon.

    Un seul dossard est commun (`1`), porté par le même coureur : il a un
    équivalent, donc il ne sera pas perdu, et son coureur survit à la fusion.
    Quatre résultats de l'absorbée n'ont **aucun** équivalent — dont deux du TCN
    et un **sans dossard**, irréconciliable par construction.
    """
    target = course_repository.get_or_create(
        db_session, name="Triathlon de Mesquer", event_date=date(2026, 5, 16),
        event_type="triathlon-m", source_url=TARGET_URL, provider="klikego",
    )
    absorbed = course_repository.get_or_create(
        db_session, name="Mesquer Tri", event_date=date(2026, 5, 17),
        event_type="triathlon-s", source_url=ABSORBED_URL, provider="breizhchrono",
    )
    db_session.flush()

    _result(db_session, target, nom="PARTAGE", bib="1", club="Triathlon Club Nantais")
    _result(db_session, target, nom="CIBLE-SEULE", bib="2", club="ASPTT Nantes")

    _result(db_session, absorbed, nom="PARTAGE", bib="1", club="Triathlon Club Nantais")
    _result(db_session, absorbed, nom="PERDU-TCN-1", bib="50", club="Triathlon Club Nantais")
    _result(db_session, absorbed, nom="PERDU-TCN-2", bib="51", club="TCN")
    _result(db_session, absorbed, nom="PERDU-AUTRE", bib="52", club="ASPTT Nantes")
    _result(db_session, absorbed, nom="PERDU-SANS-DOSSARD", bib=None, club="ASPTT Nantes")
    db_session.commit()
    return {"target": target, "absorbed": absorbed}


def _impact(client, pair):
    return client.get(
        f"/api/v1/admin/courses/{pair['target'].id}/merge-impact",
        params={"absorbed_id": pair["absorbed"].id},
    )


# --- AC1 : la garde ---------------------------------------------------------


def test_the_preview_is_refused_without_the_sources_permission(client, db_session, pair):
    """AC1 — 403 pour une session connectée mais sans `courses:sources`."""
    _session_etroite(client, db_session)

    assert _impact(client, pair).status_code == 403


def test_the_preview_is_served_with_the_sources_permission_alone(client, db_session, pair):
    """AC1 — la garde nomme un pouvoir, pas un rôle : celui-ci suffit, et lui seul."""
    _session_etroite(client, db_session, P.COURSES_SOURCES)

    assert _impact(client, pair).status_code == 200


def test_the_preview_needs_a_session(client, pair):
    """AC1 — 401 avant 403, structurellement : la garde compose `current_user`."""
    client.cookies.clear()

    assert _impact(client, pair).status_code == 401


# --- AC2 : deux épreuves qui diffèrent, et ce n'est pas une erreur ----------


def test_both_courses_may_differ_on_name_date_and_type(client, pair):
    """AC2 — le cas nominal : deux chronométreurs, deux libellés, deux types."""
    response = _impact(client, pair)

    assert response.status_code == 200
    payload = response.json()
    assert payload["target"] == {
        "id": pair["target"].id,
        "name": "Triathlon de Mesquer",
        "event_date": "2026-05-16",
        "event_type": "triathlon-m",
        "is_relay": False,
        "provider": "klikego",
        "participations": 2,
    }
    assert payload["absorbed"] == {
        "id": pair["absorbed"].id,
        "name": "Mesquer Tri",
        "event_date": "2026-05-17",
        "event_type": "triathlon-s",
        "is_relay": False,
        "provider": "breizhchrono",
        "participations": 5,
    }


# --- AC3 : fusionner une épreuve avec elle-même -----------------------------


def test_merging_a_course_with_itself_is_a_bad_request(client, pair):
    """AC3 — 400 et message français : rien à absorber, et #287 supprimerait la cible."""
    target_id = pair["target"].id

    response = client.get(
        f"/api/v1/admin/courses/{target_id}/merge-impact", params={"absorbed_id": target_id}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Une épreuve ne peut pas être fusionnée avec elle-même."


# --- AC4 : le compte TCN, le chiffre qui décide ------------------------------


def test_the_tcn_count_is_exact_when_only_some_bibs_differ(client, pair):
    """AC4 — quatre résultats sans équivalent, dont deux membres du club.

    Le rapprochement se fait par **dossard**, la clé de `uq_participation_bib` :
    le `1` de l'absorbée a son jumeau dans la cible, les autres non. Le résultat
    **sans dossard** compte parmi les perdus — il n'y a rien pour le rapprocher.

    Les deux libellés TCN de la fixture (`Triathlon Club Nantais` et `TCN`) sont
    deux variantes de la liste blanche de `core/club.py` : compter à l'égalité
    sur une seule forme en manquerait une.
    """
    payload = _impact(client, pair).json()

    assert payload["participations_without_match"] == 4
    assert payload["tcn_participations_without_match"] == 2


def test_a_bibless_result_on_the_target_side_does_not_hide_the_losses(
    client, db_session, pair
):
    """Le piège du `NOT IN`, du **côté cible** — celui qu'aucune fixture n'exerce.

    Un `NULL` dans la sous-requête rend un `NOT IN` toujours faux : il suffirait
    d'un seul partant sans dossard **dans la cible** pour que l'aperçu annonce
    « aucune perte » sur une fusion qui en cause quatre. Le sans-dossard de la
    fixture est du côté absorbé, où il compte parmi les perdus — l'autre moitié de
    la règle, et la raison pour laquelle le repository écrit un `NOT EXISTS`
    corrélé. Sans ce test, un retour au `NOT IN` passerait la suite entière.
    """
    _result(db_session, pair["target"], nom="CIBLE-SANS-DOSSARD", bib=None, club="")
    db_session.commit()

    payload = _impact(client, pair).json()

    assert payload["participations_without_match"] == 4
    assert payload["tcn_participations_without_match"] == 2


def test_the_orphaned_athletes_are_those_the_merge_would_leave_empty(client, pair):
    """Les fiches coureur que la pair viderait — celles du seul absorbé.

    Le coureur au dossard commun court les deux épreuves : il survit. Les quatre
    autres n'ont que l'absorbée, et #287 les emportera.
    """
    payload = _impact(client, pair).json()

    assert payload["athletes_orphaned"] == 4


# --- AC5 : le drapeau « même URL », sur le cas Mesquer -----------------------


def test_the_flag_is_false_when_the_two_courses_have_distinct_urls(client, pair):
    """Deux chronométreurs distincts : la pair **ajoutera** une source."""
    assert _impact(client, pair).json()["same_source_url"] is False


def test_the_flag_is_true_on_the_reconstituted_mesquer_case(client, db_session):
    """AC5 — même URL, même provider, deux `event_type` (ids 38 et 50 en base de dev).

    La pair n'ajoute alors aucune source : elle ne fait que supprimer un
    doublon. C'est ce que le drapeau permet d'annoncer.
    """
    target = course_repository.get_or_create(
        db_session, name="Triathlon de Mesquer", event_date=date(2026, 5, 16),
        event_type="triathlon-m", source_url=TARGET_URL, provider="klikego",
    )
    absorbed = course_repository.get_or_create(
        db_session, name="Triathlon de Mesquer", event_date=date(2026, 5, 16),
        event_type="triathlon-s", source_url=TARGET_URL, provider="klikego",
    )
    db_session.commit()

    payload = client.get(
        f"/api/v1/admin/courses/{target.id}/merge-impact",
        params={"absorbed_id": absorbed.id},
    ).json()

    assert payload["same_source_url"] is True


def test_the_flag_also_sees_a_passive_source_of_the_target(client, db_session, pair):
    """L'URL de l'absorbée est déjà **connue** de la cible, fût-ce en passive.

    C'est la forme de la contrainte qui l'impose : `UNIQUE(course_id, url)`
    ignore `is_active`. Repointer cette source sur la cible (#287) lèverait, donc
    la pair n'ajoute rien — annoncer le contraire ferait attendre une source de
    plus qui ne viendra pas.
    """
    course_source_repository.add(
        db_session, course=pair["target"], url=ABSORBED_URL, provider="breizhchrono"
    )
    db_session.commit()

    assert _impact(client, pair).json()["same_source_url"] is True


# --- Les deux épreuves doivent exister, et rien ne bouge --------------------


def test_an_unknown_target_is_a_not_found(client, pair):
    response = client.get(
        "/api/v1/admin/courses/424242/merge-impact",
        params={"absorbed_id": pair["absorbed"].id},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Épreuve introuvable."


def test_an_unknown_absorbed_course_is_a_not_found(client, pair):
    response = client.get(
        f"/api/v1/admin/courses/{pair['target'].id}/merge-impact",
        params={"absorbed_id": 424242},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Épreuve introuvable."


def test_the_absorbed_course_is_required(client, pair):
    """Sans `absorbed_id`, la question n'a pas de sens : 422, pas d'aperçu vide."""
    response = client.get(f"/api/v1/admin/courses/{pair['target'].id}/merge-impact")

    assert response.status_code == 422


def test_the_preview_changes_nothing(client, db_session, pair):
    """Une lecture, comme `deletion-impact` : ni source, ni résultat, ni épreuve."""
    _impact(client, pair)

    assert course_repository.get(db_session, pair["absorbed"].id) is not None
    assert participation_repository.count_for_course(db_session, pair["absorbed"].id) == 5
    assert len(course_source_repository.list_for_course(db_session, pair["target"].id)) == 1


def test_the_sources_permission_is_offered_to_role_composition(client):
    """Un pouvoir qui garde une ressource sans figurer à l'inventaire serait mort."""
    groups = client.get("/api/v1/admin/permissions").json()

    courses_feature = next(group for group in groups if group["feature"] == "Épreuves")
    codes = {permission["code"] for permission in courses_feature["permissions"]}
    assert "courses:sources" in codes
