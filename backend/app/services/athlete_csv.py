"""Mise en forme CSV des résultats d'un athlète (#1375), pour Excel en français.

UTF-8 avec BOM, séparateur `;` et virgule décimale : sans le BOM, Excel lit les
accents en Windows-1252 ; avec `,`, il range tout dans la première colonne.
"""
import csv
import io
import re
from datetime import date

from app.core.text import deaccent
from app.models.athlete import Athlete
from app.models.participation import Participation

HEADER = [
    "Date", "Épreuve", "Discipline", "Distance (km)", "Statut", "Temps",
    "Rang général", "Classés", "Rang catégorie", "Catégorie", "Rang sexe",
    "Équipe", "Validation",
]


SPLIT_LABELS = {
    "swim": "Natation", "bike": "Vélo", "run": "Course", "t1": "T1", "t2": "T2",
    "course1": "Course 1", "course2": "Course 2",
}
#: Excel exécute une cellule qui commence par l'un de ces caractères comme une
#: formule. `POST /participations` étant ouvert sans session, nom d'épreuve,
#: d'équipe ou de segment sont libres.
_FORMULA_START = ("=", "+", "@", "\t", "\r")
_NUMERIC_TAIL = re.compile(r"[\d:.,\s-]*")


def _text(value: str) -> str:
    risky = value.startswith(_FORMULA_START) or (
        value.startswith("-") and not _NUMERIC_TAIL.fullmatch(value)
    )
    return f"'{value}" if risky else value


def filename(athlete: Athlete) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", deaccent(f"{athlete.prenom or ''} {athlete.nom}").lower()).strip("-")
    return f"resultats-{slug or 'athlete'}.csv"


def _validation(participation: Participation) -> str:
    if not participation.is_pending_validation:
        return "Validé"
    return "Refusé" if participation.is_rejected else "En attente"


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:g}".replace(".", ",")
    if isinstance(value, str):
        return _text(value)
    return str(value)


def render(participations: list[Participation], finishers: dict[tuple[int, bool], int]) -> str:
    """`finishers` : classés par `(course_id, is_relay)`, comme `course_finishers` de la fiche."""
    rows = sorted(participations, key=lambda p: p.course.event_date or date.min, reverse=True)
    split_keys = list(dict.fromkeys(key for p in rows for key in (p.splits or {})))
    out = io.StringIO()
    out.write("﻿")
    writer = csv.writer(out, delimiter=";", lineterminator="\r\n")
    # Préfixe « Segment » : un libellé libre (« Temps ») ne double pas une colonne fixe.
    writer.writerow(HEADER + [f"Segment {SPLIT_LABELS.get(key, key)}" for key in split_keys])
    for p in rows:
        # Comme l'écran : un résultat non validé n'a pas encore de rang.
        ranked = not p.is_pending_validation
        writer.writerow([_cell(v) for v in (
            p.course.event_date, p.course.name, p.course.event_type, p.course.distance_km,
            p.status, p.total_time,
            p.rank_overall if ranked else None,
            finishers.get((p.course_id, bool(p.is_relay))),
            p.rank_category if ranked else None,
            p.category,
            p.rank_gender if ranked else None,
            p.team_name, _validation(p),
            *((p.splits or {}).get(key) for key in split_keys),
        )])
    return out.getvalue()
