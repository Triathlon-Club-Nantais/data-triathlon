"""Validation des saisies CLI : rejeter une entrée invalide avant tout travail.

De la validation d'entrée utilisateur, pas de la logique métier — sa place est
donc ici, en couche CLI, et nulle part ailleurs (une seule validation, partagée
par les deux commandes).
"""
import typer

from app.scrapers import registry


def valider_provider(value: str | None) -> str | None:
    """Callback Typer : refuse un nom de provider inconnu.

    `--provider kliego` (faute de frappe) était comparé tel quel aux providers
    réels : le filtre ne retenait rien, la commande affichait « Courses ciblées :
    0 » et sortait en code 0. L'opérateur croyait sa base à jour alors que rien
    n'avait été fait. On échoue désormais immédiatement, en listant les valeurs
    acceptées — corrigeable sans lire le code.

    Non renseigné (`None`) reste valide : c'est le défaut « tous les providers ».

    Rejeter ici plutôt qu'en service : `typer.BadParameter` donne gratuitement le
    bon contrat — message + usage sur **stderr** (stdout, seul flux parsable,
    n'est pas pollué), code de sortie non nul, et arrêt **avant** l'ouverture de
    la Session ou le téléchargement du CSV. Les services resteraient sinon à
    inventer une exception et un code de sortie, alors que la CLI est leur unique
    appelant.
    """
    if value is None:
        return None
    connus = registry.provider_names()
    if value not in connus:
        raise typer.BadParameter(
            f"provider inconnu : « {value} ». "
            f"Valeurs acceptées : {', '.join(connus)}."
        )
    return value


def valider_max_concurrent_hosts(value: int) -> int:
    """Callback Typer : refuse un plafond de concurrence non strictement positif.

    `0` ou une valeur négative ne correspondent à aucun degré de parallélisme
    sensé (`ThreadPoolExecutor` lève sur `max_workers <= 0`) — autant le dire
    avant tout travail plutôt que de laisser l'exception interne remonter.
    """
    if value <= 0:
        raise typer.BadParameter(
            f"le plafond de concurrence doit être un entier strictement positif, "
            f"reçu : {value}."
        )
    return value
