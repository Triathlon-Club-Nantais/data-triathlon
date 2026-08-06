"""Modèle AdminActionLog — la trace des altérations manuelles de données (#117).

**`entity_id` ne porte aucune clé étrangère, et c'est l'invariant du modèle.**
Une trace doit survivre à ce qu'elle décrit (FR-014) : une FK vers `courses.id`
interdirait d'enregistrer une suppression d'épreuve, c'est-à-dire l'usage
principal du journal. `entity_id` peut donc pointer dans le vide — c'est voulu,
et le couple `(entity_type, entity_id)` est la seule clé de relecture.

`user_id`, lui, porte une FK : l'auteur ne disparaît pas. Sans `ondelete`, comme
partout dans le dépôt — `database.py` n'émet aucun `PRAGMA foreign_keys=ON`, la
contrainte serait inerte en SQLite (dev et tests) et active en PostgreSQL.

**Écriture seule** : ni mise à jour, ni suppression, ni route de lecture. Un
journal qu'on peut réécrire ne prouve rien.
"""
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.time import utcnow


class AdminActionLog(Base):
    __tablename__ = "admin_action_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    #: Le geste, en anglais et stable : il traverse la base (Principe I).
    action: Mapped[str] = mapped_column(String, index=True)
    entity_type: Mapped[str] = mapped_column(String)
    entity_id: Mapped[int] = mapped_column(Integer)
    #: Le contexte de relecture : avant/après, comptes, entités emportées (FR-013).
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
