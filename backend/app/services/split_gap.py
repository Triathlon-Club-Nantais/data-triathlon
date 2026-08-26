"""L'écart entre le temps total d'une ligne et la somme de ses temps intermédiaires.

Domicile **unique** de cette règle (#486). Le front en a besoin par ligne, le service de
synthèse en a besoin pour la médiane d'épreuve : l'implémenter des deux côtés rejouerait
#76, où trois listes divergentes du critère club ont fait compter tout Nantes comme TCN.
L'écran ne fait donc que comparer aux seuils d'affichage ce que ce module calcule.

Dans `services/`, à côté de `mapping` dont il dérive son gabarit de segments. Ses deux
consommateurs sont `stats_service` (la médiane d'épreuve) et `schemas/participation.py`
(le champ calculé d'une ligne) : les DTO relèvent de la couche API, donc les deux vont
dans le sens autorisé `api → services`.

Les seuils publiés ici viennent du sondage
`docs/superpowers/specs/2026-08-25-ecart-inters-total-sondage.md`, qui **prime** sur ce
module : le seuil de 2 % proposé par l'audit signalait 6,89 % du classement, dont 285
lignes d'une épreuve que le produit tient pour fiable. Les ajuster se fait là-bas, en
re-mesurant, pas ici.
"""
import re
import statistics

from app.services.mapping import _DEFAULT_SPLIT_KEYS, _SPLIT_KEYS_BY_SPORT, _sport_base

#: Segments attendus par sport — **dérivés** de `mapping._SPLIT_KEYS_BY_SPORT`, jamais
#: réécrits ici. Cette table est celle qui *produit* les clés de `Participation.splits` :
#: en tenir une copie, c'était garantir la divergence. Le premier jet de ce module en
#: avait une, et elle mentait déjà — `bike-run` y valait `bike/run` quand le gabarit
#: réel pose `segment1/bike/run`, de sorte que la somme ignorait un tiers du parcours et
#: fabriquait un écart systématique. Il y manquait aussi `swimrun`, `course-a-pied`,
#: `trail`, `cyclisme`, `swim-bike` et `raid-multisport`.
#:
#: `_sport_base` vient du même module : les bases multi-mots (`bike-run`,
#: `course-a-pied`) portent un tiret qui n'est pas un séparateur de taille, et
#: `event_type.split("-")` ferait tomber `bike-run-s` sur le gabarit triathlon.
SCHEMAS: dict[str, list[str]] = {
    sport: list(gabarit.values()) for sport, gabarit in _SPLIT_KEYS_BY_SPORT.items()
}

#: Le triathlon est le gabarit par défaut, comme dans `mapping.build_splits`.
_DEFAULT_SCHEMA: list[str] = list(_DEFAULT_SPLIT_KEYS.values())

#: Écart relatif à la médiane de l'épreuve au-delà duquel une ligne est signalée.
#: Mesuré : 0 ligne sur les 4 150 évaluables de la base de dev.
OUTLIER_RATIO = 0.05

#: Sous cet effectif de lignes évaluables, la médiane de l'épreuve n'a pas de sens —
#: la course 65 est neuf enfants dont les totaux tiennent en cinq minutes.
MIN_EVALUATED_ROWS = 10

#: Sans ce plancher, un petit dénominateur suffit à franchir le seuil relatif.
MIN_GAP_SECONDS = 60

#: Médiane d'épreuve au-delà de laquelle les inters publiés ne couvrent manifestement
#: pas tout le parcours. 1 épreuve sur 25 dans la base de dev.
EVENT_GAP_RATIO = 0.01

# `fullmatch`, et non le `search` de `app.scrapers.utils.to_seconds` : cette dernière
# rend 900 sur « 0-2:-15:00 » (elle n'ancre qu'à droite) et 3825 sur « 01:23:45.6 »,
# là où l'écran rejette les deux (`secondsFromHms`, garde posée par #472). Réutiliser
# `to_seconds` ferait donc évaluer ici des lignes que l'écran affiche « — ⚠ ».
_DURATION = re.compile(r"(?:(?P<hours>\d+):)?(?P<minutes>\d{1,2}):(?P<seconds>\d{2})")


def parse_duration(value: str | None) -> int | None:
    """Secondes d'un `HH:MM:SS` ou `MM:SS`, `None` si ce n'est pas une durée."""
    if not isinstance(value, str):
        return None
    match = _DURATION.fullmatch(value.strip())
    if not match:
        return None
    minutes = int(match["minutes"])
    seconds = int(match["seconds"])
    if minutes >= 60 or seconds >= 60:
        return None
    return int(match["hours"] or 0) * 3600 + minutes * 60 + seconds


def schema_for(event_type: str | None) -> list[str]:
    """Segments attendus pour ce sport, tels que `mapping.build_splits` les a posés."""
    return SCHEMAS.get(_sport_base(event_type or ""), _DEFAULT_SCHEMA)


def gap(
    total_time: str | None,
    splits: dict | None,
    *,
    event_type: str | None,
    is_relay: bool,
) -> float | None:
    """Écart relatif **signé** `(total − Σ inters) / total`, `None` si non évaluable.

    Le signe porte l'information : positif, le total couvre plus que la somme des inters,
    signature d'un segment que le chronométreur ne publie pas (81,7 % des cas mesurés) ;
    négatif, la somme dépasse le total, ce qui n'a pas d'explication bénigne.

    Les cinq conditions d'évaluabilité sont cumulatives — une seule qui manque, et le
    produit ne signale rien plutôt que de mesurer ce qu'il ne peut pas mesurer.

    Prend des colonnes plutôt qu'une `Participation` : la synthèse d'épreuve lit des
    tuples, jamais des modèles hydratés (#163), et la règle ne peut pas se dédoubler
    pour autant.
    """
    if is_relay or not splits:
        return None

    keys = schema_for(event_type)
    # Gabarit vide — `raid-multisport`, dont `mapping` dit qu'aucun découpage n'est
    # prévisible. Sans cette garde, `all(...)` sur une liste vide vaut `True`, la somme
    # vaut 0, et **chaque** ligne rend un écart de 100 % : la page annoncerait qu'il
    # « manque environ 100 % du temps total » dès le premier import d'un raid.
    if not keys:
        return None
    if not all(key in splits for key in keys):
        return None

    total = parse_duration(total_time)
    if not total:
        return None

    segments = [parse_duration(splits[key]) for key in keys]
    if any(segment is None for segment in segments):
        return None

    return (total - sum(segments)) / total


def ratio(participation) -> float | None:
    """`gap` pour une participation hydratée — le classement paginé, lui, en a une."""
    course = getattr(participation, "course", None)
    if course is None:
        return None
    return gap(
        participation.total_time,
        participation.splits,
        event_type=course.event_type,
        is_relay=course.is_relay,
    )


def median(ratios) -> float | None:
    """Médiane des écarts évaluables d'une épreuve — sa **référence**.

    C'est elle qui distingue « le chronométreur ne publie pas ce segment » (toutes les
    lignes s'écartent pareil) de « cette ligne est fausse » (elle s'écarte de ses
    voisines). Elle porte sur l'épreuve entière, donc hors de portée d'un écran qui n'en
    reçoit que vingt lignes.
    """
    evaluated = [value for value in ratios if value is not None]
    return statistics.median(evaluated) if evaluated else None


def is_outlier(
    value: float | None,
    *,
    median: float | None,
    evaluated_rows: int,
    total_seconds: int | None,
) -> bool:
    """Cette ligne s'écarte-t-elle de ses pairs au point d'être signalée ?

    Les deux gardes ne sont pas décoratives : sans l'effectif minimal, une épreuve de neuf
    enfants aux totaux de cinq minutes fait signaler deux lignes pour vingt secondes ;
    sans le plancher en secondes, un petit dénominateur suffit à franchir 5 %.
    """
    if value is None or median is None or evaluated_rows < MIN_EVALUATED_ROWS:
        return False
    ecart = abs(value - median)
    if ecart <= OUTLIER_RATIO:
        return False
    return total_seconds is not None and ecart * total_seconds > MIN_GAP_SECONDS
