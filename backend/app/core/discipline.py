"""
Disciplines fédérales triathlon, et les autres.

Un club de triathlon importe aussi des trails et des courses sur route de ses
membres : légitime à conserver, mais ces résultats gonflent des compteurs qu'on
lit comme des compteurs de triathlon (issue #76). D'où la partition.

**Liste d'exclusion, pas d'inclusion** : est fédéral tout ce qui n'est pas
explicitement listé ici. Une discipline future entre donc dans les compteurs par
défaut, comme le repli du classifieur retombe déjà sur `triathlon`
(`app/scrapers/classify.py`). Le contraire ferait disparaître des résultats sans
que personne ne s'en aperçoive.

Les slugs sont comparés **entiers** des deux côtés (Python et SQL), ce qui rend
les deux implémentations incapables de diverger.
"""

#: Slugs canoniques (cf. `classify.CANONICAL_TYPES`) hors fédération triathlon.
NON_FEDERAL_TYPES: frozenset[str] = frozenset({
    "trail",
    "cyclisme",
    "cyclisme-route",
    "cyclisme-clm",
    "course-a-pied",
    "course-a-pied-5k",
    "course-a-pied-10k",
    "course-a-pied-semi",
    "course-a-pied-marathon",
})


def is_federal(event_type: str | None) -> bool:
    """Vrai si `event_type` relève d'une discipline de la fédération triathlon."""
    return (event_type or "") not in NON_FEDERAL_TYPES


def federal_clause(column):
    """Clause SQLAlchemy : `column` (un `event_type`) est une discipline fédérale."""
    return column.notin_(sorted(NON_FEDERAL_TYPES))
