"""Corpus de libellés de club, partagé par les tests du prédicat.

Tiré des données de prod du 25/07/2026 (issue #76). C'est le **contrat** du
filtre club : il est passé à la fois dans `is_tcn()` (Python) et dans une requête
filtrée par `tcn_clause()` (SQL), et les deux doivent rendre le même verdict.

Ajouter un cas ici, c'est l'exiger des deux implémentations à la fois.
"""

#: (libellé brut, appartient au TCN)
CORPUS: list[tuple[str | None, bool]] = [
    # Vrais libellés du club, dans les casses réellement observées.
    ("TRIATHLON CLUB NANTAIS", True),
    ("TRI CLUB NANTAIS", True),
    ("Triathlon Club Nantais", True),
    ("TCN", True),
    # Bords et espaces internes : la normalisation les aplatit.
    ("  TRI CLUB NANTAIS  ", True),
    ("TRI  CLUB   NANTAIS", True),
    # Blancs non-ASCII : le HTML français en glisse (espace insécable, tabulation,
    # saut de ligne) et `\s`/`str.strip()` les couvrent côté Python — le miroir
    # SQL doit en faire autant.
    ("TRI CLUB NANTAIS", True),
    ("TRI\tCLUB NANTAIS", True),
    ("TRI CLUB NANTAIS\n", True),
    # Les faux positifs de #76 : des clubs nantais, mais pas le nôtre.
    ("ASSOCIATION SPORTIVE  MARATHONIENS NANTAIS", False),
    ("S/L STADE NANTAIS AC", False),
    ("RACING CLUB NANTAIS *", False),
    # Breizh Chrono met parfois la ville dans la colonne club.
    ("NANTES (44200)", False),
    ("LE LANDREAU (44430)", False),
    # L'égalité est stricte : un libellé qui contient le nôtre n'est pas le nôtre.
    ("TRIATHLON CLUB NANTAIS SUD", False),
    ("TCN ATHLETISME", False),
    # Absence d'information.
    ("", False),
    (None, False),
]

#: Sous-ensemble insérable en base (SQL ne voit jamais de `None` utile ici).
CORPUS_SQL: list[tuple[str, bool]] = [
    (libelle, attendu) for libelle, attendu in CORPUS if libelle
]
