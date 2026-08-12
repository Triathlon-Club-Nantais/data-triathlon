"""Contrat des deux ressources de `admin_course_merge.py` — l'aperçu, puis l'acte.

Fusionner supprime l'épreuve absorbée **et ses résultats** : ceux qui n'ont pas
d'équivalent dans la cible disparaissent. La première moitié du fichier éprouve
que le chiffre qui décide — combien de **membres du club** on perdrait — est
exact avant le geste (`GET …/merge-impact`, #286) ; la seconde éprouve le geste
lui-même (`POST …/merge`, #287).

**Les deux dans le même fichier, et c'est le point de conception central de
#287** : l'aperçu annonce « aucune source ne sera ajoutée », la fusion doit tenir
cette promesse. Un test appelle donc les deux à la suite et compare — c'est la
seule forme qui interdise à l'annonce et à l'acte de diverger.

**Sur la session.** Le conftest de ce dossier ouvre une session
superutilisateur ; les tests de refus ouvrent la leur, plus étroite, et écrasent
le cookie posé par la fixture — patron de `test_admin_data_api.py`.
"""
from datetime import date

import pytest

from app.core.permissions import P
from app.models.athlete import Athlete
from app.repositories import (
    admin_action_log_repository,
    athlete_repository,
    course_repository,
    course_source_repository,
    participation_repository,
)
from tests.test_api.test_admin_data_api import _session_etroite

TARGET_URL = "https://www.klikego.com/resultats/mesquer-2026"
ABSORBED_URL = "https://www.breizhchrono.com/resultats/mesquer-2026"
#: Un troisième chronométreur, pour éprouver le sort des sources **passives** de
#: l'absorbée — celles que #283 lui rattache à l'import.
THIRD_URL = "https://www.wiclax.com/resultats/mesquer-2026"


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
    """Les fiches coureur que la fusion viderait — celles du seul absorbé.

    Le coureur au dossard commun court les deux épreuves : il survit. Les quatre
    autres n'ont que l'absorbée, et #287 les emportera.
    """
    payload = _impact(client, pair).json()

    assert payload["athletes_orphaned"] == 4


# --- AC5 : le drapeau « même URL », sur le cas Mesquer -----------------------


def test_the_flag_is_false_when_the_two_courses_have_distinct_urls(client, pair):
    """Deux chronométreurs distincts : la fusion **ajoutera** une source."""
    assert _impact(client, pair).json()["same_source_url"] is False


def test_the_flag_is_true_on_the_reconstituted_mesquer_case(client, db_session):
    """AC5 — même URL, même provider, deux `event_type` (ids 38 et 50 en base de dev).

    La fusion n'ajoute alors aucune source : elle ne fait que supprimer un
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
    la fusion n'ajoute rien — annoncer le contraire ferait attendre une source de
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


# ============================================================================
# `POST /admin/courses/{id}/merge` — l'acte (#287)
# ============================================================================
#
# La fusion ne re-scrape **rien** : la cible garde sa source active et ses
# participations, l'absorbée disparaît avec les siennes, et son URL rejoint la
# cible en passive. Prendre les données de l'autre chronométreur est un **second**
# geste, la bascule de #285 — deux décisions distinctes, deux gestes distincts.

#: Le nom, la date et le type de la cible, tels que la fixture les pose. La
#: fusion ne doit **jamais** y toucher : l'épreuve qui survit survit telle quelle.
IDENTITE_CIBLE = ("Triathlon de Mesquer", date(2026, 5, 16), "triathlon-m")


def _merge(client, target_id: int, absorbed_id: int):
    return client.post(
        f"/api/v1/admin/courses/{target_id}/merge", json={"absorbed_id": absorbed_id}
    )


def _fusionne(client, pair):
    return _merge(client, pair["target"].id, pair["absorbed"].id)


def _sources(db_session, course_id: int) -> list[tuple[str, bool]]:
    return [
        (source.url, source.is_active)
        for source in course_source_repository.list_for_course(db_session, course_id)
    ]


def _dossards(db_session, course_id: int) -> list[str | None]:
    return sorted(
        (ligne.bib_number or "")
        for ligne in participation_repository.list_for_course(db_session, course_id)
    )


def _fusions(db_session, course_id: int) -> list:
    return [
        entree
        for entree in admin_action_log_repository.list_for_entity(
            db_session, entity_type="course", entity_id=course_id
        )
        if entree.action == "course.merge"
    ]


# --- #287 AC1 : l'absorbée disparaît, la cible ne bouge pas -----------------


def test_the_merge_deletes_the_absorbed_course_and_leaves_the_target_intact(
    client, db_session, pair
):
    """AC1 — trois affirmations en une, parce qu'elles sont indissociables.

    L'absorbée n'existe plus, la cible porte **une source passive de plus**, et
    ses participations sont **inchangées** : la fusion ne re-scrape rien, elle
    rapproche deux lignes. Une fusion qui réécrirait aussi le classement serait la
    bascule de #285, et l'exploitant n'aurait plus aucun geste pour rapprocher
    sans remplacer.
    """
    response = _fusionne(client, pair)

    assert response.status_code == 200, response.text
    assert course_repository.get(db_session, pair["absorbed"].id) is None
    assert _sources(db_session, pair["target"].id) == [
        (TARGET_URL, True),
        (ABSORBED_URL, False),
    ]
    assert _dossards(db_session, pair["target"].id) == ["1", "2"]


def test_the_merge_answers_with_the_scale_of_what_it_destroyed(client, pair):
    """Les chiffres rendus sont ceux que l'aperçu annonçait, une fois le geste fait.

    `sources` sort dans la forme et l'ordre de `GET /courses/{id}/sources` (#284),
    comme la bascule (#285) : l'écran se réaffiche sans second appel, et le front
    n'a qu'une forme à connaître pour cette donnée.
    """
    corps = _fusionne(client, pair).json()

    assert corps["target_id"] == pair["target"].id
    assert corps["absorbed_id"] == pair["absorbed"].id
    assert corps["participations_deleted"] == 5
    assert corps["athletes_purged"] == 4
    assert corps["source_added"] is True
    assert [(source["url"], source["is_active"]) for source in corps["sources"]] == [
        (TARGET_URL, True),
        (ABSORBED_URL, False),
    ]


def test_two_courses_differing_on_name_date_and_type_are_merged_anyway(
    client, db_session, pair
):
    """C'est tout l'objet du ticket : deux chronométreurs, deux libellés, deux types.

    `mapping.get_or_create_course` apparie à l'égalité stricte, donc ces deux
    lignes ne pouvaient pas se rejoindre à l'import ; la bascule (#285) refuse
    même de les toucher. Ici la divergence est le **cas nominal**, et l'identité
    de la cible en sort intacte — la fusion ne renomme rien (faire converger deux
    identités est #289).
    """
    assert _fusionne(client, pair).status_code == 200

    db_session.expire_all()
    survivante = course_repository.get(db_session, pair["target"].id)
    assert (survivante.name, survivante.event_date, survivante.event_type) == IDENTITE_CIBLE


# --- #287 AC2 : l'URL déjà connue, et l'accord avec l'aperçu ----------------


def test_no_source_is_added_when_the_absorbed_url_is_already_known(client, db_session):
    """AC2 — le cas Mesquer (ids 38 et 50 en base de dev) : même URL des deux côtés.

    `UNIQUE(course_id, url)` ignore `is_active` : repointer cette source sur la
    cible lèverait une `IntegrityError`, en message technique anglais et sur une
    transaction devenue inutilisable. La fusion n'ajoute donc rien — elle
    **supprime un doublon**, et c'est exactement ce que l'aperçu annonçait.
    """
    target = course_repository.get_or_create(
        db_session, name="Triathlon de Mesquer", event_date=date(2026, 5, 16),
        event_type="triathlon-m", source_url=TARGET_URL, provider="klikego",
    )
    absorbed = course_repository.get_or_create(
        db_session, name="Triathlon de Mesquer", event_date=date(2026, 5, 16),
        event_type="swimrun-s", source_url=TARGET_URL, provider="klikego",
    )
    db_session.commit()

    response = _merge(client, target.id, absorbed.id)

    assert response.status_code == 200, response.text
    assert response.json()["source_added"] is False
    assert _sources(db_session, target.id) == [(TARGET_URL, True)]
    assert course_repository.get(db_session, absorbed.id) is None


def test_the_url_already_known_as_a_passive_of_the_target_is_not_added_twice(
    client, db_session, pair
):
    """La même règle quand la cible connaît l'URL en **passive**, pas en active.

    C'est la forme de la contrainte qui l'impose, et c'est aussi ce que l'aperçu
    regarde (`same_source_url` lit *toutes* les sources de la cible) : lire
    seulement l'active ferait lever l'insertion sur une paire que l'écran annonce
    comme sans effet.
    """
    course_source_repository.add(
        db_session, course=pair["target"], url=ABSORBED_URL, provider="breizhchrono"
    )
    db_session.commit()

    response = _fusionne(client, pair)

    assert response.status_code == 200, response.text
    assert response.json()["source_added"] is False
    assert _sources(db_session, pair["target"].id) == [
        (TARGET_URL, True),
        (ABSORBED_URL, False),
    ]


def test_the_preview_and_the_merge_never_disagree_on_the_added_source(
    client, db_session, pair
):
    """L'annonce et l'acte, comparés dans le même test — le point de conception de #287.

    L'aperçu promet, quand `same_source_url` est vrai, que « la fusion n'ajoute
    aucune source ». Ici l'absorbée porte **en plus** une passive d'un troisième
    chronométreur, inconnue de la cible : faire suivre les passives ferait
    apparaître une source que l'écran n'avait pas annoncée. Seule l'**active** de
    l'absorbée rejoint la cible, donc le prédicat de l'aperçu est exactement celui
    de la fusion, et la promesse ne peut pas être fausse.
    """
    course_source_repository.add(
        db_session, course=pair["target"], url=ABSORBED_URL, provider="breizhchrono"
    )
    course_source_repository.add(
        db_session, course=pair["absorbed"], url=THIRD_URL, provider="wiclax"
    )
    db_session.commit()
    annonce = _impact(client, pair).json()["same_source_url"]
    avant = _sources(db_session, pair["target"].id)

    assert _fusionne(client, pair).status_code == 200

    assert annonce is True
    assert _sources(db_session, pair["target"].id) == avant


def test_the_passive_sources_of_the_absorbed_course_do_not_follow(
    client, db_session, pair
):
    """Décision assumée : seule l'**active** de l'absorbée survit, ses passives non.

    Une passive n'alimente rien — jamais scrapée (#282), jamais affichée (#279) —
    et la faire suivre rendrait falsifiable la promesse de l'aperçu (cf. le test
    ci-dessus). L'URL reste rattrapable par le chemin ordinaire : la recoller
    recrée une épreuve, que #288 signale et qu'une seconde fusion rapproche.
    """
    course_source_repository.add(
        db_session, course=pair["absorbed"], url=THIRD_URL, provider="wiclax"
    )
    db_session.commit()

    assert _fusionne(client, pair).status_code == 200

    assert _sources(db_session, pair["target"].id) == [
        (TARGET_URL, True),
        (ABSORBED_URL, False),
    ]


# --- #287 AC3 : deux pouvoirs, pas un --------------------------------------


def test_the_merge_needs_courses_delete_on_top_of_courses_sources(
    client, db_session, pair
):
    """AC3 — `courses:sources` seul ne suffit pas : le geste **détruit** une épreuve.

    L'arbitrage des sources ne fait perdre aucune ligne (la bascule réimporte),
    la fusion oui : les résultats de l'absorbée sans jumeau de dossard
    disparaissent. Exiger le seul pouvoir d'arbitrage donnerait une suppression
    d'épreuve à qui n'en a pas reçu le droit.
    """
    _session_etroite(client, db_session, P.COURSES_SOURCES)

    response = _fusionne(client, pair)

    assert response.status_code == 403
    assert course_repository.get(db_session, pair["absorbed"].id) is not None


def test_courses_delete_alone_is_not_enough_either(client, db_session, pair):
    """AC3, l'autre moitié — les deux pouvoirs sont exigés, pas l'un ou l'autre.

    Sans ce test, une garde à `courses:delete` seul passerait le précédent.
    """
    _session_etroite(client, db_session, P.COURSES_DELETE)

    response = _fusionne(client, pair)

    assert response.status_code == 403
    assert course_repository.get(db_session, pair["absorbed"].id) is not None


def test_the_two_powers_together_pass(client, db_session, pair):
    """AC3 — et la conjonction suffit : aucun rôle n'est nommé, deux pouvoirs le sont."""
    _session_etroite(client, db_session, P.COURSES_SOURCES, P.COURSES_DELETE)

    assert _fusionne(client, pair).status_code == 200


def test_the_merge_needs_a_session(client, pair):
    """401 avant 403, structurellement : chaque garde compose `current_user`."""
    client.cookies.clear()

    assert _fusionne(client, pair).status_code == 401


# --- #287 AC4 : les fiches coureur devenues vides --------------------------


def test_the_athletes_left_without_any_result_are_purged(client, db_session, pair):
    """AC4 — les quatre coureurs de la seule absorbée partent, les deux autres restent.

    Même dette et même primitive qu'une suppression d'épreuve : les laisser
    ferait de chaque fusion un ajout d'orphelins, invisible jusqu'au prochain
    `rescrape-db`. `PARTAGE` court les deux épreuves et garde un résultat,
    `CIBLE-SEULE` n'a jamais quitté la cible.
    """
    assert _fusionne(client, pair).status_code == 200

    restants = {athlete.nom for athlete in db_session.query(Athlete).all()}
    assert {"PARTAGE", "CIBLE-SEULE"} <= restants
    assert not restants & {
        "PERDU-TCN-1", "PERDU-TCN-2", "PERDU-AUTRE", "PERDU-SANS-DOSSARD",
    }


def test_the_purge_matches_what_the_preview_announced(client, pair):
    """`athletes_orphaned` et `athletes_purged` sortent de la même définition.

    À base constante l'annonce et l'acte ne peuvent pas diverger : les deux
    passent par `athlete_repository.only_on_course`. Le test le vérifie plutôt que
    de le supposer, parce que le piège est l'**ordre** — relever les candidats
    après la suppression rendrait une liste vide, et la purge serait un no-op que
    rien ne signale.
    """
    annonce = _impact(client, pair).json()["athletes_orphaned"]

    assert _fusionne(client, pair).json()["athletes_purged"] == annonce


# --- #287 AC5 : le cas Mesquer complet, reconstitué ------------------------

MESQUER = "Triathlon et SwimRun Mesquer-Quimiac 2026"
MESQUER_VARIANTE = "Triathlon et Swimrun Mesquer Quimiac 2026"
MESQUER_JOUR = date(2026, 6, 13)
KLIKEGO_EVENT = "https://www.klikego.com/resultats/triathlon-et-swimrun-mesquer-quimiac-2026/1677015306084-12"
MESQUER_URLS = {
    "tri-s": f"{KLIKEGO_EVENT}?heat=triathlon-s-indiv",
    "tri-xs": f"{KLIKEGO_EVENT}?heat=triathlon-xs-indiv",
    "tri-xs-duo": f"{KLIKEGO_EVENT}?heat=triathlon-xs-duo",
    "bc-tri-s": (
        "https://resultats.breizhchrono.com/resultats-courses/"
        "triathlon-et-swimrun-mesquer-quimiac-2026-1677015306084-12/triathlon-s-indiv"
    ),
}


@pytest.fixture
def mesquer(db_session):
    """Les cinq lignes Mesquer de #210, pour **trois** heats réels.

    L'état historique de la preview (`id` 38, 50, 52, 53, 54) tel que le sondage
    du 12/08/2026 le décrit, réduit aux trois heats que ces URLs publient :

    - `triathlon-s` sous l'URL de heat Klikego — **le heat réel**, la cible ;
    - `swimrun-s` sous la **même** URL : le doublon d'`id=38`/`id=50`, né d'un
      `classify_event_type` instable à l'époque. Rien à ajouter à la cible ;
    - `triathlon-xs` et `triathlon-xs` en relais : deux heats réels distincts, que
      la fusion ne doit **pas** toucher (le relais est un heat à part entière,
      quatrième colonne d'`uq_course_identity`) ;
    - la publication Breizh Chrono du premier heat, sous un libellé qui diverge —
      espace au lieu du tiret, `Swimrun` au lieu de `SwimRun`. C'est elle qui fait
      gagner une source passive à la cible.

    Le tout se résorbe en **deux appels HTTP**, sans une ligne de SQL.
    """
    lignes = {}
    for cle, (nom, event_type, is_relay, url) in {
        "tri-s": (MESQUER, "triathlon-s", False, MESQUER_URLS["tri-s"]),
        "swimrun-s": (MESQUER, "swimrun-s", False, MESQUER_URLS["tri-s"]),
        "tri-xs": (MESQUER, "triathlon-xs", False, MESQUER_URLS["tri-xs"]),
        "tri-xs-duo": (MESQUER, "triathlon-xs", True, MESQUER_URLS["tri-xs-duo"]),
        "bc-tri-s": (MESQUER_VARIANTE, "triathlon-s", False, MESQUER_URLS["bc-tri-s"]),
    }.items():
        lignes[cle] = course_repository.get_or_create(
            db_session, name=nom, event_date=MESQUER_JOUR, event_type=event_type,
            is_relay=is_relay, source_url=url, provider="klikego",
        )
    db_session.flush()

    _result(db_session, lignes["tri-s"], nom="MESQUER-A", bib="1", club="TCN")
    _result(db_session, lignes["tri-s"], nom="MESQUER-B", bib="2", club="ASPTT Nantes")
    _result(db_session, lignes["swimrun-s"], nom="MESQUER-A", bib="1", club="TCN")
    _result(db_session, lignes["bc-tri-s"], nom="MESQUER-C", bib="3", club="TCN")
    _result(db_session, lignes["tri-xs"], nom="MESQUER-D", bib="4", club="TCN")
    _result(db_session, lignes["tri-xs-duo"], nom="MESQUER-E", bib="5", club="TCN")
    db_session.commit()
    return lignes


def test_the_five_mesquer_rows_collapse_to_one_course_per_real_heat(
    client, db_session, mesquer
):
    """AC5 — cinq lignes, deux appels, trois épreuves : une par heat réel.

    Le cas qui a ouvert l'epic, résorbé sans SQL. Les deux branches de la fusion
    y passent dans le même enchaînement : la première absorption ne peut ajouter
    aucune source (même URL), la seconde en ajoute une (autre chronométreur). Et
    les deux heats `triathlon-xs`, solo et relais, restent **deux** épreuves : le
    relais est la quatrième colonne de l'identité, pas une variante.
    """
    cible = mesquer["tri-s"].id

    assert _merge(client, cible, mesquer["swimrun-s"].id).status_code == 200
    assert _merge(client, cible, mesquer["bc-tri-s"].id).status_code == 200

    db_session.expire_all()
    restantes = [
        (course.name, course.event_type, course.is_relay)
        for course in course_repository.list_all(db_session, date_from=MESQUER_JOUR)
    ]
    assert sorted(restantes) == [
        (MESQUER, "triathlon-s", False),
        (MESQUER, "triathlon-xs", False),
        (MESQUER, "triathlon-xs", True),
    ]
    assert _sources(db_session, cible) == [
        (MESQUER_URLS["tri-s"], True),
        (MESQUER_URLS["bc-tri-s"], False),
    ]
    assert _dossards(db_session, cible) == ["1", "2"]
    assert len(_fusions(db_session, cible)) == 2


# --- #287 AC6 : le journal ------------------------------------------------


def test_the_merge_is_journalled_and_names_both_courses(client, db_session, pair):
    """AC6 — l'entrée nomme les deux épreuves, et c'est la **seule** trace de l'absorbée.

    Sa ligne est supprimée : si l'entrée ne portait que son identifiant, plus rien
    en base ne dirait quelle épreuve a disparu, et un exploitant qui relit six
    mois plus tard n'aurait aucun moyen de le retrouver. D'où l'identité complète
    de l'absorbée, son URL, et l'ampleur du geste — comme `course.delete`, dont
    c'est le même problème.
    """
    assert _fusionne(client, pair).status_code == 200

    entrees = _fusions(db_session, pair["target"].id)
    assert len(entrees) == 1
    charge = entrees[0].payload
    assert charge["name"] == "Triathlon de Mesquer"
    assert charge["absorbed"] == {
        "id": pair["absorbed"].id,
        "name": "Mesquer Tri",
        "event_date": "2026-05-17",
        "event_type": "triathlon-s",
        "is_relay": False,
        "source_url": ABSORBED_URL,
    }
    assert charge["participations_deleted"] == 5
    assert charge["athletes_purged"] == 4
    assert charge["source_added"] is True


# --- Les refus n'écrivent rien, ni donnée ni trace -------------------------


def test_merging_a_course_with_itself_is_refused_and_writes_nothing(
    client, db_session, pair
):
    """Le même message que l'aperçu, et pas une ligne écrite.

    Le service `flush`, la route `commit` : un refus lève avant, donc il n'y a ni
    donnée ni entrée de journal à défaire. Et le message est celui de l'aperçu,
    mot pour mot — deux formulations pour un même refus se contrediraient un jour.
    """
    cible = pair["target"].id

    response = _merge(client, cible, cible)

    assert response.status_code == 400
    assert response.json()["detail"] == "Une épreuve ne peut pas être fusionnée avec elle-même."
    assert course_repository.get(db_session, cible) is not None
    assert participation_repository.count_for_course(db_session, cible) == 2
    assert _fusions(db_session, cible) == []


def test_merging_into_an_unknown_target_is_a_not_found(client, db_session, pair):
    """Et l'absorbée est toujours là : le service lève avant le premier `flush`."""
    response = _merge(client, 424242, pair["absorbed"].id)

    assert response.status_code == 404
    assert response.json()["detail"] == "Épreuve introuvable."
    assert course_repository.get(db_session, pair["absorbed"].id) is not None


def test_merging_an_unknown_absorbed_course_is_a_not_found(client, db_session, pair):
    """Le classement de la cible est intact : rien n'a été supprimé avant la lecture."""
    response = _merge(client, pair["target"].id, 424242)

    assert response.status_code == 404
    assert response.json()["detail"] == "Épreuve introuvable."
    assert participation_repository.count_for_course(db_session, pair["target"].id) == 2


def test_a_boolean_absorbed_id_is_refused_instead_of_absorbing_course_one(client, pair):
    """`StrictInt` : en mode permissif, `true` deviendrait `1` — et l'épreuve 1 mourrait.

    Une case à cocher mal sérialisée par le front supprimerait une épreuve prise
    au hasard, avec ses résultats. Même parti pris que `AllowedEmailCreate.role_id`,
    pour un geste plus destructeur encore.
    """
    response = client.post(
        f"/api/v1/admin/courses/{pair['target'].id}/merge", json={"absorbed_id": True}
    )

    assert response.status_code == 422


def test_the_delete_permission_is_offered_to_role_composition(client):
    """Les deux pouvoirs exigés figurent à l'inventaire — sans quoi la garde serait morte."""
    groups = client.get("/api/v1/admin/permissions").json()

    courses_feature = next(group for group in groups if group["feature"] == "Épreuves")
    codes = {permission["code"] for permission in courses_feature["permissions"]}
    assert {"courses:sources", "courses:delete"} <= codes
