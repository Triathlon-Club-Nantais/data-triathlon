"""
Appartenance au Triathlon Club Nantais — **définition unique**.

Le prédicat a longtemps existé en trois exemplaires divergents (ici, dans le
front, dans le scraper Breizh Chrono), le plus permissif faisant autorité sur les
compteurs : tout libellé contenant « nantais » était compté comme TCN, ce qui
ramassait les clubs d'athlétisme nantais (issue #76). Il n'y a plus qu'une
définition, et elle vit ici.

Le match se fait à l'**égalité** sur une forme normalisée, jamais en
sous-chaîne : « RACING CLUB NANTAIS » est un club nantais, pas le nôtre.

**La règle est ici ; la liste des libellés vit en base** et s'édite depuis le
panel admin (#95). `core/counter_scope.py` en porte l'image en mémoire, et c'est
la seule source que `is_tcn` et `tcn_clause` lisent — ce qui étend leur accord à
toute configuration, pas seulement à celle livrée.

**Ce qui devient configurable est l'ensemble des libellés, jamais la
normalisation.** La distinction n'est pas théorique : `_normalise_sql` est
compilée dans un index fonctionnel (cf. `CLUB_NORMALIZED_INDEX_EXPRESSION` en
bas de ce fichier), et la toucher sans migration de reconstruction périme cet
index en silence. Ajouter un libellé ne change pas l'expression indexée ;
changer la façon de comparer, si.
"""
import re

from sqlalchemy import column, func

from app.core import counter_scope

#: Libellé canonique affiché quand on parle du club — utilisé côté serveur pour
#: fusionner les variantes scrapées dans « Top clubs » (issue #200). Le front
#: garde sa propre constante pour ne pas dépendre d'un round-trip API sur les
#: labels statiques (aria-label, meta, filtre) : deux définitions, même valeur.
TCN_CANONICAL_NAME = "Triathlon Club Nantais"

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
    """Vrai si `club` désigne le Triathlon Club Nantais.

    Déclarer une variante d'orthographe est le geste prévu, et il se fait depuis
    le panel admin — `python -m app.cli club-labels` sert à repérer celles qui
    manquent.
    """
    return normalize_club(club) in counter_scope.tcn_club_labels()


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
    return _normalise_sql(column).in_(sorted(counter_scope.tcn_club_labels()))


#: Expression SQL de `_normalise_sql`, compilée en littéral DDL portable
#: SQLite/Postgres (issue #351) — `replace`/`lower`/`trim` compilent à
#: l'identique sur les deux moteurs, aucune branche `dialect.name` n'est donc
#: nécessaire ici, à la différence des extensions Postgres (`pg_trgm`,
#: `unaccent`). Source unique consommée par `Participation.__table_args__`
#: **et** par la migration qui pose l'index fonctionnel : un seul texte, pas
#: deux copies qui pourraient diverger silencieusement de `_normalise_sql`.
#: Le nom de colonne générique `"club"` convient à `Participation.club`, seule
#: colonne indexée par ce ticket (cf. issue #351, hors périmètre : `Athlete.club`).
#:
#: **Modifier `_normalise_sql` sans migration de reconstruction périme
#: silencieusement l'index existant.** L'index fonctionnel `ix_participations_
#: club_normalized` (migration `e9cdbf3a4866`) fige, à la construction, le texte
#: SQL compilé *au moment où cette migration a tourné* — dans le catalogue de la
#: base, pas dans ce fichier. Un environnement déjà migré qui voit `_normalise_sql`
#: changer garde l'**ancienne** expression indexée : les lectures via
#: `tcn_clause` restent correctes (elles recompilent la nouvelle expression à
#: chaque requête), mais l'index ne les sert plus — retour silencieux au
#: balayage complet que #351 corrigeait, sans erreur ni avertissement. Seul un
#: environnement reconstruit de zéro (`create_all`, ou `alembic upgrade head`
#: depuis une base vierge) obtient la nouvelle expression. Toute évolution de
#: `_normalise_sql` doit donc s'accompagner d'une nouvelle migration qui
#: `drop_index` puis `create_index` avec le texte à jour.
CLUB_NORMALIZED_INDEX_EXPRESSION: str = str(
    _normalise_sql(column("club")).compile(compile_kwargs={"literal_binds": True})
)
