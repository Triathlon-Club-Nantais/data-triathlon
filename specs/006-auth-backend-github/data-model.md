# Data Model — Auth backend (#114)

Une seule nouvelle entité (`User`) et **aucune** modification des entités
existantes. La FK vers `Athlete` est portée côté `users`, en `nullable=True`,
`ON DELETE SET NULL`.

## Entité `User`

**Table** : `users`

**Rôle métier** : fiche applicative d'un contributeur du back-office admin.
Créée à la première connexion réussie via GitHub OAuth, retrouvée par
`github_id` à chaque connexion suivante.

### Colonnes

| Colonne | Type | Contraintes | Description |
|---|---|---|---|
| `id` | `Integer` | `PK`, auto-incrément | Identifiant applicatif. Porté par le cookie de session. |
| `github_id` | `String` | `NOT NULL`, `UNIQUE`, index | Identifiant numérique GitHub de l'utilisateur (stocké en `String` pour éviter le débordement 32 bits ; cf. research §2). Clé de dédoublonnage. |
| `github_login` | `String` | `NOT NULL` | Login GitHub (`octocat`). Peut évoluer côté GitHub — mis à jour au callback si nécessaire. |
| `email` | `String` | `NOT NULL`, index (non-unique) | Email GitHub vérifié récupéré au callback. Non-unique par choix (cf. FR-010 : deux `github_id` distincts peuvent partager un email). |
| `is_active` | `Boolean` | `NOT NULL`, `default=True` | Désactivation applicative sans suppression. Sur #114 : toujours `True`. #115 pourra le mettre à `False`. |
| `created_at` | `DateTime` | `NOT NULL`, `default=utcnow` | Horodate de création de la fiche. |
| `athlete_id` | `Integer` | `FK(athletes.id) ON DELETE SET NULL`, `nullable=True` | Rapprochement optionnel vers un membre du TCN. Vide sur #114 (aucun mécanisme de rapprochement), exploité par les sous-issues #117/#119. |

### Contraintes et index

- `PRIMARY KEY (id)`
- `UNIQUE (github_id)` — nommée `uq_user_github_id`
- `INDEX (email)` — nommé `ix_user_email` (non-unique, aide les recherches futures)
- `FOREIGN KEY (athlete_id) REFERENCES athletes(id) ON DELETE SET NULL` — nommée `fk_user_athlete`

### Règles de validation métier

- `github_id` obligatoire, chaîne non vide. Toujours renseigné à la création par
  le callback GitHub (jamais saisi manuellement).
- `github_login` obligatoire, chaîne non vide. Mise à jour au callback si la
  fiche existante avait un login différent.
- `email` obligatoire, chaîne non vide. Provenance : email `verified=true` de
  l'API GitHub (`/user` en premier lieu, `/user/emails` si `null`). Refus de
  création si aucun email vérifié disponible (cf. FR-005).
- `athlete_id` restrictions : aucune sur ce ticket. #117 gardera la
  responsabilité de vérifier l'existence de l'athlète cible.

### État & transitions

`is_active` est le seul état applicatif :

- Création → `is_active=True`.
- Désactivation (hors périmètre #114, mais colonne prête) : passage à `False`.
  La spec ne traite pas ce cas ; il est prévu pour #115/#117.

Aucune transition n'existe sur `email` / `github_login` : ces champs sont mis
à jour en place à chaque callback si GitHub a renvoyé une valeur différente.

## Modèle SQLAlchemy

Un seul module à créer : `backend/app/models/user.py`.

```python
"""Modèle User — fiche applicative d'un contributeur du back-office admin."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.time import utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    github_id: Mapped[str] = mapped_column(
        String, nullable=False, unique=True, index=True
    )
    github_login: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )
    athlete_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("athletes.id", ondelete="SET NULL"),
        nullable=True,
    )

    athlete: Mapped["Athlete | None"] = relationship(  # noqa: F821
        "Athlete", lazy="joined", passive_deletes=True
    )
```

`backend/app/models/__init__.py` — enregistrement :
```python
from app.models.user import User
__all__ = ["Athlete", "Course", "Participation", "PendingProvider", "User"]
```

## Migration Alembic

Une révision unique, dépendant de la dernière révision existante
(`c3d4e5f6a7b8_course_quality_index`). Générée par
`uv run alembic revision --autogenerate -m "add users table"` puis **relue** :

- vérifier que **seule** la table `users` est créée ;
- vérifier qu'**aucune** table existante n'est modifiée (sécurité FR-018) ;
- vérifier que la FK est bien `ON DELETE SET NULL` (Alembic autogen ne le
  détecte pas toujours — cf. `_render_on_delete` du template) ;
- `downgrade()` doit contenir `op.drop_table("users")` et rien d'autre.

## Schéma Pydantic (DTO)

Un seul DTO de sortie sur ce ticket, exposé par `GET /api/v1/auth/me` :

```python
# backend/app/schemas/user.py
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    github_login: str
    created_at: datetime
```

`github_id` **n'est pas exposé** : c'est un identifiant technique, sans usage
côté frontend. Le principe I recommande de ne pas exposer d'identifiant
technique inutile. `is_active` non plus (redondant avec « l'endpoint répond
200 »). `athlete_id` sera ajouté par #117 quand le rapprochement sera exploité.

## Aucune donnée à migrer

L'installation initiale de la table est vide (`users` n'existait pas). Aucune
opération de backfill à prévoir. Le seed de dev (`scripts/reset_db.py`)
n'ajoute **pas** d'utilisateur — l'auth ne servant à rien avant #115, il n'y a
pas de scénario où un dev en aurait besoin.
