# Journal d'administration lisible — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre lisible le journal d'administration promis par l'écran (#501) — une route de lecture, un écran dédié, et le décompte réel dans les messages de succès des deux purges totales et de la fusion.

**Architecture:** Backend : une route de lecture paginée (`GET /admin/action-log`, pouvoir dédié `admin_log:read`) au-dessus du modèle `AdminActionLog` existant, plus un changement de contrat sur `DELETE /admin/courses` et `DELETE /admin/participations` (204 → 200 avec décompte). Frontend : un écran `/admin/journal` (table paginée, patron de `FeedbackTable`), une entrée de navigation, et trois toasts de succès mis à jour pour afficher le décompte déjà renvoyé ou nouvellement renvoyé par l'API.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (sync), Pydantic v2, pytest ; Next.js 16 App Router, TypeScript, React Query, Vitest + RTL.

**Spec:** `docs/superpowers/specs/2026-08-25-journal-admin-lisible-design.md`

## Global Constraints

- Français pour tout ce qui est visible utilisateur (libellés, messages) ; anglais pour les identifiants techniques et les codes d'action (`course.delete`, etc.) — Principe I.
- `admin_action_log` reste **écriture seule** au sens création : aucune route `PATCH`/`DELETE` n'est ajoutée sur cette ressource.
- Le changement de contrat porte **uniquement** sur `DELETE /admin/courses` et `DELETE /admin/participations` — `DELETE /admin/courses/{id}` reste en 204, hors périmètre.
- Nouveau pouvoir `admin_log:read` ajouté au catalogue plat `core/permissions.py`, sans migration (FR-014 de #115) ; gardé route par route, jamais en `dependencies=` de router (FR-018).
- Tests unitaires sans réseau (`uv run pytest -m "not integration"` côté backend, `npm test` côté frontend) ; aucun test ne doit dépendre du réseau.

---

### Task 1: Backend — relation `User` et lecture paginée du journal

**Files:**
- Modify: `backend/app/models/admin_action_log.py`
- Modify: `backend/app/repositories/admin_action_log_repository.py`
- Test: `backend/tests/test_repositories/test_admin_action_log_repository.py`

**Interfaces:**
- Consumes: rien (fondation de la feature).
- Produces: `AdminActionLog.user: Mapped["User"]` (relation, résolue par `joinedload`) ; `admin_action_log_repository.list_recent(db, *, page: int = 1, page_size: int = 20) -> tuple[list[AdminActionLog], int]`, triée par `id desc`, `total` = nombre total d'entrées.

- [ ] **Step 1: Écrire les tests de `list_recent`**

Ajouter à la fin de `backend/tests/test_repositories/test_admin_action_log_repository.py` :

```python
def test_list_recent_rend_la_plus_recente_d_abord(db_session):
    auteur = _auteur(db_session)
    for indice in range(3):
        admin_action_log_repository.create(
            db_session,
            user_id=auteur.id,
            action="athlete.update",
            entity_type="athlete",
            entity_id=indice,
            payload={"rang": indice},
        )
    db_session.flush()

    entrees, total = admin_action_log_repository.list_recent(db_session)

    assert [e.payload["rang"] for e in entrees] == [2, 1, 0]
    assert total == 3


def test_list_recent_pagine(db_session):
    auteur = _auteur(db_session)
    for indice in range(5):
        admin_action_log_repository.create(
            db_session,
            user_id=auteur.id,
            action="athlete.update",
            entity_type="athlete",
            entity_id=indice,
            payload={"rang": indice},
        )
    db_session.flush()

    entrees, total = admin_action_log_repository.list_recent(db_session, page=2, page_size=2)

    assert [e.payload["rang"] for e in entrees] == [2, 1]
    assert total == 5


def test_list_recent_charge_l_auteur_sans_requete_supplementaire(db_session):
    auteur = _auteur(db_session, email="jean@exemple.fr")
    admin_action_log_repository.create(
        db_session, user_id=auteur.id, action="course.delete", entity_type="course", entity_id=1
    )
    db_session.flush()

    entrees, _ = admin_action_log_repository.list_recent(db_session)

    assert entrees[0].user.email == "jean@exemple.fr"
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `cd backend && uv run pytest tests/test_repositories/test_admin_action_log_repository.py -v`
Expected: FAIL — `AttributeError: module 'app.repositories.admin_action_log_repository' has no attribute 'list_recent'`

- [ ] **Step 3: Ajouter la relation sur le modèle**

Dans `backend/app/models/admin_action_log.py`, remplacer le docstring du module (lignes 12-15) :

```python
"""...
**Jamais modifiable** : ni mise à jour, ni suppression — un journal qu'on peut
réécrire ne prouve rien. Une route de lecture existe (#501,
`GET /admin/action-log`) ; c'est l'écriture qui reste fermée.
"""
```

Ajouter l'import et la relation :

```python
from sqlalchemy.orm import Mapped, mapped_column, relationship
```
(remplace la ligne d'import existante `from sqlalchemy.orm import Mapped, mapped_column`)

Puis, à la fin de la classe `AdminActionLog` :

```python
    # Sens unique : aucune collection n'est ajoutée sur `User`. `user_id` est
    # `NOT NULL`, donc jamais `| None` — contrairement à `AllowedEmail.created_by`,
    # nullable, elle. `list_recent` (#501) la charge par `joinedload` pour
    # afficher l'auteur sur chaque ligne sans requête par ligne.
    user: Mapped["User"] = relationship()  # noqa: F821
```

- [ ] **Step 4: Ajouter `list_recent` au repository**

Dans `backend/app/repositories/admin_action_log_repository.py`, remplacer le docstring du module :

```python
"""Accès données pour AdminActionLog — seule couche qui touche la Session (Principe II).

**Trois fonctions, jamais de quatrième.** Ni `update`, ni `delete` : un journal
d'audit modifiable ne prouve rien. `list_recent` (#501) est la lecture paginée
qui alimente l'écran d'administration ; `list_for_entity` reste utilisée par
les tests et n'a pas d'autre lecteur.
"""
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.admin_action_log import AdminActionLog
```

Ajouter à la fin du fichier :

```python
def list_recent(
    db: Session, *, page: int = 1, page_size: int = 20
) -> tuple[list[AdminActionLog], int]:
    """Les dernières entrées du journal, la plus récente d'abord (#501).

    Tri sur `id` et non sur `created_at`, même raison que `list_for_entity` :
    deux gestes de la même transaction partagent l'horodatage à la microseconde
    près. `user` est chargé dans la même requête (`joinedload`) — l'écran
    affiche l'auteur sur chaque ligne, et une requête par ligne serait un N+1.
    """
    total = db.query(func.count(AdminActionLog.id)).scalar() or 0
    offset = (page - 1) * page_size
    entries = (
        db.query(AdminActionLog)
        .options(joinedload(AdminActionLog.user))
        .order_by(AdminActionLog.id.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return entries, total
```

- [ ] **Step 5: Lancer les tests, vérifier qu'ils passent**

Run: `cd backend && uv run pytest tests/test_repositories/test_admin_action_log_repository.py -v`
Expected: PASS (7 tests : les 4 existants + les 3 ajoutés)

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/admin_action_log.py backend/app/repositories/admin_action_log_repository.py backend/tests/test_repositories/test_admin_action_log_repository.py
git commit -m "feat(501): lecture paginée du journal d'administration"
```

---

### Task 2: Backend — pouvoir `admin_log:read`

**Files:**
- Modify: `backend/app/core/permissions.py`

**Interfaces:**
- Consumes: rien.
- Produces: `P.ADMIN_LOG_READ` (code `admin_log:read`), listé dans `ALL`.

- [ ] **Step 1: Ajouter la feature et le pouvoir**

Dans `backend/app/core/permissions.py`, après `FEATURE_FEEDBACK = "Retours utilisateurs"` :

```python
FEATURE_ADMIN_LOG = "Journal d'administration"
```

Dans la classe `P`, après `FEEDBACK_MANAGE` (avant la fermeture de la classe) :

```python
    ADMIN_LOG_READ = Permission(
        "admin_log:read",
        "Consulter le journal d'administration",
        "Voir l'historique des gestes d'administration effectués sur les "
        "données — qui, quoi, quand.",
        FEATURE_ADMIN_LOG,
    )
```

Dans le tuple `ALL`, après `P.FEEDBACK_MANAGE,` :

```python
    P.ADMIN_LOG_READ,
```

- [ ] **Step 2: Vérifier le catalogue**

Run: `cd backend && uv run pytest tests/test_permissions_catalogue.py -v`
Expected: FAIL — le pouvoir `admin_log:read` du catalogue ne garde encore aucune route (ce test ne repasse au vert qu'après la Task 4, qui pose la garde). Confirmer que le message d'échec cite bien `admin_log:read`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/permissions.py
git commit -m "feat(501): pouvoir admin_log:read au catalogue"
```

(Le test rouge de l'étape 2 est attendu et se corrige à la Task 4 — ne pas amender ce commit, la Task 4 apporte son propre commit.)

---

### Task 3: Backend — schémas de réponse

**Files:**
- Modify: `backend/app/schemas/admin.py`

**Interfaces:**
- Consumes: rien (DTO purs).
- Produces: `AdminActionLogEntry`, `AdminActionLogPage`, `CoursesWipeResult`, `ParticipationsWipeResult` — importables depuis `app.schemas.admin`.

- [ ] **Step 1: Ajouter les deux schémas de résultat de purge**

Dans `backend/app/schemas/admin.py`, juste après la classe `CoursesWipeImpact` (qui se termine à la ligne 381 par `athletes: int`) :

```python


class ParticipationsWipeResult(BaseModel):
    """Ce qu'une purge totale des résultats a détruit, une fois faite (#501).

    Miroir du `resume` que `admin_actions.wipe_all_participations` calcule déjà
    — la route ne le jetait pas moins qu'elle ne le rendait, elle rendait un
    `204` sans corps. `courses_reset` n'apparaît jamais dans le payload
    journalisé (la règle du journal borne ce qu'il garde à ce que la
    confirmation a chiffré), mais il fait partie de la réponse : c'est
    l'appelant HTTP qui en a besoin pour l'annoncer, pas le journal.
    """

    participations_deleted: int
    athletes_purged: int
    courses_reset: int


class CoursesWipeResult(BaseModel):
    """Ce qu'une purge totale des épreuves a détruit, une fois faite (#501)."""

    courses_deleted: int
    athletes_purged: int
```

- [ ] **Step 2: Ajouter les schémas du journal, à la fin du fichier**

Après la classe `SessionRevocationRequest` (fin du fichier) :

```python


class AdminActionLogEntry(BaseModel):
    """Une entrée du journal d'administration, prête à afficher (#501).

    `user_name` vient de `AdminActionLog.user.display_name`, résolu côté route
    — pas de `| None` ici contrairement à `AllowedEmailRead.created_by_name` :
    `user_id` est une FK `NOT NULL`, l'auteur existe toujours.
    """

    id: int
    created_at: datetime
    user_name: str
    action: str
    entity_type: str
    entity_id: int
    payload: dict | None = None


class AdminActionLogPage(BaseModel):
    """Une page du journal — `total` porte le compte plein, pas celui de la page."""

    entries: list[AdminActionLogEntry]
    total: int
```

- [ ] **Step 3: Vérifier que le module s'importe sans erreur**

Run: `cd backend && uv run python -c "from app.schemas.admin import AdminActionLogEntry, AdminActionLogPage, CoursesWipeResult, ParticipationsWipeResult"`
Expected: aucune sortie, code de sortie 0.

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/admin.py
git commit -m "feat(501): schémas du journal d'administration et des résultats de purge"
```

---

### Task 4: Backend — route `GET /admin/action-log`

**Files:**
- Create: `backend/app/api/v1/admin_action_log.py`
- Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/test_api/test_admin_action_log_api.py`

**Interfaces:**
- Consumes: `admin_action_log_repository.list_recent` (Task 1), `P.ADMIN_LOG_READ` (Task 2), `AdminActionLogEntry`/`AdminActionLogPage` (Task 3).
- Produces: `GET /admin/action-log?page=&page_size=` → `AdminActionLogPage`, gardée par `admin_log:read`.

- [ ] **Step 1: Écrire les tests de la route**

Créer `backend/tests/test_api/test_admin_action_log_api.py` :

```python
"""GET /admin/action-log — lecture du journal d'administration (#501)."""
from app.core.permissions import P
from app.models.organisation import Organisation
from app.models.role_permission import RolePermission
from app.repositories import admin_action_log_repository, role_repository, user_repository, user_role_repository
from app.services.auth import session as session_service
from app.api.v1.auth import session_cookie_name
from app.core.config import get_settings


def _session_etroite(client, db_session, *codes, email="etroit@exemple.fr"):
    """Remplace la session superutilisateur du conftest par une session à pouvoirs comptés."""
    organisation = db_session.query(Organisation).first()
    user = user_repository.create(db_session, email=email)
    db_session.flush()
    if codes:
        role = role_repository.create(db_session, slug="etroit", name="Étroit")
        for code in codes:
            role.permissions.append(RolePermission(permission_code=str(code)))
        db_session.flush()
        user_role_repository.grant(
            db_session, user_id=user.id, role_id=role.id, organisation_id=organisation.id
        )
    jeton = session_service.open_for(db_session, user)
    db_session.commit()
    client.cookies.set(session_cookie_name(get_settings()), jeton)
    return user


def _semer(db_session, *, n=3, user_id):
    for indice in range(n):
        admin_action_log_repository.create(
            db_session,
            user_id=user_id,
            action="athlete.update",
            entity_type="athlete",
            entity_id=indice,
            payload={"rang": indice},
        )
    db_session.commit()


def test_lister_rend_la_page_par_defaut(client, db_session):
    auteur = user_repository.create(db_session, email="auteur@exemple.fr")
    db_session.flush()
    _semer(db_session, user_id=auteur.id)

    reponse = client.get("/api/v1/admin/action-log")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["total"] == 3
    assert [e["payload"]["rang"] for e in corps["entries"]] == [2, 1, 0]
    # `user_repository.create` pose `display_name=""` par défaut (aucun
    # fournisseur SSO ici) : la route retombe sur l'adresse.
    assert corps["entries"][0]["user_name"] == "auteur@exemple.fr"


def test_lister_pagine(client, db_session):
    auteur = user_repository.create(db_session, email="auteur@exemple.fr")
    db_session.flush()
    _semer(db_session, n=5, user_id=auteur.id)

    reponse = client.get("/api/v1/admin/action-log?page=2&page_size=2")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert [e["payload"]["rang"] for e in corps["entries"]] == [2, 1]
    assert corps["total"] == 5


def test_lister_sans_session_rend_401(client):
    client.cookies.clear()

    assert client.get("/api/v1/admin/action-log").status_code == 401


def test_lister_sans_le_pouvoir_rend_403(client, db_session):
    _session_etroite(client, db_session)

    assert client.get("/api/v1/admin/action-log").status_code == 403


def test_lister_avec_le_seul_pouvoir_utile_reussit(client, db_session):
    _session_etroite(client, db_session, P.ADMIN_LOG_READ)

    assert client.get("/api/v1/admin/action-log").status_code == 200
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `cd backend && uv run pytest tests/test_api/test_admin_action_log_api.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.api.v1.admin_action_log'` (le router n'existe pas encore)

- [ ] **Step 3: Créer le router**

Créer `backend/app/api/v1/admin_action_log.py` :

```python
"""Lecture du journal d'administration (#501) — une ressource, une garde.

Couche mince : délégation à `repositories/admin_action_log_repository.py`,
traduction en HTTP. Aucune écriture ici — le journal ne s'écrit que depuis les
gestes qu'il trace (`services/admin_actions.py`, `course_merge.py`,
`course_review.py`).

La garde est posée **sur la route**, jamais sur le préfixe (#115, FR-018) :
`admin.py` monte sous le même `/admin/` le signalement anonyme du site public.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.permissions import P
from app.models.user import User
from app.repositories import admin_action_log_repository
from app.schemas.admin import AdminActionLogEntry, AdminActionLogPage

router = APIRouter(tags=["admin"])


@router.get("/admin/action-log", response_model=AdminActionLogPage)
def list_action_log(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.ADMIN_LOG_READ)),
):
    """Les dernières entrées du journal, la plus récente d'abord.

    Pouvoir dédié plutôt que réutilisation de `courses:delete` ou
    `participations:wipe_all` : le journal couvre des entités que ces pouvoirs
    ne gardent pas (corrections de coureurs, réattributions de résultats), et
    « qui peut détruire peut lire son propre geste » n'est vrai que par
    accident.
    """
    entries, total = admin_action_log_repository.list_recent(
        db, page=page, page_size=page_size
    )
    return AdminActionLogPage(
        entries=[
            AdminActionLogEntry(
                id=entry.id,
                created_at=entry.created_at,
                user_name=entry.user.display_name or entry.user.email,
                action=entry.action,
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                payload=entry.payload,
            )
            for entry in entries
        ],
        total=total,
    )
```

- [ ] **Step 4: Monter le router**

Dans `backend/app/api/v1/router.py`, ajouter `admin_action_log` à l'import groupé (ordre alphabétique, entre `admin` et `admin_allowed_emails`) :

```python
from app.api.v1 import (
    admin,
    admin_action_log,
    admin_allowed_emails,
    ...
```

Et l'ajouter à la boucle des routers gardés par `require_site_access` (même ordre alphabétique, entre `admin` et `admin_allowed_emails`) :

```python
for module in (
    scrape,
    athletes,
    courses,
    participations,
    stats,
    admin,
    admin_action_log,
    admin_allowed_emails,
    ...
```

- [ ] **Step 5: Lancer les tests, vérifier qu'ils passent**

Run: `cd backend && uv run pytest tests/test_api/test_admin_action_log_api.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Vérifier que le catalogue de pouvoirs est de nouveau vert**

Run: `cd backend && uv run pytest tests/test_permissions_catalogue.py -v`
Expected: PASS — `admin_log:read` garde désormais `GET /admin/action-log`.

- [ ] **Step 7: Lancer la suite complète pour détecter une régression**

Run: `cd backend && uv run pytest -m "not integration" -n 0`
Expected: PASS, aucune régression.

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/v1/admin_action_log.py backend/app/api/v1/router.py backend/tests/test_api/test_admin_action_log_api.py
git commit -m "feat(501): route GET /admin/action-log"
```

---

### Task 5: Backend — les deux purges rendent leur décompte réel

**Files:**
- Modify: `backend/app/api/v1/admin_data.py`
- Modify: `backend/tests/test_api/test_admin_data_api.py`

**Interfaces:**
- Consumes: `CoursesWipeResult`/`ParticipationsWipeResult` (Task 3) ; `admin_actions.wipe_all_courses`/`wipe_all_participations` (inchangés — ils rendent déjà `resume` avec les bons compteurs).
- Produces: `DELETE /admin/courses` → `200` `CoursesWipeResult` ; `DELETE /admin/participations` → `200` `ParticipationsWipeResult`.

- [ ] **Step 1: Modifier les quatre tests qui supposaient un `204` vide**

Dans `backend/tests/test_api/test_admin_data_api.py`, remplacer les quatre tests suivants.

Ligne 288-293 (`test_purger_rend_204_et_vide_la_table`) devient :

```python
def test_purger_rend_le_decompte_reel_et_vide_la_table(client, db_session, base_avec_resultats):
    reponse = client.delete("/api/v1/admin/participations")

    assert reponse.status_code == 200
    assert reponse.json() == {
        "participations_deleted": 2,
        "athletes_purged": 2,
        "courses_reset": 2,
    }
    assert participation_repository.count_all(db_session) == 0
```

(`base_avec_resultats`, définie plus bas dans le même fichier à la ligne 235, pose deux épreuves — Tri A, Tri B — chacune avec un unique résultat porté par un athlète distinct, Jean et Paul : les deux perdent leur seule participation, donc les deux sont purgés — `athletes_purged: 2` — et les deux épreuves voient leur `scraped_at` remis à `None` — `courses_reset: 2`.)

Ligne 355-358 (`test_purger_avec_le_seul_pouvoir_utile_reussit`) devient :

```python
def test_purger_avec_le_seul_pouvoir_utile_reussit(client, db_session, base_avec_resultats):
    _session_etroite(client, db_session, P.PARTICIPATIONS_WIPE_ALL)

    assert client.delete("/api/v1/admin/participations").status_code == 200
```

Ligne 406-413 (`test_purger_les_epreuves_rend_204_et_vide_le_catalogue`) devient :

```python
def test_purger_les_epreuves_rend_le_decompte_reel_et_vide_le_catalogue(
    client, db_session, base_avec_resultats
):
    reponse = client.delete("/api/v1/admin/courses")

    assert reponse.status_code == 200
    assert reponse.json() == {"courses_deleted": 2, "athletes_purged": 2}
    assert course_repository.count_all(db_session) == 0
    assert participation_repository.count_all(db_session) == 0
    assert athlete_repository.count_all(db_session) == 0
```

Ligne 456-461 (`test_purger_les_epreuves_avec_le_seul_pouvoir_utile_reussit`) devient :

```python
def test_purger_les_epreuves_avec_le_seul_pouvoir_utile_reussit(
    client, db_session, base_avec_resultats
):
    _session_etroite(client, db_session, P.COURSES_WIPE_ALL)

    assert client.delete("/api/v1/admin/courses").status_code == 200
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `cd backend && uv run pytest tests/test_api/test_admin_data_api.py -v -k "purger"`
Expected: FAIL — les routes rendent encore `204`.

- [ ] **Step 3: Changer le contrat des deux routes**

Dans `backend/app/api/v1/admin_data.py`, ajouter l'import :

```python
from app.schemas.admin import (
    AdminAthleteRead,
    AdminAthleteUpdate,
    AdminCourseUpdate,
    CourseDeletionImpact,
    CoursesWipeImpact,
    CoursesWipeResult,
    ParticipationReassign,
    ParticipationsWipeImpact,
    ParticipationsWipeResult,
)
```

Remplacer :

```python
@router.delete("/admin/courses", status_code=204)
def wipe_all_courses(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(P.COURSES_WIPE_ALL)),
):
    """Vide le catalogue d'épreuves — sources et résultats compris (#384, suite).

    Strictement plus destructeur que `DELETE /admin/participations` : ici,
    les épreuves elles-mêmes et leurs sources disparaissent aussi. Irréversible
    et sans corps de réponse : ce qui reste du geste est son entrée au journal.
    """
    admin_actions.wipe_all_courses(db, user_id=user.id)
    db.commit()
```

par :

```python
@router.delete("/admin/courses", response_model=CoursesWipeResult)
def wipe_all_courses(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(P.COURSES_WIPE_ALL)),
):
    """Vide le catalogue d'épreuves — sources et résultats compris (#384, suite).

    Strictement plus destructeur que `DELETE /admin/participations` : ici,
    les épreuves elles-mêmes et leurs sources disparaissent aussi. Irréversible,
    et rend désormais le décompte réel (#501) — ce qui reste du geste est son
    entrée au journal, mais l'administrateur qui vient d'agir doit pouvoir le
    lire sans y aller.
    """
    resume = admin_actions.wipe_all_courses(db, user_id=user.id)
    db.commit()
    return resume
```

Remplacer :

```python
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

par :

```python
@router.delete("/admin/participations", response_model=ParticipationsWipeResult)
def wipe_all_participations(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(P.PARTICIPATIONS_WIPE_ALL)),
):
    """Vide `participations`, purge les fiches devenues vides, force un rescrape (#384).

    `Course` et `course_sources` restent intacts. Irréversible, et rend
    désormais le décompte réel (#501) au lieu d'un `204` vide.
    """
    resume = admin_actions.wipe_all_participations(db, user_id=user.id)
    db.commit()
    return resume
```

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `cd backend && uv run pytest tests/test_api/test_admin_data_api.py -v`
Expected: PASS (tout le fichier)

- [ ] **Step 5: Lancer la suite complète**

Run: `cd backend && uv run pytest -m "not integration" -n 0`
Expected: PASS, aucune régression.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/admin_data.py backend/tests/test_api/test_admin_data_api.py
git commit -m "fix(501): les deux purges totales rendent leur décompte réel au lieu d'un 204 vide"
```

---

### Task 6: Frontend — types, client HTTP et hooks React Query

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api/client.ts`
- Modify: `frontend/lib/queries/keys.ts`
- Modify: `frontend/lib/queries/admin.ts`

**Interfaces:**
- Consumes: `GET /admin/action-log`, `DELETE /admin/courses`, `DELETE /admin/participations` (Tasks 4-5).
- Produces: types `AdminActionLogEntry`, `AdminActionLogPage`, `CoursesWipeResult`, `ParticipationsWipeResult` ; `apiClient.getActionLog(page, pageSize)`, `apiClient.wipeAllCourses(): Promise<CoursesWipeResult>`, `apiClient.wipeAllParticipations(): Promise<ParticipationsWipeResult>` ; `useAdminActionLog(page)`.

- [ ] **Step 1: Ajouter les types**

Dans `frontend/lib/types.ts`, juste après `CoursesWipeImpact` (qui se termine par `}` après `athletes: number;`) :

```ts

/** Ce qu'une purge totale des résultats a détruit, une fois faite (#501). */
export interface ParticipationsWipeResult {
  participations_deleted: number;
  athletes_purged: number;
  courses_reset: number;
}

/** Ce qu'une purge totale des épreuves a détruit, une fois faite (#501). */
export interface CoursesWipeResult {
  courses_deleted: number;
  athletes_purged: number;
}
```

À la fin du fichier :

```ts

/** Une entrée du journal d'administration (#501). */
export interface AdminActionLogEntry {
  id: number;
  created_at: string;
  user_name: string;
  action: string;
  entity_type: string;
  entity_id: number;
  payload: Record<string, unknown> | null;
}

/** Une page du journal — `total` porte le compte plein, pas celui de la page. */
export interface AdminActionLogPage {
  entries: AdminActionLogEntry[];
  total: number;
}
```

- [ ] **Step 2: Mettre à jour `client.ts`**

Dans `frontend/lib/api/client.ts`, ajouter les imports de types nécessaires en haut du fichier (à côté des imports de types existants — chercher la ligne qui importe déjà `CoursesWipeImpact`, `ParticipationsWipeImpact`, et y ajouter `AdminActionLogPage`, `CoursesWipeResult`, `ParticipationsWipeResult`).

Remplacer :

```ts
  getParticipationsWipeImpact: () =>
    request<ParticipationsWipeImpact>("/admin/participations/wipe-impact"),
  wipeAllParticipations: () =>
    request<null>("/admin/participations", { method: "DELETE" }),

  // ── Purge totale des épreuves (#384, suite) ─────────────────────────────────
  // `courses:wipe_all`. Strictement plus destructeur que ci-dessus : les
  // épreuves elles-mêmes et leurs sources disparaissent aussi.
  getCoursesWipeImpact: () => request<CoursesWipeImpact>("/admin/courses/wipe-impact"),
  wipeAllCourses: () => request<null>("/admin/courses", { method: "DELETE" }),
```

par :

```ts
  getParticipationsWipeImpact: () =>
    request<ParticipationsWipeImpact>("/admin/participations/wipe-impact"),
  // Rend le décompte réel depuis #501 — la route ne rendait qu'un 204 vide.
  wipeAllParticipations: () =>
    request<ParticipationsWipeResult>("/admin/participations", { method: "DELETE" }),

  // ── Purge totale des épreuves (#384, suite) ─────────────────────────────────
  // `courses:wipe_all`. Strictement plus destructeur que ci-dessus : les
  // épreuves elles-mêmes et leurs sources disparaissent aussi.
  getCoursesWipeImpact: () => request<CoursesWipeImpact>("/admin/courses/wipe-impact"),
  wipeAllCourses: () =>
    request<CoursesWipeResult>("/admin/courses", { method: "DELETE" }),
```

Ajouter, à la suite des autres méthodes admin (par exemple juste après `updateCourse`) :

```ts
  // ── Journal d'administration (#501) ─────────────────────────────────────────
  getActionLog: (page: number, pageSize: number) =>
    request<AdminActionLogPage>(`/admin/action-log${toQuery({ page, page_size: pageSize })}`),
```

- [ ] **Step 3: Ajouter la clé de requête**

Dans `frontend/lib/queries/keys.ts`, ajouter :

```ts
  adminActionLog: (page: number) => ["admin-action-log", page] as const,
```

- [ ] **Step 4: Ajouter le hook**

Dans `frontend/lib/queries/admin.ts`, ajouter (par exemple à la fin du fichier, ou à côté des autres hooks d'administration des données) :

```ts

// ── Journal d'administration (#501) ─────────────────────────────────────────

export const TAILLE_PAGE_JOURNAL = 20;

export function useAdminActionLog(page = 1) {
  return useQuery({
    queryKey: queryKeys.adminActionLog(page),
    queryFn: () => apiClient.getActionLog(page, TAILLE_PAGE_JOURNAL),
    placeholderData: (precedent) => precedent,
  });
}
```

- [ ] **Step 5: Vérifier la compilation TypeScript**

Run: `cd frontend && npx tsc --noEmit`
Expected: aucune erreur.

- [ ] **Step 6: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/api/client.ts frontend/lib/queries/keys.ts frontend/lib/queries/admin.ts
git commit -m "feat(501): types, client HTTP et hook du journal d'administration"
```

---

### Task 7: Frontend — traduction des gestes et du détail

**Files:**
- Create: `frontend/lib/admin-action-log.ts`
- Test: `frontend/lib/admin-action-log.test.ts`

**Interfaces:**
- Consumes: rien (module pur).
- Produces: `actionLabel(action: string): string` ; `formatPayload(payload: Record<string, unknown> | null): { label: string; value: string }[]`.

- [ ] **Step 1: Écrire les tests**

Créer `frontend/lib/admin-action-log.test.ts` :

```ts
import { describe, it, expect } from "vitest";
import { actionLabel, formatPayload } from "./admin-action-log";

describe("actionLabel", () => {
  it("traduit un geste connu", () => {
    expect(actionLabel("course.delete")).toBe("Suppression d'une épreuve");
  });

  it("retombe sur le code brut pour un geste inconnu", () => {
    expect(actionLabel("future.action")).toBe("future.action");
  });
});

describe("formatPayload", () => {
  it("rend un tableau vide pour un payload absent", () => {
    expect(formatPayload(null)).toEqual([]);
  });

  it("traduit les clés connues, garde la clé brute pour une clé inconnue", () => {
    const lignes = formatPayload({ participations_deleted: 5, cle_inconnue: "x" });

    expect(lignes).toContainEqual({ label: "Résultats détruits", value: "5" });
    expect(lignes).toContainEqual({ label: "cle_inconnue", value: "x" });
  });

  it("rend un diff champ par champ pour before/after objets, sans les champs inchangés", () => {
    const lignes = formatPayload({
      before: { nom: "Dupont", club: "TCN" },
      after: { nom: "Dupond", club: "TCN" },
    });

    expect(lignes).toEqual([{ label: "Nom", value: "Dupont → Dupond" }]);
  });

  it("rend un diff simple pour before/after scalaires", () => {
    const lignes = formatPayload({ before: null, after: true, notes: "vérifié à la main" });

    expect(lignes).toContainEqual({ label: "Modification", value: "— → oui" });
    expect(lignes).toContainEqual({ label: "Note", value: "vérifié à la main" });
  });

  it("aplatit un objet imbriqué en une ligne lisible, clés traduites", () => {
    const lignes = formatPayload({
      absorbed: { name: "Triathlon d'Ancenis", event_date: "2026-05-01" },
    });

    expect(lignes).toEqual([
      {
        label: "Épreuve absorbée",
        value: "Nom de l'épreuve : Triathlon d'Ancenis, Date : 2026-05-01",
      },
    ]);
  });

  it("rend oui/non pour un booléen, un tiret pour null", () => {
    const lignes = formatPayload({ is_relay: false, source_added: null });

    expect(lignes).toContainEqual({ label: "Relais", value: "non" });
    expect(lignes).toContainEqual({ label: "Source ajoutée", value: "—" });
  });
});
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `cd frontend && npx vitest run lib/admin-action-log.test.ts`
Expected: FAIL — le module `./admin-action-log` n'existe pas.

- [ ] **Step 3: Écrire le module**

Créer `frontend/lib/admin-action-log.ts` :

```ts
/**
 * Traduction des gestes et des payloads du journal d'administration (#501).
 *
 * Deux dictionnaires plats, sur le patron de `lib/sport-colors.ts` : source
 * unique, pas de logique par geste. `actionLabel` traduit le **code**
 * (`AdminActionLog.action`) ; `formatPayload` traduit les **clés** du JSON
 * libre qu'un geste a consigné, quel que soit le geste.
 */

const ACTION_LABELS: Record<string, string> = {
  "course.delete": "Suppression d'une épreuve",
  "course.update": "Correction d'une épreuve",
  "course.merge": "Fusion de deux épreuves",
  "course.source.switch": "Bascule de la source active",
  "course.rescrape": "Re-scrape d'une épreuve",
  "course.reliability": "Fiabilité tranchée manuellement",
  "courses.wipe_all": "Purge totale des épreuves",
  "participations.wipe_all": "Purge totale des résultats",
  "participation.reassign": "Réattribution d'un résultat",
  "participation.delete": "Suppression d'un résultat",
  "participation.validate": "Validation d'un résultat en attente",
  "participation.reject": "Rejet d'un résultat en attente",
  "participation.unreject": "Annulation d'un rejet",
  "participation.correct_fields": "Correction d'un résultat en attente",
  "athlete.update": "Correction d'une fiche coureur",
};

/** Le libellé français d'un geste, ou son code brut si le catalogue l'ignore. */
export function actionLabel(action: string): string {
  return ACTION_LABELS[action] ?? action;
}

const PAYLOAD_KEY_LABELS: Record<string, string> = {
  nom: "Nom",
  prenom: "Prénom",
  birth_date: "Date de naissance",
  club: "Club",
  name: "Nom de l'épreuve",
  event_date: "Date",
  event_type: "Type",
  is_relay: "Relais",
  bib_number: "Dossard",
  rank_overall: "Place au général",
  category: "Catégorie",
  participations_deleted: "Résultats détruits",
  athletes_purged: "Fiches coureur purgées",
  courses_deleted: "Épreuves détruites",
  courses_reset: "Épreuves remises en attente de rescrape",
  previous_url: "Ancienne URL",
  new_url: "Nouvelle URL",
  participations_imported: "Résultats importés",
  source_url: "URL de la source",
  imported: "Importés",
  updated: "Mis à jour",
  skipped: "Ignorés",
  reconciled: "Rapprochés",
  course_id: "Épreuve",
  from_athlete_id: "Depuis le coureur",
  to_athlete_id: "Vers le coureur",
  athlete_id: "Coureur",
  athlete_name: "Nom du coureur",
  course_name: "Nom de l'épreuve",
  total_time: "Temps total",
  status: "Statut",
  was_pending_validation: "Était en attente de validation",
  source_added: "Source ajoutée",
  absorbed: "Épreuve absorbée",
  id: "Identifiant",
  notes: "Note",
  computed: "Verdict calculé",
};

function labelFor(key: string): string {
  return PAYLOAD_KEY_LABELS[key] ?? key;
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function formatValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "boolean") return v ? "oui" : "non";
  if (isRecord(v)) {
    return Object.entries(v)
      .map(([k, vv]) => `${labelFor(k)} : ${formatValue(vv)}`)
      .join(", ");
  }
  return String(v);
}

/**
 * Le détail lisible d'une entrée : un diff `avant → après` quand le payload
 * en porte un, sinon une ligne par clé restante — clé traduite si connue,
 * brute sinon.
 */
export function formatPayload(
  payload: Record<string, unknown> | null,
): { label: string; value: string }[] {
  if (!payload) return [];

  const { before, after, ...reste } = payload;
  const lignes: { label: string; value: string }[] = [];

  if (before !== undefined && after !== undefined) {
    if (isRecord(before) && isRecord(after)) {
      const champs = new Set([...Object.keys(before), ...Object.keys(after)]);
      for (const champ of champs) {
        if (JSON.stringify(before[champ]) !== JSON.stringify(after[champ])) {
          lignes.push({
            label: labelFor(champ),
            value: `${formatValue(before[champ])} → ${formatValue(after[champ])}`,
          });
        }
      }
    } else {
      lignes.push({
        label: "Modification",
        value: `${formatValue(before)} → ${formatValue(after)}`,
      });
    }
  }

  for (const [k, v] of Object.entries(reste)) {
    lignes.push({ label: labelFor(k), value: formatValue(v) });
  }

  return lignes;
}
```

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `cd frontend && npx vitest run lib/admin-action-log.test.ts`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/admin-action-log.ts frontend/lib/admin-action-log.test.ts
git commit -m "feat(501): traduction française des gestes et payloads du journal"
```

---

### Task 8: Frontend — `AdminActionLogTable`

**Files:**
- Create: `frontend/components/admin/AdminActionLogTable.tsx`
- Test: `frontend/components/admin/AdminActionLogTable.test.tsx`

**Interfaces:**
- Consumes: `useAdminActionLog(page)` (Task 6), `actionLabel`/`formatPayload` (Task 7), `formatDateTime` (`@/lib/utils/date`), `messageDeRefus` (`@/lib/api/refus`), `EmptyState` (`@/components/ui/empty-state`).
- Produces: `<AdminActionLogTable />` — pas de props, gère sa propre pagination en état local.

- [ ] **Step 1: Écrire les tests**

Créer `frontend/components/admin/AdminActionLogTable.test.tsx` :

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { AdminActionLogPage } from "@/lib/types";

const { getActionLog } = vi.hoisted(() => ({ getActionLog: vi.fn() }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { getActionLog } };
});

import { AdminActionLogTable } from "./AdminActionLogTable";

function page(overrides: Partial<AdminActionLogPage> = {}): AdminActionLogPage {
  return {
    entries: [
      {
        id: 1,
        created_at: "2026-08-20T10:15:00Z",
        user_name: "Jean Dupont",
        action: "course.delete",
        entity_type: "course",
        entity_id: 42,
        payload: { name: "Triathlon de Nantes", participations_deleted: 179 },
      },
    ],
    total: 1,
    ...overrides,
  };
}

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return { client, ...render(
    <QueryClientProvider client={client}>
      <AdminActionLogTable />
    </QueryClientProvider>,
  ) };
}

describe("AdminActionLogTable", () => {
  beforeEach(() => {
    getActionLog.mockReset();
  });

  it("affiche une entrée traduite", async () => {
    getActionLog.mockResolvedValue(page());

    afficher();

    expect(await screen.findByText("Suppression d'une épreuve")).toBeInTheDocument();
    expect(screen.getByText("Jean Dupont")).toBeInTheDocument();
    expect(screen.getByText(/Triathlon de Nantes/)).toBeInTheDocument();
  });

  it("affiche un état vide", async () => {
    getActionLog.mockResolvedValue(page({ entries: [], total: 0 }));

    afficher();

    expect(await screen.findByText(/aucune entrée/i)).toBeInTheDocument();
  });

  it("dit en français qu'un refus a empêché la lecture", async () => {
    getActionLog.mockRejectedValue(new ApiError(403, "Vous n'avez pas les droits nécessaires."));

    afficher();

    expect(await screen.findByText(/accès refusé/i)).toBeInTheDocument();
  });

  it("désactive « Précédent » sur la première page et pagine vers la suivante", async () => {
    getActionLog.mockResolvedValue(page({ total: 45 }));

    afficher();
    await screen.findByText("Suppression d'une épreuve");

    expect(screen.getByRole("button", { name: /précédent/i })).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: /suivant/i }));

    await waitFor(() => expect(getActionLog).toHaveBeenCalledWith(2, expect.any(Number)));
  });
});
```

- [ ] **Step 2: Lancer les tests, vérifier qu'ils échouent**

Run: `cd frontend && npx vitest run components/admin/AdminActionLogTable.test.tsx`
Expected: FAIL — le composant n'existe pas.

- [ ] **Step 3: Écrire le composant**

Créer `frontend/components/admin/AdminActionLogTable.tsx` :

```tsx
"use client";
import { useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useAdminActionLog, TAILLE_PAGE_JOURNAL } from "@/lib/queries/admin";
import { messageDeRefus } from "@/lib/api/refus";
import { formatDateTime } from "@/lib/utils/date";
import { actionLabel, formatPayload } from "@/lib/admin-action-log";

const REFUS = { sujet: "gestes d'administration", action: "consulter le journal" };

/**
 * Le journal d'administration, en lecture (#501). Pagination locale, sans
 * refléter la page dans l'URL — patron de `QualityQueueTable`, plus simple
 * que la pagination `<Link>` du catalogue d'épreuves : rien ici n'a besoin
 * d'être partageable par URL.
 */
export function AdminActionLogTable() {
  const [page, setPage] = useState(1);
  const { data, isLoading, error } = useAdminActionLog(page);

  if (isLoading) {
    return <Skeleton className="h-40 w-full" />;
  }
  if (error) {
    return <EmptyState {...messageDeRefus(error, REFUS)} />;
  }
  if (!data || data.entries.length === 0) {
    return (
      <EmptyState
        title="Aucune entrée dans le journal"
        description="Les gestes d'administration effectués sur les données apparaîtront ici."
      />
    );
  }

  const pages = Math.max(1, Math.ceil(data.total / TAILLE_PAGE_JOURNAL));

  return (
    <div className="space-y-4">
      <Card className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead>Auteur</TableHead>
              <TableHead>Geste</TableHead>
              <TableHead>Détail</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.entries.map((entree) => (
              <TableRow key={entree.id}>
                <TableCell className="whitespace-nowrap">
                  {formatDateTime(entree.created_at)}
                </TableCell>
                <TableCell>{entree.user_name}</TableCell>
                <TableCell>{actionLabel(entree.action)}</TableCell>
                <TableCell className="text-sm text-[var(--tcn-text-faint)]">
                  {formatPayload(entree.payload).map(({ label, value }) => (
                    <div key={label}>
                      {label} : {value}
                    </div>
                  ))}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      {pages > 1 && (
        <nav
          aria-label="Pagination du journal d'administration"
          className="flex items-center justify-between gap-3 rounded-xl border p-3 text-sm"
        >
          <span aria-current="page">
            Page {page} sur {pages} — {data.total} entrée{data.total > 1 ? "s" : ""}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              ‹ Précédent
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= pages}
              onClick={() => setPage((p) => p + 1)}
            >
              Suivant ›
            </Button>
          </div>
        </nav>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Lancer les tests, vérifier qu'ils passent**

Run: `cd frontend && npx vitest run components/admin/AdminActionLogTable.test.tsx`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/components/admin/AdminActionLogTable.tsx frontend/components/admin/AdminActionLogTable.test.tsx
git commit -m "feat(501): table de lecture du journal d'administration"
```

---

### Task 9: Frontend — écran `/admin/journal` et entrée de navigation

**Files:**
- Create: `frontend/app/admin/journal/page.tsx`
- Test: `frontend/app/admin/journal/page.test.tsx`
- Modify: `frontend/components/layout/nav.config.ts`

**Interfaces:**
- Consumes: `<AdminActionLogTable />` (Task 8), `PageHeader`/`ecran`/`PageShell` (existants).
- Produces: route `/admin/journal`, entrée de nav `a-journal` sous la section `admin`, gardée par `admin_log:read`.

- [ ] **Step 1: Ajouter l'entrée de navigation**

Dans `frontend/components/layout/nav.config.ts`, dans la section `admin`, ajouter après l'entrée `a-maintenance` (avant `a-benevolat`) :

```ts
      // Lecture du journal existant (#117) — sans elle, la promesse de trace
      // de `DeleteCourseDialog`/`WipeCoursesCard` était invérifiable (#501,
      // ADM-5). Pouvoir dédié : le journal couvre des entités que
      // `courses:delete`/`participations:wipe_all` ne gardent pas.
      {
        id: "a-journal",
        label: "Journal d'administration",
        description:
          "L'historique des gestes d'administration sur les données — qui, quoi, quand. Rien ici ne s'annule.",
        href: "/admin/journal",
        permission: "admin_log:read",
      },
```

- [ ] **Step 2: Écrire le test de la page**

Créer `frontend/app/admin/journal/page.test.tsx` :

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { AdminActionLogPage as AdminActionLogPageData } from "@/lib/types";

const { getActionLog } = vi.hoisted(() => ({ getActionLog: vi.fn() }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { getActionLog } };
});

import AdminJournalPage from "./page";

const PAGE: AdminActionLogPageData = {
  entries: [
    {
      id: 1,
      created_at: "2026-08-20T10:15:00Z",
      user_name: "Jean Dupont",
      action: "course.delete",
      entity_type: "course",
      entity_id: 42,
      payload: { name: "Triathlon de Nantes" },
    },
  ],
  total: 1,
};

/**
 * Garde d'accès : non re-testée ici, comme toute autre page de `app/admin/*`
 * (`app/admin/layout.tsx` la couvre déjà — voir `retours-utilisateurs/page.test.tsx`).
 */
describe("AdminJournalPage", () => {
  beforeEach(() => {
    getActionLog.mockReset();
    getActionLog.mockResolvedValue(PAGE);
  });

  it("affiche le journal", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <AdminJournalPage />
      </QueryClientProvider>,
    );

    expect(await screen.findByText(/Triathlon de Nantes/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Lancer le test, vérifier qu'il échoue**

Run: `cd frontend && npx vitest run app/admin/journal/page.test.tsx`
Expected: FAIL — `./page` n'existe pas.

- [ ] **Step 4: Écrire la page**

Créer `frontend/app/admin/journal/page.tsx` :

```tsx
import { PageHeader } from "@/components/layout/PageHeader";
import { ecran } from "@/components/layout/nav.config";
import { PageShell } from "@/components/layout/PageShell";
import { AdminActionLogTable } from "@/components/admin/AdminActionLogTable";

export default function AdminJournalPage() {
  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader {...ecran("/admin/journal")} />
        <AdminActionLogTable />
      </div>
    </PageShell>
  );
}
```

- [ ] **Step 5: Lancer le test, vérifier qu'il passe**

Run: `cd frontend && npx vitest run app/admin/journal/page.test.tsx`
Expected: PASS

- [ ] **Step 6: Vérifier que `nav.config.test.ts` reste vert**

Run: `cd frontend && npx vitest run components/layout/nav.config.test.ts`
Expected: PASS (l'entrée porte bien une `description`, exigée par `ecran()`)

- [ ] **Step 7: Commit**

```bash
git add frontend/app/admin/journal/page.tsx frontend/app/admin/journal/page.test.tsx frontend/components/layout/nav.config.ts
git commit -m "feat(501): écran /admin/journal et entrée de navigation"
```

---

### Task 10: Frontend — décomptes réels dans les trois messages de succès

**Files:**
- Modify: `frontend/components/admin/WipeCoursesCard.tsx`
- Modify: `frontend/components/admin/WipeCoursesCard.test.tsx`
- Modify: `frontend/components/admin/WipeParticipationsCard.tsx`
- Modify: `frontend/components/admin/WipeParticipationsCard.test.tsx`
- Modify: `frontend/components/admin/MergeCoursesDialog.tsx`
- Modify: `frontend/components/admin/MergeCoursesDialog.test.tsx`

**Interfaces:**
- Consumes: `CoursesWipeResult`/`ParticipationsWipeResult` (Task 6), `CourseMergeResult` (existant, déjà porteur des comptes).
- Produces: rien de nouveau — modifie le texte des trois toasts de succès existants.

- [ ] **Step 1: Mettre à jour le test de `WipeCoursesCard`**

Dans `frontend/components/admin/WipeCoursesCard.test.tsx`, remplacer le test `"s'active une fois SUPPRIMER tapé, et purge à la confirmation"` (lignes 155-171) :

```tsx
  it("s'active une fois SUPPRIMER tapé, et purge à la confirmation en annonçant le décompte réel", async () => {
    getSession.mockResolvedValue(session(["courses:wipe_all"]));
    getCoursesWipeImpact.mockResolvedValue({ courses: 53, participations: 412, athletes: 37 });
    wipeAllCourses.mockResolvedValue({ courses_deleted: 53, athletes_purged: 37 });

    afficher();
    await userEvent.click(
      await screen.findByRole("button", { name: /supprimer toutes les épreuves/i }),
    );
    await screen.findByText(/412/);
    await userEvent.type(screen.getByLabelText(/tapez/i), "SUPPRIMER");

    await userEvent.click(screen.getByRole("button", { name: /supprimer définitivement/i }));

    await waitFor(() => expect(wipeAllCourses).toHaveBeenCalled());
    expect(toastSuccess).toHaveBeenCalledWith(
      "53 épreuves supprimées, 37 fiches coureur purgées.",
    );
  });
```

- [ ] **Step 2: Lancer le test, vérifier qu'il échoue**

Run: `cd frontend && npx vitest run components/admin/WipeCoursesCard.test.tsx -t "décompte réel"`
Expected: FAIL — le toast actuel dit `"Toutes les épreuves ont été supprimées."`, sans décompte.

- [ ] **Step 3: Mettre à jour `WipeCoursesCard.tsx`**

Remplacer :

```ts
  async function confirmer() {
    try {
      await purge.mutateAsync();
      toast.success("Toutes les épreuves ont été supprimées.");
      setOuvert(false);
    } catch (erreur) {
      toast.error((erreur as Error).message);
    }
  }
```

par :

```ts
  async function confirmer() {
    try {
      const resultat = await purge.mutateAsync();
      const c = resultat.courses_deleted;
      const a = resultat.athletes_purged;
      toast.success(
        `${c} épreuve${c === 1 ? "" : "s"} supprimée${c === 1 ? "" : "s"}, ` +
          `${a} fiche${a === 1 ? "" : "s"} coureur purgée${a === 1 ? "" : "s"}.`,
      );
      setOuvert(false);
    } catch (erreur) {
      toast.error((erreur as Error).message);
    }
  }
```

- [ ] **Step 4: Lancer le test, vérifier qu'il passe**

Run: `cd frontend && npx vitest run components/admin/WipeCoursesCard.test.tsx`
Expected: PASS (tout le fichier)

- [ ] **Step 5: Même geste pour `WipeParticipationsCard`**

Dans `frontend/components/admin/WipeParticipationsCard.test.tsx`, remplacer le test `"s'active une fois SUPPRIMER tapé, et purge à la confirmation"` (lignes 137-151) :

```tsx
  it("s'active une fois SUPPRIMER tapé, et purge à la confirmation en annonçant le décompte réel", async () => {
    getSession.mockResolvedValue(session(["participations:wipe_all"]));
    getParticipationsWipeImpact.mockResolvedValue({ participations: 412, athletes: 37 });
    wipeAllParticipations.mockResolvedValue({
      participations_deleted: 412,
      athletes_purged: 37,
      courses_reset: 12,
    });

    afficher();
    await userEvent.click(await screen.findByRole("button", { name: /purger tous les résultats/i }));
    await screen.findByText(/412/);
    await userEvent.type(screen.getByLabelText(/tapez/i), "SUPPRIMER");

    await userEvent.click(screen.getByRole("button", { name: /purger définitivement/i }));

    await waitFor(() => expect(wipeAllParticipations).toHaveBeenCalled());
    expect(toastSuccess).toHaveBeenCalledWith(
      "412 résultats supprimés, 37 fiches coureur purgées.",
    );
  });
```

Dans `frontend/components/admin/WipeParticipationsCard.tsx`, remplacer :

```ts
  async function confirmer() {
    try {
      await purge.mutateAsync();
      toast.success("Tous les résultats ont été supprimés.");
      setOuvert(false);
    } catch (erreur) {
      toast.error((erreur as Error).message);
    }
  }
```

par :

```ts
  async function confirmer() {
    try {
      const resultat = await purge.mutateAsync();
      const p = resultat.participations_deleted;
      const a = resultat.athletes_purged;
      toast.success(
        `${p} résultat${p === 1 ? "" : "s"} supprimé${p === 1 ? "" : "s"}, ` +
          `${a} fiche${a === 1 ? "" : "s"} coureur purgée${a === 1 ? "" : "s"}.`,
      );
      setOuvert(false);
    } catch (erreur) {
      toast.error((erreur as Error).message);
    }
  }
```

- [ ] **Step 6: Lancer le test, vérifier qu'il passe**

Run: `cd frontend && npx vitest run components/admin/WipeParticipationsCard.test.tsx`
Expected: PASS

- [ ] **Step 7: Mettre à jour le test de `MergeCoursesDialog`**

Dans `frontend/components/admin/MergeCoursesDialog.test.tsx`, le test `"fusionne après confirmation et notifie le succès"` (lignes 180-198) vérifie déjà `toastSuccess` avec un `mergeCourses.mockResolvedValue` porteur des comptes (179, 4) — resserrer l'assertion. Le clic `/garder.*klikego/i` conserve `KLIKEGO` (id 38) comme cible, donc l'absorbée est `BREIZHCHRONO` (id 50) — les deux fixtures partagent le même `name`, `"Triathlon et SwimRun Mesquer-Quimiac 2026"` (déclarées lignes 24-46 du fichier) :

```tsx
    await waitFor(() => expect(mergeCourses).toHaveBeenCalledWith(38, 50));
    expect(toastSuccess).toHaveBeenCalledWith(
      "« Triathlon et SwimRun Mesquer-Quimiac 2026 » a été fusionnée dans la source conservée — " +
        "179 résultats sans correspondance ont disparu, 4 fiches coureur purgées.",
    );
```

- [ ] **Step 8: Lancer le test, vérifier qu'il échoue**

Run: `cd frontend && npx vitest run components/admin/MergeCoursesDialog.test.tsx -t "notifie le succès"`
Expected: FAIL — le toast actuel ne cite aucun chiffre.

- [ ] **Step 9: Mettre à jour `MergeCoursesDialog.tsx`**

Remplacer :

```ts
      await fusion.mutateAsync({ courseId: cibleId, absorbedId: absorbee.id });
      toast.success(
        `« ${absorbee.name} » a été fusionnée dans la source conservée — ses résultats sans correspondance ont disparu.`,
      );
```

par :

```ts
      const resultat = await fusion.mutateAsync({ courseId: cibleId, absorbedId: absorbee.id });
      const p = resultat.participations_deleted;
      const a = resultat.athletes_purged;
      toast.success(
        `« ${absorbee.name} » a été fusionnée dans la source conservée — ` +
          `${p} résultat${p === 1 ? "" : "s"} sans correspondance ${p === 1 ? "a" : "ont"} disparu, ` +
          `${a} fiche${a === 1 ? "" : "s"} coureur purgée${a === 1 ? "" : "s"}.`,
      );
```

- [ ] **Step 10: Lancer le test, vérifier qu'il passe**

Run: `cd frontend && npx vitest run components/admin/MergeCoursesDialog.test.tsx`
Expected: PASS

- [ ] **Step 11: Suite complète frontend**

Run: `cd frontend && npm test`
Expected: PASS, aucune régression.

- [ ] **Step 12: Commit**

```bash
git add frontend/components/admin/WipeCoursesCard.tsx frontend/components/admin/WipeCoursesCard.test.tsx frontend/components/admin/WipeParticipationsCard.tsx frontend/components/admin/WipeParticipationsCard.test.tsx frontend/components/admin/MergeCoursesDialog.tsx frontend/components/admin/MergeCoursesDialog.test.tsx
git commit -m "fix(501): les toasts de purge et de fusion annoncent le décompte réel"
```

---

## Final Verification

- [ ] Backend complet : `cd backend && uv run pytest -m "not integration" -n 0 && uv run ruff check .`
- [ ] Frontend complet : `cd frontend && npm test && npm run lint && npm run build`
- [ ] Revue manuelle : `npm run dev` (frontend) + `uv run python scripts/dev_server.py` (backend), se connecter avec un compte portant `admin_log:read`, ouvrir `/admin/journal`, vérifier l'affichage d'entrées existantes ; effectuer une purge de test sur une base de dev jetable et vérifier le message de succès chiffré.
