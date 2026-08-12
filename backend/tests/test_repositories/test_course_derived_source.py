"""`Course.source_url` et `Course.provider` : dérivés de la source active (#279).

Deux propriétés, plus deux colonnes. Le patron est celui de `Course.is_reliable`
— `hybrid_property` **plus** son `@expression`.

**Ces tests sont, depuis #281 et #282, les seuls à exercer la moitié SQL.** Elle
avait quatre appelants — les trois recherches par URL et `iter_all(provider=…)` —
et tous quatre joignent désormais `course_sources` : une sous-requête scalaire
corrélée s'évalue une fois par ligne de `courses`, une jointure ramène `courses`
par sa clé primaire. Les tests restent, parce que l'`@expression` reste et qu'un
hybride dont la moitié SQL n'est plus juste est un piège pour le premier qui
écrira `filter(Course.provider == …)`. Le sort de l'`@expression` elle-même est
une question ouverte, consignée dans `app/models/AGENTS.md`.
"""
from datetime import date

import pytest

from app.models.course import Course
from app.repositories import course_repository, course_source_repository

KLIKEGO = "https://klikego.test/mesquer"
BREIZH = "https://breizhchrono.test/mesquer"


def _epreuve(db_session, nom: str, **colonnes) -> Course:
    course = Course(name=nom, event_type=colonnes.pop("event_type", "triathlon-m"), **colonnes)
    db_session.add(course)
    db_session.flush()
    return course


def _source(db_session, course, url, *, provider, is_active=False):
    return course_source_repository.add(
        db_session, course=course, url=url, provider=provider, is_active=is_active
    )


def test_the_active_source_gives_the_course_its_url_and_provider(db_session):
    course = _epreuve(db_session, "Mesquer")
    _source(db_session, course, KLIKEGO, provider="klikego", is_active=True)

    assert course.source_url == KLIKEGO
    assert course.provider == "klikego"


def test_a_course_without_any_source_renders_empty_strings(db_session):
    """AC2 — un état légitime (saisie manuelle), pas une erreur.

    Vaut des deux côtés du hybride : la propriété Python **et** le `coalesce` de
    la sous-requête, sans quoi le SQL rendrait `NULL` là où le contrat public
    promet une chaîne.
    """
    course = _epreuve(db_session, "Saisie manuelle")

    assert course.source_url == ""
    assert course.provider == ""

    en_sql = (
        db_session.query(Course.source_url, Course.provider)
        .filter(Course.id == course.id)
        .one()
    )
    assert en_sql == ("", "")


def test_a_passive_source_never_surfaces_on_the_course(db_session):
    """D3 — la première scrapée garde la main, la seconde publication reste tue."""
    course = _epreuve(db_session, "Mesquer")
    _source(db_session, course, KLIKEGO, provider="klikego", is_active=True)
    _source(db_session, course, BREIZH, provider="breizhchrono")

    assert course.source_url == KLIKEGO
    assert course.provider == "klikego"


def test_switching_the_active_source_switches_the_derived_values(db_session):
    course = _epreuve(db_session, "Mesquer")
    _source(db_session, course, KLIKEGO, provider="klikego", is_active=True)
    passive = _source(db_session, course, BREIZH, provider="breizhchrono")

    course_source_repository.set_active(db_session, passive)

    assert course.source_url == BREIZH
    assert course.provider == "breizhchrono"


def test_filtering_on_provider_in_sql_reads_the_active_source(db_session):
    """AC3 — le test qui échouerait sans `@expression`, et qu'on ne voit pas autrement.

    La propriété Python marcherait, et ce `WHERE` lèverait — ou rendrait tout.
    """
    klikego = _epreuve(db_session, "Klikego")
    _source(db_session, klikego, KLIKEGO, provider="klikego", is_active=True)
    breizh = _epreuve(db_session, "Breizh")
    _source(db_session, breizh, BREIZH, provider="breizhchrono", is_active=True)
    # Une passive klikego sur l'épreuve Breizh : elle ne doit pas la faire sortir.
    _source(db_session, breizh, KLIKEGO, provider="klikego")

    trouvees = db_session.query(Course).filter(Course.provider == "klikego").all()

    assert [course.name for course in trouvees] == ["Klikego"]


def test_ordering_on_provider_in_sql_reads_the_active_source(db_session):
    """AC3 — `ORDER BY` sur une sous-requête scalaire, l'autre moitié du contrat."""
    for nom, provider in (("Wiclax", "wiclax"), ("Breizh", "breizhchrono"), ("Klikego", "klikego")):
        course = _epreuve(db_session, nom)
        _source(
            db_session, course, f"https://{provider}.test/{nom}",
            provider=provider, is_active=True,
        )

    ordonnees = db_session.query(Course).order_by(Course.provider).all()

    assert [course.name for course in ordonnees] == ["Breizh", "Klikego", "Wiclax"]


def test_the_derived_fields_cannot_be_written(db_session):
    """AC5 — plus aucun appelant n'**écrit** `course.source_url`.

    Ce n'est pas une convention à surveiller par grep : sans `@setter`, la
    propriété refuse l'affectation. La table est la seule vérité, et c'est la
    forme qui l'assure.
    """
    course = _epreuve(db_session, "Mesquer")

    with pytest.raises(AttributeError):
        course.source_url = KLIKEGO
    with pytest.raises(AttributeError):
        course.provider = "klikego"


def test_get_or_create_gives_a_new_course_its_active_source(db_session):
    """Le piège légué par #278 : `is_active` vaut `False` par défaut.

    La toute première source d'une épreuve neuve doit donc être passée active
    **explicitement** — aucun chemin ne l'obtient gratuitement.
    """
    course = course_repository.get_or_create(
        db_session,
        name="Mesquer",
        event_date=date(2026, 5, 16),
        event_type="triathlon-s",
        source_url=KLIKEGO,
        provider="klikego",
    )

    active = course_source_repository.get_active(db_session, course.id)
    assert active is not None
    assert (active.url, active.provider) == (KLIKEGO, "klikego")
    assert course.source_url == KLIKEGO
    assert course.provider == "klikego"


def test_get_or_create_without_url_creates_no_source(db_session):
    """La saisie manuelle n'a pas de source — même choix que la reprise de #278."""
    course = course_repository.get_or_create(
        db_session, name="Saisie manuelle", event_date=None, event_type="triathlon-m"
    )

    assert course_source_repository.list_for_course(db_session, course.id) == []
    assert course.source_url == ""


def test_a_provider_without_a_url_is_not_representable(db_session):
    """La seule divergence de #279 avec l'ancien schéma, épinglée plutôt que subie.

    Une colonne `provider` pouvait valoir `"manuel"` sur une épreuve sans URL —
    c'est ce que pose `POST /participations` quand l'appelant ne fournit pas de
    `source_url`. La table, elle, n'a pas d'endroit pour ça : le provider est un
    champ de la **source**, et `CourseSource.url` est `NOT NULL`. Une source sans
    URL serait une ligne qui ne désigne rien.

    Ce n'est pas un oubli, et la décision ne date pas d'ici : la reprise de #278
    n'a donné aucune source aux épreuves à `source_url` vide. Portée mesurée sur
    la base de dev le 12/08/2026 — **0 épreuve sur 95** porte un provider sans
    URL. Reste à revérifier sur preview avant #293.
    """
    course = course_repository.get_or_create(
        db_session, name="Saisie manuelle", event_date=None,
        event_type="triathlon-m", provider="manuel",
    )

    assert course_source_repository.list_for_course(db_session, course.id) == []
    assert course.provider == ""


def test_get_or_create_on_a_known_course_leaves_its_sources_alone(db_session):
    course = course_repository.get_or_create(
        db_session, name="Mesquer", event_date=date(2026, 5, 16),
        event_type="triathlon-s", source_url=KLIKEGO, provider="klikego",
    )

    retour = course_repository.get_or_create(
        db_session, name="Mesquer", event_date=date(2026, 5, 16),
        event_type="triathlon-s", source_url=BREIZH, provider="breizhchrono",
    )

    assert retour.id == course.id
    assert retour.source_url == KLIKEGO


def test_the_url_lookups_survive_the_derivation(db_session):
    """`get_latest_by_source_url`, `list_by_source_url`, `list_by_source_urls`.

    Trois recherches par URL qui filtraient `Course.source_url` en SQL et
    joignent `course_sources` depuis #281. Ce test ne juge que leur **résultat**,
    ce qui est exactement pourquoi il ne bouge pas d'un changement de chemin :
    c'est le filet qui a permis de basculer sans rien deviner (le détail du plan
    et du coût vit dans `test_course_source_lookups.py`).
    """
    premier = course_repository.get_or_create(
        db_session, name="Mesquer", event_date=date(2026, 5, 16),
        event_type="triathlon-s", source_url=KLIKEGO, provider="klikego",
    )
    second = course_repository.get_or_create(
        db_session, name="Mesquer", event_date=date(2026, 5, 16),
        event_type="swimrun-m", source_url=KLIKEGO, provider="klikego",
    )
    autre = course_repository.get_or_create(
        db_session, name="Vertou", event_date=date(2026, 6, 1),
        event_type="triathlon-m", source_url=BREIZH, provider="breizhchrono",
    )
    db_session.flush()

    latest = course_repository.get_latest_by_source_url(db_session, KLIKEGO)
    assert latest is not None and latest.id in {premier.id, second.id}

    heats = course_repository.list_by_source_url(db_session, KLIKEGO)
    assert {course.id for course in heats} == {premier.id, second.id}

    lot = course_repository.list_by_source_urls(db_session, [KLIKEGO, BREIZH])
    assert {course.id for course in lot} == {premier.id, second.id, autre.id}


def test_iter_all_filters_on_the_active_provider(db_session):
    klikego = course_repository.get_or_create(
        db_session, name="Klikego", event_date=date(2026, 5, 16),
        event_type="triathlon-m", source_url=KLIKEGO, provider="klikego",
    )
    course_repository.get_or_create(
        db_session, name="Breizh", event_date=date(2026, 6, 1),
        event_type="triathlon-m", source_url=BREIZH, provider="breizhchrono",
    )
    db_session.flush()

    assert [c.id for c in course_repository.iter_all(db_session, provider="klikego")] == [
        klikego.id
    ]
