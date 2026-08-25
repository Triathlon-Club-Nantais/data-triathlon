"""Agrégations statistiques (club / tableau de bord / synthèse d'épreuve)."""
from collections import Counter

from sqlalchemy.orm import Session

from app.core import season as season_module
from app.core import split_gap
from app.core.club import TCN_CANONICAL_NAME, is_tcn
from app.repositories import course_repository, participation_repository
from app.scrapers.base import STATUS_FINISHER
from app.scrapers.utils import to_seconds


def _athlete_key(part) -> int:
    # Utiliser l'id DB pour éviter les collisions entre homonymes.
    return part.athlete_id


def _bucket() -> dict:
    return {"victories": 0, "podiums": 0, "top10": 0}


def _accumule(bucket: dict, rang: int | None) -> None:
    if rang is None or rang < 1:
        return
    if rang <= 1:
        bucket["victories"] += 1
    if rang <= 3:
        bucket["podiums"] += 1
    if rang <= 10:
        bucket["top10"] += 1


def _meilleur_rang(rangs: list[int | None]) -> int | None:
    valides = [r for r in rangs if r is not None and r >= 1]
    return min(valides) if valides else None


def _rank_counters(rows) -> dict:
    """Compteurs Victoires/Podiums/Top10 des 4 modes de rang du dashboard.

    Une passe sur des tuples `(rank_overall, rank_category, rank_gender,
    gender)` — `participation_repository.stats_rank_rows`, réduite aux
    colonnes utiles, pas des `Participation` entières avec leur `course`/
    `athlete` joints (#580). Miroir du calcul auparavant fait côté client par
    `rankCounters` (`frontend/lib/utils/club-aggregate.ts`) : le comportement
    de chaque mode, y compris la ventilation genre limitée à "F"/"M", est
    repris à l'identique (#376 déplace le calcul, ne le change pas — #580 ne
    fait que déplacer une seconde fois **où** il tourne, pas ce qu'il fait).
    Ce fichier front reste vivant : `bestRank`/`isPodium` y calculent encore
    le podium club (KPI `?rank=`) et, depuis #502, celui de la bande « Ma
    saison » — à tenir en phase avec ce qui suit.
    """
    scratch, category, tous = _bucket(), _bucket(), _bucket()
    genre = {"women": _bucket(), "men": _bucket()}

    for rank_overall, rank_category_, rank_gender, gender in rows:
        _accumule(scratch, rank_overall)
        _accumule(category, rank_category_)
        _accumule(tous, _meilleur_rang([rank_overall, rank_gender, rank_category_]))

        g = (gender or "").upper()
        if g == "F":
            _accumule(genre["women"], rank_gender)
        elif g == "M":
            _accumule(genre["men"], rank_gender)

    return {"scratch": scratch, "category": category, "all": tous, "gender": genre}


def get_stats(
    db: Session,
    *,
    club_only: bool = False,
    seasons: list[int] | None = None,
    federal_only: bool = False,
) -> dict:
    """Stats agrégées : total, athlètes, épreuves, répartition par type/mois, récents.

    Cinq requêtes SQL agrégées (#580) — `total`/`athletes`/`events` en une,
    `by_type` et le jeu replié en `by_month` en un `GROUP BY` chacun, `recent`
    en `ORDER BY … LIMIT 20`, les compteurs de rang sur un balayage de tuples
    réduits — au lieu d'hydrater puis trier en Python les dizaines de milliers
    de `Participation` que `for_stats` chargeait.
    """
    total, athletes, events = participation_repository.stats_totals(
        db, club_only=club_only, seasons=seasons, federal_only=federal_only
    )
    if not total:
        return {
            "total": 0, "athletes": 0, "events": 0, "by_type": {}, "by_month": {}, "recent": [],
            "rank_counters": _rank_counters([]),
        }

    by_type_rows = participation_repository.stats_by_type(
        db, club_only=club_only, seasons=seasons, federal_only=federal_only
    )
    by_month_rows = participation_repository.stats_by_month_rows(
        db, club_only=club_only, seasons=seasons, federal_only=federal_only
    )
    recent_rows = participation_repository.stats_recent_rows(
        db, club_only=club_only, seasons=seasons, federal_only=federal_only, limit=20
    )
    rank_rows = participation_repository.stats_rank_rows(
        db, club_only=club_only, seasons=seasons, federal_only=federal_only
    )

    by_month: Counter[str] = Counter()
    for event_date, count in by_month_rows:
        by_month[str(event_date)[:7]] += int(count or 0)  # YYYY-MM

    return {
        "total": total,
        "athletes": athletes,
        "events": events,
        "by_type": dict(
            sorted(((t, int(c or 0)) for t, c in by_type_rows), key=lambda x: -x[1])
        ),
        "by_month": dict(sorted(by_month.items())),
        "recent": [
            {
                "id": id_,
                "athlete_name": nom or "",
                "athlete_firstname": prenom or "",
                "club": club or "",
                "event_name": event_name or "",
                "event_type": event_type or "",
                "event_date": event_date.isoformat() if event_date else None,
                "total_time": total_time or "",
                "scraped_at": created_at.isoformat() if created_at else None,
            }
            for id_, nom, prenom, club, event_name, event_type, event_date, total_time, created_at
            in recent_rows
        ],
        "rank_counters": _rank_counters(rank_rows),
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
        "is_reliable": r.is_reliable,
        "quality_issues": r.quality_issues,
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

#: Statut brut (majuscule) → clé de compteur dédiée (#331). `non_finishers`
#: reste leur somme, jamais recalculée séparément.
_STATUTS_NON_FINISHERS = {"DNF": "dnf", "DNS": "dns", "DSQ": "dsq"}


def _plus_frequents(compteur: Counter[str], limite: int) -> list[tuple[str, int]]:
    """Les `limite` plus fréquents, à égalité départagés par le libellé.

    `Counter.most_common` départage par ordre d'insertion, donc par ordre de
    lecture en base : deux clubs à 23 participants pouvaient changer de place
    d'une consultation à l'autre. Le libellé rend ce classement déterministe.
    """
    return sorted(compteur.items(), key=lambda item: (-item[1], item[0]))[:limite]


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
    finishers = unknown = 0
    dnf = dns = dsq = 0
    male = female = tcn_count = 0
    categories: Counter[str] = Counter()
    clubs: Counter[str] = Counter()
    split_keys: dict[str, None] = {}
    secondes: list[int] = []
    ecarts: list[float | None] = []

    # L'épreuve, lue une fois : le sport et le caractère de relais commandent le
    # schéma de segments de l'écart, et ne varient pas d'une ligne à l'autre.
    course = course_repository.get(db, course_id)
    lignes = participation_repository.summary_rows_for_course(db, course_id)
    for status, club, category, total_time, splits, gender in lignes:
        statut = (status or "").strip()
        cle_non_finisher = _STATUTS_NON_FINISHERS.get(statut.upper())
        if cle_non_finisher == "dnf":
            dnf += 1
        elif cle_non_finisher == "dns":
            dns += 1
        elif cle_non_finisher == "dsq":
            dsq += 1
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
            # Les variantes de libellé TCN (« TRI CLUB NANTAIS », « TCN »,
            # « Triathlon club nantais »… — verbatim du chronométreur) sont
            # fusionnées sous le libellé canonique dans « Top clubs » (#200).
            # Sans quoi le même club apparaissait sur deux à trois lignes selon
            # les saisies du speaker. `is_tcn` reste la définition unique — la
            # base garde le verbatim, seul l'agrégat d'affichage bascule.
            libelle = TCN_CANONICAL_NAME if is_tcn(club) else club.strip()
            clubs[libelle] += 1
        if is_tcn(club):
            tcn_count += 1

        for cle, valeur in (splits or {}).items():
            # Un `dict` plutôt qu'un `set` : l'ordre d'apparition fixe celui des
            # colonnes du tableau, et un `set` le rendrait arbitraire.
            if valeur:
                split_keys.setdefault(cle, None)

        seconde = to_seconds(total_time, strict=True)
        if seconde is not None and total_time != "00:00:00":
            secondes.append(seconde)

        ecarts.append(
            split_gap.gap(
                total_time,
                splits,
                event_type=course.event_type if course else None,
                is_relay=bool(course and course.is_relay),
            )
        )

    return {
        "total": len(lignes),
        "finishers": finishers,
        "non_finishers": dnf + dns + dsq,
        "dnf": dnf,
        "dns": dns,
        "dsq": dsq,
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
        # Une **mesure**, pas un verdict : la médiane sert de référence à l'écran,
        # qui applique ses propres seuils. Les régler après re-sondage ne touche
        # donc pas au contrat (#486).
        "split_gap_median": split_gap.median(ecarts),
    }
