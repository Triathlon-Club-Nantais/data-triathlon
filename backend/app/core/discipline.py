"""
Disciplines fédérales triathlon, et les autres.

Un club de triathlon importe aussi des trails et des courses sur route de ses
membres : légitime à conserver, mais ces résultats gonflent des compteurs qu'on
lit comme des compteurs de triathlon (issue #76). D'où la partition.

**Liste d'exclusion, pas d'inclusion** : est fédéral tout ce qui n'est pas
explicitement exclu. Une discipline future entre donc dans les compteurs par
défaut, comme le repli du classifieur retombe déjà sur `triathlon`
(`app/scrapers/classify.py`). Le contraire ferait disparaître des résultats sans
que personne ne s'en aperçoive. La règle est ici ; **la liste, elle, vit en base
et s'édite depuis le panel admin** (#95) — `core/counter_scope.py` en porte
l'image en mémoire, et c'est la seule source que ce module lit.
"""
from app.core import counter_scope


def federal_clause(column):
    """Clause SQLAlchemy : `column` (un `event_type`) est une discipline fédérale."""
    return column.notin_(sorted(counter_scope.non_federal_disciplines()))
