"""État de validation d'un résultat déclaré manuellement (#270).

Sur le patron de `core/club.py` (`is_tcn`/`tcn_clause`) et `core/discipline.py`
(`is_federal`/`federal_clause`) : un prédicat Python et une clause SQL qui
partagent la même règle, pour que les deux implémentations ne puissent pas
diverger — c'est précisément la garantie que l'issue #76 a manquée la première
fois avec la portée club.

Un résultat en attente de validation n'entre dans **aucun** agrégat public
(statistiques, podiums, classements, page résultats, page épreuves, carte) ;
sa seule surface d'affichage est la fiche de son athlète (FR-019, FR-021).
"""


def is_pending(participation) -> bool:
    """Vrai si ce résultat n'est pas encore vérifié par un bénévole."""
    return bool(participation.is_pending_validation)


def validated_clause(column):
    """Clause SQLAlchemy : `column` (un `Participation.is_pending_validation`)
    désigne un résultat déjà vérifié.

    Nommée par son sens positif — ce qu'un agrégat public doit garder — plutôt
    que par sa négation.
    """
    return column.is_(False)


def is_actionable_pending(participation) -> bool:
    """Vrai si ce résultat est encore en attente ET n'a pas été rejeté (#437).

    Garde des routes bénévoles qui doivent redevenir inaccessibles une fois
    l'entrée écartée — `reassign`, `validate`, la future correction de champs
    — sans quoi valider une entrée rejetée la ferait entrer dans tous les
    agrégats publics malgré le rejet.
    """
    return bool(participation.is_pending_validation) and not bool(participation.is_rejected)
