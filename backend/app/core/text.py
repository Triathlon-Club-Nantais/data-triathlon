"""Normalisation de texte pour la recherche.

Vit dans son propre module parce qu'il est appelé des deux côtés de la barrière :
`core/database.py` l'enregistre comme fonction SQLite, et le repository s'en sert
pour déaccentuer le terme cherché avant de le passer à la requête. L'inscrire
dans l'un des deux créerait une dépendance en travers des couches.
"""
import unicodedata


def deaccent(value: str | None) -> str | None:
    """Retire les signes diacritiques : `LEMÉE` → `LEMEE`.

    Ni SQLite ni PostgreSQL ne le font nativement — mesuré, `lower('LEMÉE')`
    rend `lemée` et non `lemee` sur les deux (#163). Côté PostgreSQL c'est
    l'extension `unaccent` qui joue ce rôle ; cette fonction est son équivalent
    SQLite, enregistrée sous le même nom pour que la requête soit unique.

    Rend `None` sur `None` : SQLite passe les `NULL` aux fonctions applicatives,
    et une chaîne les masquerait.

    **Une divergence subsiste avec l'extension PostgreSQL**, à connaître : elle
    développe les ligatures (`œ` → `oe`, `ß` → `ss`), la décomposition NFD non.
    Donc `q="lecoeur"` trouve « LECŒUR » en production et pas en développement.
    Faible portée sur un fichier de noms français, mais c'est bien le genre
    d'écart dev/prod que ce module est censé fermer — à traiter le jour où une
    recherche manquée le remonte, pas avant.
    """
    if value is None:
        return None
    decompose = unicodedata.normalize("NFD", value)
    return "".join(c for c in decompose if not unicodedata.combining(c))
