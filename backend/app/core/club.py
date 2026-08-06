"""
Appartenance au Triathlon Club Nantais — **définition unique**.

Le prédicat a longtemps existé en trois exemplaires divergents (ici, dans le
front, dans le scraper Breizh Chrono), le plus permissif faisant autorité sur les
compteurs : tout libellé contenant « nantais » était compté comme TCN, ce qui
ramassait les clubs d'athlétisme nantais (issue #76). Il n'y a plus qu'une
définition, et elle vit ici.

Le match se fait à l'**égalité** sur une forme normalisée, jamais en
sous-chaîne : « RACING CLUB NANTAIS » est un club nantais, pas le nôtre.
"""
import re

from sqlalchemy import func

#: Libellé canonique affiché quand on parle du club — utilisé côté serveur pour
#: fusionner les variantes scrapées dans « Top clubs » (issue #200). Le front
#: garde sa propre constante pour ne pas dépendre d'un round-trip API sur les
#: labels statiques (aria-label, meta, filtre) : deux définitions, même valeur.
TCN_CANONICAL_NAME = "Triathlon Club Nantais"

#: Libellés du club, sous leur forme normalisée (cf. `normalize_club`).
#: Ajouter une variante ici est le geste prévu — `python -m app.cli club-labels`
#: sert justement à repérer celles qui manquent.
TCN_CLUB_LABELS: frozenset[str] = frozenset({
    "triathlon club nantais",
    "tri club nantais",
    "tcn",
})

#: Valeur du paramètre d'API `scope` restreignant une réponse aux membres du club.
SCOPE_CLUB = "club"

_ESPACES = re.compile(r"\s+")


def normalize_club(club: str | None) -> str:
    """Forme comparable d'un libellé : minuscules, bords et espaces internes aplatis.

    Miroir Python de `_normalise_sql`. Les deux doivent rendre le même verdict —
    c'est ce que verrouille `tests/test_repositories/test_club_filter.py`.
    """
    return _ESPACES.sub(" ", (club or "").strip()).lower()


def is_tcn(club: str | None) -> bool:
    """Vrai si `club` désigne le Triathlon Club Nantais."""
    return normalize_club(club) in TCN_CLUB_LABELS


def is_club_scope(scope: str | None) -> bool:
    """Vrai si le paramètre d'API `scope` demande la portée club."""
    return scope == SCOPE_CLUB


_BLANCS_SQL = ("\t", "\n", "\r", "\xa0")


def _normalise_sql(column):
    """Miroir SQL de `normalize_club`, portable SQLite (dev) et Postgres (prod).

    `\\s` et `str.strip()` couvrent, côté Python, la tabulation, les sauts de
    ligne et l'espace insécable — le HTML français en glisse via
    `get_text(strip=True)`. `trim`/`replace` SQL ne voient que l'espace 0x20 :
    ces blancs non-ASCII sont donc ramenés à l'espace ordinaire **avant** le
    `trim`, sans quoi le miroir diverge du Python (issue #76 inversée : un
    libellé compté TCN en Python mais exclu du filtre SQL).

    Trois `replace` imbriqués aplatissent ensuite jusqu'à huit espaces
    consécutifs. Au delà, le libellé sort du filtre : le pire cas est un
    oubli, jamais un faux positif — et `club-labels` le rendra visible.
    """
    expr = column
    for blanc in _BLANCS_SQL:
        expr = func.replace(expr, blanc, " ")
    expr = func.lower(func.trim(expr))
    for _ in range(3):
        expr = func.replace(expr, "  ", " ")
    return expr


def tcn_clause(column):
    """Clause SQLAlchemy : `column` porte un libellé du club.

    `column` est passée en paramètre pour couvrir aussi bien `Participation.club`
    (le club inscrit sur la ligne de résultat) que `Athlete.club`.
    """
    return _normalise_sql(column).in_(sorted(TCN_CLUB_LABELS))
