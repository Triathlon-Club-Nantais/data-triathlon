"""Commande `grant-role` : attribue un rôle sans session. Zéro logique métier.

**La voie d'amorçage** (FR-027) : sur une installation neuve, aucun
administrateur n'existe et les ressources qui distribuent les rôles exigent
elles-mêmes un pouvoir. C'est aussi le seul rattrapage hors ligne si
l'installation se retrouve sans administrateur.

Deux contournements délibérés, et ils sont assumés :

- elle **n'applique pas** la non-amplification (FR-011) : elle s'exécute sur le
  serveur, sans session, il n'y a donc pas d'acteur dont comparer les pouvoirs.
  L'accès au serveur *est* le privilège ;
- elle **n'est pas soumise** à l'invariant du dernier administrateur : elle ne
  fait qu'accorder, jamais retirer, donc elle ne peut pas verrouiller.
"""
import logging

import typer

from app.core.database import session_scope
from app.repositories import role_repository, user_repository, user_role_repository

logger = logging.getLogger(__name__)

#: Convention Click / Typer, déjà employée par `--provider` inconnu dans
#: `rescrape-db` : `2` = erreur d'usage, et non panne.
USAGE = 2


def _fail(message: str) -> typer.Exit:
    typer.echo(message)
    return typer.Exit(USAGE)


def grant_role(
    email: str = typer.Option(..., "--email", help="Adresse de la personne."),
    role: str = typer.Option(
        ..., "--role", help="Slug du rôle : admin, validator, moderator…"
    ),
    organisation: str | None = typer.Option(
        None, "--organisation", help="Slug du club. Par défaut, le seul existant."
    ),
) -> None:
    """Attribue un rôle existant à un utilisateur existant.

    Ne crée **ni** utilisateur (FR-028) **ni** rôle : le premier naît d'une
    connexion, le second se compose depuis l'API. La CLI n'existe que pour le cas
    où l'API est inatteignable faute d'administrateur.
    """
    with session_scope() as db:
        club = (
            role_repository.find_organisation(db, organisation)
            if organisation
            else role_repository.default_organisation(db)
        )
        if club is None:
            raise _fail(
                f"Organisation « {organisation} » introuvable."
                if organisation
                else "Aucune organisation en base : appliquez les migrations "
                "(uv run alembic upgrade head)."
            )

        candidates = user_repository.find_by_email(db, email)
        if not candidates:
            raise _fail(
                f"Aucun utilisateur ne porte l'adresse « {email} ».\n"
                "Un utilisateur naît d'une **connexion** réussie, jamais d'une "
                "commande : demandez à la personne de se connecter une première "
                "fois. Si son adresse n'est pas encore autorisée : "
                f"« allow-email --email {email} »."
            )
        if len(candidates) > 1:
            # `users.email` n'est pas unique, délibérément (#114, FR-003) :
            # deux identités externes portant la même adresse donnent deux
            # utilisateurs. Trancher au hasard rouvrirait ce que ce choix ferme.
            lines = "\n".join(
                f"  id={user.id}  {user.display_name or '(sans nom)'}"
                f"  créé le {user.created_at:%Y-%m-%d}"
                for user in candidates
            )
            raise _fail(
                f"Plusieurs utilisateurs portent l'adresse « {email} » :\n{lines}\n"
                "Départagez-les par identifiant, via l'API, une fois un premier "
                "administrateur en place."
            )
        user = candidates[0]

        target = role_repository.find_in_scope(db, slug=role, organisation_id=club.id)
        if target is None:
            elsewhere = role_repository.list_by_slug(db, role)
            if elsewhere:
                owner = role_repository.get_organisation(
                    db, elsewhere[0].organisation_id
                )
                raise _fail(
                    f"Le rôle « {role} » est propre à l'organisation "
                    f"« {owner.name} » et n'est pas attribuable dans "
                    f"« {club.name} »."
                )
            known = ", ".join(r.slug for r in role_repository.list_all(db)) or "aucun"
            raise _fail(
                f"Le rôle « {role} » n'existe pas. Rôles existants : {known}."
            )

        _, created = user_role_repository.grant(
            db, user_id=user.id, role_id=target.id, organisation_id=club.id
        )
        if not created:
            typer.echo(
                f"Rien à faire : {user.display_name or user.email} (id={user.id}) "
                "porte déjà ce rôle."
            )
            return

        logger.info(
            "Role grant by cli: actor=cli target_user=%s role=%s organisation=%s",
            user.id,
            target.slug,
            club.slug,
        )
        typer.echo(
            f"Rôle « {target.name} » attribué à "
            f"{user.display_name or '(sans nom)'} (id={user.id}, {user.email}) "
            f"dans « {club.name} »."
        )
