"""Verrous consultatifs PostgreSQL de transaction (#982, #1024).

Ils remplacent le verrou en mémoire d'un seul process, qui ne voyait ni la CLI
`rescrape-db` (GitHub Actions), ni un second worker, ni les imports publics.
Tous sont des verrous **de transaction** (`pg_advisory_xact_lock`) : relâchés au
`commit` ou au `rollback`, jamais oubliés par un appelant qui lève.

Trois espaces de clés :

- `_COURSE` : une épreuve. Pris en exclusif par tout geste qui l'écrit, en
  mode *try* pour un geste admin (refus 409 immédiat), bloquant pour un import,
  qui attend la fin du geste en cours plutôt que d'échouer.
- `_ALL_COURSES` : toutes les épreuves. Chaque verrou d'épreuve le prend en
  **partagé**, une purge `wipe_*` en exclusif : une purge et un geste sur une
  épreuve s'excluent sans poser un verrou par épreuve.
- `_IMPORT_URL` : l'URL soumise à un import, hachée par `hashtext`.

**Sans effet hors PostgreSQL** : la base de dev et de tests (SQLite) n'a qu'un
écrivain, et ces fonctions y réussissent toujours. Le comportement concurrent
se vérifie sur PostgreSQL (`tests/test_repositories/test_lock_repository.py`,
job CI `backend-postgres`).
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

_COURSE = 1
_ALL_COURSES = 2
_IMPORT_URL = 3


def _on_postgres(db: Session) -> bool:
    return db.get_bind().dialect.name == "postgresql"


def bound_lock_waits(db: Session, timeout: str) -> None:
    """Borne, pour le reste de la transaction, l'attente d'un verrou de ligne
    (PostgreSQL ; sans effet ailleurs). Au-delà, l'instruction lève
    `LockNotAvailable` au lieu de suspendre la requête HTTP."""
    if _on_postgres(db):
        # `SET LOCAL` n'accepte pas de paramètre lié ; `set_config(..., true)` est son équivalent.
        db.execute(select(func.set_config("lock_timeout", timeout, True)))


def try_lock_course(db: Session, course_id: int) -> bool:
    """Verrouille une épreuve sans attendre. `False` si un autre la tient."""
    if not _on_postgres(db):
        return True
    return bool(
        db.scalar(select(func.pg_try_advisory_xact_lock_shared(_ALL_COURSES, 0)))
        and db.scalar(select(func.pg_try_advisory_xact_lock(_COURSE, course_id)))
    )


def lock_course(db: Session, course_id: int) -> None:
    """Verrouille une épreuve, en attendant qu'elle se libère."""
    if not _on_postgres(db):
        return
    db.execute(select(func.pg_advisory_xact_lock_shared(_ALL_COURSES, 0)))
    db.execute(select(func.pg_advisory_xact_lock(_COURSE, course_id)))


def try_lock_all_courses(db: Session) -> bool:
    """Verrouille toutes les épreuves sans attendre (purges `wipe_*`)."""
    if not _on_postgres(db):
        return True
    return bool(db.scalar(select(func.pg_try_advisory_xact_lock(_ALL_COURSES, 0))))


def lock_import_url(db: Session, url: str) -> None:
    """Sérialise les imports d'une même URL, entre processus (#1024)."""
    if not _on_postgres(db):
        return
    db.execute(select(func.pg_advisory_xact_lock(_IMPORT_URL, func.hashtext(url))))
