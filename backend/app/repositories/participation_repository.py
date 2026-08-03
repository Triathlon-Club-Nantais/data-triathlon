"""Accès données pour Participation, incluant les filtres de la liste publique."""
from collections.abc import Iterable
from datetime import date

from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session, contains_eager, joinedload

from app.core.club import tcn_clause
from app.core.discipline import federal_clause
from app.core.season import season_bounds, season_of
from app.core.text import deaccent
from app.models.athlete import Athlete
from app.models.course import Course
from app.models.participation import Participation
from app.scrapers.base import STATUS_FINISHER


def _is_postgres(db: Session) -> bool:
    """Vrai si le moteur est PostgreSQL (prod) — sinon SQLite (dev)."""
    return db.bind is not None and db.bind.dialect.name == "postgresql"


def _athlete_name_filter(term: str):
    """Filtre nom **ou** prénom d'athlète, en sous-chaîne, sans casse ni accents.

    `ilike` seul ne suffit pas : il ignore la casse, jamais les accents, et ce
    sur les deux moteurs. Mesuré — `lower('LEMÉE') LIKE '%lemee%'` vaut faux, y
    compris avec le listener Unicode de `core/database.py`, qui rend `lemée`.

    `unaccent` désigne l'extension PostgreSQL en production et la fonction
    applicative enregistrée sur la connexion SQLite en développement : même nom,
    donc une seule expression ici. Aucun index n'est utilisable de ce fait, sans
    conséquence — le filtre porte toujours sur une seule épreuve.
    """
    # Les jokers `LIKE` saisis par un visiteur sont échappés : ce n'est pas une
    # injection (le motif est passé en paramètre lié), mais `q=%` rendait
    # l'épreuve entière et `q=_` n'importe quel caractère.
    terme = deaccent(term).lower()
    for joker in ("\\", "%", "_"):
        terme = terme.replace(joker, f"\\{joker}")
    pattern = f"%{terme}%"
    return or_(
        func.unaccent(func.lower(Athlete.nom)).like(pattern, escape="\\"),
        func.unaccent(func.lower(Athlete.prenom)).like(pattern, escape="\\"),
    )


def _course_name_filter(db: Session, term: str):
    """Filtre nom de course tolérant : trigram pg_trgm (Postgres) sinon ILIKE (SQLite)."""
    like = Course.name.ilike(f"%{term}%")
    if _is_postgres(db):
        # `%` = opérateur de similarité trigram → tolère les fautes de frappe.
        return or_(like, Course.name.op("%")(term))
    return like


def get(db: Session, participation_id: int) -> Participation | None:
    return (
        db.query(Participation)
        .options(joinedload(Participation.athlete), joinedload(Participation.course))
        .filter(Participation.id == participation_id)
        .first()
    )


def exists_for_bib(db: Session, course_id: int, bib_number: str | None) -> bool:
    if not bib_number:
        return False
    return (
        db.query(Participation.id)
        .filter(Participation.course_id == course_id, Participation.bib_number == bib_number)
        .first()
        is not None
    )


def count_for_course(db: Session, course_id: int) -> int:
    """Nombre de participations d'une course — avec ou sans dossard."""
    return (
        db.query(func.count(Participation.id))
        .filter(Participation.course_id == course_id)
        .scalar()
        or 0
    )


def finishers_count_by_group(
    db: Session, course_ids: Iterable[int]
) -> dict[tuple[int, bool], int]:
    """Nombre de finishers classés par (course, solo/relais).

    Seule population comparable à `rank_overall` : les DNF/DNS/DSQ n'ont pas de
    rang, et solos et relais sont classés séparément (deux « rang 1 » légitimes
    dans une même course, cf. `services/quality.py`). Un groupe sans finisher
    classé est absent du résultat — l'appelant distingue « zéro classé » de
    « compte inconnu ».
    """
    ids = list(dict.fromkeys(course_ids))
    if not ids:
        return {}
    rows = (
        db.query(
            Participation.course_id,
            Participation.is_relay,
            func.count(Participation.id),
        )
        .filter(
            Participation.course_id.in_(ids),
            func.lower(Participation.status) == STATUS_FINISHER,
            Participation.rank_overall.isnot(None),
        )
        .group_by(Participation.course_id, Participation.is_relay)
        .all()
    )
    return {(course_id, bool(is_relay)): count for course_id, is_relay, count in rows}


def existing_bibs_for_course(db: Session, course_id: int) -> set[str]:
    """Dossards déjà importés pour une course — pour dédoublonner un import en masse."""
    rows = (
        db.query(Participation.bib_number)
        .filter(Participation.course_id == course_id, Participation.bib_number.isnot(None))
        .all()
    )
    return {r[0] for r in rows}


def create(db: Session, **fields) -> Participation:
    participation = Participation(**fields)
    db.add(participation)
    db.flush()
    return participation


def update(db: Session, participation: Participation, **fields) -> Participation:
    """Écrit les `fields` fournis sur une participation existante.

    Ne touche que les colonnes passées : le persister a déjà décidé, champ par
    champ, lesquelles la source a le droit de réécrire (fusion prudente).
    """
    for key, value in fields.items():
        setattr(participation, key, value)
    db.flush()
    return participation


def _season_clause(seasons: list[int]):
    """OU de plages de dates pour les saisons demandées (event_date NULL exclu)."""
    bounds = [season_bounds(y) for y in seasons]
    return or_(
        *[and_(Course.event_date >= start, Course.event_date <= end) for start, end in bounds]
    )


def _apply_filters(
    q,
    db,
    *,
    name,
    event_type,
    event_name,
    club_only,
    date_from,
    date_to,
    course_id=None,
    seasons=None,
    federal_only=False,
):
    """Joint Athlete + Course et applique les filtres communs (liste + épreuves)."""
    q = q.join(Athlete, Participation.athlete_id == Athlete.id).join(
        Course, Participation.course_id == Course.id
    )
    if course_id is not None:
        q = q.filter(Participation.course_id == course_id)
    if name:
        pattern = f"%{name}%"
        q = q.filter(or_(Athlete.nom.ilike(pattern), Athlete.prenom.ilike(pattern)))
    if club_only:
        q = q.filter(tcn_clause(Participation.club))
    if event_type:
        q = q.filter(Course.event_type == event_type)
    if event_name:
        q = q.filter(_course_name_filter(db, event_name))
    if date_from:
        q = q.filter(Course.event_date >= date_from)
    if date_to:
        q = q.filter(Course.event_date <= date_to)
    if seasons:
        q = q.filter(_season_clause(seasons))
    if federal_only:
        q = q.filter(federal_clause(Course.event_type))
    return q


def list_participations(
    db: Session,
    *,
    name: str | None = None,
    event_type: str | None = None,
    event_name: str | None = None,
    club_only: bool = False,
    date_from: date | None = None,
    date_to: date | None = None,
    course_id: int | None = None,
    seasons: list[int] | None = None,
    federal_only: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> list[Participation]:
    q = db.query(Participation).options(
        joinedload(Participation.athlete), joinedload(Participation.course)
    )
    q = _apply_filters(
        q,
        db,
        name=name,
        event_type=event_type,
        event_name=event_name,
        club_only=club_only,
        date_from=date_from,
        date_to=date_to,
        course_id=course_id,
        seasons=seasons,
        federal_only=federal_only,
    )
    offset = (page - 1) * page_size
    # Pour le détail d'une épreuve, trier par classement ; sinon par date d'import.
    order = (
        (Participation.rank_overall.is_(None), Participation.rank_overall)
        if course_id
        else (Participation.created_at.desc(),)
    )
    return q.order_by(*order).offset(offset).limit(page_size).all()


def list_for_athlete(db: Session, athlete_id: int) -> list[Participation]:
    return (
        db.query(Participation)
        .options(joinedload(Participation.course))
        .filter(Participation.athlete_id == athlete_id)
        .order_by(Participation.created_at.desc())
        .all()
    )


def list_for_course(db: Session, course_id: int) -> list[Participation]:
    return (
        db.query(Participation)
        .options(joinedload(Participation.athlete))
        .filter(Participation.course_id == course_id)
        .order_by(Participation.rank_overall.is_(None), Participation.rank_overall)
        .all()
    )


# Groupes d'affichage : finishers, puis DNF, DSQ, DNS. Un statut vide ou inconnu
# est un finisher potentiel et reste dans le groupe 0 (cf. `raceOrder.groupRank`).
_GROUPE_AFFICHAGE = case(
    (func.upper(func.coalesce(Participation.status, "")) == "DNF", 1),
    (func.upper(func.coalesce(Participation.status, "")) == "DSQ", 2),
    (func.upper(func.coalesce(Participation.status, "")) == "DNS", 3),
    else_=0,
)

# Un temps vide ou `00:00:00` vaut temps absent — sémantique partagée avec le front.
_TEMPS_ABSENT = or_(
    Participation.total_time.is_(None),
    Participation.total_time == "",
    Participation.total_time == "00:00:00",
)


def _ordre_affichage():
    """Ordre du classement d'une épreuve, **seule** définition du projet.

    Il vivait en JavaScript (`orderParticipations`) tant que le classement
    entier arrivait d'un coup ; paginé, un ordre de requête différent de l'ordre
    d'écran fait que la tranche N servie n'est pas la tranche N affichée (#163).

    Les clés « valeur absente » sont des booléens 0/1 et non un `NULLS LAST` :
    SQLite place les `NULL` en tête en tri croissant, PostgreSQL en queue, et un
    `ORDER BY` nu diverge donc entre le développement et la production.

    La comparaison alphabétique des temps vaut comparaison chronologique : ils
    sont normalisés en `HH:MM:SS` à deux chiffres d'heures à l'import.
    """
    return (
        _GROUPE_AFFICHAGE,
        # Finishers : rang croissant, les non classés en fin.
        case((and_(_GROUPE_AFFICHAGE == 0, Participation.rank_overall.is_(None)), 1), else_=0),
        case((_GROUPE_AFFICHAGE == 0, Participation.rank_overall), else_=None),
        # Non-finishers : temps croissant, les temps absents en fin.
        case((and_(_GROUPE_AFFICHAGE != 0, _TEMPS_ABSENT), 1), else_=0),
        case(
            (and_(_GROUPE_AFFICHAGE != 0, ~_TEMPS_ABSENT), Participation.total_time),
            else_="",
        ),
        func.lower(Athlete.nom),
        func.lower(Athlete.prenom),
    )


def list_page_for_course(
    db: Session,
    course_id: int,
    *,
    page: int = 1,
    page_size: int | None = 20,
    q: str | None = None,
    club_only: bool = False,
) -> tuple[list[Participation], int]:
    """Tranche ordonnée du classement d'une épreuve, et total de la sélection.

    `page_size=None` rend tout le classement en une page (`page_size=all` côté
    API). Le total porte sur la sélection — recherche et portée club comprises —,
    pas sur l'épreuve : les décomptes d'épreuve vivent dans la synthèse.
    """
    query = (
        db.query(Participation)
        .join(Athlete, Participation.athlete_id == Athlete.id)
        # `contains_eager` et non `joinedload` : la jointure sur `Athlete` existe
        # déjà (l'ordre et la recherche en dépendent), un `joinedload` en
        # ajouterait une seconde vers la même table.
        .options(contains_eager(Participation.athlete))
        .filter(Participation.course_id == course_id)
    )
    if club_only:
        query = query.filter(tcn_clause(Participation.club))
    terme = (q or "").strip()
    if terme:
        query = query.filter(_athlete_name_filter(terme))

    total = query.count()
    query = query.order_by(*_ordre_affichage())
    if page_size is not None:
        query = query.offset((page - 1) * page_size).limit(page_size)
    return query.all(), total


def summary_rows_for_course(db: Session, course_id: int) -> list[tuple]:
    """Colonnes nécessaires à la synthèse d'une épreuve, en **une** requête.

    Rend des tuples, jamais des `Participation` : hydrater le modèle et joindre
    l'athlète est précisément le coût que la pagination supprime (#163).

    L'ordre **compte**, malgré l'agrégation : `split_keys` est construite dans
    l'ordre d'apparition, et le contrat de la route en fait l'ordre des colonnes
    du tableau. Sans `ORDER BY`, l'ordre du tas PostgreSQL n'est pas stable
    (UPDATE, VACUUM) et les colonnes pourraient se réordonner entre deux pages.

    `splits` est de loin la plus lourde des six colonnes, et la seule chargée
    pour une raison indirecte : en déduire les clés de colonnes du tableau.
    Aucun des deux moteurs n'offre d'extraction portable des clés d'un objet
    JSON, donc on lit la colonne.
    """
    return (
        db.query(
            Participation.status,
            Participation.club,
            Participation.category,
            Participation.total_time,
            Participation.splits,
            Athlete.gender,
        )
        .join(Athlete, Participation.athlete_id == Athlete.id)
        .filter(Participation.course_id == course_id)
        .order_by(Participation.id)
        .all()
    )


def for_stats(
    db: Session,
    *,
    club_only: bool = False,
    seasons: list[int] | None = None,
    federal_only: bool = False,
) -> list[Participation]:
    """Charge les participations (avec course + athlète) pour les agrégations stats."""
    q = db.query(Participation).options(
        joinedload(Participation.course), joinedload(Participation.athlete)
    )
    if club_only:
        q = q.filter(tcn_clause(Participation.club))
    if seasons or federal_only:
        q = q.join(Course, Participation.course_id == Course.id)
    if seasons:
        q = q.filter(_season_clause(seasons))
    if federal_only:
        q = q.filter(federal_clause(Course.event_type))
    return q.all()


def _grouped_events_query(
    db: Session,
    *,
    name=None,
    event_type=None,
    event_name=None,
    club_only=False,
    date_from=None,
    date_to=None,
    seasons=None,
    federal_only=False,
):
    """Requête de base : une ligne par épreuve (course) avec compteurs total + TCN."""
    q = db.query(
        Course.id.label("course_id"),
        Course.name.label("event_name"),
        Course.event_date.label("event_date"),
        Course.event_type.label("event_type"),
        Course.is_relay.label("is_relay"),
        Course.distance_km.label("distance_km"),
        func.count(Participation.id).label("total"),
        func.sum(case((tcn_clause(Participation.club), 1), else_=0)).label("tcn_count"),
    )
    q = _apply_filters(
        q,
        db,
        name=name,
        event_type=event_type,
        event_name=event_name,
        club_only=club_only,
        date_from=date_from,
        date_to=date_to,
        seasons=seasons,
        federal_only=federal_only,
    )
    return q.group_by(
        Course.id,
        Course.name,
        Course.event_date,
        Course.event_type,
        Course.is_relay,
        Course.distance_km,
    )


def events_with_counts(
    db: Session,
    *,
    name: str | None = None,
    event_type: str | None = None,
    event_name: str | None = None,
    club_only: bool = False,
    date_from: date | None = None,
    date_to: date | None = None,
    seasons: list[int] | None = None,
    federal_only: bool = False,
) -> list:
    """Épreuves distinctes avec total participants et compte TCN (non paginé — carte/stats)."""
    return (
        _grouped_events_query(
            db,
            name=name,
            event_type=event_type,
            event_name=event_name,
            club_only=club_only,
            date_from=date_from,
            date_to=date_to,
            seasons=seasons,
            federal_only=federal_only,
        )
        .order_by(Course.event_date.desc().nullslast(), Course.name)
        .all()
    )


def _events_order(db: Session, sort: str, event_name: str | None):
    """Ordre de tri des épreuves. Si recherche fuzzy (Postgres), tri par similarité."""
    if event_name and _is_postgres(db):
        return (
            func.similarity(Course.name, event_name).desc(),
            Course.event_date.desc().nullslast(),
        )
    if sort == "date_asc":
        return (Course.event_date.asc().nullslast(), Course.name)
    if sort == "name":
        return (Course.name.asc(), Course.event_date.desc())
    # date_desc par défaut : dates nulles en dernier.
    return (Course.event_date.desc().nullslast(), Course.name)


def events_page(
    db: Session,
    *,
    name: str | None = None,
    event_type: str | None = None,
    event_name: str | None = None,
    club_only: bool = False,
    date_from: date | None = None,
    date_to: date | None = None,
    seasons: list[int] | None = None,
    federal_only: bool = False,
    sort: str = "date_desc",
    page: int = 1,
    page_size: int = 30,
) -> dict:
    """Page d'épreuves (scroll infini) + total épreuves et total participations."""
    grouped = _grouped_events_query(
        db,
        name=name,
        event_type=event_type,
        event_name=event_name,
        club_only=club_only,
        date_from=date_from,
        date_to=date_to,
        seasons=seasons,
        federal_only=federal_only,
    )

    total_events = db.query(func.count()).select_from(grouped.subquery()).scalar() or 0

    parts = db.query(func.count(Participation.id))
    parts = _apply_filters(
        parts,
        db,
        name=name,
        event_type=event_type,
        event_name=event_name,
        club_only=club_only,
        date_from=date_from,
        date_to=date_to,
        seasons=seasons,
        federal_only=federal_only,
    )
    total_participations = parts.scalar() or 0

    offset = (page - 1) * page_size
    rows = (
        grouped.order_by(*_events_order(db, sort, event_name))
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return {
        "items": rows,
        "total_events": int(total_events),
        "total_participations": int(total_participations),
    }


def distinct_seasons(
    db: Session, *, club_only: bool = False, federal_only: bool = False
) -> list[dict]:
    """Saisons présentes (≥ 1 participation sur une épreuve datée), repliées en Python.

    Repli Python plutôt que SQL pour rester portable SQLite/Postgres sans
    fonctions de date spécifiques. Volume de données modeste.
    """
    q = (
        db.query(
            Course.event_date.label("event_date"),
            func.count(Participation.id).label("part_count"),
        )
        .join(Participation, Participation.course_id == Course.id)
        .filter(Course.event_date.isnot(None))
    )
    if club_only:
        q = q.filter(tcn_clause(Participation.club))
    if federal_only:
        q = q.filter(federal_clause(Course.event_type))
    rows = q.group_by(Course.id, Course.event_date).all()

    agg: dict[int, dict] = {}
    for event_date, part_count in rows:
        year = season_of(event_date)
        entry = agg.setdefault(
            year, {"start_year": year, "event_count": 0, "participation_count": 0}
        )
        entry["event_count"] += 1
        entry["participation_count"] += int(part_count or 0)
    return list(agg.values())


def club_label_counts(db: Session, *, like: str | None = None) -> list[tuple[str, int]]:
    """Libellés de club distincts et leur nombre de participations, décroissant.

    Alimente `python -m app.cli club-labels`. Les libellés vides sont écartés :
    ils ne disent rien de l'appartenance à un club.
    """
    q = db.query(Participation.club, func.count(Participation.id)).filter(
        Participation.club.isnot(None), Participation.club != ""
    )
    if like:
        q = q.filter(Participation.club.ilike(f"%{like}%"))
    rows = q.group_by(Participation.club).all()
    return sorted(((club, int(count)) for club, count in rows), key=lambda r: (-r[1], r[0]))
