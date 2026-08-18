# Champs éditables et signalement non conforme (bénévoles) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sur l'écran de validation des bénévoles, rendre éditables dossard/place au général/club/catégorie et ajouter une action « signaler non conforme » réversible, sans jamais faire réapparaître une entrée rejetée dans les agrégats publics.

**Architecture:** Un seul champ nouveau, `Participation.is_rejected`, qui ne remplace jamais `is_pending_validation` (celui-ci reste `True` pour toujours sur une entrée rejetée — elle n'a jamais été validée). Les cinq fonctions qui excluent déjà `is_pending_validation=True` des agrégats publics excluent donc gratuitement toute entrée rejetée. Seuls deux endroits ont besoin de connaître `is_rejected` : la file d'attente bénévoles (qui doit l'exclure) et le badge de la page athlète (qui doit le distinguer).

**Tech Stack:** Python 3.13 / FastAPI / SQLAlchemy 2.0 / Alembic / pytest côté backend ; Next.js 16 / TypeScript / Vitest + RTL côté frontend.

**Spec:** `docs/superpowers/specs/2026-08-18-benevoles-champs-non-conforme-design.md`

## Global Constraints

- Français pour tout texte visible utilisateur (labels, messages d'erreur, docstrings de règle métier) ; anglais pour les identifiants techniques.
- `server_default=sa.false()` (l'expression SQLAlchemy) et jamais la chaîne `"false"` pour toute nouvelle colonne booléenne sur `Participation` — piège SQLite documenté dans `backend/app/models/AGENTS.md`.
- Le doublon (conflit de dossard) se détecte par lecture préalable (`exists_for_bib`), jamais par l'`IntegrityError` de `uq_participation_bib`.
- `is_pending_validation` ne doit jamais être modifié par les nouvelles fonctions (`reject_participation`/`unreject_participation`/`update_participation_fields`) — seul `is_rejected` bouge.
- Chaque commande de test s'exécute depuis le répertoire indiqué (`backend/` ou `frontend/`), via `uv run pytest ...` / `npm test`.
- Commits Conventional Commits (`feat(backend): ...`, `feat(frontend): ...`), un commit par tâche.

---

## File Structure

**Backend — Modifier :**
- `backend/app/models/participation.py` — nouvelle colonne `is_rejected`
- `backend/app/core/validation.py` — prédicat `is_actionable_pending`
- `backend/app/repositories/participation_repository.py` — `list_pending`, `has_pending_for_course` exclusifs de `is_rejected` ; nouvelle `list_rejected`
- `backend/app/schemas/participation.py` — `ParticipationOut.is_rejected`
- `backend/app/schemas/benevole.py` — `ParticipationFieldsUpdate`
- `backend/app/services/admin_actions.py` — `reject_participation`, `unreject_participation`, `update_participation_fields`
- `backend/app/api/v1/benevoles.py` — garde `validate`/`reassign`, routes `reject`/`unreject`/`PATCH .../{id}`/`GET rejected`

**Backend — Créer :**
- `backend/alembic/versions/<hash>_participation_is_rejected.py`

**Backend — Test (étendre) :**
- `backend/tests/test_repositories/test_pending_exclusion.py`
- `backend/tests/test_services/test_admin_actions.py`
- `backend/tests/test_api/test_benevoles_api.py`

**Frontend — Modifier :**
- `frontend/lib/types.ts` — `Participation.is_rejected`
- `frontend/lib/api/client.ts` — 4 nouvelles méthodes
- `frontend/components/tcn/PendingBadge.tsx` — variante `rejected`
- `frontend/components/benevoles/ParticipationPanel.tsx` — champs + bouton reject
- `frontend/components/benevoles/ValidationQueue.tsx` — onglet non-conformes
- `frontend/app/benevoles/page.tsx` — état des deux listes, action unreject
- `frontend/app/athletes/[id]/page.tsx` — badge non conforme

**Frontend — Test (étendre) :**
- `frontend/components/tcn/PendingBadge.test.tsx`
- `frontend/components/benevoles/ParticipationPanel.test.tsx`
- `frontend/components/benevoles/ValidationQueue.test.tsx`
- `frontend/app/benevoles/page.test.tsx`
- `frontend/app/athletes/[id]/page.test.tsx`

---

## Task 1: Migration — colonne `is_rejected`

**Files:**
- Create: `backend/alembic/versions/<hash>_participation_is_rejected.py`

**Interfaces:**
- Produces: colonne `participations.is_rejected` (booléen, `NOT NULL DEFAULT false`)

- [ ] **Step 1: Générer le squelette de migration**

Run: `cd backend && uv run alembic revision -m "participation is rejected"`
Expected: un nouveau fichier sous `alembic/versions/`, avec `down_revision = '194ac2494048'` (head actuel).

- [ ] **Step 2: Écrire la migration**

```python
"""participation is rejected

Revision ID: <hash généré>
Revises: 194ac2494048
Create Date: ...
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.core.club import CLUB_NORMALIZED_INDEX_EXPRESSION

revision: str = '<hash généré>'
down_revision: Union[str, None] = '194ac2494048'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    with op.batch_alter_table('participations', schema=None) as batch_op:
        # `sa.false()` et non la chaîne `'false'` : cf. is_pending_validation
        # dans app/models/participation.py — même piège SQLite.
        batch_op.add_column(sa.Column('is_rejected', sa.Boolean(), server_default=sa.false(), nullable=False))

    # `batch_alter_table` recrée la table entière sur SQLite (copie + rename) :
    # sa réflexion ne sait pas relire l'index fonctionnel
    # `ix_participations_club_normalized`, donc la copie ne l'emporte pas
    # (même correctif que la migration 05094fea3bc2).
    if op.get_bind().dialect.name == "sqlite":
        op.create_index(
            "ix_participations_club_normalized",
            "participations",
            [sa.text(CLUB_NORMALIZED_INDEX_EXPRESSION)],
        )


def downgrade() -> None:
    with op.batch_alter_table('participations', schema=None) as batch_op:
        batch_op.drop_column('is_rejected')

    if op.get_bind().dialect.name == "sqlite":
        op.create_index(
            "ix_participations_club_normalized",
            "participations",
            [sa.text(CLUB_NORMALIZED_INDEX_EXPRESSION)],
        )
```

- [ ] **Step 3: Appliquer et vérifier**

Run: `cd backend && uv run alembic upgrade head`
Expected: pas d'erreur ; `sqlite3 triathlon.db ".schema participations"` montre `is_rejected BOOLEAN DEFAULT 0 NOT NULL`.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/*_participation_is_rejected.py
git commit -m "feat(backend): ajoute la colonne participations.is_rejected (#437)"
```

---

## Task 2: Modèle — `Participation.is_rejected`

**Files:**
- Modify: `backend/app/models/participation.py:88` (juste après `is_pending_validation`)
- Test: `backend/tests/test_repositories/test_pending_exclusion.py`

**Interfaces:**
- Consumes: rien
- Produces: `Participation.is_rejected: bool`

- [ ] **Step 1: Write the failing test**

Ajouter en tête de `test_pending_exclusion.py`, après `_duo` :

```python
def test_une_participation_rejetee_reste_exclue_des_memes_agregats(db_session):
    """#437 : is_rejected ne change jamais is_pending_validation — elle
    profite donc gratuitement des cinq mêmes exclusions."""
    course, pendante, validee = _duo(db_session)
    pendante.is_rejected = True
    db_session.flush()

    assert [p.id for p in participation_repository.list_participations(db_session, course_id=course.id)] == [validee.id]
    assert [p.id for p in participation_repository.for_stats(db_session)] == [validee.id]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_repositories/test_pending_exclusion.py::test_une_participation_rejetee_reste_exclue_des_memes_agregats -v`
Expected: FAIL avec `AttributeError: 'Participation' object has no attribute 'is_rejected'`.

- [ ] **Step 3: Write minimal implementation**

Dans `backend/app/models/participation.py`, juste après le bloc `is_pending_validation` (ligne 88-90) :

```python
    # Écarté par un bénévole comme non conforme (#437) — dimension distincte
    # d'`is_pending_validation`, qui reste `True` pour toujours sur une entrée
    # rejetée : elle n'a jamais été *validée*, seulement écartée. C'est cet
    # invariant qui la fait profiter gratuitement des cinq exclusions déjà
    # posées sur `is_pending_validation` (cf. app/core/validation.py).
    is_rejected: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_repositories/test_pending_exclusion.py -v`
Expected: PASS (tous les tests du fichier, y compris le nouveau).

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/participation.py backend/tests/test_repositories/test_pending_exclusion.py
git commit -m "feat(backend): ajoute Participation.is_rejected au modèle (#437)"
```

---

## Task 3: `core/validation.py` — `is_actionable_pending`

**Files:**
- Modify: `backend/app/core/validation.py`
- Test: `backend/tests/test_core/test_validation.py` (créer si absent)

**Interfaces:**
- Consumes: `Participation.is_pending_validation`, `Participation.is_rejected` (Task 2)
- Produces: `is_actionable_pending(participation) -> bool`, utilisé par les Tasks 4 et 8.

- [ ] **Step 1: Write the failing test**

Créer `backend/tests/test_core/test_validation.py` :

```python
"""Prédicats de app/core/validation.py."""
from types import SimpleNamespace

from app.core.validation import is_actionable_pending


def _participation(pending: bool, rejected: bool):
    return SimpleNamespace(is_pending_validation=pending, is_rejected=rejected)


def test_une_participation_pendante_non_rejetee_est_actionnable():
    assert is_actionable_pending(_participation(True, False)) is True


def test_une_participation_validee_n_est_plus_actionnable():
    assert is_actionable_pending(_participation(False, False)) is False


def test_une_participation_rejetee_n_est_plus_actionnable():
    """#437 : le rejet doit bloquer reassign/rename/édition de champs tant
    qu'elle n'est pas d'abord dé-rejetée."""
    assert is_actionable_pending(_participation(True, True)) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_core/test_validation.py -v`
Expected: FAIL avec `ImportError: cannot import name 'is_actionable_pending'`.

- [ ] **Step 3: Write minimal implementation**

Ajouter à la fin de `backend/app/core/validation.py` :

```python
def is_actionable_pending(participation) -> bool:
    """Vrai si ce résultat est encore en attente ET n'a pas été rejeté (#437).

    Garde des routes bénévoles qui doivent redevenir inaccessibles une fois
    l'entrée écartée — `reassign`, `validate`, la future correction de champs
    — sans quoi valider une entrée rejetée la ferait entrer dans tous les
    agrégats publics malgré le rejet.
    """
    return bool(participation.is_pending_validation) and not bool(participation.is_rejected)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_core/test_validation.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/validation.py backend/tests/test_core/test_validation.py
git commit -m "feat(backend): ajoute le prédicat is_actionable_pending (#437)"
```

---

## Task 4: Repository — exclusion de la file, `list_rejected`

**Files:**
- Modify: `backend/app/repositories/participation_repository.py:375-402` (`list_pending`, `has_pending_for_course`)
- Test: `backend/tests/test_repositories/test_participation_repository.py` (ajouter au fichier existant — vérifier son nom exact avant d'écrire, `list_for_athlete` y est déjà testée d'après `test_pending_exclusion.py:15`)

**Interfaces:**
- Consumes: `Participation.is_rejected` (Task 2)
- Produces: `list_rejected(db) -> list[Participation]`, utilisée par la Task 8 (route `GET .../rejected`)

- [ ] **Step 1: Write the failing test**

Ajouter au fichier de test du repository (à côté des tests de `list_pending` s'ils existent, sinon créer la section) :

```python
def test_list_pending_exclut_une_rejetee(db_session):
    """#437 : une entrée rejetée reste is_pending_validation=True mais ne
    doit plus apparaître dans la file bénévoles."""
    course = course_repository.get_or_create(
        db_session, name="Tri Rejet", event_date=date(2026, 5, 16), event_type="triathlon-m"
    )
    athlete = athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean")
    pendante = participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1",
        is_pending_validation=True,
    )
    rejetee = participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="2",
        is_pending_validation=True, is_rejected=True,
    )
    db_session.flush()

    assert [p.id for p in participation_repository.list_pending(db_session)] == [pendante.id]
    assert [p.id for p in participation_repository.list_rejected(db_session)] == [rejetee.id]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_repositories/test_participation_repository.py::test_list_pending_exclut_une_rejetee -v`
Expected: FAIL avec `AttributeError: module 'app.repositories.participation_repository' has no attribute 'list_rejected'` (ou l'assertion `list_pending` échoue si la rejetée y apparaît encore).

- [ ] **Step 3: Write minimal implementation**

Dans `backend/app/repositories/participation_repository.py`, remplacer `list_pending` (ligne 375-387) :

```python
def list_pending(db: Session) -> list[Participation]:
    """Résultats déclarés en attente de validation, tous clubs confondus (#271).

    Exclut les entrées rejetées (#437) : une entrée rejetée reste
    `is_pending_validation=True` pour toujours, mais n'a plus sa place dans
    la file — c'est `list_rejected` ci-dessous qui la rend visible.
    """
    return (
        db.query(Participation)
        .options(joinedload(Participation.athlete), joinedload(Participation.course).selectinload(Course.sources))
        .filter(Participation.is_pending_validation.is_(True), Participation.is_rejected.is_(False))
        .order_by(Participation.created_at.desc())
        .all()
    )


def list_rejected(db: Session) -> list[Participation]:
    """Résultats signalés non conformes par un bénévole, tous clubs confondus (#437)."""
    return (
        db.query(Participation)
        .options(joinedload(Participation.athlete), joinedload(Participation.course).selectinload(Course.sources))
        .filter(Participation.is_pending_validation.is_(True), Participation.is_rejected.is_(True))
        .order_by(Participation.created_at.desc())
        .all()
    )
```

Puis `has_pending_for_course` (ligne 390-402), ajouter le filtre :

```python
def has_pending_for_course(db: Session, course_id: int) -> bool:
    """Cette épreuve porte-t-elle au moins un résultat en attente actionnable ? (#271, #437)

    Scope la portée du renommage bénévole. Exclut les rejetées, sur la même
    logique que `list_pending` : une épreuve dont l'unique résultat en
    attente a été rejeté n'a plus de raison d'être renommable depuis cette
    page tant qu'il n'est pas d'abord dé-rejeté.
    """
    return (
        db.query(Participation.id)
        .filter(
            Participation.course_id == course_id,
            Participation.is_pending_validation.is_(True),
            Participation.is_rejected.is_(False),
        )
        .first()
        is not None
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_repositories/test_participation_repository.py tests/test_repositories/test_pending_exclusion.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/participation_repository.py backend/tests/test_repositories/test_participation_repository.py
git commit -m "feat(backend): exclut les entrées rejetées de la file bénévoles (#437)"
```

---

## Task 5: Schémas — `ParticipationOut.is_rejected`, `ParticipationFieldsUpdate`

**Files:**
- Modify: `backend/app/schemas/participation.py:32` (après `is_pending_validation`)
- Modify: `backend/app/schemas/benevole.py`
- Test: `backend/tests/test_api/test_benevoles_api.py` (la première assertion de la Task 8 dépend de ce champ — pas de test dédié ici, couvert par les tests d'API)

**Interfaces:**
- Consumes: `Participation.is_rejected` (Task 2)
- Produces: `ParticipationOut.is_rejected: bool`, `ParticipationFieldsUpdate` (corps Pydantic pour la Task 8)

- [ ] **Step 1: Modifier `ParticipationOut`**

Dans `backend/app/schemas/participation.py`, après la ligne 32 (`is_pending_validation: bool = False`) :

```python
    # Écarté par un bénévole comme non conforme (#437).
    is_rejected: bool = False
```

- [ ] **Step 2: Ajouter `ParticipationFieldsUpdate`**

Dans `backend/app/schemas/benevole.py`, ajouter en fin de fichier :

```python
from pydantic import model_validator


class ParticipationFieldsUpdate(BaseModel):
    """Corps de `PATCH /benevoles/participations/{id}` (#437).

    Les quatre champs sont facultatifs et tous nullables en base — un
    bénévole peut aussi bien renseigner un dossard que l'effacer.
    """

    model_config = ConfigDict(extra="forbid")

    bib_number: str | None = None
    rank_overall: int | None = None
    club: str | None = None
    category: str | None = None

    @model_validator(mode="after")
    def _au_moins_un_champ(self):
        if not self.model_fields_set:
            raise ValueError("Aucune modification demandée.")
        return self
```

(Déplacer l'import `model_validator` dans la ligne d'import existante `from pydantic import BaseModel, ConfigDict, Field` plutôt qu'un second `import`.)

- [ ] **Step 3: Vérifier que rien ne casse**

Run: `cd backend && uv run pytest tests/test_api/test_benevoles_api.py tests/test_repositories/test_pending_exclusion.py -v`
Expected: PASS (`ParticipationOut.is_rejected` vaut `False` par défaut sur toutes les participations existantes des tests).

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/participation.py backend/app/schemas/benevole.py
git commit -m "feat(backend): schémas is_rejected et ParticipationFieldsUpdate (#437)"
```

---

## Task 6: Service — `reject_participation` / `unreject_participation`

**Files:**
- Modify: `backend/app/services/admin_actions.py` (après `validate_participation`, ligne ~721)
- Test: `backend/tests/test_services/test_admin_actions.py`

**Interfaces:**
- Consumes: `participation_repository.get`, `participation_repository.update`, `admin_action_log_repository.create` (déjà importés dans ce module)
- Produces: `reject_participation(db, *, participation_id, user_id) -> Participation`, `unreject_participation(db, *, participation_id, user_id) -> Participation`

- [ ] **Step 1: Write the failing tests**

Ajouter dans `test_admin_actions.py`, après la section « Valider un résultat en attente » (après la ligne 896) :

```python
# --- Signaler/dé-signaler un résultat non conforme (#437) -------------------


def test_reject_participation_pose_is_rejected(db_session, auteur):
    course = _epreuve(db_session)
    coureur = _coureur(db_session, "DUPONT")
    ligne = participation_repository.create(
        db_session, athlete_id=coureur.id, course_id=course.id, bib_number="1",
        is_pending_validation=True,
    )
    db_session.flush()

    admin_actions.reject_participation(db_session, participation_id=ligne.id, user_id=auteur.id)

    rechargee = participation_repository.get(db_session, ligne.id)
    assert rechargee.is_rejected is True
    assert rechargee.is_pending_validation is True  # jamais touché (#437)


def test_reject_participation_consigne_le_geste(db_session, auteur):
    course = _epreuve(db_session)
    coureur = _coureur(db_session, "DUPONT")
    ligne = participation_repository.create(
        db_session, athlete_id=coureur.id, course_id=course.id, bib_number="1",
        is_pending_validation=True,
    )
    db_session.flush()

    admin_actions.reject_participation(db_session, participation_id=ligne.id, user_id=auteur.id)

    entrees = _journal(db_session, "participation", ligne.id)
    assert [e.action for e in entrees] == ["participation.reject"]


def test_reject_participation_deja_rejetee_ne_consigne_pas_un_second_geste(db_session, auteur):
    course = _epreuve(db_session)
    coureur = _coureur(db_session, "DUPONT")
    ligne = participation_repository.create(
        db_session, athlete_id=coureur.id, course_id=course.id, bib_number="1",
        is_pending_validation=True, is_rejected=True,
    )
    db_session.flush()

    admin_actions.reject_participation(db_session, participation_id=ligne.id, user_id=auteur.id)

    assert _journal(db_session, "participation", ligne.id) == []


def test_reject_participation_sur_resultat_inconnu_refuse(db_session, auteur):
    with pytest.raises(NotFoundError):
        admin_actions.reject_participation(db_session, participation_id=4242, user_id=auteur.id)


def test_unreject_participation_leve_is_rejected(db_session, auteur):
    course = _epreuve(db_session)
    coureur = _coureur(db_session, "DUPONT")
    ligne = participation_repository.create(
        db_session, athlete_id=coureur.id, course_id=course.id, bib_number="1",
        is_pending_validation=True, is_rejected=True,
    )
    db_session.flush()

    admin_actions.unreject_participation(db_session, participation_id=ligne.id, user_id=auteur.id)

    assert participation_repository.get(db_session, ligne.id).is_rejected is False


def test_unreject_participation_deja_actionnable_ne_consigne_pas_un_second_geste(db_session, auteur):
    course = _epreuve(db_session)
    coureur = _coureur(db_session, "DUPONT")
    ligne = participation_repository.create(
        db_session, athlete_id=coureur.id, course_id=course.id, bib_number="1",
        is_pending_validation=True, is_rejected=False,
    )
    db_session.flush()

    admin_actions.unreject_participation(db_session, participation_id=ligne.id, user_id=auteur.id)

    assert _journal(db_session, "participation", ligne.id) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_services/test_admin_actions.py -k reject -v`
Expected: FAIL avec `AttributeError: module 'app.services.admin_actions' has no attribute 'reject_participation'`.

- [ ] **Step 3: Write minimal implementation**

Dans `backend/app/services/admin_actions.py`, après `validate_participation` (après la ligne 721) :

```python
def reject_participation(db: Session, *, participation_id: int, user_id: int) -> Participation:
    """Signale un résultat en attente comme non conforme (#437).

    **Ne touche jamais `is_pending_validation`** : une entrée rejetée n'a
    jamais été *validée*, elle reste en attente pour toujours — c'est cet
    invariant qui la fait profiter gratuitement des cinq exclusions déjà
    posées sur `is_pending_validation` (`app/core/validation.py`).

    **Idempotent**, même patron que `validate_participation`.
    """
    participation = _participation_or_404(db, participation_id)
    if participation.is_rejected:
        return participation

    participation_repository.update(db, participation, is_rejected=True)

    admin_action_log_repository.create(
        db,
        user_id=user_id,
        action="participation.reject",
        entity_type="participation",
        entity_id=participation_id,
        payload={"course_id": participation.course_id, "athlete_id": participation.athlete_id},
    )
    logger.info("Admin %s rejected participation %s", user_id, participation_id)
    return participation


def unreject_participation(db: Session, *, participation_id: int, user_id: int) -> Participation:
    """Annule un rejet — l'entrée réapparaît dans la file bénévoles (#437).

    Idempotent : une entrée qui n'est pas rejetée rend l'état voulu sans
    écrire un second geste.
    """
    participation = _participation_or_404(db, participation_id)
    if not participation.is_rejected:
        return participation

    participation_repository.update(db, participation, is_rejected=False)

    admin_action_log_repository.create(
        db,
        user_id=user_id,
        action="participation.unreject",
        entity_type="participation",
        entity_id=participation_id,
        payload={"course_id": participation.course_id, "athlete_id": participation.athlete_id},
    )
    logger.info("Admin %s unrejected participation %s", user_id, participation_id)
    return participation
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_services/test_admin_actions.py -v`
Expected: PASS (le fichier complet, pas seulement les nouveaux tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/admin_actions.py backend/tests/test_services/test_admin_actions.py
git commit -m "feat(backend): reject_participation et unreject_participation (#437)"
```

---

## Task 7: Service — `update_participation_fields`

**Files:**
- Modify: `backend/app/services/admin_actions.py` (constantes en tête, après `_CHAMPS_COURSE` ligne 650 ; fonction après `unreject_participation`)
- Test: `backend/tests/test_services/test_admin_actions.py`

**Interfaces:**
- Consumes: `_instantane`, `participation_repository.exists_for_bib`, `participation_repository.update`, `DuplicateError` (déjà importé dans ce module — vérifier ; sinon l'ajouter à l'import `app.core.exceptions`)
- Produces: `update_participation_fields(db, *, participation_id, champs: dict, user_id) -> Participation`

- [ ] **Step 1: Write the failing tests**

Ajouter dans `test_admin_actions.py`, après les tests de `unreject_participation` :

```python
# --- Corriger les champs d'un résultat en attente (#437) --------------------


def test_update_participation_fields_ecrit_les_champs_fournis(db_session, auteur):
    course = _epreuve(db_session)
    coureur = _coureur(db_session, "DUPONT")
    ligne = participation_repository.create(
        db_session, athlete_id=coureur.id, course_id=course.id, bib_number="1",
        is_pending_validation=True,
    )
    db_session.flush()

    admin_actions.update_participation_fields(
        db_session, participation_id=ligne.id,
        champs={"bib_number": "42", "rank_overall": 3, "club": "TCN", "category": "V2"},
        user_id=auteur.id,
    )

    rechargee = participation_repository.get(db_session, ligne.id)
    assert rechargee.bib_number == "42"
    assert rechargee.rank_overall == 3
    assert rechargee.club == "TCN"
    assert rechargee.category == "V2"


def test_update_participation_fields_ne_touche_pas_les_champs_absents(db_session, auteur):
    course = _epreuve(db_session)
    coureur = _coureur(db_session, "DUPONT")
    ligne = participation_repository.create(
        db_session, athlete_id=coureur.id, course_id=course.id, bib_number="1",
        is_pending_validation=True, club="ASPTT",
    )
    db_session.flush()

    admin_actions.update_participation_fields(
        db_session, participation_id=ligne.id, champs={"bib_number": "42"}, user_id=auteur.id,
    )

    assert participation_repository.get(db_session, ligne.id).club == "ASPTT"


def test_update_participation_fields_refuse_un_dossard_deja_pris(db_session, auteur):
    course = _epreuve(db_session)
    coureur = _coureur(db_session, "DUPONT")
    autre = _coureur(db_session, "MARTIN")
    ligne = participation_repository.create(
        db_session, athlete_id=coureur.id, course_id=course.id, bib_number="1",
        is_pending_validation=True,
    )
    participation_repository.create(
        db_session, athlete_id=autre.id, course_id=course.id, bib_number="2",
    )
    db_session.flush()

    with pytest.raises(DuplicateError):
        admin_actions.update_participation_fields(
            db_session, participation_id=ligne.id, champs={"bib_number": "2"}, user_id=auteur.id,
        )


def test_update_participation_fields_autorise_a_garder_son_propre_dossard(db_session, auteur):
    """Le dossard inchangé ne doit jamais se heurter à son propre conflit."""
    course = _epreuve(db_session)
    coureur = _coureur(db_session, "DUPONT")
    ligne = participation_repository.create(
        db_session, athlete_id=coureur.id, course_id=course.id, bib_number="1",
        is_pending_validation=True,
    )
    db_session.flush()

    admin_actions.update_participation_fields(
        db_session, participation_id=ligne.id, champs={"bib_number": "1", "club": "TCN"}, user_id=auteur.id,
    )

    assert participation_repository.get(db_session, ligne.id).club == "TCN"


def test_update_participation_fields_consigne_l_avant_et_l_apres(db_session, auteur):
    course = _epreuve(db_session)
    coureur = _coureur(db_session, "DUPONT")
    ligne = participation_repository.create(
        db_session, athlete_id=coureur.id, course_id=course.id, bib_number="1",
        is_pending_validation=True,
    )
    db_session.flush()

    admin_actions.update_participation_fields(
        db_session, participation_id=ligne.id, champs={"club": "TCN"}, user_id=auteur.id,
    )

    entrees = _journal(db_session, "participation", ligne.id)
    assert len(entrees) == 1
    assert entrees[0].action == "participation.correct_fields"
    assert entrees[0].payload["before"]["club"] is None
    assert entrees[0].payload["after"]["club"] == "TCN"


def test_update_participation_fields_sans_changement_ne_consigne_rien(db_session, auteur):
    course = _epreuve(db_session)
    coureur = _coureur(db_session, "DUPONT")
    ligne = participation_repository.create(
        db_session, athlete_id=coureur.id, course_id=course.id, bib_number="1",
        is_pending_validation=True, club="TCN",
    )
    db_session.flush()

    admin_actions.update_participation_fields(
        db_session, participation_id=ligne.id, champs={"club": "TCN"}, user_id=auteur.id,
    )

    assert _journal(db_session, "participation", ligne.id) == []


def test_update_participation_fields_sur_resultat_inconnu_refuse(db_session, auteur):
    with pytest.raises(NotFoundError):
        admin_actions.update_participation_fields(
            db_session, participation_id=4242, champs={"club": "TCN"}, user_id=auteur.id,
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_services/test_admin_actions.py -k update_participation_fields -v`
Expected: FAIL avec `AttributeError: module 'app.services.admin_actions' has no attribute 'update_participation_fields'`.

- [ ] **Step 3: Write minimal implementation**

Vérifier l'import de `DuplicateError` en tête de `admin_actions.py` (déjà utilisé par `reassign_participation`/`update_athlete` — probablement déjà importé ; sinon l'ajouter à la ligne `from app.core.exceptions import ...`).

Ajouter la constante après `_CHAMPS_COURSE` (ligne 650) :

```python
#: Les quatre champs qu'un bénévole peut corriger sur un résultat en attente (#437).
_CHAMPS_PARTICIPATION = ("bib_number", "rank_overall", "club", "category")
```

Ajouter la fonction après `unreject_participation` :

```python
def update_participation_fields(
    db: Session, *, participation_id: int, champs: dict, user_id: int
) -> Participation:
    """Corrige dossard, place au général, club et catégorie d'un résultat en
    attente (#437).

    **Le conflit de dossard se détecte par lecture préalable**
    (`exists_for_bib`), jamais par l'`IntegrityError` de `uq_participation_bib`
    — même règle que `update_athlete` pour les doublons d'identité. Le dossard
    inchangé ne déclenche jamais ce contrôle : `exists_for_bib` trouverait la
    ligne elle-même et rendrait un faux conflit.
    """
    participation = _participation_or_404(db, participation_id)
    demande = {champ: champs[champ] for champ in _CHAMPS_PARTICIPATION if champ in champs}

    nouveau_dossard = demande.get("bib_number")
    if nouveau_dossard and nouveau_dossard != participation.bib_number:
        if participation_repository.exists_for_bib(db, participation.course_id, nouveau_dossard):
            raise DuplicateError(
                "Ce dossard est déjà attribué à un autre participant de cette épreuve."
            )

    avant = _instantane(participation, _CHAMPS_PARTICIPATION)
    participation_repository.update(db, participation, **demande)
    apres = _instantane(participation, _CHAMPS_PARTICIPATION)
    if apres == avant:
        return participation

    admin_action_log_repository.create(
        db,
        user_id=user_id,
        action="participation.correct_fields",
        entity_type="participation",
        entity_id=participation_id,
        payload={"before": avant, "after": apres},
    )
    logger.info("Admin %s corrected fields of participation %s", user_id, participation_id)
    return participation
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_services/test_admin_actions.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/admin_actions.py backend/tests/test_services/test_admin_actions.py
git commit -m "feat(backend): update_participation_fields avec conflit de dossard (#437)"
```

---

## Task 8: API — garde des routes existantes, 4 nouvelles ressources

**Files:**
- Modify: `backend/app/api/v1/benevoles.py`
- Test: `backend/tests/test_api/test_benevoles_api.py`

**Interfaces:**
- Consumes: `is_actionable_pending` (Task 3), `list_rejected` (Task 4), `ParticipationFieldsUpdate` (Task 5), `reject_participation`/`unreject_participation`/`update_participation_fields` (Tasks 6-7)
- Produces: `POST /benevoles/participations/{id}/reject`, `POST .../unreject`, `PATCH /benevoles/participations/{id}`, `GET /benevoles/rejected`

- [ ] **Step 1: Write the failing tests**

Ajouter dans `test_benevoles_api.py`, après la section `reassign` (après la ligne 377) :

```python
# --- Le rejet bloque validate/reassign tant qu'il n'est pas levé (#437) -----


def test_validate_refuse_un_resultat_rejete(benevole_connecte, resultat_pendant, compte_systeme):
    course, athlete, ligne = resultat_pendant
    benevole_connecte.post(f"/api/v1/benevoles/participations/{ligne.id}/reject")

    reponse = benevole_connecte.post(f"/api/v1/benevoles/participations/{ligne.id}/validate")
    assert reponse.status_code == 404


def test_reassign_refuse_un_resultat_rejete(benevole_connecte, resultat_pendant, compte_systeme, db_session):
    course, athlete, ligne = resultat_pendant
    cible = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Paul", club="ASPTT")
    db_session.commit()
    benevole_connecte.post(f"/api/v1/benevoles/participations/{ligne.id}/reject")

    reponse = benevole_connecte.post(
        f"/api/v1/benevoles/participations/{ligne.id}/reassign", json={"athlete_id": cible.id}
    )
    assert reponse.status_code == 404


# --- POST .../reject, POST .../unreject, GET /benevoles/rejected (#437) -----


def test_reject_fait_sortir_le_resultat_de_la_file(benevole_connecte, resultat_pendant, compte_systeme):
    course, athlete, ligne = resultat_pendant

    reponse = benevole_connecte.post(f"/api/v1/benevoles/participations/{ligne.id}/reject")
    assert reponse.status_code == 200
    assert reponse.json()["is_rejected"] is True
    assert reponse.json()["is_pending_validation"] is True

    assert benevole_connecte.get("/api/v1/benevoles/queue").json() == []
    rejetees = benevole_connecte.get("/api/v1/benevoles/rejected").json()
    assert [r["id"] for r in rejetees] == [ligne.id]


def test_reject_sur_resultat_inconnu_est_un_404(benevole_connecte, compte_systeme):
    reponse = benevole_connecte.post("/api/v1/benevoles/participations/4242/reject")
    assert reponse.status_code == 404


def test_reject_refuse_sans_cookie(client, resultat_pendant):
    course, athlete, ligne = resultat_pendant
    reponse = client.post(f"/api/v1/benevoles/participations/{ligne.id}/reject")
    assert reponse.status_code == 401


def test_unreject_fait_revenir_le_resultat_dans_la_file(benevole_connecte, resultat_pendant, compte_systeme):
    course, athlete, ligne = resultat_pendant
    benevole_connecte.post(f"/api/v1/benevoles/participations/{ligne.id}/reject")

    reponse = benevole_connecte.post(f"/api/v1/benevoles/participations/{ligne.id}/unreject")
    assert reponse.status_code == 200
    assert reponse.json()["is_rejected"] is False

    assert [p["id"] for p in benevole_connecte.get("/api/v1/benevoles/queue").json()] == [ligne.id]
    assert benevole_connecte.get("/api/v1/benevoles/rejected").json() == []


def test_rejected_vide_sans_erreur_si_rien_de_rejete(benevole_connecte):
    reponse = benevole_connecte.get("/api/v1/benevoles/rejected")
    assert reponse.status_code == 200
    assert reponse.json() == []


# --- PATCH /benevoles/participations/{id} (#437) -----------------------------


def test_update_fields_ecrit_les_champs_fournis(benevole_connecte, resultat_pendant, compte_systeme):
    course, athlete, ligne = resultat_pendant

    reponse = benevole_connecte.patch(
        f"/api/v1/benevoles/participations/{ligne.id}",
        json={"bib_number": "42", "club": "TCN"},
    )
    assert reponse.status_code == 200
    assert reponse.json()["bib_number"] == "42"
    assert reponse.json()["club"] == "TCN"


def test_update_fields_signale_un_conflit_de_dossard(
    benevole_connecte, resultat_pendant, compte_systeme, db_session
):
    course, athlete, ligne = resultat_pendant
    autre = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Paul", club="ASPTT")
    participation_repository.create(db_session, athlete_id=autre.id, course_id=course.id, bib_number="9")
    db_session.commit()

    reponse = benevole_connecte.patch(
        f"/api/v1/benevoles/participations/{ligne.id}", json={"bib_number": "9"}
    )
    assert reponse.status_code == 409


def test_update_fields_refuse_un_corps_vide(benevole_connecte, resultat_pendant, compte_systeme):
    course, athlete, ligne = resultat_pendant
    reponse = benevole_connecte.patch(f"/api/v1/benevoles/participations/{ligne.id}", json={})
    assert reponse.status_code == 422


def test_update_fields_refuse_sur_resultat_rejete(benevole_connecte, resultat_pendant, compte_systeme):
    course, athlete, ligne = resultat_pendant
    benevole_connecte.post(f"/api/v1/benevoles/participations/{ligne.id}/reject")

    reponse = benevole_connecte.patch(
        f"/api/v1/benevoles/participations/{ligne.id}", json={"club": "TCN"}
    )
    assert reponse.status_code == 404


def test_update_fields_refuse_sans_cookie(client, resultat_pendant):
    course, athlete, ligne = resultat_pendant
    reponse = client.patch(f"/api/v1/benevoles/participations/{ligne.id}", json={"club": "TCN"})
    assert reponse.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_api/test_benevoles_api.py -v`
Expected: FAIL — 404 attendu vs 200 sur les deux premiers tests (garde absente), puis erreurs 404/405 sur les routes encore inexistantes.

- [ ] **Step 3: Write minimal implementation**

Dans `backend/app/api/v1/benevoles.py` :

1. Étendre les imports :

```python
from app.core.validation import is_actionable_pending
from app.schemas.benevole import BenevoleCourseRename, BenevoleLogin, ParticipationFieldsUpdate
```

2. Remplacer la garde de `reassign` (ligne 111-113) :

```python
    cible = participation_repository.get(db, participation_id)
    if cible is None or not is_actionable_pending(cible):
        raise NotFoundError("Ce résultat n'est pas ou plus en attente de validation.")
```

3. Ajouter la même garde à `validate` (avant l'appel actuel, ligne 129) :

```python
def validate(participation_id: int, db: Session = Depends(get_db)):
    """Valide un résultat en attente (US1) — le fait passer visible partout."""
    cible = participation_repository.get(db, participation_id)
    if cible is None or not is_actionable_pending(cible):
        raise NotFoundError("Ce résultat n'est pas ou plus en attente de validation.")
    participation = admin_actions.validate_participation(
        db, participation_id=participation_id, user_id=benevole_access.system_user_id(db)
    )
    db.commit()
    return participation
```

4. Ajouter les 4 nouvelles routes, après `validate` :

```python
@router.get(
    "/benevoles/rejected",
    response_model=list[ParticipationOut],
    dependencies=[Depends(require_benevole_access)],
)
def rejected(db: Session = Depends(get_db)):
    """Résultats signalés non conformes, tous clubs confondus (#437)."""
    return participation_repository.list_rejected(db)


@router.post(
    "/benevoles/participations/{participation_id}/reject",
    response_model=ParticipationOut,
    dependencies=[Depends(require_benevole_access)],
)
def reject(participation_id: int, db: Session = Depends(get_db)):
    """Signale un résultat en attente comme non conforme (#437)."""
    cible = participation_repository.get(db, participation_id)
    if cible is None or not is_actionable_pending(cible):
        raise NotFoundError("Ce résultat n'est pas ou plus en attente de validation.")
    participation = admin_actions.reject_participation(
        db, participation_id=participation_id, user_id=benevole_access.system_user_id(db)
    )
    db.commit()
    return participation


@router.post(
    "/benevoles/participations/{participation_id}/unreject",
    response_model=ParticipationOut,
    dependencies=[Depends(require_benevole_access)],
)
def unreject(participation_id: int, db: Session = Depends(get_db)):
    """Annule le signalement d'un résultat non conforme (#437)."""
    cible = participation_repository.get(db, participation_id)
    if cible is None or not cible.is_pending_validation or not cible.is_rejected:
        raise NotFoundError("Ce résultat n'est pas ou plus signalé non conforme.")
    participation = admin_actions.unreject_participation(
        db, participation_id=participation_id, user_id=benevole_access.system_user_id(db)
    )
    db.commit()
    return participation


@router.patch(
    "/benevoles/participations/{participation_id}",
    response_model=ParticipationOut,
    dependencies=[Depends(require_benevole_access)],
)
def update_fields(participation_id: int, body: ParticipationFieldsUpdate, db: Session = Depends(get_db)):
    """Corrige dossard, place au général, club et catégorie (#437)."""
    cible = participation_repository.get(db, participation_id)
    if cible is None or not is_actionable_pending(cible):
        raise NotFoundError("Ce résultat n'est pas ou plus en attente de validation.")
    participation = admin_actions.update_participation_fields(
        db,
        participation_id=participation_id,
        champs=body.model_dump(exclude_unset=True),
        user_id=benevole_access.system_user_id(db),
    )
    db.commit()
    return participation
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_api/test_benevoles_api.py -v`
Expected: PASS (tout le fichier).

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && uv run pytest -m "not integration"`
Expected: PASS, aucune régression sur les 745+ tests existants.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/benevoles.py backend/tests/test_api/test_benevoles_api.py
git commit -m "feat(backend): routes reject/unreject/PATCH champs et garde is_actionable_pending (#437)"
```

---

## Task 9: Frontend — types et client API

**Files:**
- Modify: `frontend/lib/types.ts:91` (après `is_pending_validation`)
- Modify: `frontend/lib/api/client.ts:415-437` (section « Page de vérification »)

**Interfaces:**
- Consumes: rien
- Produces: `Participation.is_rejected`, `apiClient.getBenevoleRejected`, `.rejectParticipationBenevole`, `.unrejectParticipationBenevole`, `.updateParticipationFieldsBenevole` — consommées par les Tasks 11-13.

- [ ] **Step 1: Étendre le type `Participation`**

Dans `frontend/lib/types.ts`, après la ligne 91 (`is_pending_validation?: boolean;`) :

```typescript
  // Écarté par un bénévole comme non conforme (#437).
  is_rejected?: boolean;
```

- [ ] **Step 2: Étendre `apiClient`**

Dans `frontend/lib/api/client.ts`, après `reassignParticipationBenevole` (ligne 433-437, avant le `};` de fermeture) :

```typescript
  getBenevoleRejected: () => request<Participation[]>("/benevoles/rejected"),
  rejectParticipationBenevole: (participationId: number) =>
    request<Participation>(`/benevoles/participations/${participationId}/reject`, {
      method: "POST",
    }),
  unrejectParticipationBenevole: (participationId: number) =>
    request<Participation>(`/benevoles/participations/${participationId}/unreject`, {
      method: "POST",
    }),
  updateParticipationFieldsBenevole: (
    participationId: number,
    champs: { bib_number?: string | null; rank_overall?: number | null; club?: string | null; category?: string | null },
  ) =>
    request<Participation>(`/benevoles/participations/${participationId}`, {
      method: "PATCH",
      body: JSON.stringify(champs),
    }),
```

- [ ] **Step 3: Vérifier la compilation TypeScript**

Run: `cd frontend && npm run build`
Expected: build réussi (pas d'erreur de type — aucun consommateur de ces méthodes n'existe encore, donc rien d'autre à vérifier ici).

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/api/client.ts
git commit -m "feat(frontend): type is_rejected et client API pour reject/unreject/champs (#437)"
```

---

## Task 10: `PendingBadge` — variante « non conforme »

**Files:**
- Modify: `frontend/components/tcn/PendingBadge.tsx`
- Test: `frontend/components/tcn/PendingBadge.test.tsx`

**Interfaces:**
- Consumes: rien
- Produces: `<PendingBadge rejected />`, consommé par la Task 13.

- [ ] **Step 1: Write the failing test**

Ajouter dans `PendingBadge.test.tsx` :

```typescript
  it("affiche « non conforme » quand rejected est vrai", () => {
    render(<PendingBadge rejected />);
    expect(screen.getByText(/non conforme/i)).toBeInTheDocument();
    expect(screen.queryByText(/en attente de validation/i)).not.toBeInTheDocument();
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- PendingBadge`
Expected: FAIL — le texte « non conforme » n'apparaît pas (le composant ignore la prop, qui n'existe pas encore).

- [ ] **Step 3: Write minimal implementation**

Remplacer le contenu de `PendingBadge.tsx` :

```tsx
/** Mention explicite d'un résultat saisi manuellement, non encore vérifié
 *  par un bénévole (#270), ou signalé non conforme par un bénévole (#437).
 *  Seule surface où une participation pendante est visible (FR-019) :
 *  distincte au premier coup d'œil, sans survol ni clic (SC-003). */
export function PendingBadge({ rejected = false }: { rejected?: boolean }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "3px 10px",
        borderRadius: 999,
        fontWeight: 700,
        fontSize: 11,
        textTransform: "uppercase",
        letterSpacing: ".03em",
        background: rejected ? "var(--tcn-danger-bg)" : "var(--tcn-warning-bg)",
        color: rejected ? "var(--tcn-danger-text)" : "var(--tcn-warning-text)",
        border: `1px solid ${rejected ? "var(--tcn-danger-border)" : "var(--tcn-warning-border)"}`,
      }}
    >
      {rejected ? "Non conforme" : "En attente de validation"}
    </span>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- PendingBadge`
Expected: PASS (les deux tests du fichier).

- [ ] **Step 5: Commit**

```bash
git add frontend/components/tcn/PendingBadge.tsx frontend/components/tcn/PendingBadge.test.tsx
git commit -m "feat(frontend): PendingBadge affiche non conforme (#437)"
```

---

## Task 11: `ParticipationPanel` — champs éditables et bouton reject

**Files:**
- Modify: `frontend/components/benevoles/ParticipationPanel.tsx`
- Test: `frontend/components/benevoles/ParticipationPanel.test.tsx`

**Interfaces:**
- Consumes: `apiClient.updateParticipationFieldsBenevole`, `.rejectParticipationBenevole` (Task 9)
- Produces: panneau avec 4 champs + « Enregistrer les modifications » + « Signaler non conforme »

- [ ] **Step 1: Write the failing tests**

Ajouter dans `ParticipationPanel.test.tsx`, en tête du `vi.hoisted`/`vi.mock` (ajouter les deux nouvelles fonctions mockées à côté des existantes) :

```typescript
const {
  validateParticipationBenevole,
  renameCourseBenevole,
  reassignParticipationBenevole,
  searchAthletes,
  updateParticipationFieldsBenevole,
  rejectParticipationBenevole,
} = vi.hoisted(() => ({
  validateParticipationBenevole: vi.fn(),
  renameCourseBenevole: vi.fn(),
  reassignParticipationBenevole: vi.fn(),
  searchAthletes: vi.fn(),
  updateParticipationFieldsBenevole: vi.fn(),
  rejectParticipationBenevole: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: {
      validateParticipationBenevole,
      renameCourseBenevole,
      reassignParticipationBenevole,
      searchAthletes,
      updateParticipationFieldsBenevole,
      rejectParticipationBenevole,
    },
  };
});
```

Puis ajouter les tests, en fin de fichier avant le `});` final :

```typescript
  // --- #437 : champs éditables ---------------------------------------------

  it("enregistre les quatre champs modifiés en un seul appel", async () => {
    const corrigee = participation({ bib_number: "42", rank_overall: 3, club: "TCN", category: "V2" });
    updateParticipationFieldsBenevole.mockResolvedValue(corrigee);
    const onChanged = vi.fn();
    const user = userEvent.setup();
    render(<ParticipationPanel participation={participation()} onChanged={onChanged} />);

    await user.type(screen.getByLabelText(/dossard/i), "42");
    await user.type(screen.getByLabelText(/place au général/i), "3");
    await user.type(screen.getByLabelText(/^club/i), "TCN");
    await user.type(screen.getByLabelText(/catégorie/i), "V2");
    await user.click(screen.getByRole("button", { name: /enregistrer les modifications/i }));

    await waitFor(() =>
      expect(updateParticipationFieldsBenevole).toHaveBeenCalledWith(7, {
        bib_number: "42",
        rank_overall: 3,
        club: "TCN",
        category: "V2",
      }),
    );
    expect(onChanged).toHaveBeenCalledWith(corrigee);
  });

  it("signale un conflit de dossard en français", async () => {
    updateParticipationFieldsBenevole.mockRejectedValue(
      new ApiError(409, "Ce dossard est déjà attribué à un autre participant de cette épreuve."),
    );
    const user = userEvent.setup();
    render(<ParticipationPanel participation={participation()} onChanged={vi.fn()} />);

    await user.type(screen.getByLabelText(/dossard/i), "9");
    await user.click(screen.getByRole("button", { name: /enregistrer les modifications/i }));

    expect(
      await screen.findByText("Ce dossard est déjà attribué à un autre participant de cette épreuve."),
    ).toBeInTheDocument();
  });

  // --- #437 : signalement non conforme -------------------------------------

  it("signale non conforme après confirmation", async () => {
    const rejetee = participation({ is_rejected: true });
    rejectParticipationBenevole.mockResolvedValue(rejetee);
    const onChanged = vi.fn();
    const user = userEvent.setup();
    render(<ParticipationPanel participation={participation()} onChanged={onChanged} />);

    await user.click(screen.getByRole("button", { name: /signaler non conforme/i }));
    await user.click(screen.getByRole("button", { name: /confirmer/i }));

    await waitFor(() => expect(rejectParticipationBenevole).toHaveBeenCalledWith(7));
    expect(onChanged).toHaveBeenCalledWith(rejetee);
  });

  it("n'appelle rien si le signalement n'est pas confirmé", async () => {
    const user = userEvent.setup();
    render(<ParticipationPanel participation={participation()} onChanged={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: /signaler non conforme/i }));

    expect(rejectParticipationBenevole).not.toHaveBeenCalled();
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- ParticipationPanel`
Expected: FAIL — `getByLabelText(/dossard/i)` etc. introuvables, boutons absents.

- [ ] **Step 3: Write minimal implementation**

Dans `ParticipationPanel.tsx` :

1. Ajouter les états, après `enCoursReattribution` (ligne 32) :

```tsx
  const [champs, setChamps] = useState({
    bib_number: participation.bib_number ?? "",
    rank_overall: participation.rank_overall != null ? String(participation.rank_overall) : "",
    club: participation.club ?? "",
    category: participation.category ?? "",
  });
  const [erreurChamps, setErreurChamps] = useState<string | null>(null);
  const [enCoursChamps, setEnCoursChamps] = useState(false);

  const [confirmationRejet, setConfirmationRejet] = useState(false);
  const [erreurRejet, setErreurRejet] = useState<string | null>(null);
  const [enCoursRejet, setEnCoursRejet] = useState(false);
```

2. Ajouter les fonctions, après `reattribuer` (ligne 101) :

```tsx
  async function enregistrerChamps() {
    setErreurChamps(null);
    setEnCoursChamps(true);
    try {
      const resultat = await apiClient.updateParticipationFieldsBenevole(participation.id, {
        bib_number: champs.bib_number || null,
        rank_overall: champs.rank_overall ? Number(champs.rank_overall) : null,
        club: champs.club || null,
        category: champs.category || null,
      });
      onChanged(resultat);
    } catch (err) {
      gererErreur(err, setErreurChamps, "L'enregistrement a échoué. Réessayez plus tard.");
    } finally {
      setEnCoursChamps(false);
    }
  }

  async function signalerNonConforme() {
    setErreurRejet(null);
    setEnCoursRejet(true);
    try {
      const resultat = await apiClient.rejectParticipationBenevole(participation.id);
      onChanged(resultat);
    } catch (err) {
      gererErreur(err, setErreurRejet, "Le signalement a échoué. Réessayez plus tard.");
    } finally {
      setEnCoursRejet(false);
      setConfirmationRejet(false);
    }
  }
```

3. Ajouter le bloc des champs éditables, après le bloc « Réattribuer à » (après la ligne 216, avant le bloc de validation) :

```tsx
        <div style={{ borderTop: "1px solid var(--tcn-border)", paddingTop: 16 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div>
              <label htmlFor="benevole-dossard" style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                Dossard
              </label>
              <Input
                id="benevole-dossard"
                value={champs.bib_number}
                onChange={(e) => setChamps((c) => ({ ...c, bib_number: e.target.value }))}
              />
            </div>
            <div>
              <label htmlFor="benevole-place" style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                Place au général
              </label>
              <Input
                id="benevole-place"
                type="number"
                value={champs.rank_overall}
                onChange={(e) => setChamps((c) => ({ ...c, rank_overall: e.target.value }))}
              />
            </div>
            <div>
              <label htmlFor="benevole-club" style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                Club
              </label>
              <Input
                id="benevole-club"
                value={champs.club}
                onChange={(e) => setChamps((c) => ({ ...c, club: e.target.value }))}
              />
            </div>
            <div>
              <label htmlFor="benevole-categorie" style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                Catégorie
              </label>
              <Input
                id="benevole-categorie"
                value={champs.category}
                onChange={(e) => setChamps((c) => ({ ...c, category: e.target.value }))}
              />
            </div>
          </div>
          <Button variant="secondary" onClick={enregistrerChamps} disabled={enCoursChamps} style={{ marginTop: 12 }}>
            {enCoursChamps ? "Enregistrement…" : "Enregistrer les modifications"}
          </Button>
          {erreurChamps && (
            <div role="alert" style={{ color: "var(--tcn-danger-text)", fontSize: 13, marginTop: 8 }}>
              {erreurChamps}
            </div>
          )}
        </div>
```

4. Modifier le bloc final (« Valider ce résultat », lignes 218-227) pour y ajouter le bouton de rejet :

```tsx
        <div style={{ borderTop: "1px solid var(--tcn-border)", paddingTop: 16, display: "flex", flexDirection: "column", gap: 8 }}>
          <Button onClick={valider} disabled={enCoursValidation} style={{ width: "100%" }}>
            {enCoursValidation ? "Validation…" : "Valider ce résultat"}
          </Button>
          {erreurValidation && (
            <div role="alert" style={{ color: "var(--tcn-danger-text)", fontSize: 13 }}>
              {erreurValidation}
            </div>
          )}
          {!confirmationRejet ? (
            <Button
              variant="secondary"
              onClick={() => setConfirmationRejet(true)}
              style={{ width: "100%", color: "var(--tcn-danger-text)", borderColor: "var(--tcn-danger-border)" }}
            >
              Signaler non conforme
            </Button>
          ) : (
            <div style={{ display: "flex", gap: 8 }}>
              <Button
                variant="secondary"
                onClick={signalerNonConforme}
                disabled={enCoursRejet}
                style={{ flex: 1, color: "var(--tcn-danger-text)", borderColor: "var(--tcn-danger-border)" }}
              >
                {enCoursRejet ? "Signalement…" : "Confirmer ?"}
              </Button>
              <Button variant="ghost" onClick={() => setConfirmationRejet(false)} disabled={enCoursRejet} style={{ flex: 1 }}>
                Annuler
              </Button>
            </div>
          )}
          {erreurRejet && (
            <div role="alert" style={{ color: "var(--tcn-danger-text)", fontSize: 13 }}>
              {erreurRejet}
            </div>
          )}
        </div>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- ParticipationPanel`
Expected: PASS (tout le fichier — vérifier aussi que les tests existants de validation/réattribution n'ont pas régressé, le libellé du bouton `/valider/i` matchant toujours).

- [ ] **Step 5: Commit**

```bash
git add frontend/components/benevoles/ParticipationPanel.tsx frontend/components/benevoles/ParticipationPanel.test.tsx
git commit -m "feat(frontend): champs éditables et signalement non conforme sur le panneau bénévoles (#437)"
```

---

## Task 12: `ValidationQueue` + `app/benevoles/page.tsx` — onglet non-conformes

**Files:**
- Modify: `frontend/components/benevoles/ValidationQueue.tsx`
- Modify: `frontend/app/benevoles/page.tsx`
- Test: `frontend/components/benevoles/ValidationQueue.test.tsx`, `frontend/app/benevoles/page.test.tsx`

**Interfaces:**
- Consumes: `apiClient.getBenevoleRejected`, `.unrejectParticipationBenevole` (Task 9)
- Produces: onglet « Non conformes » basculable, action « Annuler le rejet »

- [ ] **Step 1: Write the failing tests**

Dans `ValidationQueue.test.tsx`, ajouter un test pour le mode « non conformes » (vérifier d'abord la forme exacte des props existantes dans le fichier avant d'écrire — le composant actuel ne prend que `participations`/`selectedId`/`onSelect`) :

```typescript
  it("affiche un onglet Non conformes et bascule la liste affichée", async () => {
    const user = userEvent.setup();
    const rejetee = { ...participation, id: 9, athlete: { ...participation.athlete, nom: "MARTIN" } };
    render(
      <ValidationQueue
        participations={[participation]}
        rejected={[rejetee]}
        selectedId={null}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText(/DUPONT/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /non conformes/i }));
    expect(screen.getByText(/MARTIN/)).toBeInTheDocument();
    expect(screen.queryByText(/DUPONT/)).not.toBeInTheDocument();
  });
```

(Adapter la fixture `participation` locale du fichier de test existant si son nom diffère — vérifier en tête du fichier avant d'écrire ce test.)

Dans `page.test.tsx`, ajouter un test d'intégration pour l'action « Annuler le rejet » (mock `apiClient.getBenevoleQueue`, `.getBenevoleRejected`, `.unrejectParticipationBenevole` — vérifier les mocks déjà en place dans le fichier existant pour reprendre le même patron `vi.hoisted`).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- ValidationQueue page.test`
Expected: FAIL — prop `rejected` ignorée, bouton « Non conformes » absent.

- [ ] **Step 3: Write minimal implementation**

Dans `ValidationQueue.tsx`, ajouter un état de bascule interne et la prop `rejected` :

```tsx
"use client";

import { useState } from "react";
import { Card } from "@/components/tcn";
import type { Participation } from "@/lib/types";
import { formatEventName } from "@/lib/utils/event";

/** File des résultats en attente de validation (#271, US1), avec un second
 *  onglet pour les entrées signalées non conformes (#437) — tous clubs
 *  confondus. */
export function ValidationQueue({
  participations,
  rejected = [],
  selectedId,
  onSelect,
}: {
  participations: Participation[];
  rejected?: Participation[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}) {
  const [onglet, setOnglet] = useState<"file" | "non-conformes">("file");
  const liste = onglet === "file" ? participations : rejected;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", gap: 8 }}>
        <button
          type="button"
          onClick={() => setOnglet("file")}
          aria-pressed={onglet === "file"}
          style={{ fontWeight: onglet === "file" ? 700 : 400, background: "none", border: "none", cursor: "pointer" }}
        >
          File ({participations.length})
        </button>
        <button
          type="button"
          onClick={() => setOnglet("non-conformes")}
          aria-pressed={onglet === "non-conformes"}
          style={{ fontWeight: onglet === "non-conformes" ? 700 : 400, background: "none", border: "none", cursor: "pointer" }}
        >
          Non conformes ({rejected.length})
        </button>
      </div>

      {liste.length === 0 ? (
        <Card padding={24}>
          <div style={{ color: "var(--tcn-text-faint)", fontSize: 14, textAlign: "center" }}>
            {onglet === "file" ? "Aucun résultat en attente de validation." : "Aucun résultat signalé non conforme."}
          </div>
        </Card>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {liste.map((participation) => {
            const selectionnee = participation.id === selectedId;
            return (
              <button
                key={participation.id}
                type="button"
                className="tcn-rowlink"
                aria-current={selectionnee ? "true" : undefined}
                onClick={() => onSelect(participation.id)}
                style={{
                  textAlign: "left",
                  padding: "14px 16px",
                  borderRadius: "var(--tcn-radius-lg)",
                  border: `1.5px solid ${selectionnee ? "var(--tcn-orange)" : "var(--tcn-border)"}`,
                  background: selectionnee ? "var(--tcn-orange-08)" : "var(--tcn-surface)",
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                  width: "100%",
                }}
              >
                <span style={{ fontWeight: 700, color: "var(--tcn-ink)" }}>
                  {participation.athlete.prenom} {participation.athlete.nom}
                </span>
                <span style={{ fontSize: 13, color: "var(--tcn-text-faint)" }}>
                  {formatEventName(participation.course.name, participation.course.is_relay)}
                </span>
                {participation.team_name && (
                  <span style={{ fontSize: 12, color: "var(--tcn-text-body)" }}>
                    Équipe : <strong>{participation.team_name}</strong>
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
```

Dans `app/benevoles/page.tsx` : ajouter un état `rejetees`, le charger en même temps que la file, et exposer une action d'annulation de rejet passée au panneau via `onChanged` (le rejet et l'annulation transitent tous deux par `surChangement`, qui doit maintenant router l'entrée entre les deux listes) :

```tsx
  const [rejetees, setRejetees] = useState<Participation[]>([]);

  const chargerLaFile = useCallback(async () => {
    setEtat("chargement");
    try {
      const [resultats, rejets] = await Promise.all([
        apiClient.getBenevoleQueue(),
        apiClient.getBenevoleRejected(),
      ]);
      setParticipations(resultats);
      setRejetees(rejets);
      setEtat("file");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setEtat("gate");
      } else {
        setEtat("erreur");
      }
    }
  }, []);
```

Remplacer `surChangement` (lignes 45-52) pour router entre les deux listes :

```tsx
  function surChangement(mise_a_jour: Participation) {
    if (!mise_a_jour.is_pending_validation) {
      // Validée : sort des deux listes.
      setParticipations((liste) => liste.filter((p) => p.id !== mise_a_jour.id));
      setRejetees((liste) => liste.filter((p) => p.id !== mise_a_jour.id));
      setSelectedId((id) => (id === mise_a_jour.id ? null : id));
      return;
    }
    if (mise_a_jour.is_rejected) {
      // Vient d'être rejetée : sort de la file, entre dans les non-conformes.
      setParticipations((liste) => liste.filter((p) => p.id !== mise_a_jour.id));
      setRejetees((liste) => [mise_a_jour, ...liste.filter((p) => p.id !== mise_a_jour.id)]);
      return;
    }
    // Rejet annulé : sort des non-conformes, revient dans la file.
    setRejetees((liste) => liste.filter((p) => p.id !== mise_a_jour.id));
    setParticipations((liste) =>
      liste.some((p) => p.id === mise_a_jour.id)
        ? liste.map((p) => (p.id === mise_a_jour.id ? mise_a_jour : p))
        : [mise_a_jour, ...liste],
    );
  }
```

Passer `rejetees` à `ValidationQueue` et chercher la sélection dans les deux listes :

```tsx
  const selectionnee =
    participations.find((p) => p.id === selectedId) ?? rejetees.find((p) => p.id === selectedId) ?? null;
```

```tsx
        <ValidationQueue
          participations={participations}
          rejected={rejetees}
          selectedId={selectedId}
          onSelect={setSelectedId}
        />
```

Ajouter enfin, dans `ParticipationPanel.tsx` (Task 11), un bouton « Annuler le rejet » visible quand `participation.is_rejected` est vrai, appelant `apiClient.unrejectParticipationBenevole` — remplaçant le bouton « Signaler non conforme » dans ce cas (une entrée déjà rejetée n'a plus de raison de proposer de la re-rejeter) :

```tsx
          {participation.is_rejected ? (
            <Button variant="secondary" onClick={annulerLeRejet} disabled={enCoursRejet} style={{ width: "100%" }}>
              {enCoursRejet ? "Annulation…" : "Annuler le rejet"}
            </Button>
          ) : !confirmationRejet ? (
            /* … bouton « Signaler non conforme » existant … */
          ) : (
            /* … confirmation existante … */
          )}
```

avec la fonction correspondante, à côté de `signalerNonConforme` :

```tsx
  async function annulerLeRejet() {
    setErreurRejet(null);
    setEnCoursRejet(true);
    try {
      const resultat = await apiClient.unrejectParticipationBenevole(participation.id);
      onChanged(resultat);
    } catch (err) {
      gererErreur(err, setErreurRejet, "L'annulation a échoué. Réessayez plus tard.");
    } finally {
      setEnCoursRejet(false);
    }
  }
```

*(Note : ce dernier morceau appartient logiquement à la Task 11 — l'ajouter là en relisant le fichier avant de committer, pour ne pas dupliquer le JSX du bloc de rejet écrit à la Task 11.)*

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- ValidationQueue page.test ParticipationPanel`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/benevoles/ValidationQueue.tsx frontend/components/benevoles/ValidationQueue.test.tsx frontend/app/benevoles/page.tsx frontend/app/benevoles/page.test.tsx frontend/components/benevoles/ParticipationPanel.tsx
git commit -m "feat(frontend): onglet non-conformes et annulation du rejet (#437)"
```

---

## Task 13: Page athlète — badge « non conforme »

**Files:**
- Modify: `frontend/app/athletes/[id]/page.tsx` (ligne 114, `{p.is_pending_validation && <PendingBadge />}`)
- Test: `frontend/app/athletes/[id]/page.test.tsx`

**Interfaces:**
- Consumes: `PendingBadge` (Task 10)
- Produces: rien de plus — dernière tâche du plan.

- [ ] **Step 1: Write the failing test**

Ajouter dans `page.test.tsx` (adapter le nom exact de la fixture de participation utilisée dans ce fichier — vérifier en tête avant d'écrire) :

```typescript
  it("distingue une participation rejetée d'une simple attente", () => {
    render(await AthletePage({ params: Promise.resolve({ id: "1" }) }) /* … reprendre le patron existant du fichier … */);
    // Le badge affiché doit être "Non conforme", pas "En attente de validation",
    // pour la participation dont is_rejected est vrai.
    expect(screen.getByText(/non conforme/i)).toBeInTheDocument();
  });
```

*(Ce test doit reprendre exactement le patron de mock déjà en place dans `page.test.tsx` pour `apiServer.getAthlete` — le lire d'abord, l'ébauche ci-dessus n'est qu'indicative de l'assertion attendue.)*

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- app/athletes`
Expected: FAIL — le badge affiché reste « En attente de validation » quelle que soit la valeur de `is_rejected`.

- [ ] **Step 3: Write minimal implementation**

Dans `frontend/app/athletes/[id]/page.tsx`, ligne 114 :

```tsx
                      {p.is_pending_validation && <PendingBadge rejected={p.is_rejected} />}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- app/athletes`
Expected: PASS.

- [ ] **Step 5: Run the full frontend suite**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: PASS — aucune régression sur l'ensemble des tests, lint et build de production.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/athletes/\[id\]/page.tsx frontend/app/athletes/\[id\]/page.test.tsx
git commit -m "feat(frontend): badge non conforme sur la page athlète (#437)"
```

---

## Self-Review

- **Couverture de la spec** : modèle/invariant (Tasks 1-2), API (Tasks 3-8), frontend champs+reject (Tasks 9-11), frontend file/onglet (Task 12), badge athlète (Task 13), gestion d'erreurs (conflit dossard : Tasks 7-8-11 ; 404 sur non-actionnable : Tasks 3-8 ; validation client des champs numériques : le champ `type="number"` de la Task 11 délègue au navigateur, cohérent avec le niveau de validation déjà en place sur ce panneau — aucun champ existant du formulaire ne fait plus). Rien de la spec n'est sans tâche.
- **Placeholders** : aucun « TBD »/« TODO » ; les deux seules notes indicatives (Tasks 12 et 13) portent sur *où lire le patron exact avant d'écrire*, pas sur du code à deviner — elles pointent vers un fichier réel à consulter, jamais vers une décision laissée en suspens.
- **Cohérence des types** : `is_actionable_pending` (Task 3) est repris identiquement dans les Tasks 4 et 8 ; `_CHAMPS_PARTICIPATION` (Task 7) et `ParticipationFieldsUpdate` (Task 5) portent les 4 mêmes noms de champs (`bib_number`, `rank_overall`, `club`, `category`) jusqu'au bout de la chaîne frontend (Task 9 → 11).
