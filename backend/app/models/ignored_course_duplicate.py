"""Modèle IgnoredCourseDuplicate — une paire de doublons suspects écartée (#754).

**L'existence de la ligne porte la décision**, patron de `SeasonValidation` :
ignorer crée la ligne. Il n'y a pas de retour dans ce ticket — #754 laisse
« revenir sur une paire ignorée par erreur » hors périmètre, à évaluer
séparément si le besoin se confirme.

`course_id_low`/`course_id_high` normalisent la paire non ordonnée (le plus
petit id en premier) : la route `POST /admin/courses/duplicates/ignore`
accepte les deux ids dans n'importe quel ordre — rien ne garantit que
l'écran, ou un futur appelant direct de l'API, envoie toujours le même côté de
la paire en premier —, donc filtrer sur `(a, b)` sans normaliser manquerait la
paire présentée dans l'autre sens.

**Pas d'`ondelete` vers `courses.id`, ni de relation `cascade` sur `Course`**,
contrairement à `CourseSource` (`Course.sources`, `delete-orphan`) : c'est
`course_repository.delete`/`.delete_all` qui appellent explicitement
`ignored_course_duplicate_repository.delete_for_course`/`.delete_all` **avant**
de supprimer l'épreuve — sans quoi une ligne survivrait à la course qu'elle
référence, invisible en SQLite (`database.py` n'émet aucun
`PRAGMA foreign_keys=ON`) mais un `ForeignKeyViolation` en PostgreSQL.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.time import utcnow


class IgnoredCourseDuplicate(Base):
    __tablename__ = "ignored_course_duplicates"
    __table_args__ = (
        UniqueConstraint(
            "course_id_low", "course_id_high", name="uq_ignored_course_duplicate_pair"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id_low: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    course_id_high: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    ignored_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    ignored_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # Pas de relation `ignored_by`, contrairement à `AdminActionLog.user` : rien
    # ne la lit — #754 exclut explicitement un écran « paires ignorées », et
    # l'entrée du journal (`course_duplicate.ignore`) porte déjà le chemin de
    # lecture pour l'auteur. L'ajouter maintenant serait de l'indirection
    # spéculative (principes de conception, AGENTS.md).
