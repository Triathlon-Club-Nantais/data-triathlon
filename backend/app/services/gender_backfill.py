"""Rattrapage du sexe vide des fiches existantes (#1201).

#964 remplit le sexe à l'import quand la source le publie, mais 8 995 fiches
sur 115 268 restaient vides en production le 06/10 : importées avant, ou par une
source qui ne le publie pas. Le sexe se lit, pour chaque résultat de la fiche,
dans la ligne source (`raw_data`) quand elle le porte, sinon dans la catégorie
quand elle l'encode sans ambiguïté (`utils.gender_from_category`, calibré sur
RaceResult : `SEF`, `V1M`). Une fiche n'est remplie que si tous ses indices
s'accordent ; un conflit (homonymes fusionnés, #1209) la laisse vide.
"""
from dataclasses import dataclass
from itertools import groupby

from sqlalchemy.orm import Session

from app.core.gender import normalize_gender
from app.repositories import athlete_repository
from app.scrapers.utils import gender_from_category

#: Clés de `raw_data` où des sources publient le sexe (Sport Innovation `sex`…).
_RAW_GENDER_KEYS = ("sex", "sexe", "gender", "genre")


@dataclass(frozen=True)
class GenderFill:
    athlete_id: int
    gender: str


def _evidence(category: str | None, raw_data: dict | None) -> str:
    if isinstance(raw_data, dict):
        for key in _RAW_GENDER_KEYS:
            if gender := normalize_gender(str(raw_data.get(key) or "")):
                return gender
    return gender_from_category(category or "")


def plan(db: Session) -> list[GenderFill]:
    """Les fiches sans sexe dont tous les résultats désignent le même."""
    fills = []
    rows = athlete_repository.genderless_evidence(db)
    for athlete_id, group in groupby(rows, key=lambda row: row[0]):
        genders = {gender for _id, category, raw in group if (gender := _evidence(category, raw))}
        if len(genders) == 1:
            fills.append(GenderFill(athlete_id, genders.pop()))
    return fills


def apply(db: Session) -> list[GenderFill]:
    """Écrit le plan et le rend."""
    fills = plan(db)
    athlete_repository.set_genders(db, {fill.athlete_id: fill.gender for fill in fills})
    db.commit()
    return fills
