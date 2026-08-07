"""Modèle AllowedEmail — qui a le droit d'ouvrir une session (#170)."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class AllowedEmail(Base):
    """Une adresse autorisée à ouvrir une session, éditable sans redéploiement.

    Remplace `AUTH_ALLOWED_EMAILS`, dont la lecture par un `Settings` en
    `lru_cache` faisait de l'ajout d'un contributeur un redéploiement.

    **L'adresse est rangée normalisée** — minuscules, espaces de bordure retirés.
    C'est ce qui rend le `UNIQUE` suffisant et la comparaison de connexion
    triviale ; sans quoi il faudrait un index fonctionnel `lower(email)` côté
    PostgreSQL, et deux graphies de la même adresse cohabiteraient comme deux
    entrées.

    **Cette table autorise, elle n'identifie pas.** Aucune colonne ne désigne le
    titulaire et aucune ne le désignera : une identité externe inconnue crée
    **toujours** un nouvel utilisateur (#114, FR-003), et apparier sur l'adresse
    rouvrirait la prise de contrôle par pré-inscription.
    `created_by_user_id` nomme celui qui **accorde**, jamais celui qui reçoit.

    Elle n'est pas non plus rattachée à une organisation : elle répond « cette
    adresse peut-elle ouvrir une session ? », pas « dans quel club ? » — c'est le
    rôle qui porte l'organisation (#115). Une liste par club supposerait de
    savoir à quel club rattacher quelqu'un *avant* qu'il existe.
    """

    __tablename__ = "allowed_emails"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # Nullable, et le restera : ni la CLI d'amorçage ni la reprise depuis
    # l'environnement n'ont d'acteur à nommer.
    #
    # **Sans `ondelete`**, comme les trois tables de #114 : `database.py` n'émet
    # aucun `PRAGMA foreign_keys=ON`, la contrainte serait inerte en SQLite et
    # active en PostgreSQL. Surtout, supprimer l'utilisateur qui a inscrit une
    # adresse ne doit **jamais** retirer l'adresse — ce serait une révocation
    # d'accès par effet de bord.
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    # Le rôle posé à la **naissance** du compte (#239), et rien de plus.
    #
    # Il ne contredit pas « cette table autorise, elle n'identifie pas » : il ne
    # désigne toujours aucun titulaire, il dit avec quoi celui qui viendra
    # commencera. Sans lui, le geste d'administration était coupé en deux par un
    # événement que l'administrateur ne contrôle pas — la première connexion.
    #
    # **Sans `ondelete`**, comme `created_by_user_id` et pour la même raison : la
    # contrainte serait inerte en SQLite et active en PostgreSQL. C'est
    # `authorization.delete_role` qui garde le cas, par un 409 qui nomme les
    # adresses concernées — comme il le fait déjà pour les porteurs.
    role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id"), nullable=True)

    role: Mapped["Role | None"] = relationship()  # noqa: F821

    # Sens unique : aucune collection n'est ajoutée sur `User`. L'écran affiche
    # « ajoutée le … par … », donc quelque chose la lit — c'est le critère que
    # `User.athlete_id` pose déjà pour rester colonne seule faute de lecteur.
    created_by: Mapped["User | None"] = relationship()  # noqa: F821
