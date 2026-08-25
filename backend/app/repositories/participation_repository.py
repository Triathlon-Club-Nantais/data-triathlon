"""Accès données pour Participation, incluant les filtres de la liste publique."""
from collections.abc import Iterable
from datetime import date

from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session, aliased, contains_eager, joinedload

from app.core.club import tcn_clause
from app.core.discipline import federal_clause
from app.core.season import season_bounds, season_of
from app.core.validation import validated_clause
from app.models.athlete import Athlete
from app.models.course import Course
from app.models.participation import Participation
from app.repositories.athlete_repository import name_filter
from app.scrapers.base import STATUS_FINISHER


def _is_postgres(db: Session) -> bool:
    """Vrai si le moteur est PostgreSQL (prod) — sinon SQLite (dev)."""
    return db.bind is not None and db.bind.dialect.name == "postgresql"


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


def exists_for_athlete_on_course(db: Session, *, athlete_id: int, course_id: int) -> bool:
    """Ce coureur a-t-il déjà un résultat sur cette épreuve ? (#117, FR-006)

    **Aucune contrainte de base ne couvre ce cas** : `uq_participation_bib` porte
    sur `(course_id, bib_number)`, pas sur l'athlète. Sans cette vérification, un
    rattachement peut classer deux fois la même personne sur une même course —
    une incohérence visible publiquement, dans les classements.
    """
    return (
        db.query(Participation.id)
        .filter(
            Participation.course_id == course_id,
            Participation.athlete_id == athlete_id,
        )
        .first()
        is not None
    )


def reassign(db: Session, participation: Participation, *, athlete_id: int) -> Participation:
    """Rattache ce résultat à un autre coureur. **Ne touche rien d'autre** (#117).

    Ni les temps, ni les rangs, ni le statut, ni `course_id` : déplacer un
    résultat vers une autre *épreuve* n'est pas dans le périmètre de #117, et le
    silence sur les valeurs mesurées est délibéré.
    """
    participation.athlete_id = athlete_id
    db.flush()
    return participation


def count_for_course(db: Session, course_id: int) -> int:
    """Nombre de participations d'une course — avec ou sans dossard."""
    return (
        db.query(func.count(Participation.id))
        .filter(Participation.course_id == course_id)
        .scalar()
        or 0
    )


def count_all(db: Session) -> int:
    """Nombre total de participations en base (#384)."""
    return db.query(func.count(Participation.id)).scalar() or 0


def delete(db: Session, participation: Participation) -> None:
    """Supprime **un** résultat, et lui seul (#439).

    Prend l'entité et non un identifiant : l'appelant l'a déjà hydratée pour en
    construire la trace au journal, la relire ici serait un aller-retour de plus.
    Aucune purge de fiche coureur — c'est la décision D5, pas un oubli.
    """
    db.delete(participation)
    db.flush()


def delete_all(db: Session) -> int:
    """Supprime **toutes** les participations de la base. Rend le nombre effacé (#384).

    Patron de `delete_for_course`, sans filtre : une purge totale n'a pas de
    course à périmer une par une — `Course` et `course_sources` restent
    strictement intacts, seule `participations` se vide.
    """
    efface = db.query(Participation).delete(synchronize_session=False)
    db.flush()
    return efface


def delete_for_course(db: Session, course: Course) -> int:
    """Supprime **toutes** les participations de l'épreuve. Rend le nombre effacé (#285).

    Un `DELETE` d'ensemble et non une boucle sur la collection : une bascule de
    source réécrit des classements de 1811 lignes, et les hydrater une à une pour
    les jeter est un aller-retour par ligne.

    Prend l'entité et non un `course_id`, parce qu'il faut la **périmer** après
    coup : `synchronize_session=False` est le seul mode qui n'ait pas de coût, mais
    il laisse `course.participations` sur son contenu d'avant. Or l'appelant
    ré-importe juste derrière, et le persister lit cette collection — il y verrait
    les lignes qu'on vient d'effacer, et les compterait comme déjà en base.
    """
    efface = (
        db.query(Participation)
        .filter(Participation.course_id == course.id)
        .delete(synchronize_session=False)
    )
    db.expire(course, ["participations"])
    db.flush()
    return efface


def count_bibs_absent_from(
    db: Session, *, course_id: int, other_course_id: int
) -> tuple[int, int]:
    """Participations de `course_id` sans jumeau de dossard dans `other_course_id`.

    Rend `(total, tcn)` : ce que la fusion de #287 perdrait, et **combien
    concernent des membres du club** — le second chiffre est celui qui décide en
    pratique, deux chronométreurs ne publiant pas les mêmes partants (#261).

    Le rapprochement se fait par **dossard**, la clé de `uq_participation_bib` :
    c'est la seule identité qu'un même partant garde d'un chronométreur à
    l'autre, l'orthographe des noms, elle, variant d'une source à l'autre.

    **Un dossard absent ou vide n'a pas d'équivalent, par construction** — il n'y
    a rien pour le rapprocher, et deux chaînes vides ne sont pas le même coureur.
    Les compter comme rapprochés annoncerait des résultats sauvés qui
    disparaîtraient.

    `NOT EXISTS` corrélé, et non `NOT IN` : un `NULL` dans la sous-requête rend
    un `NOT IN` **toujours faux**, donc l'aperçu annoncerait « aucune perte » dès
    qu'un seul partant de la cible n'a pas de dossard. Une seule requête
    agrégée, deux colonnes : compter en Python supposerait de charger les deux
    classements, soit 1811 lignes sur la plus chargée des épreuves en base.
    """
    twin = aliased(Participation)
    has_twin = (
        db.query(twin.id)
        .filter(
            twin.course_id == other_course_id,
            twin.bib_number == Participation.bib_number,
        )
        .exists()
    )
    total, tcn = (
        db.query(
            func.count(Participation.id),
            func.sum(case((tcn_clause(Participation.club), 1), else_=0)),
        )
        .filter(
            Participation.course_id == course_id,
            or_(
                Participation.bib_number.is_(None),
                Participation.bib_number == "",
                ~has_twin,
            ),
        )
        .one()
    )
    return int(total or 0), int(tcn or 0)


def count_for_athlete(db: Session, athlete_id: int) -> int:
    """Nombre de résultats portés par un coureur — le poids de sa fiche.

    Un `COUNT()` et non `len(athlete.participations)` : ce dernier hydrate la
    collection entière pour n'en garder que la taille, et un coureur prolifique
    en porte des dizaines.
    """
    return (
        db.query(func.count(Participation.id))
        .filter(Participation.athlete_id == athlete_id)
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

    Exclut les résultats en attente de validation (#270, FR-021) : la taille du
    classement annoncée sur la fiche athlète (`course_finishers`) doit rester
    celle du classement publié.
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
            validated_clause(Participation.is_pending_validation),
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


def season_clause(seasons: list[int]):
    """OU de plages de dates pour les saisons demandées (event_date NULL exclu).

    Publique (pas de `_`) : réutilisée telle quelle par `athlete_repository`
    (#274) plutôt que recopiée — `core/season.py` reste pur (aucune dépendance
    SQLAlchemy), donc cette clause vit ici, au plus près de `Course.event_date`.
    """
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
    """Joint Athlete + Course et applique les filtres communs (liste + épreuves).

    `validated_clause` exclut systématiquement les résultats en attente de
    validation (#270, FR-021) : cette fonction alimente `list_participations`
    et, via `_grouped_events_query`, `events_with_counts`/`events_page` — soit
    trois surfaces publiques agrégées.
    """
    q = q.join(Athlete, Participation.athlete_id == Athlete.id).join(
        Course, Participation.course_id == Course.id
    ).filter(validated_clause(Participation.is_pending_validation))
    if course_id is not None:
        q = q.filter(Participation.course_id == course_id)
    if name:
        q = q.filter(name_filter(name))
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
        q = q.filter(season_clause(seasons))
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
        joinedload(Participation.athlete),
        joinedload(Participation.course).selectinload(Course.sources),
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


def list_for_athlete(
    db: Session,
    athlete_id: int,
    *,
    seasons: list[int] | None = None,
    federal_only: bool = False,
) -> list[Participation]:
    """Participations d'un athlète, filtrables comme les agrégats du club (#502).

    Les deux filtres sont **neutres par défaut** : la fiche athlète
    (`GET /athletes/{id}` sans paramètre) continue de rendre une carrière
    entière. Ils n'existent que pour la bande « Ma saison » du tableau de bord,
    qui doit compter sur exactement la même base que les compteurs club — d'où
    les mêmes clauses que `for_stats`, et non une recopie.
    """
    q = (
        db.query(Participation)
        .options(joinedload(Participation.course).selectinload(Course.sources))
        .filter(Participation.athlete_id == athlete_id)
    )
    if seasons or federal_only:
        q = q.join(Course, Participation.course_id == Course.id)
    if seasons:
        q = q.filter(season_clause(seasons))
    if federal_only:
        q = q.filter(federal_clause(Course.event_type))
    return q.order_by(Participation.created_at.desc()).all()


def list_pending(db: Session) -> list[Participation]:
    """Résultats déclarés en attente de validation, tous clubs confondus (#271).

    Aucun filtre `tcn_clause`/`scope` : les bénévoles valident les saisies de
    leurs propres membres (research.md §D5 de la feature).

    Exclut les entrées rejetées (#437) : une entrée rejetée reste
    `is_pending_validation=True` pour toujours, mais n'a plus sa place dans
    la file — c'est `list_rejected` ci-dessous qui la rend visible.
    """
    return (
        db.query(Participation)
        .options(joinedload(Participation.athlete), joinedload(Participation.course).selectinload(Course.sources))
        .filter(Participation.is_pending_validation.is_(True), Participation.is_rejected.is_(False))
        .order_by(Participation.created_at.desc())
        .all()
    )


def list_rejected(db: Session) -> list[Participation]:
    """Résultats signalés non conformes par un bénévole, tous clubs confondus (#437)."""
    return (
        db.query(Participation)
        .options(joinedload(Participation.athlete), joinedload(Participation.course).selectinload(Course.sources))
        .filter(Participation.is_pending_validation.is_(True), Participation.is_rejected.is_(True))
        .order_by(Participation.created_at.desc())
        .all()
    )


def has_pending_for_course(db: Session, course_id: int) -> bool:
    """Cette épreuve porte-t-elle au moins un résultat en attente actionnable ? (#271, #437)

    Scope la portée du renommage bénévole. Exclut les rejetées, sur la même
    logique que `list_pending` : une épreuve dont l'unique résultat en
    attente a été rejeté n'a plus de raison d'être renommable depuis cette
    page tant qu'il n'est pas d'abord dé-rejeté.
    """
    return (
        db.query(Participation.id)
        .filter(
            Participation.course_id == course_id,
            Participation.is_pending_validation.is_(True),
            Participation.is_rejected.is_(False),
        )
        .first()
        is not None
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
        # Départage final : deux homonymes exacts (même nom/prénom, même groupe,
        # même rang, même temps) ne sont sinon départagés par rien, et un
        # feuilletage peut alors voir la même ligne deux fois ou pas du tout
        # (#566). `Participation.id` ne peut jamais être à égalité.
        Participation.id,
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

    Exclut les résultats en attente de validation (#270, FR-021) : c'est le
    classement publié d'une épreuve.
    """
    query = (
        db.query(Participation)
        .join(Athlete, Participation.athlete_id == Athlete.id)
        .options(
            # `contains_eager` et non `joinedload` : la jointure sur `Athlete`
            # existe déjà (l'ordre et la recherche en dépendent), un `joinedload`
            # en ajouterait une seconde vers la même table. `Course`, lui, n'a
            # pas de jointure préexistante — `joinedload` classique, chaîné avec
            # `selectinload` pour ses sources (#350) : sans lui, `Course.provider`
            # et `.source_url`, lus à la sérialisation, lazy-loadaient
            # `course_sources` par course distincte de la page.
            contains_eager(Participation.athlete),
            joinedload(Participation.course).selectinload(Course.sources),
        )
        .filter(Participation.course_id == course_id)
        .filter(validated_clause(Participation.is_pending_validation))
    )
    if club_only:
        query = query.filter(tcn_clause(Participation.club))
    terme = (q or "").strip()
    if terme:
        query = query.filter(name_filter(terme))

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

    Exclut les résultats en attente de validation (#270, FR-021) : la synthèse
    ne doit pas compter un résultat que le classement paginé n'affiche pas.
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
        .filter(validated_clause(Participation.is_pending_validation))
        .order_by(Participation.id)
        .all()
    )


# ── Stats agrégées (issue #580) ──────────────────────────────────────────────
#
# `for_stats` chargeait les participations entières (avec `course`/`athlete`
# joints) pour que `stats_service.get_stats` fasse en Python ce que cinq
# `GROUP BY` triviaux, un `ORDER BY … LIMIT 20` et un balayage de tuples
# réduits font en SQL — mesuré à 724 ms contre 8 ms pour les mêmes compteurs en
# SQL agrégé, sur 31 280 participations (#580). Les cinq fonctions ci-dessous
# la remplacent, chacune sur le patron d'une des quatre pistes de l'issue.
# `for_stats` n'a plus d'appelant et a été supprimée.


def _stats_filters(q, *, club_only: bool, seasons: list[int] | None, federal_only: bool):
    """Filtres communs à toutes les stats agrégées, `Course` déjà joint.

    Toujours après `validated_clause` (#270, FR-021) et `Course` déjà présent
    dans `q` — appliqué par chaque appelante selon qu'elle a ou non déjà besoin
    de la jointure pour ses propres colonnes.
    """
    if club_only:
        q = q.filter(tcn_clause(Participation.club))
    if seasons:
        q = q.filter(season_clause(seasons))
    if federal_only:
        q = q.filter(federal_clause(Course.event_type))
    return q


def stats_totals(
    db: Session,
    *,
    club_only: bool = False,
    seasons: list[int] | None = None,
    federal_only: bool = False,
) -> tuple[int, int, int]:
    """`(total, athlètes distincts, épreuves distinctes)` en une requête agrégée."""
    q = db.query(
        func.count(Participation.id),
        func.count(func.distinct(Participation.athlete_id)),
        func.count(func.distinct(Participation.course_id)),
    ).filter(validated_clause(Participation.is_pending_validation))
    if seasons or federal_only:
        q = q.join(Course, Participation.course_id == Course.id)
    q = _stats_filters(q, club_only=club_only, seasons=seasons, federal_only=federal_only)
    total, athletes, events = q.one()
    return int(total or 0), int(athletes or 0), int(events or 0)


def stats_by_type(
    db: Session,
    *,
    club_only: bool = False,
    seasons: list[int] | None = None,
    federal_only: bool = False,
) -> list[tuple[str, int]]:
    """Nombre de participations par `event_type`, un `GROUP BY`.

    Un `event_type` vide ou absent n'entre pas dans la répartition, comme
    l'ancien repli Python (`if course and course.event_type`).  Ordre
    secondaire alphabétique pour départager les égalités de compte de façon
    déterministe : `stats_service.get_stats` trie ensuite par compte
    décroissant, ce que `sorted` (stable) préserve pour les non-égalités.
    """
    q = (
        db.query(Course.event_type, func.count(Participation.id))
        .join(Course, Participation.course_id == Course.id)
        .filter(validated_clause(Participation.is_pending_validation))
        .filter(Course.event_type.isnot(None), Course.event_type != "")
    )
    q = _stats_filters(q, club_only=club_only, seasons=seasons, federal_only=federal_only)
    return q.group_by(Course.event_type).order_by(Course.event_type).all()


def stats_by_month_rows(
    db: Session,
    *,
    club_only: bool = False,
    seasons: list[int] | None = None,
    federal_only: bool = False,
) -> list[tuple]:
    """Une ligne par épreuve datée : `(event_date, nombre de participations)`.

    Même patron que `distinct_seasons` : l'extraction du mois (`YYYY-MM`) n'a
    pas d'expression SQL portable SQLite/PostgreSQL, donc `stats_service`
    replie ce jeu **agrégé** (une ligne par épreuve, pas par participation) en
    Python. Un `event_date` absent n'entre pas dans la répartition, comme
    l'ancien repli Python (`if course and course.event_date`).
    """
    q = (
        db.query(Course.event_date, func.count(Participation.id))
        .join(Course, Participation.course_id == Course.id)
        .filter(validated_clause(Participation.is_pending_validation))
        .filter(Course.event_date.isnot(None))
    )
    q = _stats_filters(q, club_only=club_only, seasons=seasons, federal_only=federal_only)
    return q.group_by(Course.id, Course.event_date).all()


def stats_recent_rows(
    db: Session,
    *,
    club_only: bool = False,
    seasons: list[int] | None = None,
    federal_only: bool = False,
    limit: int = 20,
) -> list[tuple]:
    """Les `limit` participations les plus récentes, triées et bornées en SQL.

    Rend des tuples (`id`, nom, prénom, club, nom d'épreuve, type, date,
    temps, `created_at`) — les seules colonnes que rend le tableau de bord —
    et non des `Participation` : trier 31 280 objets en mémoire pour en garder
    20 est exactement le coût que #580 supprime. Départage à compte égal (rare
    en pratique, `created_at` portant les microsecondes) par `id` décroissant,
    pour un ordre déterministe qu'un `ORDER BY` sur la seule date ne garantit
    pas d'un moteur à l'autre.
    """
    q = (
        db.query(
            Participation.id,
            Athlete.nom,
            Athlete.prenom,
            Participation.club,
            Course.name,
            Course.event_type,
            Course.event_date,
            Participation.total_time,
            Participation.created_at,
        )
        .join(Athlete, Participation.athlete_id == Athlete.id)
        .join(Course, Participation.course_id == Course.id)
        .filter(validated_clause(Participation.is_pending_validation))
        .filter(Participation.created_at.isnot(None))
    )
    q = _stats_filters(q, club_only=club_only, seasons=seasons, federal_only=federal_only)
    return (
        q.order_by(Participation.created_at.desc(), Participation.id.desc())
        .limit(limit)
        .all()
    )


def stats_rank_rows(
    db: Session,
    *,
    club_only: bool = False,
    seasons: list[int] | None = None,
    federal_only: bool = False,
) -> list[tuple]:
    """`(rank_overall, rank_category, rank_gender, gender)` — un balayage réduit.

    Alimente `stats_service._rank_counters`, qui fait les douze compteurs en
    une passe Python sur ces tuples plutôt que sur des `Participation`
    entières avec leur `course`/`athlete` joints (#580) — le patron déjà suivi
    par `summary_rows_for_course`.
    """
    q = (
        db.query(
            Participation.rank_overall,
            Participation.rank_category,
            Participation.rank_gender,
            Athlete.gender,
        )
        .join(Athlete, Participation.athlete_id == Athlete.id)
        .filter(validated_clause(Participation.is_pending_validation))
    )
    if seasons or federal_only:
        q = q.join(Course, Participation.course_id == Course.id)
    q = _stats_filters(q, club_only=club_only, seasons=seasons, federal_only=federal_only)
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
    """Ordre de tri des épreuves, toujours terminé par `Course.id` (#567).

    `_grouped_events_query` rend une ligne par `Course.id`, et plusieurs
    `Course` peuvent partager nom et date (six heats TimePulse, cas Mesquer —
    cf. `services/course_duplicates`) : sans clé de départage unique, ces
    lignes sont entièrement à égalité et `LIMIT/OFFSET` peut en rendre une
    deux fois, ou aucune.

    Si une recherche fuzzy est active (Postgres), la similarité **complète**
    le tri demandé au lieu de le remplacer — `sort` reste consulté, et
    `courses.name` reste dans l'ordre : le regroupement par compétition du
    front (#568) en dépend.
    """
    if sort == "date_asc":
        order = (Course.event_date.asc().nullslast(), Course.name, Course.id)
    elif sort == "name":
        order = (Course.name.asc(), Course.event_date.desc(), Course.id)
    elif sort == "imported_desc":
        # « Derniers résultats enregistrés » de /ajouter (#201) : trier par date
        # d'entrée en base, pas par date d'épreuve — une épreuve ancienne qu'on
        # vient d'importer doit apparaître en tête, sans quoi la carte semble ne
        # rien avoir enregistré. `created_at` est figé au premier import (un
        # re-scrape ne le bouge pas, cf. modèle `Course`).
        order = (Course.created_at.desc(), Course.name, Course.id)
    else:
        # date_desc par défaut : dates nulles en dernier.
        order = (Course.event_date.desc().nullslast(), Course.name, Course.id)
    if event_name and _is_postgres(db):
        return (func.similarity(Course.name, event_name).desc(), *order)
    return order


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

    # `total_events` : COUNT(DISTINCT course_id) sur la requête filtrée plutôt
    # qu'un COUNT sur la sous-requête groupée — même valeur (`_apply_filters`
    # est la clause partagée des deux requêtes, prouvé par
    # tests/test_repositories/test_events_page_total_events.py), 12× moins
    # cher : #584 mesure 70 ms contre 6 ms sur 31 280 participations, la
    # moitié du temps de la route qui recalculait ce que la page groupée
    # venait de produire.
    counts = _apply_filters(
        db.query(
            func.count(func.distinct(Participation.course_id)).label("total_events"),
            func.count(Participation.id).label("total_participations"),
        ),
        db,
        name=name,
        event_type=event_type,
        event_name=event_name,
        club_only=club_only,
        date_from=date_from,
        date_to=date_to,
        seasons=seasons,
        federal_only=federal_only,
    ).one()
    total_events = counts.total_events or 0
    total_participations = counts.total_participations or 0

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

    `validated_clause` exclut systématiquement les résultats en attente de
    validation (#270, #562) : sans elle, une saison entière pouvait n'exister
    dans le sélecteur que par une saisie jamais vérifiée.
    """
    q = (
        db.query(
            Course.event_date.label("event_date"),
            func.count(Participation.id).label("part_count"),
        )
        .join(Participation, Participation.course_id == Course.id)
        .filter(Course.event_date.isnot(None))
        .filter(validated_clause(Participation.is_pending_validation))
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
