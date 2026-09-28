"""État de validation d'un résultat déclaré manuellement (#270).

Le code applicatif filtre en SQL (`validated_clause`) ; seules les routes
bénévoles testent une ligne chargée (`is_actionable_pending`). Le prédicat
Python `is_pending`, que seuls les tests appelaient, a été supprimé (#1048).

Un résultat en attente de validation n'entre dans **aucun** agrégat public
(statistiques, podiums, classements, page résultats, page épreuves, carte) ;
sa seule surface d'affichage est la fiche de son athlète (FR-019, FR-021).
"""


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
