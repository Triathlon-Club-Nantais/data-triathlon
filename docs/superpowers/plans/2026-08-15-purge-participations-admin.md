# Purge totale des résultats (admin) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Donner à un porteur du pouvoir dédié un bouton back-office qui vide entièrement `participations`, purge les fiches `athlete` devenues orphelines, et force un rescrape immédiat — sans toucher `courses` ni `course_sources`.

**Architecture:** Suit exactement le patron de la suppression d'épreuve (#117, `admin_data.py` / `admin_actions.py`) : un endpoint d'impact en lecture pure, un endpoint de purge synchrone gardé par un pouvoir composable, une trace `admin_action_log_repository`. Côté front, une carte « zone dangereuse » sur le patron de `RevokeSessionsCard`, un dialog de confirmation sur le patron de `DeleteCourseDialog`, augmenté d'un champ « tapez SUPPRIMER ».

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (sync), Alembic, pytest ; Next.js 16, TanStack Query, shadcn/ui, Vitest + Testing Library.

**Spec:** Issue [#384](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/384) — le corps de l'issue *est* la spec, brainstormée et affinée le 2026-08-15 ; ce plan l'exécute sans réouvrir les décisions qu'elle tranche.

## Global Constraints

- **Français** pour tout ce qui est visible utilisateur ou métier (UI, messages d'erreur, docstrings de règle métier) ; **English** pour la couche technique invisible (identifiants, noms de fonctions techniques). Les tests sont en français dans ce dépôt (patron déjà en place) — on le suit.
- **TDD non-négociable** (Principe III) : chaque tâche écrit le test avant le code, le fait échouer, puis le fait passer.
- **Pas de compatibilité ascendante à préserver** : c'est du code neuf, aucun chemin de repli à garder.
- **`Course.scraped_at` doit devenir nullable** — actuellement `NOT NULL` en modèle *et* en base (migration initiale) ; sans la migration de la Tâche 1, l'`UPDATE ... SET scraped_at = NULL` de la Tâche 2 échouerait en PostgreSQL (silencieusement accepté en SQLite, donc invisible en test si on saute l'étape).
- **Le service `flush`, la route `commit`** (FR-015 du domaine #117) : l'action et sa trace au journal partagent la transaction du router, jamais un `db.commit()` dans `admin_actions.py`.
- **`admin_action_log_repository.create` reçoit un `payload` de compteurs, pas de listes d'ids** : à l'échelle d'une base entière (potentiellement des milliers d'athlètes), stocker chaque id purgé gonflerait le journal pour rien — contrairement à `delete_course`, dont le périmètre borné à une épreuve rend la liste lisible.
- **Aucune migration de schéma au-delà de la nullabilité de `scraped_at`** : le reste de la feature ne fait que des `DELETE`/`UPDATE` de masse sur un schéma inchangé.

---

### Task 1: `Course.scraped_at` devient nullable (modèle + migration Alembic)

**Files:**
- Modify: `backend/app/models/course.py:72`
- Create: `backend/alembic/versions/c9d0e1f2a3b4_scraped_at_nullable.py`
- Modify: `backend/tests/test_migrations.py`

**Interfaces:**
- Produces: `Course.scraped_at: datetime | None` — lu par `services/cache.is_fresh` (déjà prêt pour `None`, aucun changement là), et par la future `course_repository.reset_scraped_at_all` (Task 2).

- [ ] **Step 1: Écrire le test de montée/descente qui échoue**

Ajouter à la fin de `backend/tests/test_migrations.py` :

```python
# --- Purge totale des résultats (#384) ---------------------------------------

#: Révision qui précède immédiatement la nullabilité de `scraped_at`. **Nommée** :
#: un `-1` se décalerait à la première migration insérée entre-temps.
_BEFORE_SCRAPED_AT_NULLABLE = "05094fea3bc2"


def _nullable(url: str, table: str, column: str) -> bool:
    engine = sa.create_engine(url)
    try:
        colonnes = {c["name"]: c for c in sa.inspect(engine).get_columns(table)}
        return bool(colonnes[column]["nullable"])
    finally:
        engine.dispose()


def test_scraped_at_devient_nullable(sqlite_url):
    command.upgrade(_alembic_config(), "head")

    assert _nullable(sqlite_url, "courses", "scraped_at") is True


def test_downgrade_puis_upgrade_de_la_nullabilite_de_scraped_at(sqlite_url):
    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    command.downgrade(cfg, _BEFORE_SCRAPED_AT_NULLABLE)
    assert _nullable(sqlite_url, "courses", "scraped_at") is False

    command.upgrade(cfg, "head")
    assert _nullable(sqlite_url, "courses", "scraped_at") is True
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `cd backend && uv run pytest tests/test_migrations.py -k scraped_at_devient_nullable -v`
Expected: FAIL — `assert False is True` (la colonne est encore `NOT NULL`, la migration n'existe pas).

- [ ] **Step 3: Rendre la colonne nullable dans le modèle**

Dans `backend/app/models/course.py:72`, remplacer :

```python
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
```

par :

```python
    # Nullable depuis #384 : une purge totale des résultats remet ce champ à
    # `NULL` sur toute la base pour forcer un rescrape immédiat — `services/
    # cache.is_fresh` lit déjà `None` comme « jamais scrapée ».
    scraped_at: Mapped[datetime | None] = mapped_column(DateTime, default=utcnow, nullable=True)
```

- [ ] **Step 4: Écrire la migration Alembic**

Créer `backend/alembic/versions/c9d0e1f2a3b4_scraped_at_nullable.py` :

```python
"""scraped_at nullable sur courses — purge totale des résultats (#384)

Revision ID: c9d0e1f2a3b4
Revises: 05094fea3bc2
Create Date: 2026-08-15 18:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: str | None = "05094fea3bc2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    # La purge totale des résultats (#384) remet `scraped_at` à `NULL` sur
    # toute la base pour forcer un rescrape immédiat — `services/cache.is_fresh`
    # lit déjà `course.scraped_at is None` comme « jamais scrapée ». Sans cette
    # migration, l'`UPDATE` échouerait sur la contrainte `NOT NULL` en
    # PostgreSQL (silencieusement accepté en SQLite, donc invisible en test).
    op.alter_column("courses", "scraped_at", existing_type=sa.DateTime(), nullable=True)


def downgrade() -> None:
    op.alter_column("courses", "scraped_at", existing_type=sa.DateTime(), nullable=False)
```

- [ ] **Step 5: Lancer les tests, vérifier qu'ils passent**

Run: `cd backend && uv run pytest tests/test_migrations.py -v`
Expected: PASS — tous les tests de `test_migrations.py`, y compris les deux nouveaux.

- [ ] **Step 6: Vérifier que la suite complète reste verte**

Run: `cd backend && uv run pytest -m "not integration" -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
cd backend
git add app/models/course.py alembic/versions/c9d0e1f2a3b4_scraped_at_nullable.py tests/test_migrations.py
git commit -m "feat(backend): scraped_at devient nullable sur courses (#384)"
```

---

### Task 2: Repositories — compteurs et opérations de masse

**Files:**
- Modify: `backend/app/repositories/athlete_repository.py`
- Modify: `backend/app/repositories/participation_repository.py`
- Modify: `backend/app/repositories/course_repository.py`
- Modify: `backend/tests/test_repositories/test_athlete_repository.py`
- Modify: `backend/tests/test_repositories/test_participation_repository.py`
- Modify: `backend/tests/test_repositories/test_course_repository.py`

**Interfaces:**
- Consumes: rien de nouveau — s'appuie sur les modèles `Athlete`, `Participation`, `Course` déjà en place, et sur `athlete_repository.delete_orphans(db) -> int` (existant, réutilisé tel quel par la Task 5).
- Produces:
  - `athlete_repository.count_all(db: Session) -> int`
  - `participation_repository.count_all(db: Session) -> int`
  - `participation_repository.delete_all(db: Session) -> int`
  - `course_repository.reset_scraped_at_all(db: Session) -> int`

- [ ] **Step 1: Écrire les quatre tests qui échouent**

Dans `backend/tests/test_repositories/test_athlete_repository.py`, ajouter :

```python
def test_count_all_compte_toute_la_base(db_session):
    athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean")
    athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Paul")
    db_session.flush()

    assert athlete_repository.count_all(db_session) == 2
```

Dans `backend/tests/test_repositories/test_participation_repository.py`, ajouter :

```python
def test_count_all_compte_toutes_les_participations(db_session):
    athlete, course = _setup(db_session)
    other = athlete_repository.get_or_create(db_session, nom="MARTIN", prenom="Paul", club="TCN")
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1", club="TCN"
    )
    participation_repository.create(
        db_session, athlete_id=other.id, course_id=course.id, bib_number="2", club="TCN"
    )
    db_session.flush()

    assert participation_repository.count_all(db_session) == 2


def test_delete_all_vide_la_table_sans_toucher_aux_courses(db_session):
    athlete, course = _setup(db_session)
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1", club="TCN"
    )
    db_session.flush()

    efface = participation_repository.delete_all(db_session)

    assert efface == 1
    assert participation_repository.count_all(db_session) == 0
    assert course_repository.get(db_session, course.id) is not None
```

Dans `backend/tests/test_repositories/test_course_repository.py`, ajouter :

```python
def test_reset_scraped_at_all_remet_toutes_les_epreuves_a_null(db_session):
    a = course_repository.get_or_create(
        db_session, name="Tri A", event_date=date(2026, 5, 1), event_type="triathlon-m"
    )
    b = course_repository.get_or_create(
        db_session, name="Tri B", event_date=date(2026, 5, 2), event_type="triathlon-m"
    )
    course_repository.touch_scraped_at(db_session, a)
    course_repository.touch_scraped_at(db_session, b)
    db_session.flush()

    touchees = course_repository.reset_scraped_at_all(db_session)

    assert touchees == 2
    db_session.expire(a)
    db_session.expire(b)
    assert course_repository.get(db_session, a.id).scraped_at is None
    assert course_repository.get(db_session, b.id).scraped_at is None
```

(Vérifier que `date` et `course_repository` sont déjà importés en tête de `test_course_repository.py` — sinon les ajouter.)

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `cd backend && uv run pytest tests/test_repositories/test_athlete_repository.py tests/test_repositories/test_participation_repository.py tests/test_repositories/test_course_repository.py -k "count_all or delete_all or reset_scraped_at_all" -v`
Expected: FAIL — `AttributeError: module 'app.repositories.athlete_repository' has no attribute 'count_all'` (et pareil pour les deux autres).

- [ ] **Step 3: Implémenter `athlete_repository.count_all`**

Dans `backend/app/repositories/athlete_repository.py`, ajouter à la suite de `delete_orphans` :

```python
def count_all(db: Session) -> int:
    """Nombre total de fiches coureur en base (#384).

    Sert à chiffrer l'impact d'une purge totale des résultats **avant** de la
    commettre : vider `Participation` entièrement laisse *tout* athlète
    orphelin (`Participation.athlete_id` est sa seule FK, cf. `delete_orphans_among`
    ci-dessus), donc ce compte est exactement celui que `delete_orphans` purgera.
    """
    return db.query(func.count(Athlete.id)).scalar() or 0
```

- [ ] **Step 4: Implémenter `participation_repository.count_all` et `delete_all`**

Dans `backend/app/repositories/participation_repository.py`, ajouter à la suite de `count_for_course`/`delete_for_course` :

```python
def count_all(db: Session) -> int:
    """Nombre total de participations en base (#384)."""
    return db.query(func.count(Participation.id)).scalar() or 0


def delete_all(db: Session) -> int:
    """Supprime **toutes** les participations de la base. Rend le nombre effacé (#384).

    Patron de `delete_for_course`, sans filtre : une purge totale n'a pas de
    course à périmer une par une — `Course` et `course_sources` restent
    strictement intacts, seule `participations` se vide.
    """
    efface = db.query(Participation).delete(synchronize_session=False)
    db.flush()
    return efface
```

- [ ] **Step 5: Implémenter `course_repository.reset_scraped_at_all`**

Dans `backend/app/repositories/course_repository.py`, ajouter à la suite de `touch_scraped_at` :

```python
def reset_scraped_at_all(db: Session) -> int:
    """Remet `scraped_at` à `NULL` sur **toutes** les épreuves. Rend le nombre touché (#384).

    `services/cache.is_fresh` lit `scraped_at is None` comme « jamais
    scrapée » : après une purge totale des résultats, ceci force un rescrape
    immédiat au lieu de laisser le TTL masquer la base vide jusqu'à 30 jours.

    ponytail: `iter_all(older_than_days=...)` filtre sur `Course.scraped_at <
    cutoff`, et `NULL` n'y matche jamais côté SQL — un rescrape en masse par
    CLI avec `--older-than-days` ne retrouvera donc pas ces épreuves tant
    qu'elles n'ont pas été re-scrapées au moins une fois. Sans incidence sur
    le geste back-office (aucun filtre d'ancienneté ici) ; à garder en tête si
    un usage CLI de cette purge apparaît un jour.
    """
    touchees = db.query(Course).update({Course.scraped_at: None}, synchronize_session=False)
    db.flush()
    return touchees
```

- [ ] **Step 6: Lancer les tests, vérifier qu'ils passent**

Run: `cd backend && uv run pytest tests/test_repositories/test_athlete_repository.py tests/test_repositories/test_participation_repository.py tests/test_repositories/test_course_repository.py -v`
Expected: PASS.

- [ ] **Step 7: Lint et suite complète**

Run: `cd backend && uv run ruff check . && uv run pytest -m "not integration"`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
cd backend
git add app/repositories/athlete_repository.py app/repositories/participation_repository.py \
        app/repositories/course_repository.py tests/test_repositories/
git commit -m "feat(backend): compteurs et purge de masse pour participations/athletes/courses (#384)"
```

---

### Task 3: Pouvoir composable `participations:wipe_all`

**Files:**
- Modify: `backend/app/core/permissions.py`
- Modify: `backend/tests/test_api/test_admin_data_api.py` (un test d'inventaire, sur le patron de `test_le_pouvoir_de_suppression_est_offert_a_la_composition_des_roles`)

**Interfaces:**
- Produces: `P.PARTICIPATIONS_WIPE_ALL` (code `"participations:wipe_all"`), consommé par le routeur de la Task 6.

> Ce pouvoir ne peut pas encore être **cité** par une garde à ce stade (elle arrive Task 6) : `tests/test_permissions_catalogue.py` exige que chaque pouvoir du catalogue soit gardé par au moins une ressource. **Cette tâche seule laissera donc `test_permissions_catalogue.py` rouge** — c'est attendu, il revient au vert à la fin de la Task 6. Ne pas s'arrêter dessus entre les deux tâches.

- [ ] **Step 1: Écrire le test d'inventaire qui échoue**

Dans `backend/tests/test_api/test_admin_data_api.py`, à la suite de `test_le_pouvoir_de_suppression_est_offert_a_la_composition_des_roles` :

```python
def test_le_pouvoir_de_purge_totale_est_offert_a_la_composition_des_roles(client):
    """#384 — même garde-fou que pour `courses:delete`."""
    groupes = client.get("/api/v1/admin/permissions").json()

    resultats = next(g for g in groupes if g["feature"] == "Résultats")
    codes = {p["code"] for p in resultats["permissions"]}
    assert "participations:wipe_all" in codes
    libelle = next(p for p in resultats["permissions"] if p["code"] == "participations:wipe_all")
    assert libelle["label"] == "Purger tous les résultats"
```

- [ ] **Step 2: Lancer le test, vérifier qu'il échoue**

Run: `cd backend && uv run pytest tests/test_api/test_admin_data_api.py -k purge_totale_est_offert -v`
Expected: FAIL — `StopIteration` (le code `"participations:wipe_all"` n'existe pas encore dans l'inventaire).

- [ ] **Step 3: Ajouter le pouvoir au catalogue**

Dans `backend/app/core/permissions.py`, à la suite de `PARTICIPATIONS_REASSIGN` (ligne ~189) :

```python
    PARTICIPATIONS_WIPE_ALL = Permission(
        "participations:wipe_all",
        "Purger tous les résultats",
        "Vider entièrement la base des résultats pour repartir d'une base "
        "propre — par exemple avant un rescrape complet suite à un "
        "changement de logique d'import. Les épreuves et leurs sources "
        "restent intactes.",
        FEATURE_PARTICIPATIONS,
    )
```

Et l'ajouter au tuple `ALL` (ligne ~244), juste après `P.PARTICIPATIONS_REASSIGN` :

```python
    P.PARTICIPATIONS_DELETE,
    P.PARTICIPATIONS_REASSIGN,
    P.PARTICIPATIONS_WIPE_ALL,
    P.BATCH_RUN,
```

- [ ] **Step 4: Lancer le test d'inventaire, vérifier qu'il passe**

Run: `cd backend && uv run pytest tests/test_api/test_admin_data_api.py -k purge_totale_est_offert -v`
Expected: PASS.

- [ ] **Step 5: Confirmer que `test_permissions_catalogue.py` est rouge pour la bonne raison (attendu à ce stade)**

Run: `cd backend && uv run pytest tests/test_permissions_catalogue.py -v`
Expected: FAIL sur `test_chaque_pouvoir_du_catalogue_garde_au_moins_une_ressource` (aucune garde ne cite encore `participations:wipe_all`). Aucun autre test du fichier ne doit rougir.

- [ ] **Step 6: Commit**

```bash
cd backend
git add app/core/permissions.py tests/test_api/test_admin_data_api.py
git commit -m "feat(backend): pouvoir composable participations:wipe_all (#384)"
```

---

### Task 4: Schéma `ParticipationsWipeImpact`

**Files:**
- Modify: `backend/app/schemas/admin.py`

**Interfaces:**
- Produces: `ParticipationsWipeImpact(BaseModel)` avec `participations: int`, `athletes: int` — `response_model` de l'endpoint d'impact (Task 6).

- [ ] **Step 1: Ajouter le schéma**

Dans `backend/app/schemas/admin.py`, à la suite de la classe `CourseDeletionImpact` (ligne ~348) :

```python
class ParticipationsWipeImpact(BaseModel):
    """Ce qu'une purge totale des résultats détruirait, chiffré avant le geste (#384).

    `athletes` est le compte total de fiches coureur : vider `participations`
    entièrement laisse *toute* fiche orpheline (`Participation.athlete_id` en
    est la seule FK), donc c'est le compte de la table entière, pas seulement
    des coureurs inscrits quelque part.
    """

    participations: int
    athletes: int
```

Pas de test dédié pour cette étape seule : elle n'a pas de comportement observable avant d'être branchée sur le service (Task 5) et le routeur (Task 6), qui la couvrent.

- [ ] **Step 2: Vérifier que le module s'importe sans erreur**

Run: `cd backend && uv run python -c "from app.schemas.admin import ParticipationsWipeImpact; print(ParticipationsWipeImpact(participations=1, athletes=1))"`
Expected: affiche `participations=1 athletes=1` sans traceback.

- [ ] **Step 3: Commit**

```bash
cd backend
git add app/schemas/admin.py
git commit -m "feat(backend): schema ParticipationsWipeImpact (#384)"
```

---

### Task 5: Service — `wipe_impact` et `wipe_all_participations`

**Files:**
- Modify: `backend/app/services/admin_actions.py`
- Modify: `backend/tests/test_services/test_admin_actions.py`

**Interfaces:**
- Consumes: `participation_repository.count_all`, `participation_repository.delete_all`, `athlete_repository.count_all`, `athlete_repository.delete_orphans` (existant), `course_repository.reset_scraped_at_all` (tous de la Task 2) ; `admin_action_log_repository.create` (existant).
- Produces:
  - `admin_actions.wipe_impact(db: Session) -> dict` — `{"participations": int, "athletes": int}`, lecture pure.
  - `admin_actions.wipe_all_participations(db: Session, *, user_id: int) -> dict` — `{"participations_deleted": int, "athletes_purged": int, "courses_reset": int}`, **`flush` seulement, jamais `commit`**.

- [ ] **Step 1: Écrire les tests de service qui échouent**

Dans `backend/tests/test_services/test_admin_actions.py`, ajouter (après les tests de `delete_course`, avant ceux de `switch_course_source` ou en fin de fichier — peu importe l'ordre, ils ne dépendent de rien d'autre) :

```python
def _epreuve_avec_resultat(db_session, nom, dossard, event_date=date(2026, 5, 17)):
    """Une épreuve, un athlète, une participation, `scraped_at` posé — pour la purge.

    `participation_repository` est déjà importé en tête de ce fichier."""
    course = _epreuve(db_session, nom, event_date)
    athlete = _coureur(db_session, "COUREUR", "Jean")
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number=dossard, club="TCN"
    )
    course_repository.touch_scraped_at(db_session, course)
    db_session.flush()
    return course, athlete


def test_wipe_impact_chiffre_participations_et_athletes(db_session):
    _epreuve_avec_resultat(db_session, "Tri A", "1")
    _epreuve_avec_resultat(db_session, "Tri B", "2")

    impact = admin_actions.wipe_impact(db_session)

    assert impact == {"participations": 2, "athletes": 2}


def test_wipe_impact_ne_modifie_rien(db_session):
    _epreuve_avec_resultat(db_session, "Tri A", "1")

    admin_actions.wipe_impact(db_session)

    assert participation_repository.count_all(db_session) == 1
    assert athlete_repository.count_all(db_session) == 1


def test_wipe_all_participations_vide_la_table_et_laisse_les_courses_intactes(
    db_session, auteur
):
    course_a, _ = _epreuve_avec_resultat(db_session, "Tri A", "1")
    course_b, _ = _epreuve_avec_resultat(db_session, "Tri B", "2")

    resume = admin_actions.wipe_all_participations(db_session, user_id=auteur.id)

    assert resume == {
        "participations_deleted": 2,
        "athletes_purged": 2,
        "courses_reset": 2,
    }
    assert participation_repository.count_all(db_session) == 0
    assert athlete_repository.count_all(db_session) == 0
    assert course_repository.get(db_session, course_a.id) is not None
    assert course_repository.get(db_session, course_b.id) is not None


def test_wipe_all_participations_remet_scraped_at_a_null(db_session, auteur):
    course, _ = _epreuve_avec_resultat(db_session, "Tri A", "1")
    assert course.scraped_at is not None

    admin_actions.wipe_all_participations(db_session, user_id=auteur.id)

    db_session.expire(course)
    assert course_repository.get(db_session, course.id).scraped_at is None


def test_wipe_all_participations_consigne_le_geste(db_session, auteur):
    """Le journal ne garde que les deux compteurs annoncés par `wipe_impact` — pas
    `courses_reset`, absent de la spec de l'issue #384 (« payload = les deux
    compteurs »), même s'il reste dans la valeur de retour pour l'appelant."""
    _epreuve_avec_resultat(db_session, "Tri A", "1")

    admin_actions.wipe_all_participations(db_session, user_id=auteur.id)

    entrees = _journal(db_session, "participations", 0)
    assert [e.action for e in entrees] == ["participations.wipe_all"]
    assert entrees[0].payload == {"participations_deleted": 1, "athletes_purged": 1}


def test_wipe_all_participations_sur_base_vide_ne_consigne_rien_a_tort(db_session, auteur):
    """Une base déjà vide reste un geste réel (compteurs à 0), pas un no-op tu."""
    resume = admin_actions.wipe_all_participations(db_session, user_id=auteur.id)

    assert resume == {"participations_deleted": 0, "athletes_purged": 0, "courses_reset": 0}
    entrees = _journal(db_session, "participations", 0)
    assert [e.action for e in entrees] == ["participations.wipe_all"]
```

Vérifier en tête de fichier que `participation_repository` et `athlete_repository` sont importés (ils le sont déjà, cf. imports de tête du fichier) et que `date` l'est aussi.

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `cd backend && uv run pytest tests/test_services/test_admin_actions.py -k wipe -v`
Expected: FAIL — `AttributeError: module 'app.services.admin_actions' has no attribute 'wipe_impact'`.

- [ ] **Step 3: Implémenter le service**

Dans `backend/app/services/admin_actions.py`, ajouter à la suite de `delete_course` (après la ligne 129) :

```python
def wipe_impact(db: Session) -> dict:
    """Ce qu'une purge totale des résultats détruirait. **Ne modifie rien** (#384).

    Même principe que `course_deletion_impact` : `athletes` vient de la
    **même** lecture que celle sur laquelle s'appuiera la purge (le compte
    total de la table), pour que l'annonce et l'acte ne puissent pas diverger
    à base constante.
    """
    return {
        "participations": participation_repository.count_all(db),
        "athletes": athlete_repository.count_all(db),
    }


def wipe_all_participations(db: Session, *, user_id: int) -> dict:
    """Vide `participations`, purge les fiches devenues vides, force un rescrape (#384).

    **`Course` et `course_sources` restent strictement intacts** — c'est ce
    qui permet de relancer un rescrape sans tout réimporter depuis les URLs
    sources. `scraped_at` est remis à `NULL` sur toute la base pour que le
    cache TTL ne masque pas ce rescrape immédiat.

    Contrairement à `delete_course`, le journal ne garde que des **comptes**,
    jamais la liste des ids purgés : à l'échelle de la base entière, cette
    liste peut porter des milliers d'entrées, et gonflerait le journal d'audit
    pour un geste qui n'a par nature qu'un seul lecteur (« combien la dernière
    purge a-t-elle emporté »).
    """
    resume = {"participations_deleted": participation_repository.count_all(db)}
    participation_repository.delete_all(db)
    resume["athletes_purged"] = athlete_repository.delete_orphans(db)
    resume["courses_reset"] = course_repository.reset_scraped_at_all(db)

    admin_action_log_repository.create(
        db,
        user_id=user_id,
        action="participations.wipe_all",
        entity_type="participations",
        entity_id=0,  # sentinelle « base entière » — aucune entité unique à désigner
        # Les deux compteurs annoncés par `wipe_impact` (#384) — pas
        # `courses_reset` : la spec de l'issue borne le payload à ce que la
        # confirmation a chiffré, et `resume` (la valeur de retour) le garde
        # pour l'appelant qui en aurait besoin.
        payload={
            "participations_deleted": resume["participations_deleted"],
            "athletes_purged": resume["athletes_purged"],
        },
    )
    logger.info(
        "Admin %s wiped all participations (%s deleted, %s athletes purged, %s courses reset)",
        user_id,
        resume["participations_deleted"],
        resume["athletes_purged"],
        resume["courses_reset"],
    )
    return resume
```

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `cd backend && uv run pytest tests/test_services/test_admin_actions.py -v`
Expected: PASS — tous les tests du fichier, y compris les nouveaux.

- [ ] **Step 5: Lint et suite complète**

Run: `cd backend && uv run ruff check . && uv run pytest -m "not integration"`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd backend
git add app/services/admin_actions.py tests/test_services/test_admin_actions.py
git commit -m "feat(backend): service de purge totale des resultats (#384)"
```

---

### Task 6: Router — `GET /admin/participations/wipe-impact` et `DELETE /admin/participations`

**Files:**
- Modify: `backend/app/api/v1/admin_data.py`
- Modify: `backend/tests/test_api/test_admin_data_api.py`

**Interfaces:**
- Consumes: `admin_actions.wipe_impact`, `admin_actions.wipe_all_participations` (Task 5) ; `P.PARTICIPATIONS_WIPE_ALL` (Task 3) ; `ParticipationsWipeImpact` (Task 4).
- Produces: les deux routes HTTP, gardées par `require_permission(P.PARTICIPATIONS_WIPE_ALL)`.

- [ ] **Step 1: Écrire les tests API qui échouent**

Dans `backend/tests/test_api/test_admin_data_api.py`, ajouter une fixture et un bloc de tests après celui de `courses:delete` (après la ligne ~209, avant `# --- POST /admin/participations/{id}/reassign`) :

```python
@pytest.fixture
def base_avec_resultats(db_session):
    """Deux épreuves, chacune un résultat — pour chiffrer et purger la base entière."""
    a = course_repository.get_or_create(
        db_session, name="Tri A", event_date=date(2026, 5, 1),
        event_type="triathlon-m", source_url="https://k/a", provider="klikego",
    )
    b = course_repository.get_or_create(
        db_session, name="Tri B", event_date=date(2026, 5, 2),
        event_type="triathlon-m", source_url="https://k/b", provider="klikego",
    )
    db_session.flush()
    jean = athlete_repository.get_or_create(db_session, nom="COUREUR", prenom="Jean")
    paul = athlete_repository.get_or_create(db_session, nom="COUREUR", prenom="Paul")
    db_session.flush()
    participation_repository.create(db_session, athlete_id=jean.id, course_id=a.id, bib_number="1")
    participation_repository.create(db_session, athlete_id=paul.id, course_id=b.id, bib_number="1")
    course_repository.touch_scraped_at(db_session, a)
    course_repository.touch_scraped_at(db_session, b)
    db_session.commit()
    return a, b


# --- GET /admin/participations/wipe-impact -----------------------------------


def test_l_impact_de_purge_chiffre_participations_et_athletes(client, base_avec_resultats):
    reponse = client.get("/api/v1/admin/participations/wipe-impact")

    assert reponse.status_code == 200
    assert reponse.json() == {"participations": 2, "athletes": 2}


def test_l_impact_de_purge_ne_modifie_rien(client, base_avec_resultats, db_session):
    client.get("/api/v1/admin/participations/wipe-impact")

    assert participation_repository.count_all(db_session) == 2


def test_l_impact_de_purge_sans_session_rend_401(client, base_avec_resultats):
    client.cookies.clear()

    assert client.get("/api/v1/admin/participations/wipe-impact").status_code == 401


def test_l_impact_de_purge_sans_le_pouvoir_rend_403(client, db_session, base_avec_resultats):
    _session_etroite(client, db_session)

    assert client.get("/api/v1/admin/participations/wipe-impact").status_code == 403


# --- DELETE /admin/participations ---------------------------------------------


def test_purger_rend_204_et_vide_la_table(client, db_session, base_avec_resultats):
    reponse = client.delete("/api/v1/admin/participations")

    assert reponse.status_code == 204
    assert reponse.content == b""
    assert participation_repository.count_all(db_session) == 0


def test_purger_laisse_courses_et_sources_intacts(client, db_session, base_avec_resultats):
    from app.repositories import course_source_repository

    a, b = base_avec_resultats

    client.delete("/api/v1/admin/participations")

    assert course_repository.get(db_session, a.id) is not None
    assert course_repository.get(db_session, b.id) is not None
    assert len(course_source_repository.list_for_course(db_session, a.id)) == 1
    assert len(course_source_repository.list_for_course(db_session, b.id)) == 1


def test_purger_remet_scraped_at_a_null_sur_toutes_les_epreuves(
    client, db_session, base_avec_resultats
):
    a, b = base_avec_resultats

    client.delete("/api/v1/admin/participations")

    db_session.expire(a)
    db_session.expire(b)
    assert course_repository.get(db_session, a.id).scraped_at is None
    assert course_repository.get(db_session, b.id).scraped_at is None


def test_purger_supprime_les_fiches_devenues_orphelines(client, db_session, base_avec_resultats):
    jean = athlete_repository.get_by_identity(db_session, nom="COUREUR", prenom="Jean", birth_date=None)
    jean_id = jean.id

    client.delete("/api/v1/admin/participations")

    assert athlete_repository.get(db_session, jean_id) is None


def test_purger_consigne_le_geste(client, db_session, base_avec_resultats):
    from app.repositories import admin_action_log_repository

    client.delete("/api/v1/admin/participations")

    entrees = admin_action_log_repository.list_for_entity(
        db_session, entity_type="participations", entity_id=0
    )
    assert [e.action for e in entrees] == ["participations.wipe_all"]
    assert entrees[0].payload["participations_deleted"] == 2


def test_purger_sans_session_rend_401(client, base_avec_resultats):
    client.cookies.clear()

    assert client.delete("/api/v1/admin/participations").status_code == 401


def test_purger_sans_le_pouvoir_rend_403(client, db_session, base_avec_resultats):
    _session_etroite(client, db_session)

    assert client.delete("/api/v1/admin/participations").status_code == 403


def test_purger_avec_le_seul_pouvoir_utile_reussit(client, db_session, base_avec_resultats):
    _session_etroite(client, db_session, P.PARTICIPATIONS_WIPE_ALL)

    assert client.delete("/api/v1/admin/participations").status_code == 204


def test_un_refus_de_pouvoir_ne_purge_rien(client, db_session, base_avec_resultats):
    """FR-015 — un 403 laisse la base strictement inchangée."""
    _session_etroite(client, db_session)

    client.delete("/api/v1/admin/participations")

    assert participation_repository.count_all(db_session) == 2
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `cd backend && uv run pytest tests/test_api/test_admin_data_api.py -k "purge or purger" -v`
Expected: FAIL — 404 (routes inexistantes) sur les nouveaux tests.

- [ ] **Step 3: Ajouter les deux routes**

Dans `backend/app/api/v1/admin_data.py` :

Ajouter `ParticipationsWipeImpact` à l'import de `app.schemas.admin` (ligne ~22-28) :

```python
from app.schemas.admin import (
    AdminAthleteRead,
    AdminAthleteUpdate,
    AdminCourseUpdate,
    CourseDeletionImpact,
    ParticipationReassign,
    ParticipationsWipeImpact,
)
```

Puis ajouter les deux routes, à la suite de `delete_course` (après la ligne 140, avant `update_athlete`) :

```python
@router.get("/admin/participations/wipe-impact", response_model=ParticipationsWipeImpact)
def participations_wipe_impact(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.PARTICIPATIONS_WIPE_ALL)),
):
    """Chiffre l'ampleur d'une purge totale des résultats **avant** de la commettre (#384).

    Gardée par `participations:wipe_all` et non par un pouvoir de lecture,
    même logique que `course_deletion_impact` : qui peut détruire peut
    mesurer, l'inverse n'aurait pas d'usage.
    """
    return admin_actions.wipe_impact(db)


@router.delete("/admin/participations", status_code=204)
def wipe_all_participations(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(P.PARTICIPATIONS_WIPE_ALL)),
):
    """Vide `participations`, purge les fiches devenues vides, force un rescrape (#384).

    `Course` et `course_sources` restent intacts. Irréversible et sans corps
    de réponse : ce qui reste du geste est son entrée au journal.
    """
    admin_actions.wipe_all_participations(db, user_id=user.id)
    db.commit()
```

- [ ] **Step 4: Lancer les tests API, vérifier qu'ils passent**

Run: `cd backend && uv run pytest tests/test_api/test_admin_data_api.py -v`
Expected: PASS — tous les tests du fichier.

- [ ] **Step 5: Vérifier que le catalogue de pouvoirs redevient vert**

Run: `cd backend && uv run pytest tests/test_permissions_catalogue.py -v`
Expected: PASS — `participations:wipe_all` est désormais cité par une garde.

- [ ] **Step 6: Lint et suite complète**

Run: `cd backend && uv run ruff check . && uv run pytest -m "not integration"`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
cd backend
git add app/api/v1/admin_data.py tests/test_api/test_admin_data_api.py
git commit -m "feat(backend): endpoints de purge totale des resultats (#384)"
```

---

### Task 7: Frontend — types, client API, clés de cache, hooks

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api/client.ts`
- Modify: `frontend/lib/queries/keys.ts`
- Modify: `frontend/lib/queries/admin.ts`

**Interfaces:**
- Produces:
  - `ParticipationsWipeImpact` (type) — `{ participations: number; athletes: number }`.
  - `apiClient.getParticipationsWipeImpact(): Promise<ParticipationsWipeImpact>`
  - `apiClient.wipeAllParticipations(): Promise<null>`
  - `queryKeys.participationsWipeImpact(): readonly ["participations-wipe-impact"]`
  - `useParticipationsWipeImpact(enabled: boolean)` — hook TanStack Query.
  - `useWipeAllParticipations()` — hook TanStack Query (mutation).

Pas de comportement observable isolément (pas de composant qui les consomme encore) — cette tâche n'a donc pas de test dédié à écrire en premier ; elle est vérifiée par le `tsc`/build et couverte de bout en bout par le test de composant de la Task 9. C'est la même situation que la Task 4 côté backend.

- [ ] **Step 1: Ajouter le type**

Dans `frontend/lib/types.ts`, à la suite de l'interface `CourseDeletionImpact` :

```typescript
/**
 * Ce qu'une purge totale des résultats détruirait (#384).
 *
 * `athletes` est le compte total de fiches coureur : vider `participations`
 * entièrement laisse *toute* fiche orpheline, donc c'est le compte de la
 * table entière, pas seulement des coureurs inscrits quelque part.
 */
export interface ParticipationsWipeImpact {
  participations: number;
  athletes: number;
}
```

- [ ] **Step 2: Ajouter les deux appels au client API**

Dans `frontend/lib/api/client.ts`, à la suite de `deleteCourse` (après la ligne ~182) :

```typescript
  // ── Purge totale des résultats (#384) ──────────────────────────────────────
  // `participations:wipe_all`. Vide `participations` entièrement ; `courses`
  // et `course_sources` restent intacts — c'est ce qui permet un rescrape
  // immédiat sans tout réimporter depuis les URLs sources.
  getParticipationsWipeImpact: () =>
    request<ParticipationsWipeImpact>("/admin/participations/wipe-impact"),
  wipeAllParticipations: () =>
    request<null>("/admin/participations", { method: "DELETE" }),
```

Ajouter `ParticipationsWipeImpact` à l'import de types en tête du fichier (à côté de `CourseDeletionImpact`).

- [ ] **Step 3: Ajouter la clé de cache**

Dans `frontend/lib/queries/keys.ts`, à la suite de `courseDeletionImpact` :

```typescript
  participationsWipeImpact: () => ["participations-wipe-impact"] as const,
```

- [ ] **Step 4: Ajouter les deux hooks**

Dans `frontend/lib/queries/admin.ts`, à la suite de `useDeleteCourse` :

```typescript
/**
 * Ce qu'une purge totale des résultats détruirait — chargé **à l'ouverture
 * de la modale** (#384), même patron que `useCourseDeletionImpact`.
 */
export function useParticipationsWipeImpact(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.participationsWipeImpact(),
    queryFn: () => apiClient.getParticipationsWipeImpact(),
    enabled,
    retry: false,
  });
}

/**
 * La purge totale des résultats (#384). Invalide tout ce qu'un résultat
 * alimente : le catalogue d'épreuves (leur `scraped_at` vient de changer),
 * le détail d'une épreuve, les fiches coureur, et les résultats publics.
 */
export function useWipeAllParticipations() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.wipeAllParticipations(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.courses });
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.detailEpreuve });
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.coureurs });
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.resultatsPublics });
    },
  });
}
```

- [ ] **Step 5: Vérifier que le projet compile toujours**

Run: `cd frontend && npx tsc --noEmit`
Expected: aucune erreur.

- [ ] **Step 6: Commit**

```bash
cd frontend
git add lib/types.ts lib/api/client.ts lib/queries/keys.ts lib/queries/admin.ts
git commit -m "feat(frontend): client et hooks de purge totale des resultats (#384)"
```

---

### Task 8: Frontend — `WipeParticipationsCard` et intégration dans `/admin/courses`

**Files:**
- Create: `frontend/components/admin/WipeParticipationsCard.tsx`
- Modify: `frontend/app/admin/courses/page.tsx`
- Create: `frontend/components/admin/WipeParticipationsCard.test.tsx`

**Interfaces:**
- Consumes: `useParticipationsWipeImpact`, `useWipeAllParticipations` (Task 7) ; `useSession` (`@/lib/queries/auth`, existant).
- Produces: `WipeParticipationsCard()` — composant client sans props, s'auto-masque si la session ne porte pas `participations:wipe_all` (même convention que `CoursesAdminTable`).

- [ ] **Step 1: Écrire le test de composant qui échoue**

Créer `frontend/components/admin/WipeParticipationsCard.test.tsx` :

```typescript
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { SessionUser } from "@/lib/types";

const { getParticipationsWipeImpact, wipeAllParticipations, getSession, toastError, toastSuccess } =
  vi.hoisted(() => ({
    getParticipationsWipeImpact: vi.fn(),
    wipeAllParticipations: vi.fn(),
    getSession: vi.fn(),
    toastError: vi.fn(),
    toastSuccess: vi.fn(),
  }));

vi.mock("sonner", () => ({ toast: { error: toastError, success: toastSuccess } }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { getParticipationsWipeImpact, wipeAllParticipations, getSession },
  };
});

import { WipeParticipationsCard } from "./WipeParticipationsCard";

function session(permissions: string[]): SessionUser {
  return {
    id: 1,
    email: "admin@exemple.fr",
    display_name: "Admin",
    created_at: "2026-01-01T00:00:00Z",
    permissions,
    roles: [],
    groups: [],
  };
}

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <WipeParticipationsCard />
    </QueryClientProvider>,
  );
}

describe("WipeParticipationsCard (#384)", () => {
  beforeEach(() => {
    getParticipationsWipeImpact.mockReset();
    wipeAllParticipations.mockReset();
    getSession.mockReset();
    toastError.mockReset();
    toastSuccess.mockReset();
  });

  it("reste invisible sans le pouvoir", async () => {
    getSession.mockResolvedValue(session([]));

    afficher();

    await waitFor(() => expect(getSession).toHaveBeenCalled());
    expect(screen.queryByText(/zone dangereuse/i)).not.toBeInTheDocument();
  });

  it("propose le geste au porteur du pouvoir", async () => {
    getSession.mockResolvedValue(session(["participations:wipe_all"]));

    afficher();

    expect(await screen.findByText(/zone dangereuse/i)).toBeInTheDocument();
  });

  it("le bouton de confirmation reste désactivé sans avoir tapé SUPPRIMER", async () => {
    getSession.mockResolvedValue(session(["participations:wipe_all"]));
    getParticipationsWipeImpact.mockResolvedValue({ participations: 412, athletes: 37 });

    afficher();
    await userEvent.click(await screen.findByRole("button", { name: /purger tous les résultats/i }));
    await screen.findByText(/412/);

    expect(screen.getByRole("button", { name: /purger définitivement/i })).toBeDisabled();
  });

  it("s'active une fois SUPPRIMER tapé, et purge à la confirmation", async () => {
    getSession.mockResolvedValue(session(["participations:wipe_all"]));
    getParticipationsWipeImpact.mockResolvedValue({ participations: 412, athletes: 37 });
    wipeAllParticipations.mockResolvedValue(null);

    afficher();
    await userEvent.click(await screen.findByRole("button", { name: /purger tous les résultats/i }));
    await screen.findByText(/412/);
    await userEvent.type(screen.getByLabelText(/tapez/i), "SUPPRIMER");

    await userEvent.click(screen.getByRole("button", { name: /purger définitivement/i }));

    await waitFor(() => expect(wipeAllParticipations).toHaveBeenCalled());
    expect(toastSuccess).toHaveBeenCalled();
  });

  it("une saisie approximative ne suffit pas", async () => {
    getSession.mockResolvedValue(session(["participations:wipe_all"]));
    getParticipationsWipeImpact.mockResolvedValue({ participations: 412, athletes: 37 });

    afficher();
    await userEvent.click(await screen.findByRole("button", { name: /purger tous les résultats/i }));
    await screen.findByText(/412/);
    await userEvent.type(screen.getByLabelText(/tapez/i), "supprimer");

    expect(screen.getByRole("button", { name: /purger définitivement/i })).toBeDisabled();
  });

  it("dit en français qu'un refus de droits a bloqué la purge", async () => {
    getSession.mockResolvedValue(session(["participations:wipe_all"]));
    getParticipationsWipeImpact.mockResolvedValue({ participations: 3, athletes: 1 });
    wipeAllParticipations.mockRejectedValue(
      new ApiError(403, "Vous n'avez pas les droits nécessaires."),
    );

    afficher();
    await userEvent.click(await screen.findByRole("button", { name: /purger tous les résultats/i }));
    await screen.findByText(/^3$|3 résultat/);
    await userEvent.type(screen.getByLabelText(/tapez/i), "SUPPRIMER");
    await userEvent.click(screen.getByRole("button", { name: /purger définitivement/i }));

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("Vous n'avez pas les droits nécessaires."),
    );
  });

  it("n'offre aucune annulation : le geste est irréversible", async () => {
    getSession.mockResolvedValue(session(["participations:wipe_all"]));
    getParticipationsWipeImpact.mockResolvedValue({ participations: 3, athletes: 1 });

    afficher();
    await userEvent.click(await screen.findByRole("button", { name: /purger tous les résultats/i }));

    expect(await screen.findByText(/irréversible/i)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /annuler la purge|rétablir|restaurer/i }),
    ).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Lancer le test, vérifier qu'il échoue**

Run: `cd frontend && npx vitest run components/admin/WipeParticipationsCard.test.tsx`
Expected: FAIL — `Cannot find module './WipeParticipationsCard'`.

- [ ] **Step 3: Écrire le composant**

Créer `frontend/components/admin/WipeParticipationsCard.tsx` :

```tsx
"use client";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useParticipationsWipeImpact, useWipeAllParticipations } from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";

//: Le mot à taper pour activer la confirmation — la portée est la base
//: entière, pas une épreuve, d'où ce garde-fou renforcé par rapport à
//: `DeleteCourseDialog` (#384).
const MOT_DE_CONFIRMATION = "SUPPRIMER";

/**
 * Repartir d'une base de résultats propre (#384) — par exemple avant un
 * rescrape complet suite à un changement de logique d'import.
 *
 * Vit au bas de `/admin/courses`, sur le patron de `RevokeSessionsCard` :
 * un unique bouton ne justifie pas un écran ni une entrée de navigation
 * dédiés. `Course` et `course_sources` restent intacts — c'est ce qui rend
 * un rescrape possible juste après, sans tout réimporter depuis les URLs
 * sources.
 *
 * **Le serveur reste seul juge** (FR-009 du domaine #115) : ce test de
 * pouvoir n'autorise rien, il évite de proposer un bouton qui rendrait 403.
 */
export function WipeParticipationsCard() {
  const [ouvert, setOuvert] = useState(false);
  const [saisie, setSaisie] = useState("");
  const session = useSession();
  const impact = useParticipationsWipeImpact(ouvert);
  const purge = useWipeAllParticipations();

  const peutPurger = session.data?.permissions.includes("participations:wipe_all") ?? false;
  if (!peutPurger) return null;

  function fermer(prochain: boolean) {
    setOuvert(prochain);
    if (!prochain) setSaisie("");
  }

  async function confirmer() {
    try {
      await purge.mutateAsync();
      toast.success("Tous les résultats ont été supprimés.");
      fermer(false);
    } catch (erreur) {
      toast.error((erreur as Error).message);
    }
  }

  return (
    <>
      <Card className="border-destructive/40">
        <CardHeader>
          <CardTitle>Zone dangereuse</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-[var(--tcn-text-faint)] text-sm">
            Vide entièrement les résultats pour repartir d&apos;une base propre —
            avant un rescrape complet, par exemple. Les épreuves et leurs sources
            restent intactes ; seuls les résultats et les fiches coureur qu&apos;ils
            laissent vides sont détruits.
          </p>
          <Button variant="destructive" onClick={() => setOuvert(true)}>
            Purger tous les résultats
          </Button>
        </CardContent>
      </Card>

      <Dialog open={ouvert} onOpenChange={fermer}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Purger tous les résultats ?</DialogTitle>
            <DialogDescription>
              Cette action est <strong>irréversible</strong>. Les épreuves et leurs
              sources restent en base : un rescrape pourra les réimporter aussitôt.
            </DialogDescription>
          </DialogHeader>

          {impact.isLoading && <Skeleton className="h-16 w-full" />}

          {impact.error && (
            <p className="text-sm text-destructive">
              L&apos;ampleur de la purge n&apos;a pas pu être chiffrée. Par prudence,
              la purge n&apos;est pas proposée — réessayez plus tard.
            </p>
          )}

          {impact.data && (
            <>
              <ul className="space-y-1 text-sm">
                <li>
                  <strong>{impact.data.participations}</strong> résultat
                  {impact.data.participations > 1 ? "s" : ""} seront détruits.
                </li>
                <li>
                  <strong>{impact.data.athletes}</strong> fiche
                  {impact.data.athletes > 1 ? "s" : ""} coureur
                  {impact.data.athletes > 1 ? " seront retirées" : " sera retirée"}.
                </li>
              </ul>
              <label className="block space-y-1 text-sm" htmlFor="wipe-confirm-input">
                Tapez <strong>{MOT_DE_CONFIRMATION}</strong> pour activer la confirmation.
                <Input
                  id="wipe-confirm-input"
                  value={saisie}
                  onChange={(e) => setSaisie(e.target.value)}
                  autoComplete="off"
                  spellCheck={false}
                />
              </label>
            </>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => fermer(false)}>
              Renoncer
            </Button>
            {impact.data && (
              <Button
                variant="destructive"
                onClick={confirmer}
                disabled={purge.isPending || saisie !== MOT_DE_CONFIRMATION}
              >
                Purger définitivement
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
```

- [ ] **Step 4: Intégrer la carte dans `/admin/courses`**

Dans `frontend/app/admin/courses/page.tsx`, ajouter l'import et le composant :

```tsx
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { CoursesAdminTable } from "@/components/admin/CoursesAdminTable";
import { WipeParticipationsCard } from "@/components/admin/WipeParticipationsCard";
```

Et dans le JSX, après `<CoursesAdminTable ... />` :

```tsx
        <CoursesAdminTable
          page={Number(sp.page)}
          filtres={{
            name: sp.name,
            event_type: sp.event_type,
            date_from: sp.date_from,
            date_to: sp.date_to,
          }}
        />
        <WipeParticipationsCard />
```

- [ ] **Step 5: Lancer les tests du composant, vérifier qu'ils passent**

Run: `cd frontend && npx vitest run components/admin/WipeParticipationsCard.test.tsx`
Expected: PASS.

- [ ] **Step 6: Suite complète, lint, build**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: PASS — tous verts, build prod OK.

- [ ] **Step 7: Commit**

```bash
cd frontend
git add components/admin/WipeParticipationsCard.tsx components/admin/WipeParticipationsCard.test.tsx \
        app/admin/courses/page.tsx
git commit -m "feat(frontend): carte de purge totale des resultats sur /admin/courses (#384)"
```

---

## Après l'implémentation

Fin de branche commune aux trois voies (`AGENTS.md`) : `requesting-code-review` →
`verification-before-completion` → (la branche touche `frontend/`, donc)
`ui-ux-review` sur déclenchement de l'utilisateur → `finishing-a-development-branch`.
