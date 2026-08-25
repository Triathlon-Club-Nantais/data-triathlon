"""`POST /participations` reste publique (#270), mais ne doit plus laisser
l'appelant choisir la source active d'une épreuve — ni détourner une épreuve
existante (#565).

Voisin de `test_public_routes_still_open.py` : c'est là que la surface
publique de cette route est décrite, celui-ci en couvre l'écriture annexe que
personne ne regardait — `course_sources` — plutôt que la seule réponse HTTP.
"""
from datetime import date

from app.repositories import course_repository
from app.scrapers.base import ScrapedResult
from app.services import scrape_service


def test_source_url_et_provider_hostiles_ne_creent_aucune_source_active(client, db_session):
    """Reproduction de l'issue : sans cookie de session, `source_url` +
    `provider` fournis par l'appelant ne doivent influencer ni l'un ni
    l'autre l'épreuve créée (#565, option 1)."""
    reponse = client.post(
        "/api/v1/participations",
        json={
            "athlete_name": "DUPONT",
            "event_name": "Epreuve Inventee",
            "event_date": "2026-05-16",
            "event_type": "triathlon-m",
            "source_url": "https://www.klikego.com/resultats/nantes/heat/duathlon-m?heat=abc",
            "provider": "klikego",
        },
    )

    assert reponse.status_code == 201
    assert not client.cookies, "le test doit passer sans le moindre cookie"

    course = course_repository.get(db_session, reponse.json()["course"]["id"])
    assert course.sources == []
    assert course.provider == ""
    assert course.source_url == ""


def test_provider_est_ignore_meme_declare_manuel_explicitement(client):
    """`provider` n'est plus un champ du contrat d'entrée : l'envoyer ne
    produit ni 422 ni effet — silencieusement ignoré, comme tout champ
    inconnu d'un modèle Pydantic par défaut."""
    reponse = client.post(
        "/api/v1/participations",
        json={
            "athlete_name": "MARTIN",
            "event_name": "Autre Epreuve Inventee",
            "event_date": "2026-05-16",
            "event_type": "triathlon-m",
            "provider": "manuel",
        },
    )

    assert reponse.status_code == 201


def test_ne_detourne_pas_une_epreuve_existante_via_la_regle_r(client, db_session):
    """Second angle de l'issue #565, démontré sur le code non corrigé : un
    `provider` ∈ {klikego, breizhchrono} et une `source_url` partageant
    `platform_event_id` + `heat_slug` avec une épreuve déjà en base la
    détournaient via `services.course_reconciliation.find_reconcilable_course`
    (appelée **avant** l'identité stricte nom/date/type). Forcer
    `provider="manuel"` sur cette route ferme aussi cet angle : la règle R ne
    s'applique jamais à `"manuel"`.
    """
    url_legitime = "https://www.klikego.com/resultats/nantes-2026/duathlon-m?heat=serie-1"
    participation_legitime = scrape_service.save_one(
        db_session,
        ScrapedResult(
            source_url=url_legitime,
            provider="klikego",
            athlete_name="LEGIT",
            athlete_firstname="Vrai",
            event_name="Triathlon Legit",
            event_date=date(2026, 5, 16),
            event_type="triathlon-m",
            bib_number="1",
        ),
    )
    course_id_legitime = participation_legitime.course_id

    # Même (platform_event_id, heat_slug) que l'épreuve légitime, mais une
    # chaîne d'URL différente et un événement sans rapport.
    url_hostile = "https://www.klikego.com/resultats/AUTRE-NOM/duathlon-m?heat=serie-1&extra=1"
    reponse = client.post(
        "/api/v1/participations",
        json={
            "athlete_name": "ATTAQUANT",
            "event_name": "Epreuve Bidon Sans Rapport",
            "event_date": "1999-01-01",
            "event_type": "triathlon-m",
            "source_url": url_hostile,
            "provider": "klikego",
        },
    )
    assert reponse.status_code == 201
    assert not client.cookies

    assert reponse.json()["course"]["id"] != course_id_legitime, (
        "la participation forgée ne doit pas atterrir sur l'épreuve légitime existante"
    )

    course_legitime = course_repository.get(db_session, course_id_legitime)
    assert [s.url for s in course_legitime.sources] == [url_legitime], (
        "aucune source hostile ne doit avoir été rattachée à l'épreuve légitime"
    )
