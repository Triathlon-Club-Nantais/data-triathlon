"""Accès données pour Course."""
from datetime import date, datetime, timedelta

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session, selectinload

from app.core.club import tcn_clause
from app.core.time import utcnow
from app.core.validation import validated_clause
from app.models.course import Course
from app.models.course_source import CourseSource


def get(db: Session, course_id: int) -> Course | None:
    return db.get(Course, course_id)


def get_by_identity(
    db: Session,
    name: str,
    event_date: date | None,
    event_type: str,
    is_relay: bool,
) -> Course | None:
    return (
        db.query(Course)
        .filter(
            Course.name == name,
            Course.event_date == event_date,
            Course.event_type == event_type,
            Course.is_relay == is_relay,
        )
        .first()
    )


def get_or_create(
    db: Session,
    *,
    name: str,
    event_date: date | None,
    event_type: str,
    source_url: str = "",
    provider: str = "",
    is_relay: bool = False,
    distance_km: float | None = None,
    format_label: str | None = None,
) -> Course:
    """L'épreuve d'identité `(name, event_date, event_type, is_relay)`, créée au besoin.

    **La signature ne bouge pas, la destination des deux derniers kwargs si** :
    `source_url` et `provider` n'étant plus des colonnes (#279), ils deviennent la
    **source active** de l'épreuve neuve. Les 14 scrapers et `services/mapping`
    appellent donc exactement comme avant.

    Sur une épreuve **déjà connue**, rien n'est touché — ni l'identité, ni les
    sources. C'est le contrat d'origine (la première scrapée garde la main, D3) ;
    enregistrer la seconde URL en passive est le travail de #283, pas d'ici.
    """
    existing = get_by_identity(db, name, event_date, event_type, is_relay)
    if existing:
        return existing
    course = Course(
        name=name,
        event_date=event_date,
        event_type=event_type,
        is_relay=is_relay,
        distance_km=distance_km,
        format_label=format_label,
    )
    if source_url:
        # `is_active=True` explicitement : la colonne vaut `False` par défaut
        # (#278, D3), et la **première** source d'une épreuve neuve est la seule
        # qui doive prendre la main sans arbitrage. Passée par la relation, elle
        # est visible de `course.source_url` avant même le flush.
        course.sources.append(
            CourseSource(url=source_url, provider=provider, is_active=True)
        )
    db.add(course)
    db.flush()
    return course


def _by_active_source(db: Session, clause):
    """La requête de base des trois recherches par URL — **jointure**, pas hybride (#281).

    `Course.source_url` reste juste dans un `WHERE`, mais son `@expression` est
    une sous-requête scalaire corrélée : le moteur l'évalue **une fois par ligne
    de `courses`**. La jointure pose la question dans l'autre sens — « quelles
    sources portent cette URL, et à quelle épreuve appartiennent-elles ? » — et
    ramène `courses` par sa clé primaire.

    `CourseSource.is_active` dans la clause, et il porte l'AC4 : une source
    passive n'alimente aucun affichage et n'est jamais re-scrapée (#282), donc
    elle ne cache rien. Sans ce filtre, coller la seconde publication d'une
    épreuve fraîche rendrait un résultat caché portant le classement de l'autre
    chronométreur.

    `join` **plus** `selectinload`, et les deux sont nécessaires : la jointure est
    filtrée sur la seule active, elle ne peut donc pas peupler `course.sources`
    (un `contains_eager` y mettrait une collection tronquée). Le `selectinload`
    reste ce qui évite le N+1 chez les appelants, qui lisent `provider` sur
    chaque épreuve rendue.

    Aucune épreuve n'apparaît deux fois, et c'est la base qui le garantit :
    l'index partiel `UNIQUE(course_id) WHERE is_active` ne laisse **au plus une**
    ligne joignable par épreuve, même quand le lot contient à la fois l'URL
    active et une passive de la même épreuve. Pas de `DISTINCT` — il masquerait
    la garantie au lieu de s'appuyer sur elle.
    """
    return (
        db.query(Course)
        .join(Course.sources)
        .options(selectinload(Course.sources))
        .filter(clause, CourseSource.is_active)
        .order_by(Course.scraped_at.desc())
    )


def get_by_active_source(
    db: Session,
    *,
    source_url: str,
    name: str,
    event_date: date | None,
    is_relay: bool,
) -> Course | None:
    """L'épreuve dont la source **active** est cette URL, classification exclue (#294).

    `event_type` est volontairement hors du filtre : c'est justement le champ qui
    a pu changer d'un scrape à l'autre (heuristique de `classify` affinée, contexte
    de nom différent), et le chercher à l'égalité est ce qui faisait naître une
    seconde épreuve.

    **Trois champs d'identité sur quatre ne désignent pas un heat**, et il ne faut
    pas le croire : TimePulse publie ses six heats sous **une** URL d'événement et
    sous le **même** nom, seuls `event_type` et `is_relay` les distinguent (mesuré,
    cf. `services/course_duplicates._same_source_url`). Cette lecture rend donc un
    candidat, pas un verdict — c'est à l'appelant d'établir que le scrape ne publie
    qu'une classification pour cette clé (`import_service._reclassify_heats`).

    **Jointure, jamais `Course.source_url`** : l'hybride n'a plus d'`@expression`
    depuis #306, un filtre dessus lève. Et `CourseSource.is_active` porte ici du
    sens, pas seulement de la performance — une source passive n'alimente aucun
    affichage (#279) et ne classe donc rien non plus (D2).
    """
    return _by_active_source(
        db,
        (CourseSource.url == source_url)
        & (Course.name == name)
        & (Course.event_date == event_date)
        & (Course.is_relay == is_relay),
    ).first()


def reclassify(db: Session, course: Course, event_type: str) -> Course:
    """Aligne la classification de l'épreuve sur celle du dernier scrape (#294).

    **N'écrit rien si l'identité visée est déjà prise.** `uq_course_identity` porte
    sur `(name, event_date, event_type, is_relay)` : réécrire `event_type` fait
    changer l'épreuve d'identité, et viser celle d'une épreuve déjà en base ferait
    tomber le flush sur la contrainte, en plein import. La ligne garde alors sa
    classification — deux épreuves à réunir sont un doublon à fusionner (#287,
    #288), pas une écriture à forcer.
    """
    if course.event_type == event_type:
        return course
    if get_by_identity(db, course.name, course.event_date, event_type, course.is_relay):
        return course
    course.event_type = event_type
    db.flush()
    return course


def get_latest_by_source_url(db: Session, source_url: str) -> Course | None:
    """Course la plus récemment scrapée pour cette URL d'import (clé du cache TTL)."""
    return _by_active_source(db, CourseSource.url == source_url).first()


def list_by_source_url(db: Session, source_url: str) -> list[Course]:
    """Toutes les `Course` publiées sous cette URL d'import — les heats.

    Une URL peut porter N courses (Klikego heats, Wiclax multi-catégories,
    RaceResult multi-listes, Chronoplace multi-épreuves). Alimente le SSE
    `done` sur le chemin cache TTL pour que le sélecteur de course du front
    (#135) rende **toutes** les courses touchées, pas la seule représentative
    de `get_latest_by_source_url`.

    Ordre stable, sur la même clé de tri que le repli latest : `scraped_at`
    décroissant → la plus récente en tête (comportement de la première course
    pré-sélectionnée du sélecteur).
    """
    return _by_active_source(db, CourseSource.url == source_url).all()


def list_by_source_urls(db: Session, source_urls: list[str]) -> list[Course]:
    """Un seul `IN` pour un lot d'URLs — évite le N+1 sur les heats cachés.

    Utilisé par le SSE `done` du fan-out Klikego (#156) : quand k heats sur N
    sont sautés par le cache TTL, on récupère leurs `Course` déjà en base pour
    étoffer le sélecteur de fin d'import. Sans lot, un import à 20 heats cachés
    ferait 20 requêtes à la place d'une.

    Le coût reste constant en k depuis #281, et l'endroit du `IN` a changé : il
    porte sur `course_sources.url` au travers de la jointure, plus sur la
    sous-requête corrélée du hybride qui, elle, se rejouait par ligne de
    `courses` — donc k fois pour rien.

    Liste vide → requête évitée, retour `[]`.
    """
    if not source_urls:
        return []
    return _by_active_source(db, CourseSource.url.in_(source_urls)).all()


def touch_scraped_at(db: Session, course: Course) -> None:
    """Met à jour l'horodatage de scraping (clé du cache TTL)."""
    course.scraped_at = utcnow()


def reset_scraped_at_all(db: Session) -> int:
    """Remet `scraped_at` à `NULL` sur **toutes** les épreuves. Rend le nombre touché (#384).

    `services/cache.is_fresh` lit `scraped_at is None` comme « jamais
    scrapée » : après une purge totale des résultats, ceci force un rescrape
    immédiat au lieu de laisser le TTL masquer la base vide jusqu'à 30 jours.

    ponytail: `iter_all(older_than_days=...)` filtre sur `Course.scraped_at <
    cutoff`, et `NULL` n'y matche jamais côté SQL — un rescrape en masse par
    CLI avec `--older-than-days` ne retrouvera donc pas ces épreuves tant
    qu'elles n'ont pas été re-scrapées au moins une fois. Sans incidence sur
    le geste back-office (aucun filtre d'ancienneté ici) ; à garder en tête si
    un usage CLI de cette purge apparaît un jour.
    """
    touchees = db.query(Course).update({Course.scraped_at: None}, synchronize_session=False)
    db.flush()
    return touchees


def coordinates_by_id(db: Session, course_ids: list[int]) -> dict[int, tuple[float, float]]:
    """Coordonnées déjà géocodées d'un ensemble d'épreuves, sans requête N+1 (#579).

    Ne rend que les épreuves **géocodées avec succès** : `GET /stats/events-geo`
    écarte déjà celles sans coordonnées (`if coord:`), ce filtre en amont évite
    de transporter des `None` que la route devrait re-filtrer.
    """
    if not course_ids:
        return {}
    rows = (
        db.query(Course.id, Course.latitude, Course.longitude)
        .filter(Course.id.in_(course_ids))
        .filter(Course.latitude.isnot(None))
        .all()
    )
    return {r.id: (r.latitude, r.longitude) for r in rows}


def list_missing_geocode(
    db: Session, *, retry_after: datetime, limit: int | None = None
) -> list[Course]:
    """Épreuves sans coordonnées, hors celles dont l'échec est encore « frais » (#579).

    Une tentative échouée pose `geocoded_at` sans poser `latitude`/`longitude`
    (cf. `save_geocode_attempt`) : sans le filtre sur `retry_after`, une épreuve
    que Nominatim ne trouve pas serait retentée à chaque lancement de
    `geocode-courses`, en pure perte.
    """
    q = (
        db.query(Course)
        .filter(Course.latitude.is_(None))
        .filter(or_(Course.geocoded_at.is_(None), Course.geocoded_at <= retry_after))
        .order_by(Course.id)
    )
    if limit is not None:
        q = q.limit(limit)
    return q.all()


def save_geocode_attempt(db: Session, course: Course, coord: tuple[float, float] | None) -> None:
    """Persiste le résultat d'une tentative de géocodage, réussie ou non (#579).

    `geocoded_at` est posé dans tous les cas — c'est lui qui empêche de
    retenter en boucle un échec. `latitude`/`longitude` ne le sont que sur un
    succès : `None` les laisse tels quels, plutôt que d'écraser un succès
    passé si une recherche redevenait bredouille.

    Commite immédiatement : chaque épreuve est traitée séparément, sur le
    patron des batches CLI (`rescrape-db`) — un Ctrl-C au milieu du lot ne
    perd que la tentative en cours, jamais celles déjà persistées.
    """
    if coord is not None:
        course.latitude, course.longitude = coord
    course.geocoded_at = utcnow()
    db.commit()


def delete(db: Session, course: Course) -> None:
    """Supprime l'épreuve **et tous ses résultats** (#117, FR-002).

    La cascade est portée par la relation (`cascade="all, delete-orphan"`), donc
    par l'**ORM** et non par la base. C'est délibéré : `database.py` n'émet aucun
    `PRAGMA foreign_keys=ON`, un `ondelete="CASCADE"` serait inerte en SQLite
    (développement et tests) et actif en PostgreSQL — un comportement que la
    suite de tests ne verrait jamais.

    ponytail: la cascade ORM charge les participations et émet un DELETE par
    ligne — quelques secondes pour une épreuve de 3 000 finishers, sur un geste
    d'administration ponctuel. Si le volume change de nature, la sortie est un
    delete en masse plus un `ondelete` en base, avec le PRAGMA qui va avec.
    """
    db.delete(course)


def delete_all(db: Session) -> int:
    """Supprime **toutes** les épreuves, avec leurs sources et résultats. Rend le
    nombre d'épreuves supprimées (#384 — « Supprimer toutes les épreuves »).

    **`DELETE` de masse, enfants d'abord — pas la cascade ORM de `delete()`.**
    Celle-ci charge une épreuve et ses résultats en mémoire pour émettre un
    `DELETE` par ligne : correct pour **une** épreuve, mais un aller-retour
    réseau par résultat sur la base entière — l'un des gestes les plus
    destructeurs du back-office ne peut pas se permettre ce coût. Vider
    `participations` puis `course_sources` avant `courses` rend un `DELETE`
    de masse sûr malgré l'absence d'`ondelete` sur
    `course_sources.course_id` : la contrainte ne peut être rompue que par un
    enfant *restant*, pas par l'ordre des tables vidées.

    Le compte vient du `DELETE` sur `courses` lui-même, jamais d'un
    `COUNT(*)` préalable — même précaution que `participation_repository.delete_all`.

    Comme `participation_repository.delete_all` et `athlete_repository.delete_all`,
    aucun `expire`/`expunge` de session ici : le seul appelant
    (`wipe_all_courses`) ne relit aucune `Course` après ce `DELETE`, et c'est
    la route qui `commit` juste après — ce qui périme normalement toute
    instance encore en mémoire. Un appelant qui relirait une épreuve dans la
    **même** session avant ce `commit` obtiendrait une instance périmée ;
    aucun appelant de ce dépôt ne le fait aujourd'hui.
    """
    from app.models.participation import Participation

    db.query(Participation).delete(synchronize_session=False)
    db.query(CourseSource).delete(synchronize_session=False)
    efface = db.query(Course).delete(synchronize_session=False)
    db.flush()
    return efface


def set_quality(
    db: Session,
    course: Course,
    *,
    is_reliable_computed: bool,
    quality_issues: dict[str, int],
) -> None:
    """Persiste l'indice de fiabilité **calculé** à l'import (cf. services/quality.py).

    Écrit `is_reliable_computed`, jamais `reliability_override` : l'avis d'un
    humain survit à tous les re-scrapes, et aucune garde n'est nécessaire pour
    cela — les deux colonnes sont distinctes (FR-037).
    """
    course.is_reliable_computed = is_reliable_computed
    course.quality_issues = quality_issues


def set_counts(db: Session, course: Course, *, participation_count: int, tcn_count: int) -> None:
    """Écrit les deux compteurs dénormalisés (#623) — recalcul complet, pour
    l'import qui tient déjà en mémoire l'ensemble des participations de la
    course (`_Persister.finalize`)."""
    course.participation_count = participation_count
    course.tcn_count = tcn_count


def adjust_counts(db: Session, course: Course, *, participation_delta: int, tcn_delta: int) -> None:
    """Ajuste les deux compteurs d'un delta — pour un geste qui touche une
    seule participation (`admin_actions.validate_participation`/
    `.delete_participation`), plutôt qu'un recalcul complet évité à dessein :
    aucune requête supplémentaire, pas de risque de diverger de l'état qui
    vient d'être lu.
    """
    course.participation_count = max(0, course.participation_count + participation_delta)
    course.tcn_count = max(0, course.tcn_count + tcn_delta)


def zero_counts_all(db: Session) -> int:
    """Remet les deux compteurs à zéro sur **toutes** les épreuves. Rend le
    nombre touché — même patron que `reset_scraped_at_all`, appelée juste à
    côté par `wipe_all_participations` (#384) : `Course` reste intacte, seuls
    ses agrégats retombent avec les participations qu'ils comptaient.
    """
    touchees = db.query(Course).update(
        {Course.participation_count: 0, Course.tcn_count: 0}, synchronize_session=False
    )
    db.flush()
    return touchees


def _filtered(
    db: Session,
    *,
    name: str | None,
    event_type: str | None,
    club_only: bool,
    date_from: date | None,
    date_to: date | None,
    unreliable: bool = False,
):
    """Les filtres du catalogue, en un seul endroit — `list_all` et `count_all`.

    Deux chaînes de filtres jumelles dériveraient l'une de l'autre au premier
    filtre ajouté, et la dérive se lirait comme « page 4 sur 7 » sans page 4.
    """
    from app.models.participation import Participation

    q = db.query(Course)
    if name:
        q = q.filter(Course.name.ilike(f"%{name}%"))
    if event_type:
        q = q.filter(Course.event_type == event_type)
    if date_from:
        q = q.filter(Course.event_date >= date_from)
    if date_to:
        q = q.filter(Course.event_date <= date_to)
    if unreliable:
        # `is_reliable` est `coalesce(reliability_override, is_reliable_computed)` :
        # l'avis humain prime, et `NULL` — « jamais évaluée » — n'entre pas dans la
        # comparaison, donc reste hors de la file. Toute la règle tient dans
        # l'`@expression` du modèle ; il n'y a rien à brancher ici.
        q = q.filter(Course.is_reliable.is_(False))
    if club_only:
        q = (
            q.join(Participation, Participation.course_id == Course.id)
            .filter(tcn_clause(Participation.club))
            # #562 : une épreuve dont l'unique participation club est en
            # attente de validation ne doit pas apparaître dans le catalogue.
            .filter(validated_clause(Participation.is_pending_validation))
            .distinct()
        )
    return q


def list_all(
    db: Session,
    *,
    name: str | None = None,
    event_type: str | None = None,
    club_only: bool = False,
    date_from: date | None = None,
    date_to: date | None = None,
    unreliable: bool = False,
    page: int = 1,
    page_size: int = 50,
) -> list[Course]:
    q = _filtered(
        db,
        name=name,
        event_type=event_type,
        club_only=club_only,
        date_from=date_from,
        date_to=date_to,
        unreliable=unreliable,
    )
    offset = (page - 1) * page_size
    # `selectinload` et non `_filtered` : le catalogue sérialise `CourseBrief`,
    # qui expose `source_url` et `provider` — une page de 50 épreuves ferait
    # sinon 50 requêtes de plus. `count_all` partage `_filtered` et n'a, lui,
    # aucune entité à charger.
    return (
        q.options(selectinload(Course.sources))
        .order_by(Course.event_date.desc().nullslast(), Course.name)
        .offset(offset)
        .limit(page_size)
        .all()
    )


def count_all(
    db: Session,
    *,
    name: str | None = None,
    event_type: str | None = None,
    club_only: bool = False,
    date_from: date | None = None,
    date_to: date | None = None,
    unreliable: bool = False,
) -> int:
    """Combien d'épreuves la liste rendrait sans pagination — le « sur 7 »."""
    return _filtered(
        db,
        name=name,
        event_type=event_type,
        club_only=club_only,
        date_from=date_from,
        date_to=date_to,
        unreliable=unreliable,
    ).count()


def iter_all(
    db: Session,
    *,
    provider: str | None = None,
    older_than_days: int | None = None,
) -> list[Course]:
    """Les courses **scrapables** (non paginé), filtrables par provider et ancienneté.

    Alimente le rescrape en masse ; l'accès DB reste confiné au repository.

    « Scrapables » est le mot exact depuis #282 : la jointure sur la source
    **active** écarte les épreuves qui n'en ont aucune — saisie manuelle, ou
    épreuve dont on n'a rattaché que des passives. Aucune n'était re-scrapable de
    toute façon (`rescrape_service` filtrait ensuite sur `source_url` non vide) ;
    la différence est que la base ne les rend plus, au lieu de les rendre pour
    qu'on les jette.

    `provider` porte sur la source active, et c'est le seul sens qu'il puisse
    avoir : il nomme le chronométreur **qu'on va interroger**. Retenir une épreuve
    parce qu'elle porte une passive du bon provider ferait scraper l'URL d'un
    autre fournisseur sous un `--provider` explicite.

    `join` **plus** `selectinload`, même raison que `_by_active_source` : la
    jointure est filtrée sur la seule active, elle ne peut pas peupler
    `course.sources`. Et le `selectinload` n'est pas décoratif —
    `rescrape_service.run_rescrape_db` lit `source_url` **et** `provider` sur
    *chaque* course rendue ; sans lui, un rescrape de toute la base émettait une
    requête de plus par épreuve, sur le chemin qui traite le plus de lignes.
    """
    q = (
        db.query(Course)
        .join(Course.sources)
        .options(selectinload(Course.sources))
        .filter(CourseSource.is_active)
    )
    if provider:
        q = q.filter(CourseSource.provider == provider)
    if older_than_days is not None:
        cutoff = utcnow() - timedelta(days=older_than_days)
        q = q.filter(Course.scraped_at < cutoff)
    return q.order_by(Course.event_date.desc().nullslast(), Course.name).all()


def list_identities_with_counts(db: Session) -> list:
    """Toute la base en **une** ligne par épreuve : identité, source active, compteurs.

    La détection de doublons (#288) compare les épreuves entre elles : elle a
    besoin de la base entière, et de rien d'autre que ces neuf colonnes. Trois
    raisons de la servir en une requête agrégée plutôt qu'en entités :

    - lire `course.participations` par épreuve donnerait la même réponse en une
      requête par ligne — le N+1 que `core/sql_observability` a été écrit pour
      rendre visible (« 1812 requêtes pour 1810 participants ») ;
    - `Course.source_url` et `Course.provider` sont des sous-requêtes scalaires
      corrélées (#279), donc **deux évaluations par ligne** de plus dans un
      `SELECT` ; la jointure sur la source active les rend en une passe (#281) ;
    - aucune entité n'a besoin d'être suivie par la Session : rien n'est écrit
      ici, et l'appelant n'a que des comparaisons à faire.

    `outerjoin` sur les deux tables, et les deux cas existent : une épreuve
    saisie à la main n'a aucune source, une épreuve fraîchement créée par un
    scraper qui n'a rien trouvé n'a aucun résultat. Les écarter serait cacher
    précisément les épreuves dont l'import a dérapé.
    """
    from app.models.participation import Participation

    return (
        db.query(
            Course.id.label("id"),
            Course.name.label("name"),
            Course.event_date.label("event_date"),
            Course.event_type.label("event_type"),
            Course.is_relay.label("is_relay"),
            func.coalesce(CourseSource.provider, "").label("provider"),
            func.coalesce(CourseSource.url, "").label("source_url"),
            func.count(Participation.id).label("total"),
            # `coalesce` autour du `sum` : sur une épreuve sans résultat, le
            # `outerjoin` ne donne aucune ligne à sommer et `SUM` rend `NULL`,
            # là où `COUNT` rend `0`. Deux compteurs affichés côte à côte ne
            # peuvent pas dire l'un « 0 » et l'autre « aucune idée ».
            func.coalesce(
                func.sum(case((tcn_clause(Participation.club), 1), else_=0)), 0
            ).label("tcn_count"),
        )
        .outerjoin(
            CourseSource,
            (CourseSource.course_id == Course.id) & CourseSource.is_active,
        )
        .outerjoin(Participation, Participation.course_id == Course.id)
        .group_by(Course.id, CourseSource.provider, CourseSource.url)
        .order_by(Course.event_date.desc().nullslast(), Course.name, Course.id)
        .all()
    )


def update_identity(db: Session, course: Course, **champs) -> Course:
    """Écrit les champs d'identité fournis. **Ne vérifie pas l'unicité** — c'est
    le service qui la contrôle par lecture préalable, pour pouvoir nommer
    l'épreuve en conflit (#117, FR-021)."""
    for nom_champ, valeur in champs.items():
        setattr(course, nom_champ, valeur)
    db.flush()
    return course
