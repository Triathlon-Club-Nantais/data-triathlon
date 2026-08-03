"""Agrégations statistiques (club / tableau de bord / synthèse d'épreuve)."""
import re
from collections import Counter

from sqlalchemy.orm import Session

from app.core import season as season_module
from app.core.club import is_tcn
from app.repositories import participation_repository
from app.scrapers.base import STATUS_FINISHER


def _athlete_key(part) -> int:
    # Utiliser l'id DB pour éviter les collisions entre homonymes.
    return part.athlete_id


def get_stats(
    db: Session,
    *,
    club_only: bool = False,
    seasons: list[int] | None = None,
    federal_only: bool = False,
) -> dict:
    """Stats agrégées : total, athlètes, épreuves, répartition par type/mois, récents."""
    parts = participation_repository.for_stats(
        db, club_only=club_only, seasons=seasons, federal_only=federal_only
    )
    if not parts:
        return {"total": 0, "athletes": 0, "events": 0, "by_type": {}, "by_month": {}, "recent": []}

    athlete_set = {p.athlete_id for p in parts}
    event_set = {p.course_id for p in parts}
    by_type: dict[str, int] = {}
    by_month: dict[str, int] = {}
    for p in parts:
        course = p.course
        if course and course.event_type:
            by_type[course.event_type] = by_type.get(course.event_type, 0) + 1
        if course and course.event_date:
            key = str(course.event_date)[:7]  # YYYY-MM
            by_month[key] = by_month.get(key, 0) + 1

    recent = sorted(
        (p for p in parts if p.created_at),
        key=lambda p: p.created_at,
        reverse=True,
    )[:20]

    return {
        "total": len(parts),
        "athletes": len(athlete_set),
        "events": len(event_set),
        "by_type": dict(sorted(by_type.items(), key=lambda x: -x[1])),
        "by_month": dict(sorted(by_month.items())),
        "recent": [
            {
                "id": p.id,
                "athlete_name": p.athlete.nom if p.athlete else "",
                "athlete_firstname": p.athlete.prenom if p.athlete else "",
                "club": p.club or "",
                "event_name": p.course.name if p.course else "",
                "event_type": p.course.event_type if p.course else "",
                "event_date": p.course.event_date.isoformat()
                if p.course and p.course.event_date
                else None,
                "total_time": p.total_time or "",
                "scraped_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in recent
        ],
    }


def list_seasons(
    db: Session, *, club_only: bool = False, federal_only: bool = False
) -> list[dict]:
    """Saisons disponibles pour le sélecteur.

    Saisons ayant ≥ 1 résultat daté + saison en cours toujours présente (à 0 si
    absente), enrichies de `label`/`is_current`, triées par année décroissante.
    """
    rows = participation_repository.distinct_seasons(
        db, club_only=club_only, federal_only=federal_only
    )
    by_year = {r["start_year"]: r for r in rows}

    current = season_module.current_season()
    by_year.setdefault(
        current, {"start_year": current, "event_count": 0, "participation_count": 0}
    )

    out = []
    for year in sorted(by_year, reverse=True):
        entry = by_year[year]
        out.append(
            {
                "start_year": year,
                "event_count": entry["event_count"],
                "participation_count": entry["participation_count"],
                "label": season_module.season_label(year),
                "is_current": year == current,
            }
        )
    return out


def _event_row(r) -> dict:
    return {
        "id": r.course_id,
        "event_name": r.event_name or "",
        "event_date": r.event_date.isoformat() if r.event_date else None,
        "event_type": r.event_type or "",
        "is_relay": bool(r.is_relay),
        "distance_km": r.distance_km,
        "total": r.total,
        "tcn_count": int(r.tcn_count or 0),
    }


def list_events(db: Session, **filters) -> dict:
    """Page d'épreuves (scroll infini) + compteurs globaux du filtre."""
    page = participation_repository.events_page(db, **filters)
    return {
        "items": [_event_row(r) for r in page["items"]],
        "total_events": page["total_events"],
        "total_participations": page["total_participations"],
    }


# ── Synthèse d'une épreuve (issue #163) ──────────────────────────────────────
#
# Ces agrégats étaient calculés dans le navigateur, sur le classement entier.
# Les déplacer ici est ce qui permet à la page de n'en recevoir que vingt lignes.
# Les valeurs, les limites d'affichage et le découpage de l'histogramme sont
# repris tels quels : la feature déplace ces calculs, elle ne les rejuge pas.

#: Tranche de l'histogramme des temps, et plafond du nombre de tranches.
_HISTOGRAM_BUCKET_SEC = 300
_HISTOGRAM_MAX_BARS = 60

#: Limites d'affichage de la page, historiques.
_MAX_CATEGORIES = 8
_MAX_CLUBS = 9

_STATUTS_NON_FINISHERS = frozenset({"DNF", "DNS", "DSQ"})


def _plus_frequents(compteur: Counter[str], limite: int) -> list[tuple[str, int]]:
    """Les `limite` plus fréquents, à égalité départagés par le libellé.

    `Counter.most_common` départage par ordre d'insertion, donc par ordre de
    lecture en base : deux clubs à 23 participants pouvaient changer de place
    d'une consultation à l'autre. Le libellé rend ce classement déterministe.
    """
    return sorted(compteur.items(), key=lambda item: (-item[1], item[0]))[:limite]


def _seconds(temps: str | None) -> int | None:
    """Secondes d'un temps `HH:MM:SS`, ou `None` s'il est absent ou illisible."""
    if not temps:
        return None
    match = re.search(r"(?:(\d+):)?(\d{1,2}):(\d{2})$", temps)
    if not match:
        return None
    return int(match.group(1) or 0) * 3600 + int(match.group(2)) * 60 + int(match.group(3))


def _histogram(secondes: list[int]) -> dict | None:
    if not secondes:
        return None
    premiere = min(secondes) // _HISTOGRAM_BUCKET_SEC
    derniere = max(secondes) // _HISTOGRAM_BUCKET_SEC
    tranches = min(derniere - premiere + 1, _HISTOGRAM_MAX_BARS)
    bars = [0] * tranches
    for valeur in secondes:
        # Le plafond fait retomber les temps extrêmes dans la dernière tranche
        # plutôt que de les perdre.
        bars[min(valeur // _HISTOGRAM_BUCKET_SEC - premiere, tranches - 1)] += 1
    return {
        "bars": bars,
        # Bord gauche de la première tranche : ancre l'axe des abscisses sur des
        # heures rondes côté affichage (#129).
        "start_sec": premiere * _HISTOGRAM_BUCKET_SEC,
        "bucket_sec": _HISTOGRAM_BUCKET_SEC,
    }


def course_summary(db: Session, course_id: int) -> dict:
    """Synthèse d'une épreuve **entière**, indépendante de toute sélection.

    Ni la recherche ni la portée club n'entrent ici : chercher un nom ne doit
    pas faire tomber l'histogramme à une barre. C'est pour cela que la route
    qui l'expose n'accepte aucun paramètre.
    """
    finishers = non_finishers = unknown = 0
    male = female = tcn_count = 0
    categories: Counter[str] = Counter()
    clubs: Counter[str] = Counter()
    split_keys: dict[str, None] = {}
    secondes: list[int] = []

    lignes = participation_repository.summary_rows_for_course(db, course_id)
    for status, club, category, total_time, splits, gender in lignes:
        statut = (status or "").strip()
        if statut.upper() in _STATUTS_NON_FINISHERS:
            non_finishers += 1
        elif statut.lower() == STATUS_FINISHER:
            finishers += 1
        else:
            # Statut vide ou non reconnu : ni finisher ni abandon (#23).
            unknown += 1

        initiale = (gender or "").strip().lower()[:1]
        if initiale in ("f", "w"):
            female += 1
        elif initiale in ("m", "h"):
            male += 1

        if category and category.strip():
            categories[category.strip()] += 1
        if club and club.strip():
            clubs[club.strip()] += 1
        if is_tcn(club):
            tcn_count += 1

        for cle, valeur in (splits or {}).items():
            # Un `dict` plutôt qu'un `set` : l'ordre d'apparition fixe celui des
            # colonnes du tableau, et un `set` le rendrait arbitraire.
            if valeur:
                split_keys.setdefault(cle, None)

        seconde = _seconds(total_time)
        if seconde is not None and total_time != "00:00:00":
            secondes.append(seconde)

    return {
        "total": len(lignes),
        "finishers": finishers,
        "non_finishers": non_finishers,
        "unknown": unknown,
        "tcn_count": tcn_count,
        "male": male,
        "female": female,
        "categories": [
            {"name": nom, "count": nombre}
            for nom, nombre in _plus_frequents(categories, _MAX_CATEGORIES)
        ],
        # Dénominateur des pourcentages affichés : **toutes** les catégories
        # renseignées, pas seulement les 8 rendues. Les rapporter à la somme du
        # top 8 gonflerait chaque barre — 1,28× sur une épreuve à 20 catégories
        # dont le top 8 ne couvre que 78 % des participants — et les ferait
        # sommer à 100 %, ce qu'elles ne font pas.
        "categories_total": sum(categories.values()),
        "clubs": [
            {"name": nom, "count": nombre, "is_tcn": is_tcn(nom)}
            for nom, nombre in _plus_frequents(clubs, _MAX_CLUBS)
        ],
        "histogram": _histogram(secondes),
        "split_keys": list(split_keys),
    }
