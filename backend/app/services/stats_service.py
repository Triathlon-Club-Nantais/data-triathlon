"""Agrégations statistiques (club / tableau de bord / synthèse d'épreuve)."""
from collections import Counter

from sqlalchemy.orm import Session

from app.core import season as season_module
from app.core.club import TCN_CANONICAL_NAME, broad_club_key, normalize_club
from app.repositories import club_alias_repository, course_repository, participation_repository
from app.scrapers.base import STATUS_FINISHER
from app.scrapers.utils import to_seconds
from app.services import split_gap


def _bucket() -> dict:
    return {"victories": 0, "podiums": 0, "top10": 0}


def _accumulate(bucket: dict, rank: int | None) -> None:
    if rank is None or rank < 1:
        return
    if rank <= 1:
        bucket["victories"] += 1
    if rank <= 3:
        bucket["podiums"] += 1
    if rank <= 10:
        bucket["top10"] += 1


def _best_rank(ranks: list[int | None]) -> int | None:
    valid = [r for r in ranks if r is not None and r >= 1]
    return min(valid) if valid else None


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
    scratch, category, all_modes = _bucket(), _bucket(), _bucket()
    by_gender = {"women": _bucket(), "men": _bucket()}

    for rank_overall, rank_category_, rank_gender, gender in rows:
        _accumulate(scratch, rank_overall)
        _accumulate(category, rank_category_)
        _accumulate(all_modes, _best_rank([rank_overall, rank_gender, rank_category_]))

        if gender == "F":
            _accumulate(by_gender["women"], rank_gender)
        elif gender == "M":
            _accumulate(by_gender["men"], rank_gender)

    return {"scratch": scratch, "category": category, "all": all_modes, "gender": by_gender}


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
                "athlete_name": last_name or "",
                "athlete_firstname": first_name or "",
                "club": club or "",
                "event_name": event_name or "",
                "event_type": event_type or "",
                "event_date": event_date.isoformat() if event_date else None,
                "total_time": total_time or "",
                "scraped_at": created_at.isoformat() if created_at else None,
            }
            for id_, last_name, first_name, club, event_name, event_type, event_date, total_time, created_at
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
        "pending_count": int(r.pending_count or 0),
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

#: Largeurs de tranche possibles, de la plus fine à la plus large, et plafond
#: du nombre de tranches. La plus fine qui tient sous le plafond l'emporte :
#: 5 min pour une épreuve courte, plus large pour une longue distance (#1586).
_HISTOGRAM_BUCKET_SECS = (300, 600, 900, 1800, 3600)
_HISTOGRAM_MAX_BARS = 60

#: Limites d'affichage de la page, historiques.
_MAX_CATEGORIES = 8
_MAX_CLUBS = 9

#: Statut brut (majuscule) → clé de compteur dédiée (#331). `non_finishers`
#: reste leur somme, jamais recalculée séparément.
_NON_FINISHER_STATUSES = {"DNF": "dnf", "DNS": "dns", "DSQ": "dsq"}


def _most_frequent(counter: Counter[str], limit: int) -> list[tuple[str, int]]:
    """Les `limit` plus fréquents, à égalité départagés par le libellé.

    `Counter.most_common` départage par ordre d'insertion, donc par ordre de
    lecture en base : deux clubs à 23 participants pouvaient changer de place
    d'une consultation à l'autre. Le libellé rend ce classement déterministe.
    """
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]


def _histogram(seconds: list[int]) -> dict | None:
    if not seconds:
        return None
    low, high = min(seconds), max(seconds)
    bucket_sec = next(
        (b for b in _HISTOGRAM_BUCKET_SECS if high // b - low // b < _HISTOGRAM_MAX_BARS),
        _HISTOGRAM_BUCKET_SECS[-1],
    )
    first_bucket = low // bucket_sec
    bucket_count = min(high // bucket_sec - first_bucket + 1, _HISTOGRAM_MAX_BARS)
    bars = [0] * bucket_count
    for value in seconds:
        # Le plafond ne mord plus qu'au delà de 60 h d'écart : un temps aberrant
        # retombe alors dans la dernière tranche plutôt que d'être perdu.
        bars[min(value // bucket_sec - first_bucket, bucket_count - 1)] += 1
    return {
        "bars": bars,
        # Bord gauche de la première tranche : ancre l'axe des abscisses sur des
        # heures rondes côté affichage (#129).
        "start_sec": first_bucket * bucket_sec,
        "bucket_sec": bucket_sec,
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
    # Clé large -> libellés bruts vus sous cette clé, avec leur effectif. Sert à
    # fusionner l'affichage des variantes sans alias déclaré : casse et espaces
    # depuis #635 (`_club_filter_targets` les matche déjà au filtre), et depuis
    # #1110 accents, ponctuation et espaces internes (« Côte d'Émeraude »,
    # « Cote dEmeraude »). `broad_club_key` ne remplace pas `normalize_club`,
    # `_normalize_sql` étant compilée dans un index fonctionnel : le filtre la
    # résout en graphies présentes sur l'épreuve (#1127).
    variants_by_key: dict[str, Counter[str]] = {}
    split_keys: dict[str, None] = {}
    seconds: list[int] = []
    gaps: list[float | None] = []

    # L'épreuve, lue une fois : le sport et le caractère de relais commandent le
    # schéma de segments de l'écart, et ne varient pas d'une ligne à l'autre.
    course = course_repository.get(db, course_id)
    # Alias de club déclarés (#635) — chargés une fois, jamais par ligne : une
    # épreuve porte jusqu'à ~1800 participations (#163).
    alias_map = club_alias_repository.canonical_map(db)
    rows = participation_repository.summary_rows_for_course(db, course_id)
    for status, club, category, total_time, splits, gender, counts_for_tcn in rows:
        stripped_status = (status or "").strip()
        non_finisher_key = _NON_FINISHER_STATUSES.get(stripped_status.upper())
        if non_finisher_key == "dnf":
            dnf += 1
        elif non_finisher_key == "dns":
            dns += 1
        elif non_finisher_key == "dsq":
            dsq += 1
        elif stripped_status.lower() == STATUS_FINISHER:
            finishers += 1
        else:
            # Statut vide ou non reconnu : ni finisher ni abandon (#23).
            unknown += 1

        if gender == "F":
            female += 1
        elif gender == "M":
            male += 1

        # Un libellé sans lettre ni chiffre (« - », « --- ») est le remplissage
        # d'une catégorie inconnue, pas une catégorie (#1113).
        if category and any(c.isalnum() for c in category):
            categories[category.strip()] += 1
        if club and club.strip():
            # Les variantes de libellé d'un même club (« TRI CLUB NANTAIS »,
            # « TCN »… pour le TCN ; des alias déclarés pour tout autre club,
            # #635) sont fusionnées sous un libellé canonique dans « Top
            # clubs » (#200, #635). Sans quoi le même club apparaissait sur
            # plusieurs lignes selon les saisies du chronométreur. Le TCN
            # est la ligne qui compte pour le club (`counts_for_tcn`, #1206) : un
            # « TCN » de Narbonne reste sur sa propre ligne ; tout autre
            # club par `alias_map`, chargé une fois plus haut, avec repli sur
            # la forme normalisée (`variants_by_key`) pour rester
            # cohérent avec ce que `_club_filter_targets` matche déjà sans
            # alias déclaré. La base garde le verbatim — seul l'agrégat
            # d'affichage bascule.
            if counts_for_tcn:
                clubs[TCN_CANONICAL_NAME] += 1
            elif canonical := alias_map.get(normalize_club(club)):
                clubs[canonical] += 1
            elif key := broad_club_key(club):
                # Clé vide : « - » ou « -- », remplissage d'un club inconnu.
                variants_by_key.setdefault(key, Counter())[club.strip()] += 1
        if counts_for_tcn:
            tcn_count += 1

        for key, value in (splits or {}).items():
            # Un `dict` plutôt qu'un `set` : l'ordre d'apparition départage les
            # clés hors gabarit (#880), et un `set` le rendrait arbitraire.
            if value:
                split_keys.setdefault(key, None)

        total_sec = to_seconds(total_time, strict=True)
        if total_sec is not None and total_time != "00:00:00":
            seconds.append(total_sec)

        gaps.append(
            split_gap.gap(
                total_time,
                splits,
                event_type=course.event_type if course else None,
                is_relay=bool(course and course.is_relay),
            )
        )

    # Le libellé affiché d'un groupe fusionné est sa variante la plus fréquente,
    # la première vue à égalité (#1110).
    for variants in variants_by_key.values():
        label = max(variants.items(), key=lambda item: item[1])[0]
        clubs[label] += sum(variants.values())

    return {
        "total": len(rows),
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
            {"name": name, "count": count}
            for name, count in _most_frequent(categories, _MAX_CATEGORIES)
        ],
        # Dénominateur des pourcentages affichés : **toutes** les catégories
        # renseignées, pas seulement les 8 rendues. Les rapporter à la somme du
        # top 8 gonflerait chaque barre — 1,28× sur une épreuve à 20 catégories
        # dont le top 8 ne couvre que 78 % des participants — et les ferait
        # sommer à 100 %, ce qu'elles ne font pas.
        "categories_total": sum(categories.values()),
        "clubs": [
            {"name": name, "count": count, "is_tcn": name == TCN_CANONICAL_NAME}
            for name, count in _most_frequent(clubs, _MAX_CLUBS)
        ],
        # Dénominateur du « et N autres clubs » (#486). **Pas homogène** à
        # `categories_total` juste au-dessus, qui compte des participants : ici
        # ce sont des clubs. Les deux disent ce que la carte omet, dans deux
        # unités différentes.
        "clubs_total": len(clubs),
        # Une épreuve à durée fixe classe aux tours : ses temps ne se comparent pas (#993).
        "histogram": None if course is not None and course.ranked_by_laps else _histogram(seconds),
        "split_keys": split_gap.chronological(split_keys),
        # Une **mesure**, pas un verdict : la médiane sert de référence à l'écran,
        # qui applique ses propres seuils. Les régler après re-sondage ne touche
        # donc pas au contrat (#486).
        "split_gap_median": split_gap.median(gaps),
        "split_gap_rows": sum(1 for gap in gaps if gap is not None),
    }
