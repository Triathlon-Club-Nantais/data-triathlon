# Écran de revalidation qualité — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Livrer l'écran `/admin/quality` qui rassemble les épreuves douteuses, permet de trancher leur fiabilité en traçant la décision, et annonce leur nombre en badge de navigation.

**Architecture:** Quatre unités indépendantes. Un filtre `unreliable` sur le catalogue existant (aucune route neuve). Une trace d'audit ajoutée au geste de verdict déjà livré par #115. Un écran qui compose des briques existantes (`describeQualityIssues`, `EditCourseDialog`, `useRescrapeStream`). Un mécanisme de badge générique dans la table de navigation, avec une seule clé renseignée.

**Tech Stack:** Python 3.13 / FastAPI / SQLAlchemy 2.0 / pytest côté backend ; Next.js 16 App Router / TypeScript / TanStack Query / shadcn-ui / Vitest côté frontend.

**Spec:** `docs/superpowers/specs/2026-08-21-admin-revalidation-qualite-design.md`

## Global Constraints

- **Issue** : #119. Le message de PR devra porter `Closes #119`.
- **Langue** (Principe I de la constitution) : **français** pour tout ce qui est visible utilisateur ou métier — libellés d'interface, messages d'erreur affichés, commentaires de règle métier ; **anglais** pour la couche technique invisible — identifiants de code, noms de tests, docstrings techniques, valeurs stockées de `AdminActionLog.action`, préfixes de commit.
- **Architecture backend** : le flux ne va que dans un sens, `api → services → repositories → DB`. **Seuls les repositories touchent la `Session`** (Principe II).
- **Transactions** : les services font `flush`, **jamais** `commit` ; la route clôt la transaction. C'est ce qui rend un geste et sa trace indissociables.
- **Journal d'audit** : une demande sans effet n'est pas un geste et n'écrit **aucune** ligne.
- **Contrat v1** (Principe IV) : tout nouveau paramètre de `GET /courses` et `GET /courses/count` est optionnel et faux par défaut ; aucun appelant existant ne change de réponse.
- **TDD non négociable** (Principe III) : le test échoue d'abord, on le voit échouer, puis on implémente.
- **Style booléen SQLAlchemy** : `.is_(False)` / `.is_(True)`, jamais `== False` (convention du dépôt, `core/validation.py`).
- **Tests unitaires sans réseau.** Aucun test de ce plan ne porte le marker `integration`.
- **Commandes** : backend depuis `backend/` avec `uv run …` (aucun venv à activer) ; frontend depuis `frontend/` avec `npm …`.
- **Pouvoir de l'écran** : `quality:override`, déjà au catalogue (`core/permissions.py`). Aucun pouvoir à créer.

---

## Structure des fichiers

**Backend**

| Fichier | Responsabilité | Action |
| --- | --- | --- |
| `backend/app/repositories/course_repository.py` | Le filtre `unreliable` dans `_filtered`, `list_all`, `count_all` | Modifier |
| `backend/app/api/v1/courses.py` | Le paramètre `unreliable` sur les deux routes de catalogue | Modifier |
| `backend/app/schemas/admin.py` | `notes` sur `CourseReliabilityUpdate` | Modifier |
| `backend/app/services/course_review.py` | La trace du verdict | Modifier |
| `backend/app/api/v1/admin.py` | Passer l'auteur et les notes au service | Modifier |
| `backend/tests/test_repositories/test_course_reliability.py` | Le filtre, au niveau repository | Modifier |
| `backend/tests/test_api/test_courses_api.py` | Le filtre, au niveau route | Modifier ou créer |
| `backend/tests/test_services/test_course_review.py` | La trace, au niveau service | Modifier |
| `backend/tests/test_api/test_course_reliability_api.py` | Les notes et la trace, au niveau route | Modifier |

**Frontend**

| Fichier | Responsabilité | Action |
| --- | --- | --- |
| `frontend/lib/api/client.ts` | `unreliable` sur le catalogue, `setCourseReliability` | Modifier |
| `frontend/lib/queries/admin.ts` | `FiltresCourses.unreliable`, `enabled` sur le comptage, mutation de verdict | Modifier |
| `frontend/components/admin/ReliabilityVerdictDialog.tsx` | Le dialogue de confirmation portant les notes | Créer |
| `frontend/components/admin/QualityQueueTable.tsx` | La file, ses filtres, ses gestes | Créer |
| `frontend/app/admin/quality/page.tsx` | La page, qui lit l'URL | Créer |
| `frontend/lib/queries/nav-badges.ts` | Clé de badge → requête de comptage | Créer |
| `frontend/components/layout/nav.config.ts` | `badge` sur `NavItem`, `href` de l'entrée qualité | Modifier |
| `frontend/components/layout/AppNav.tsx` | Rendu du nombre dans le rail et le panneau | Modifier |

---

### Task 1: Le filtre `unreliable` au niveau repository

**Files:**
- Modify: `backend/app/repositories/course_repository.py:307-390`
- Test: `backend/tests/test_repositories/test_course_reliability.py`

**Interfaces:**
- Consumes: `Course.is_reliable` (hybrid property avec son `@expression`, `app/models/course.py`).
- Produces: `course_repository.list_all(db, …, unreliable: bool = False)` et `course_repository.count_all(db, …, unreliable: bool = False)`.

- [ ] **Step 1: Write the failing tests**

Ajouter à la fin de `backend/tests/test_repositories/test_course_reliability.py` :

```python
def _epreuve_filtrable(db_session, **colonnes):
    """Une épreuve nommée et datée, pour que le tri du catalogue ait prise."""
    course = Course(
        name=colonnes.pop("name", "Épreuve"),
        event_type="triathlon-m",
        event_date=colonnes.pop("event_date", date(2026, 6, 1)),
        **colonnes,
    )
    db_session.add(course)
    db_session.flush()
    return course


def test_le_filtre_unreliable_ne_garde_que_les_epreuves_douteuses(db_session):
    douteuse = _epreuve_filtrable(db_session, name="Douteuse", is_reliable_computed=False)
    _epreuve_filtrable(db_session, name="Fiable", is_reliable_computed=True)

    resultats = course_repository.list_all(db_session, unreliable=True)

    assert [c.id for c in resultats] == [douteuse.id]


def test_une_epreuve_jamais_evaluee_reste_hors_de_la_file(db_session):
    """`NULL` n'est pas « douteuse » : c'est « jamais évaluée ».

    L'y inclure ferait tomber dans la file toute la base antérieure à l'indice.
    """
    _epreuve_filtrable(db_session, name="Jamais évaluée", is_reliable_computed=None)

    assert course_repository.list_all(db_session, unreliable=True) == []


def test_l_avis_humain_favorable_sort_l_epreuve_de_la_file(db_session):
    """Le `coalesce` fait tout le travail : l'avis humain prime sur le calculé."""
    _epreuve_filtrable(
        db_session, name="Revalidée", is_reliable_computed=False, reliability_override=True
    )

    assert course_repository.list_all(db_session, unreliable=True) == []


def test_l_avis_humain_defavorable_fait_entrer_l_epreuve_dans_la_file(db_session):
    """Une épreuve que la machine juge saine mais qu'un humain conteste est du
    travail en attente, donc dans la file."""
    contestee = _epreuve_filtrable(
        db_session, name="Contestée", is_reliable_computed=True, reliability_override=False
    )

    resultats = course_repository.list_all(db_session, unreliable=True)

    assert [c.id for c in resultats] == [contestee.id]


def test_sans_le_filtre_le_catalogue_est_inchange(db_session):
    """Le paramètre est additif : son absence ne change aucune réponse."""
    _epreuve_filtrable(db_session, name="Douteuse", is_reliable_computed=False)
    _epreuve_filtrable(db_session, name="Fiable", is_reliable_computed=True)
    _epreuve_filtrable(db_session, name="Jamais évaluée", is_reliable_computed=None)

    assert len(course_repository.list_all(db_session)) == 3


def test_count_all_compte_le_meme_ensemble_que_list_all(db_session):
    """Sinon la pagination annoncerait une page 4 qui ne rend rien."""
    _epreuve_filtrable(db_session, name="Douteuse 1", is_reliable_computed=False)
    _epreuve_filtrable(db_session, name="Douteuse 2", is_reliable_computed=False)
    _epreuve_filtrable(db_session, name="Fiable", is_reliable_computed=True)

    assert course_repository.count_all(db_session, unreliable=True) == 2
    assert len(course_repository.list_all(db_session, unreliable=True)) == 2


def test_le_filtre_unreliable_se_combine_aux_filtres_du_catalogue(db_session):
    """Les filtres se composent — la file reste filtrable par nom et par date."""
    cible = _epreuve_filtrable(
        db_session, name="Triathlon de Vertou", is_reliable_computed=False
    )
    _epreuve_filtrable(db_session, name="Triathlon de Carnac", is_reliable_computed=False)

    resultats = course_repository.list_all(db_session, unreliable=True, name="Vertou")

    assert [c.id for c in resultats] == [cible.id]
```

Vérifier les imports en tête du fichier : il faut `from datetime import date`, `from app.models.course import Course` et `from app.repositories import course_repository`. Ajouter ceux qui manquent.

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/test_repositories/test_course_reliability.py -v
```

Attendu : ÉCHEC sur les sept nouveaux tests, avec `TypeError: list_all() got an unexpected keyword argument 'unreliable'`.

- [ ] **Step 3: Write the implementation**

Dans `backend/app/repositories/course_repository.py`, ajouter le paramètre à `_filtered` — signature et clause :

```python
def _filtered(
    db: Session,
    *,
    name: str | None,
    event_type: str | None,
    club_only: bool,
    date_from: date | None,
    date_to: date | None,
    unreliable: bool = False,
):
```

et, juste après le bloc `if date_to:` :

```python
    if unreliable:
        # `is_reliable` est `coalesce(reliability_override, is_reliable_computed)` :
        # l'avis humain prime, et `NULL` — « jamais évaluée » — n'entre pas dans la
        # comparaison, donc reste hors de la file. Toute la règle tient dans
        # l'`@expression` du modèle ; il n'y a rien à brancher ici.
        q = q.filter(Course.is_reliable.is_(False))
```

Puis propager dans `list_all` et `count_all` : ajouter `unreliable: bool = False` à leurs signatures (après `date_to`, avant `page` pour `list_all`) et `unreliable=unreliable` à leurs appels respectifs de `_filtered`.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/test_repositories/ -v && uv run ruff check .
```

Attendu : tous PASSENT, lint propre.

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/course_repository.py backend/tests/test_repositories/test_course_reliability.py
git commit -m "feat(courses): filtre les épreuves douteuses dans le catalogue (#119)"
```

---

### Task 2: Le filtre sur les routes de catalogue

**Files:**
- Modify: `backend/app/api/v1/courses.py:66-110`
- Test: `backend/tests/test_api/test_courses_api.py`

**Interfaces:**
- Consumes: `course_repository.list_all(…, unreliable=…)` et `count_all(…, unreliable=…)` (Task 1).
- Produces: `GET /api/v1/courses?unreliable=true` et `GET /api/v1/courses/count?unreliable=true`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_api/test_courses_api.py` existe déjà (contrat des routes de lecture, #163) : ajouter les tests **à la fin** du fichier. Ses imports portent déjà `from datetime import date` ; ajouter `from app.models.course import Course`.

```python
def _epreuve(db_session, **colonnes) -> Course:
    """Une épreuve minimale pour le filtre de revalidation (#119)."""
    course = Course(
        name=colonnes.pop("name", "Épreuve"),
        event_type="triathlon-m",
        event_date=colonnes.pop("event_date", date(2026, 6, 1)),
        **colonnes,
    )
    db_session.add(course)
    db_session.commit()
    return course


def test_le_catalogue_filtre_les_epreuves_douteuses(client, db_session):
    douteuse = _epreuve(db_session, name="Douteuse", is_reliable_computed=False)
    _epreuve(db_session, name="Fiable", is_reliable_computed=True)

    reponse = client.get("/api/v1/courses", params={"unreliable": "true"})

    assert reponse.status_code == 200
    assert [c["id"] for c in reponse.json()] == [douteuse.id]


def test_le_catalogue_rend_les_anomalies_de_chaque_epreuve_douteuse(client, db_session):
    """AC2 — l'écran décode `quality_issues`, encore faut-il que la route le rende."""
    _epreuve(
        db_session,
        name="Douteuse",
        is_reliable_computed=False,
        quality_issues={"rank_gap": 3, "duplicate_bib": 1},
    )

    corps = client.get("/api/v1/courses", params={"unreliable": "true"}).json()

    assert corps[0]["quality_issues"] == {"rank_gap": 3, "duplicate_bib": 1}
    assert corps[0]["is_reliable"] is False


def test_sans_le_parametre_la_reponse_est_inchangee(client, db_session):
    """Principe IV — l'ajout est additif, aucun appelant existant ne bouge."""
    _epreuve(db_session, name="Douteuse", is_reliable_computed=False)
    _epreuve(db_session, name="Fiable", is_reliable_computed=True)

    assert len(client.get("/api/v1/courses").json()) == 2


def test_le_comptage_suit_le_meme_filtre(client, db_session):
    _epreuve(db_session, name="Douteuse 1", is_reliable_computed=False)
    _epreuve(db_session, name="Douteuse 2", is_reliable_computed=False)
    _epreuve(db_session, name="Fiable", is_reliable_computed=True)

    reponse = client.get("/api/v1/courses/count", params={"unreliable": "true"})

    assert reponse.status_code == 200
    assert reponse.json()["total"] == 2


def test_la_file_est_triee_par_date_la_plus_recente(client, db_session):
    """AC1 — le tri vient de `list_all`, ce test le verrouille au niveau route."""
    ancienne = _epreuve(
        db_session, name="Ancienne", event_date=date(2025, 3, 1), is_reliable_computed=False
    )
    recente = _epreuve(
        db_session, name="Récente", event_date=date(2026, 9, 1), is_reliable_computed=False
    )

    corps = client.get("/api/v1/courses", params={"unreliable": "true"}).json()

    assert [c["id"] for c in corps] == [recente.id, ancienne.id]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/test_api/test_courses_api.py -v
```

Attendu : ÉCHEC — les deux premiers tests rendent 2 épreuves au lieu d'1, le paramètre étant ignoré par FastAPI.

- [ ] **Step 3: Write the implementation**

Dans `backend/app/api/v1/courses.py`, sur `list_courses` **et** `count_courses`, ajouter le paramètre juste après `date_to` :

```python
    unreliable: bool = Query(
        False,
        description="Ne garde que les épreuves à revalider (indice de fiabilité défavorable).",
    ),
```

et passer `unreliable=unreliable` aux appels `course_repository.list_all(…)` et `course_repository.count_all(…)` correspondants.

Ajouter en tête de `list_courses` la docstring qui nomme la décision :

```python
    """Le catalogue d'épreuves, filtrable.

    `unreliable=true` sert la file de revalidation (#119) : une route dédiée
    aurait dupliqué cette pagination, ce tri et cette sérialisation pour le seul
    bénéfice d'un préfixe d'URL. Le paramètre n'expose rien de neuf —
    `CourseBrief` rend `is_reliable` et `quality_issues` depuis l'origine.
    """
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/test_api/ -v && uv run ruff check .
```

Attendu : tous PASSENT, lint propre.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/courses.py backend/tests/test_api/test_courses_api.py
git commit -m "feat(api): expose le filtre unreliable sur le catalogue (#119)"
```

---

### Task 3: Les notes et la trace du verdict

**Files:**
- Modify: `backend/app/schemas/admin.py:465-475` (`CourseReliabilityUpdate`)
- Modify: `backend/app/services/course_review.py` (intégralement)
- Modify: `backend/app/api/v1/admin.py:77-99` (`set_course_reliability`)
- Test: `backend/tests/test_services/test_course_review.py`
- Test: `backend/tests/test_api/test_course_reliability_api.py`

**Interfaces:**
- Consumes: `admin_action_log_repository.create(db, *, user_id, action, entity_type, entity_id, payload)`.
- Produces: `course_review.set_override(db, course, *, verdict: bool | None, user_id: int, notes: str | None = None) -> Course`. **`user_id` est obligatoire** : une trace sans auteur ne prouve rien. Les cinq tests existants de `test_course_review.py` appellent la fonction sans lui et doivent être mis à jour dans cette tâche.

- [ ] **Step 1: Write the failing tests**

D'abord, mettre à jour les cinq appels existants dans `backend/tests/test_services/test_course_review.py` pour qu'ils passent un auteur. Ajouter en tête du fichier une fixture d'auteur :

```python
from app.repositories import admin_action_log_repository, course_repository, user_repository


def _auteur(db_session) -> int:
    user = user_repository.create(db_session, email="validateur@exemple.fr")
    db_session.flush()
    return user.id
```

puis, dans chacun des cinq tests, remplacer les appels `course_review.set_override(db_session, course, verdict=…)` par `course_review.set_override(db_session, course, verdict=…, user_id=_auteur(db_session))` — en appelant `_auteur` une seule fois par test, stocké dans une variable locale `auteur`.

Ensuite, ajouter les tests de la trace :

```python
def test_le_verdict_est_journalise_avec_ses_notes(db_session):
    """AC3 — la décision est tracée, avec le motif que le validateur a saisi."""
    auteur = _auteur(db_session)
    course = _epreuve(db_session, is_reliable_computed=False, quality_issues={"rank_gap": 3})

    course_review.set_override(
        db_session,
        course,
        verdict=True,
        user_id=auteur,
        notes="Trous vérifiés à la source : classement correct.",
    )

    traces = admin_action_log_repository.list_for_entity(
        db_session, entity_type="course", entity_id=course.id
    )
    assert len(traces) == 1
    assert traces[0].action == "course.reliability"
    assert traces[0].user_id == auteur
    assert traces[0].payload == {
        "before": None,
        "after": True,
        "computed": False,
        "notes": "Trous vérifiés à la source : classement correct.",
    }


def test_un_verdict_deja_en_place_n_ecrit_aucune_trace(db_session):
    """Une demande sans effet n'est pas un geste : un journal rempli de
    non-événements est un journal qu'on cesse de lire."""
    auteur = _auteur(db_session)
    course = _epreuve(db_session, is_reliable_computed=False)
    course_review.set_override(db_session, course, verdict=True, user_id=auteur)

    course_review.set_override(db_session, course, verdict=True, user_id=auteur)

    traces = admin_action_log_repository.list_for_entity(
        db_session, entity_type="course", entity_id=course.id
    )
    assert len(traces) == 1, "le second appel ne change rien, donc ne trace rien"


def test_lever_l_avis_est_un_geste_et_se_trace(db_session):
    auteur = _auteur(db_session)
    course = _epreuve(db_session, is_reliable_computed=False)
    course_review.set_override(db_session, course, verdict=True, user_id=auteur)

    course_review.set_override(db_session, course, verdict=None, user_id=auteur)

    traces = admin_action_log_repository.list_for_entity(
        db_session, entity_type="course", entity_id=course.id
    )
    assert len(traces) == 2
    assert traces[0].payload["before"] is True
    assert traces[0].payload["after"] is None


def test_lever_un_avis_absent_ne_trace_rien(db_session):
    """Rien à lever, donc rien qui change, donc rien à consigner."""
    auteur = _auteur(db_session)
    course = _epreuve(db_session, is_reliable_computed=True)

    course_review.set_override(db_session, course, verdict=None, user_id=auteur)

    assert (
        admin_action_log_repository.list_for_entity(
            db_session, entity_type="course", entity_id=course.id
        )
        == []
    )


def test_les_notes_sont_facultatives(db_session):
    auteur = _auteur(db_session)
    course = _epreuve(db_session, is_reliable_computed=False)

    course_review.set_override(db_session, course, verdict=True, user_id=auteur)

    traces = admin_action_log_repository.list_for_entity(
        db_session, entity_type="course", entity_id=course.id
    )
    assert traces[0].payload["notes"] is None
```

Et, dans `backend/tests/test_api/test_course_reliability_api.py`, les tests de bout en bout :

```python
def test_le_patch_transmet_les_notes_au_journal(client, db_session, epreuve_douteuse):
    """AC3 de bout en bout : le geste et sa trace partagent la transaction."""
    reponse = client.patch(
        f"/api/v1/admin/courses/{epreuve_douteuse.id}/reliability",
        json={"reliability_override": True, "notes": "Vérifié à la source."},
    )

    assert reponse.status_code == 200
    traces = admin_action_log_repository.list_for_entity(
        db_session, entity_type="course", entity_id=epreuve_douteuse.id
    )
    assert len(traces) == 1
    assert traces[0].payload["notes"] == "Vérifié à la source."
    assert traces[0].payload["after"] is True


def test_le_patch_refuse_des_notes_hors_limite(client, epreuve_douteuse):
    """Un champ texte libre écrit en base se borne, même derrière une session."""
    reponse = client.patch(
        f"/api/v1/admin/courses/{epreuve_douteuse.id}/reliability",
        json={"reliability_override": True, "notes": "x" * 501},
    )

    assert reponse.status_code == 422


def test_le_patch_sans_notes_reste_accepte(client, db_session, epreuve_douteuse):
    reponse = client.patch(
        f"/api/v1/admin/courses/{epreuve_douteuse.id}/reliability",
        json={"reliability_override": True},
    )

    assert reponse.status_code == 200
    traces = admin_action_log_repository.list_for_entity(
        db_session, entity_type="course", entity_id=epreuve_douteuse.id
    )
    assert traces[0].payload["notes"] is None


def test_un_refus_n_ecrit_ni_verdict_ni_trace(client, db_session, epreuve_douteuse):
    """Le geste et sa trace partagent la transaction : un refus lève **avant**,
    et rien n'est écrit — ni la donnée, ni le journal."""
    _session_etroite(client, db_session)  # aucun pouvoir

    reponse = client.patch(
        f"/api/v1/admin/courses/{epreuve_douteuse.id}/reliability",
        json={"reliability_override": True, "notes": "Tentative."},
    )

    assert reponse.status_code == 403
    db_session.refresh(epreuve_douteuse)
    assert epreuve_douteuse.reliability_override is None
    assert (
        admin_action_log_repository.list_for_entity(
            db_session, entity_type="course", entity_id=epreuve_douteuse.id
        )
        == []
    )
```

Ajouter `admin_action_log_repository` à la liste importée depuis `app.repositories` en tête de `test_course_reliability_api.py`. Les tests de refus par pouvoir insuffisant (`403`) déjà présents dans ce fichier restent valables tels quels — ils couvrent la garde `quality:override` demandée par le design.

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/test_services/test_course_review.py tests/test_api/test_course_reliability_api.py -v
```

Attendu : ÉCHEC — `TypeError: set_override() got an unexpected keyword argument 'user_id'` côté service, et `422` sur `notes` (champ interdit par `extra="forbid"`) côté route.

- [ ] **Step 3: Write the implementation**

**3a.** Dans `backend/app/schemas/admin.py`, ajouter le champ à `CourseReliabilityUpdate` :

```python
class CourseReliabilityUpdate(BaseModel):
    """L'avis humain sur la fiabilité d'une épreuve. `null` **lève** l'avis."""

    model_config = ConfigDict(extra="forbid")

    reliability_override: bool | None = None
    #: Le motif de la décision, consigné au journal (#119, AC3). Facultatif —
    #: un verdict sans commentaire reste un verdict — mais borné : un champ
    #: texte libre écrit en base se borne, même derrière une session.
    notes: str | None = Field(default=None, max_length=500)
```

**3b.** Réécrire `backend/app/services/course_review.py` :

```python
"""Revue humaine de la fiabilité d'une épreuve (#115, FR-036 ; tracée par #119).

**Aucune branche, aucun recalcul** : `Course.is_reliable` est
`coalesce(reliability_override, is_reliable_computed)`, la propriété fait le
travail. Lever l'avis humain fait donc réapparaître le *dernier* verdict
calculé — pas celui qui valait au moment de la décision (FR-039).
"""
from sqlalchemy.orm import Session

from app.models.course import Course
from app.repositories import admin_action_log_repository


def set_override(
    db: Session,
    course: Course,
    *,
    verdict: bool | None,
    user_id: int,
    notes: str | None = None,
) -> Course:
    """Pose (`True`/`False`) ou **lève** (`None`) l'avis humain, et le consigne.

    N'écrit jamais `is_reliable_computed` : les deux chemins d'écriture ne se
    croisent pas, et c'est la forme qui l'assure — pas une garde applicative
    qu'un import distrait pourrait contourner (FR-037).

    `flush`, jamais `commit` : la route clôt la transaction, ce qui rend le
    verdict et sa trace indissociables. Et **rien n'est consigné quand rien ne
    change** — reposer le verdict déjà en place n'est pas un geste.
    """
    avant = course.reliability_override
    if avant == verdict:
        return course

    course.reliability_override = verdict
    admin_action_log_repository.create(
        db,
        user_id=user_id,
        action="course.reliability",
        entity_type="course",
        entity_id=course.id,
        payload={
            # Les trois valeurs, parce qu'elles ne se déduisent pas l'une de
            # l'autre : « la machine doutait, un humain a tranché l'inverse »
            # est précisément ce qu'une relecture du journal doit pouvoir dire.
            "before": avant,
            "after": verdict,
            "computed": course.is_reliable_computed,
            "notes": notes,
        },
    )
    db.flush()
    return course
```

**3c.** Dans `backend/app/api/v1/admin.py`, la route passe l'auteur et les notes — renommer la dépendance `_` en `user` :

```python
@router.patch(
    "/admin/courses/{course_id}/reliability", response_model=CourseReliabilityRead
)
def set_course_reliability(
    course_id: int,
    body: CourseReliabilityUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(P.QUALITY_OVERRIDE)),
):
    """Tranche à la main la fiabilité d'une épreuve, contre l'avis calculé.

    `null` **lève** l'avis humain : l'épreuve reprend son verdict calculé, à jour
    — le *dernier*, pas celui qui valait au moment de la décision (FR-039).

    Rend les **trois** valeurs, et c'est délibéré : elles ne se déduisent pas
    l'une de l'autre, et c'est ce qu'une interface de revue doit montrer.
    """
    course = course_repository.get(db, course_id)
    if course is None:
        raise NotFoundError("Épreuve introuvable")
    course_review.set_override(
        db,
        course,
        verdict=body.reliability_override,
        user_id=user.id,
        notes=body.notes,
    )
    db.commit()
    db.refresh(course)
    return course
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && uv run pytest -m "not integration" -q && uv run ruff check .
```

Attendu : toute la suite PASSE, lint propre. Si un autre appelant de `set_override` apparaît dans les erreurs, le corriger — il doit fournir un `user_id`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/admin.py backend/app/services/course_review.py backend/app/api/v1/admin.py backend/tests/test_services/test_course_review.py backend/tests/test_api/test_course_reliability_api.py
git commit -m "feat(admin): journalise le verdict de fiabilité et ses notes (#119)"
```

---

### Task 4: La couche d'accès frontend

**Files:**
- Modify: `frontend/lib/api/client.ts:171-183` (catalogue) et section administration
- Modify: `frontend/lib/queries/admin.ts:70-101`
- Test: `frontend/lib/queries/admin.test.ts`

**Interfaces:**
- Consumes: `GET /courses?unreliable=true`, `GET /courses/count?unreliable=true`, `PATCH /admin/courses/{id}/reliability` (Tasks 2 et 3).
- Produces:
  - `FiltresCourses` gagne `unreliable?: true` (littéral `true`, jamais `false` — voir Step 3).
  - `useAdminCoursesCount(filtres: FiltresCourses = {}, actif = true)`.
  - `useSetCourseReliability()` → mutation `{ courseId: number; verdict: boolean | null; notes?: string }`.
  - `apiClient.setCourseReliability(id, { reliability_override, notes })` → `CourseReliability`.
  - Type `CourseReliability` dans `lib/types.ts`.

- [ ] **Step 1: Write the failing tests**

Dans `frontend/lib/queries/admin.test.ts`, trois modifications :

1. ajouter `countCourses: vi.fn()` et `setCourseReliability: vi.fn()` au bloc `vi.hoisted` **et** à l'objet `apiClient` du `vi.mock` ;
2. ajouter `useAdminCoursesCount` et `useSetCourseReliability` à l'import `from "./admin"` ;
3. ajouter le bloc suivant à la fin du fichier. Il réutilise le `wrapper` et la variable `client` déjà définis en tête (`wrapper` est un composant, pas une fabrique : il se passe tel quel).

```typescript
describe("file de revalidation qualité (#119)", () => {
  beforeEach(() => {
    client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    countCourses.mockReset();
    setCourseReliability.mockReset();
  });

  it("n'émet le comptage de la file que si l'appel est actif", async () => {
    const { result } = renderHook(() => useAdminCoursesCount({ unreliable: true }, false), {
      wrapper,
    });

    await waitFor(() => expect(result.current.fetchStatus).toBe("idle"));
    expect(countCourses).not.toHaveBeenCalled();
  });

  it("émet le comptage de la file quand l'appel est actif", async () => {
    countCourses.mockResolvedValue({ total: 4 });

    const { result } = renderHook(() => useAdminCoursesCount({ unreliable: true }), {
      wrapper,
    });

    await waitFor(() => expect(result.current.data).toEqual({ total: 4 }));
    expect(countCourses).toHaveBeenCalledWith({ unreliable: true });
  });

  it("transmet verdict et notes au PATCH de fiabilité", async () => {
    setCourseReliability.mockResolvedValue({
      id: 7,
      is_reliable: true,
      is_reliable_computed: false,
      reliability_override: true,
      quality_issues: { rank_gap: 3 },
    });

    const { result } = renderHook(() => useSetCourseReliability(), { wrapper });
    await result.current.mutateAsync({ courseId: 7, verdict: true, notes: "Vérifié." });

    expect(setCourseReliability).toHaveBeenCalledWith(7, {
      reliability_override: true,
      notes: "Vérifié.",
    });
  });

  it("omet les notes quand le motif est vide", async () => {
    setCourseReliability.mockResolvedValue({});

    const { result } = renderHook(() => useSetCourseReliability(), { wrapper });
    await result.current.mutateAsync({ courseId: 7, verdict: null });

    expect(setCourseReliability).toHaveBeenCalledWith(7, { reliability_override: null });
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npx vitest run lib/queries/admin.test.ts
```

Attendu : ÉCHEC — `useSetCourseReliability is not a function`, et `useAdminCoursesCount` n'accepte pas de second argument.

- [ ] **Step 3: Write the implementation**

**4a.** Dans `frontend/lib/types.ts`, à la suite de `CourseBrief` :

```typescript
/** Les trois verdicts d'une épreuve, rendus par `PATCH …/reliability` (#115). */
export interface CourseReliability {
  id: number;
  is_reliable: boolean | null;
  is_reliable_computed: boolean | null;
  reliability_override: boolean | null;
  quality_issues: Record<string, number> | null;
}
```

**4b.** Dans `frontend/lib/api/client.ts`, ajouter `unreliable?: true` aux deux signatures du catalogue et la mutation de verdict :

```typescript
  listCourses: (
    opts: {
      name?: string;
      event_type?: string;
      date_from?: string;
      date_to?: string;
      // `true` seul, jamais `false` : `toQuery` sérialise tout ce qui n'est ni
      // `undefined`, ni `null`, ni `""` — un `false` partirait en
      // `?unreliable=false` et brouillerait les clés de cache pour rien.
      unreliable?: true;
      page?: number;
      page_size?: number;
    } = {},
  ) => request<CourseBrief[]>(`/courses${toQuery(opts)}`),
  countCourses: (
    opts: {
      name?: string;
      event_type?: string;
      date_from?: string;
      date_to?: string;
      unreliable?: true;
    } = {},
  ) => request<{ total: number }>(`/courses/count${toQuery(opts)}`),
```

et, dans la section administration :

```typescript
  // ── Revalidation qualité (#119) ────────────────────────────────────────────
  // `quality:override`. `reliability_override: null` **lève** l'avis humain et
  // fait reprendre le verdict calculé ; `notes` motive la décision au journal.
  setCourseReliability: (
    id: number,
    body: { reliability_override: boolean | null; notes?: string },
  ) =>
    request<CourseReliability>(`/admin/courses/${id}/reliability`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
```

Ajouter `CourseReliability` à la liste des types importés en tête du fichier.

**4c.** Dans `frontend/lib/queries/admin.ts` :

```typescript
/** Les filtres du catalogue, tels que `GET /courses` les accepte. */
export type FiltresCourses = {
  name?: string;
  event_type?: string;
  date_from?: string;
  date_to?: string;
  /** La file de revalidation (#119). `true` seul — voir `client.listCourses`. */
  unreliable?: true;
};
```

`useAdminCoursesCount` gagne son interrupteur :

```typescript
/**
 * Le total du catalogue aux mêmes filtres — le « sur 7 » de la pagination.
 *
 * Clé **sans la page** : feuilleter ne redemande pas un total qui ne bouge pas.
 *
 * `actif` sert le badge de navigation (#119), monté sur **toutes** les pages :
 * sans lui, chaque visiteur paierait un comptage qu'il n'a pas le droit de voir.
 */
export function useAdminCoursesCount(filtres: FiltresCourses = {}, actif = true) {
  return useQuery({
    queryKey: queryKeys.adminCoursesCount(filtres as Record<string, string>),
    queryFn: () => apiClient.countCourses(filtres),
    placeholderData: (precedent) => precedent,
    enabled: actif,
  });
}
```

et la mutation, à placer près de `useUpdateCourse` :

```typescript
/**
 * Trancher la fiabilité d'une épreuve (#119, `quality:override`).
 *
 * `verdict: null` **lève** l'avis humain. L'invalidation de « admin-courses »
 * suffit à faire sortir la ligne de la file : la file n'est qu'une vue filtrée
 * du catalogue, il n'y a aucune seconde liste à tenir à jour (AC4).
 */
export function useSetCourseReliability() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      courseId,
      verdict,
      notes,
    }: {
      courseId: number;
      verdict: boolean | null;
      notes?: string;
    }) =>
      apiClient.setCourseReliability(courseId, {
        reliability_override: verdict,
        ...(notes ? { notes } : {}),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.courses });
      qc.invalidateQueries({ queryKey: CACHES_ADMIN.detailEpreuve });
    },
  });
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd frontend && npx vitest run lib/queries/admin.test.ts && npm run lint
```

Attendu : PASSENT, lint propre.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/api/client.ts frontend/lib/queries/admin.ts frontend/lib/queries/admin.test.ts
git commit -m "feat(frontend): accès API de la file de revalidation qualité (#119)"
```

---

### Task 5: Le dialogue de verdict

**Files:**
- Create: `frontend/components/admin/ReliabilityVerdictDialog.tsx`
- Test: `frontend/components/admin/ReliabilityVerdictDialog.test.tsx`

**Interfaces:**
- Consumes: `useSetCourseReliability()` (Task 4), `describeQualityIssues()` (`@/lib/quality`), `CourseBrief` (`@/lib/types`).
- Produces:
  ```typescript
  export type Verdict = "fiable" | "douteuse" | "calcule";
  export function ReliabilityVerdictDialog(props: {
    course: CourseBrief;
    verdict: Verdict | null;   // `null` = fermé
    onOpenChange: (ouvert: boolean) => void;
  }): JSX.Element;
  ```

- [ ] **Step 1: Write the failing test**

Créer `frontend/components/admin/ReliabilityVerdictDialog.test.tsx` :

```typescript
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { CourseBrief } from "@/lib/types";

const { setCourseReliability } = vi.hoisted(() => ({ setCourseReliability: vi.fn() }));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, apiClient: { setCourseReliability } };
});

import { ReliabilityVerdictDialog } from "./ReliabilityVerdictDialog";

const EPREUVE: CourseBrief = {
  id: 7,
  name: "Triathlon de Vertou",
  event_date: "2026-06-13",
  event_type: "triathlon-s",
  provider: "klikego",
  source_url: "https://klikego.com/x",
  is_relay: false,
  is_reliable: false,
  quality_issues: { rank_gap: 3 },
};

function rendre(verdict: "fiable" | "douteuse" | "calcule") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const onOpenChange = vi.fn();
  render(
    <QueryClientProvider client={client}>
      <ReliabilityVerdictDialog course={EPREUVE} verdict={verdict} onOpenChange={onOpenChange} />
    </QueryClientProvider>,
  );
  return { onOpenChange };
}

beforeEach(() => {
  setCourseReliability.mockReset();
  setCourseReliability.mockResolvedValue({
    id: 7,
    is_reliable: true,
    is_reliable_computed: false,
    reliability_override: true,
    quality_issues: { rank_gap: 3 },
  });
});

describe("ReliabilityVerdictDialog", () => {
  it("envoie true et les notes saisies pour « Marquer OK »", async () => {
    rendre("fiable");

    await userEvent.type(
      screen.getByLabelText(/motif/i),
      "Classement vérifié à la source.",
    );
    await userEvent.click(screen.getByRole("button", { name: /confirmer/i }));

    await waitFor(() =>
      expect(setCourseReliability).toHaveBeenCalledWith(7, {
        reliability_override: true,
        notes: "Classement vérifié à la source.",
      }),
    );
  });

  it("envoie false pour « Marquer douteuse »", async () => {
    rendre("douteuse");

    await userEvent.click(screen.getByRole("button", { name: /confirmer/i }));

    await waitFor(() =>
      expect(setCourseReliability).toHaveBeenCalledWith(7, { reliability_override: false }),
    );
  });

  it("envoie null pour « Revenir à l'avis calculé »", async () => {
    rendre("calcule");

    await userEvent.click(screen.getByRole("button", { name: /confirmer/i }));

    await waitFor(() =>
      expect(setCourseReliability).toHaveBeenCalledWith(7, { reliability_override: null }),
    );
  });

  it("rappelle les anomalies relevées, décodées", () => {
    rendre("fiable");

    expect(screen.getByText(/3 trous dans le classement/i)).toBeInTheDocument();
  });

  it("ferme après un envoi réussi", async () => {
    const { onOpenChange } = rendre("fiable");

    await userEvent.click(screen.getByRole("button", { name: /confirmer/i }));

    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run components/admin/ReliabilityVerdictDialog.test.tsx
```

Attendu : ÉCHEC — `Failed to resolve import "./ReliabilityVerdictDialog"`.

- [ ] **Step 3: Write the implementation**

Créer `frontend/components/admin/ReliabilityVerdictDialog.tsx` :

```tsx
"use client";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { describeQualityIssues } from "@/lib/quality";
import { useSetCourseReliability } from "@/lib/queries/admin";
import type { CourseBrief } from "@/lib/types";

/** Les trois gestes que porte `PATCH …/reliability`, nommés côté écran. */
export type Verdict = "fiable" | "douteuse" | "calcule";

/**
 * Un seul dialogue pour les trois gestes de verdict (#119).
 *
 * Trois modales quasi identiques auraient divergé au premier ajustement de
 * microcopie, et le champ « motif » — le seul contenu réel de l'écran — y aurait
 * été recopié trois fois. Ce qui change entre les gestes tient dans la table
 * `TEXTES` ci-dessous.
 *
 * Le motif est **facultatif** : un verdict sans commentaire reste un verdict, et
 * rendre la saisie obligatoire ferait écrire « ok » trois cents fois.
 */
const TEXTES: Record<Verdict, { titre: string; corps: string; valeur: boolean | null }> = {
  fiable: {
    titre: "Marquer cette épreuve comme fiable",
    corps:
      "Elle sortira de la file de revalidation. L'indice calculé, lui, est conservé : il reparaîtra si vous revenez à l'avis de la machine.",
    valeur: true,
  },
  douteuse: {
    titre: "Marquer cette épreuve comme douteuse",
    corps:
      "Elle restera dans la file de revalidation, même si la machine ne relève plus rien après un re-scrape.",
    valeur: false,
  },
  calcule: {
    titre: "Revenir à l'avis calculé",
    corps:
      "Votre décision est retirée et l'épreuve reprend le **dernier** verdict de la machine — pas celui qui valait au moment de votre décision.",
    valeur: null,
  },
};

export function ReliabilityVerdictDialog({
  course,
  verdict,
  onOpenChange,
}: {
  course: CourseBrief;
  /** `null` = fermé. */
  verdict: Verdict | null;
  onOpenChange: (ouvert: boolean) => void;
}) {
  const [motif, setMotif] = useState("");
  const decision = useSetCourseReliability();

  // Rouvrir sur une autre épreuve ne doit pas hériter du motif précédent : ce
  // serait consigner au journal une justification écrite pour un autre cas.
  useEffect(() => {
    if (verdict) setMotif("");
  }, [verdict, course.id]);

  const textes = verdict ? TEXTES[verdict] : null;
  const anomalies = describeQualityIssues(course.quality_issues);

  async function confirmer() {
    if (!textes) return;
    try {
      await decision.mutateAsync({
        courseId: course.id,
        verdict: textes.valeur,
        notes: motif.trim() || undefined,
      });
      toast.success("Décision enregistrée.");
      onOpenChange(false);
    } catch (erreur) {
      toast.error(erreur instanceof Error ? erreur.message : "Décision refusée.");
    }
  }

  return (
    <Dialog open={verdict !== null} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{textes?.titre}</DialogTitle>
          <DialogDescription>
            {course.name} — {textes?.corps}
          </DialogDescription>
        </DialogHeader>

        {anomalies.length > 0 && (
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {anomalies.map((phrase) => (
              <li key={phrase}>{phrase}</li>
            ))}
          </ul>
        )}

        <div className="space-y-2">
          <Label htmlFor="motif-verdict">Motif (facultatif)</Label>
          <Textarea
            id="motif-verdict"
            value={motif}
            maxLength={500}
            onChange={(e) => setMotif(e.target.value)}
            placeholder="Ce qui a été vérifié, et comment."
          />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Annuler
          </Button>
          <Button onClick={confirmer} disabled={decision.isPending}>
            {decision.isPending ? "Enregistrement…" : "Confirmer"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npx vitest run components/admin/ReliabilityVerdictDialog.test.tsx && npm run lint
```

Attendu : les cinq tests PASSENT, lint propre.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/admin/ReliabilityVerdictDialog.tsx frontend/components/admin/ReliabilityVerdictDialog.test.tsx
git commit -m "feat(admin): dialogue de verdict de fiabilité avec motif (#119)"
```

---

### Task 6: La file et sa page

**Files:**
- Create: `frontend/components/admin/QualityQueueTable.tsx`
- Create: `frontend/components/admin/QualityQueueTable.test.tsx`
- Create: `frontend/app/admin/quality/page.tsx`
- Modify: `frontend/components/layout/nav.config.ts` (entrée `a-quality`)

**Interfaces:**
- Consumes: `useAdminCourses(page, { unreliable: true, …filtres })`, `useAdminCoursesCount`, `TAILLE_PAGE_ADMIN`, `FiltresCourses` (Task 4) ; `ReliabilityVerdictDialog` et son type `Verdict` (Task 5) ; `EditCourseDialog` ; `useRescrapeStream` ; `describeQualityIssues` ; `useSession`.
- Produces: `QualityQueueTable({ page?: number; filtres?: FiltresCourses })`, monté par `app/admin/quality/page.tsx`.

- [ ] **Step 1: Write the failing test**

Créer `frontend/components/admin/QualityQueueTable.test.tsx` :

```typescript
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { CourseBrief, SessionUser } from "@/lib/types";

const { listCourses, countCourses, setCourseReliability, getSession } = vi.hoisted(() => ({
  listCourses: vi.fn(),
  countCourses: vi.fn(),
  setCourseReliability: vi.fn(),
  getSession: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return {
    ...original,
    apiClient: { listCourses, countCourses, setCourseReliability, getSession },
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/admin/quality",
}));

import { QualityQueueTable } from "./QualityQueueTable";

const AVEC_POUVOIR: SessionUser = {
  id: 1,
  email: "validateur@exemple.fr",
  permissions: ["quality:override"],
  roles: [],
  created_at: "2026-01-01T00:00:00Z",
} as unknown as SessionUser;

const SANS_POUVOIR: SessionUser = { ...AVEC_POUVOIR, permissions: [] } as SessionUser;

const VERTOU: CourseBrief = {
  id: 7,
  name: "Triathlon de Vertou",
  event_date: "2026-06-13",
  event_type: "triathlon-s",
  provider: "klikego",
  source_url: "https://klikego.com/x",
  is_relay: false,
  is_reliable: false,
  quality_issues: { rank_gap: 3 },
};

const CARNAC: CourseBrief = {
  ...VERTOU,
  id: 8,
  name: "Triathlon de Carnac",
  event_date: "2026-05-02",
  quality_issues: { duplicate_bib: 2 },
};

function rendre() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <QualityQueueTable />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  listCourses.mockReset();
  countCourses.mockReset();
  setCourseReliability.mockReset();
  getSession.mockReset();
  listCourses.mockResolvedValue([VERTOU, CARNAC]);
  countCourses.mockResolvedValue({ total: 2 });
  getSession.mockResolvedValue(AVEC_POUVOIR);
  setCourseReliability.mockResolvedValue({
    id: 7,
    is_reliable: true,
    is_reliable_computed: false,
    reliability_override: true,
    quality_issues: { rank_gap: 3 },
  });
});

describe("QualityQueueTable", () => {
  it("ne demande que les épreuves à revalider", async () => {
    rendre();

    await waitFor(() =>
      expect(listCourses).toHaveBeenCalledWith(
        expect.objectContaining({ unreliable: true }),
      ),
    );
  });

  it("affiche les anomalies de chaque épreuve en libellés lisibles (AC2)", async () => {
    rendre();

    expect(await screen.findByText(/3 trous dans le classement/i)).toBeInTheDocument();
    expect(screen.getByText(/2 dossards en doublon/i)).toBeInTheDocument();
  });

  it("« Marquer OK » envoie le verdict favorable (AC4)", async () => {
    rendre();
    const ligne = (await screen.findByText("Triathlon de Vertou")).closest("tr")!;

    await userEvent.click(within(ligne).getByRole("button", { name: /marquer ok/i }));
    await userEvent.click(await screen.findByRole("button", { name: /confirmer/i }));

    await waitFor(() =>
      expect(setCourseReliability).toHaveBeenCalledWith(
        7,
        expect.objectContaining({ reliability_override: true }),
      ),
    );
  });

  it("n'offre aucun geste de verdict sans le pouvoir", async () => {
    getSession.mockResolvedValue(SANS_POUVOIR);
    rendre();

    await screen.findByText("Triathlon de Vertou");
    expect(screen.queryByRole("button", { name: /marquer ok/i })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /marquer douteuse/i }),
    ).not.toBeInTheDocument();
  });

  it("le filtre par anomalie restreint les lignes affichées", async () => {
    rendre();
    await screen.findByText("Triathlon de Vertou");

    await userEvent.selectOptions(
      screen.getByLabelText(/anomalie/i),
      "rank_gap",
    );

    expect(screen.getByText("Triathlon de Vertou")).toBeInTheDocument();
    expect(screen.queryByText("Triathlon de Carnac")).not.toBeInTheDocument();
  });

  it("annonce une file vide sans faire disparaître ses filtres", async () => {
    listCourses.mockResolvedValue([]);
    countCourses.mockResolvedValue({ total: 0 });
    rendre();

    expect(await screen.findByText(/aucune épreuve à revalider/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/anomalie/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run components/admin/QualityQueueTable.test.tsx
```

Attendu : ÉCHEC — `Failed to resolve import "./QualityQueueTable"`.

- [ ] **Step 3: Write the implementation**

Créer `frontend/components/admin/QualityQueueTable.tsx` :

```tsx
"use client";
import { useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { toast } from "sonner";
import { Pencil, RefreshCw } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { eventTypeLabel, providerLabel } from "@/lib/constants";
import { describeQualityIssues } from "@/lib/quality";
import {
  useAdminCourses,
  useAdminCoursesCount,
  TAILLE_PAGE_ADMIN,
  type FiltresCourses,
} from "@/lib/queries/admin";
import { useSession } from "@/lib/queries/auth";
import { formatDate } from "@/lib/utils/date";
import { useRescrapeStream } from "@/hooks/useRescrapeStream";
import type { CourseBrief } from "@/lib/types";
import { EditCourseDialog } from "./EditCourseDialog";
import { ReliabilityVerdictDialog, type Verdict } from "./ReliabilityVerdictDialog";

/**
 * La file de revalidation qualité (#119).
 *
 * **Une vue filtrée du catalogue, pas une seconde liste** : `GET /courses` avec
 * `unreliable=true` pagine, trie par date décroissante et rend déjà
 * `quality_issues`. Une route dédiée aurait dupliqué tout cela pour un préfixe
 * d'URL, et une seconde liste à tenir à jour après chaque verdict.
 *
 * Un composant distinct de `CoursesAdminTable`, en revanche : les colonnes et
 * les gestes ne sont pas les mêmes, et un composant à deux personnalités, c'est
 * une branche par ligne de rendu et un test par branche.
 *
 * **Le filtre par anomalie agit côté client**, sur la page affichée :
 * `quality_issues` est une colonne JSON, et la filtrer en SQL divergerait entre
 * SQLite (dev) et PostgreSQL (prod). Il affine la page, il ne cherche pas
 * au-delà — à rouvrir le jour où la file dépasse durablement une page.
 */
export function QualityQueueTable({
  page: pageDemandee = 1,
  filtres = {},
}: {
  page?: number;
  filtres?: FiltresCourses;
}) {
  const router = useRouter();
  const chemin = usePathname();
  const page = Math.max(1, Math.trunc(pageDemandee) || 1);

  const requete = { ...filtres, unreliable: true as const };
  const { data, isLoading, error } = useAdminCourses(page, requete);
  const { data: comptage } = useAdminCoursesCount(requete);
  const session = useSession();
  const rescrape = useRescrapeStream();

  const [anomalie, setAnomalie] = useState("");
  const [aTrancher, setATrancher] = useState<{ course: CourseBrief; verdict: Verdict } | null>(
    null,
  );
  const [aCorriger, setACorriger] = useState<CourseBrief | null>(null);

  // Le serveur reste seul juge : ces tests n'autorisent rien, ils évitent de
  // proposer un bouton qui rendrait 403.
  const pouvoirs = session.data?.permissions ?? [];
  const peutTrancher = pouvoirs.includes("quality:override");
  const peutCorriger = pouvoirs.includes("courses:write");
  const peutRescraper = pouvoirs.includes("courses:sources");

  const lignes = data ?? [];
  const affichees = anomalie
    ? lignes.filter((c) => Boolean(c.quality_issues?.[anomalie]))
    : lignes;

  // Les codes proposés sont ceux réellement présents sur la page : une liste
  // figée offrirait des filtres qui ne rendent jamais rien.
  const codes = [...new Set(lignes.flatMap((c) => Object.keys(c.quality_issues ?? {})))];

  const total = comptage?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / TAILLE_PAGE_ADMIN));

  function naviguer(valeurs: FiltresCourses, versLaPage: number) {
    const qs = new URLSearchParams();
    Object.entries(valeurs).forEach(([cle, valeur]) => valeur && qs.set(cle, String(valeur)));
    if (versLaPage > 1) qs.set("page", String(versLaPage));
    router.push(qs.size ? `${chemin}?${qs}` : chemin);
  }

  async function relancer(course: CourseBrief) {
    await rescrape.start(course.id);
    toast.success("Re-scrape terminé — l'indice sera recalculé à l'import.");
  }

  // La barre de filtres reste montée dans **tous** les états : la retirer sur
  // une file vide enfermerait le validateur dans son propre filtre.
  const barre = (
    <Card>
      <CardContent className="flex flex-wrap items-end gap-3 pt-6">
        <div className="space-y-1">
          <label className="text-sm" htmlFor="filtre-nom">
            Nom de l'épreuve
          </label>
          <Input
            id="filtre-nom"
            defaultValue={filtres.name ?? ""}
            onBlur={(e) => naviguer({ ...filtres, name: e.target.value || undefined }, 1)}
          />
        </div>
        <div className="space-y-1">
          <label className="text-sm" htmlFor="filtre-anomalie">
            Anomalie
          </label>
          <select
            id="filtre-anomalie"
            className="h-9 rounded-md border px-3 text-sm"
            value={anomalie}
            onChange={(e) => setAnomalie(e.target.value)}
          >
            <option value="">Toutes</option>
            {codes.map((code) => (
              <option key={code} value={code}>
                {describeQualityIssues({ [code]: 1 })[0]}
              </option>
            ))}
          </select>
        </div>
      </CardContent>
    </Card>
  );

  if (isLoading) {
    return (
      <div className="space-y-4">
        {barre}
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        {barre}
        <EmptyState title="La file n'a pas pu être chargée." description={String(error)} />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {barre}

      {affichees.length === 0 ? (
        <EmptyState
          title="Aucune épreuve à revalider"
          description="Toutes les épreuves du catalogue passent l'indice de fiabilité, ou ont été tranchées à la main."
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Épreuve</TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Anomalies</TableHead>
              <TableHead>Verdict</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {affichees.map((course) => (
              <TableRow key={course.id}>
                <TableCell>
                  <div className="font-medium">{course.name}</div>
                  <div className="text-xs text-muted-foreground">
                    {eventTypeLabel(course.event_type)} · {providerLabel(course.provider)}
                  </div>
                </TableCell>
                <TableCell>{formatDate(course.event_date)}</TableCell>
                <TableCell>
                  <ul className="space-y-1 text-sm">
                    {describeQualityIssues(course.quality_issues).map((phrase) => (
                      <li key={phrase}>{phrase}</li>
                    ))}
                  </ul>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {/* Le calculé **et** l'humain : ils ne se déduisent pas l'un de
                      l'autre, et c'est ce qu'une interface de revue doit montrer. */}
                  Machine : {libelleVerdict(course.is_reliable)}
                </TableCell>
                <TableCell className="space-x-2 text-right">
                  {peutTrancher && (
                    <>
                      <Button
                        size="sm"
                        onClick={() => setATrancher({ course, verdict: "fiable" })}
                      >
                        Marquer OK
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setATrancher({ course, verdict: "douteuse" })}
                      >
                        Marquer douteuse
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setATrancher({ course, verdict: "calcule" })}
                      >
                        Revenir à l'avis calculé
                      </Button>
                    </>
                  )}
                  {peutRescraper && (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={rescrape.state.running}
                      onClick={() => relancer(course)}
                      aria-label={`Re-scraper ${course.name}`}
                    >
                      <RefreshCw size={14} />
                    </Button>
                  )}
                  {peutCorriger && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setACorriger(course)}
                      aria-label={`Éditer ${course.name}`}
                    >
                      <Pencil size={14} />
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {pages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <span>
            Page {page} sur {pages} — {total} épreuve{total > 1 ? "s" : ""} à revalider
          </span>
          <div className="space-x-2">
            <Button
              size="sm"
              variant="outline"
              disabled={page <= 1}
              onClick={() => naviguer(filtres, page - 1)}
            >
              Précédente
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={page >= pages}
              onClick={() => naviguer(filtres, page + 1)}
            >
              Suivante
            </Button>
          </div>
        </div>
      )}

      {aTrancher && (
        <ReliabilityVerdictDialog
          course={aTrancher.course}
          verdict={aTrancher.verdict}
          onOpenChange={(ouvert) => !ouvert && setATrancher(null)}
        />
      )}
      {aCorriger && (
        <EditCourseDialog
          course={aCorriger}
          open
          onOpenChange={(ouvert) => !ouvert && setACorriger(null)}
        />
      )}
    </div>
  );
}

function libelleVerdict(verdict: boolean | null | undefined): string {
  if (verdict === true) return "fiable";
  if (verdict === false) return "douteuse";
  return "jamais évaluée";
}
```

Créer `frontend/app/admin/quality/page.tsx` :

```tsx
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { QualityQueueTable } from "@/components/admin/QualityQueueTable";

/**
 * Revalidation qualité (#119).
 *
 * Aucune garde ici : le `layout.tsx` de `/admin` couvre déjà ses sous-routes, et
 * chaque geste porte la sienne côté serveur. **C'est la page qui lit l'URL**,
 * comme `/admin/courses` : `useSearchParams` dans le tableau forcerait une
 * frontière `Suspense`, faute de quoi le prérendu de la route échoue au build.
 */
export default async function AdminQualityPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;

  return (
    <PageShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Administration"
          title="Revalidation qualité"
          description="Les épreuves dont l'indice de fiabilité doute. Inspecter, corriger, puis trancher — chaque décision est tracée."
        />
        <QualityQueueTable
          page={Number(sp.page)}
          filtres={{ name: sp.name, date_from: sp.date_from, date_to: sp.date_to }}
        />
      </div>
    </PageShell>
  );
}
```

Dans `frontend/components/layout/nav.config.ts`, livrer l'entrée :

```typescript
      {
        id: "a-quality",
        label: "Revalidation qualité",
        href: "/admin/quality",
        permission: "quality:override",
      },
```

Et retirer, dans le commentaire qui précède les entrées `soon`, la phrase « La revalidation qualité, elle, a le sien depuis #115. » devenue sans objet.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd frontend && npx vitest run components/admin/QualityQueueTable.test.tsx && npm run build && npm run lint
```

Attendu : les six tests PASSENT, le build strict passe (la route `/admin/quality` apparaît dans la sortie), lint propre.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/admin/QualityQueueTable.tsx frontend/components/admin/QualityQueueTable.test.tsx frontend/app/admin/quality/page.tsx frontend/components/layout/nav.config.ts
git commit -m "feat(admin): écran de revalidation qualité (#119)"
```

---

### Task 7: Le badge de navigation

**Files:**
- Create: `frontend/lib/queries/nav-badges.ts`
- Modify: `frontend/components/layout/nav.config.ts` (type `NavItem`, entrée `a-quality`)
- Modify: `frontend/components/layout/AppNav.tsx:31` (`Destination`), `:103-118` (filtrage), `Tuile`, `Entree`
- Test: `frontend/components/layout/AppNav.test.tsx`

**Interfaces:**
- Consumes: `useAdminCoursesCount(filtres, actif)` (Task 4).
- Produces: `useNavBadges(pouvoirs: Set<string>): Record<string, number | undefined>` ; `NavItem.badge?: string` ; `Destination` gagne `count?: number`.

- [ ] **Step 1: Write the failing test**

Dans `frontend/components/layout/AppNav.test.tsx`, deux modifications :

1. ajouter `countCourses: vi.fn()` au bloc `vi.hoisted` **et** à l'objet `apiClient` du `vi.mock` ;
2. ajouter le bloc suivant à la fin du fichier. Il réutilise les assistants déjà définis en tête : `afficher(session)` monte `AppNav` sous un `QueryClientProvider`, `habilite(...pouvoirs)` fabrique la session, et `deplier()` ouvre le rail — c'est là que les libellés des entrées apparaissent.

```typescript
describe("badge de la file de revalidation (#119)", () => {
  beforeEach(() => {
    countCourses.mockReset();
  });

  it("affiche le nombre d'épreuves à revalider sur son entrée", async () => {
    countCourses.mockResolvedValue({ total: 4 });
    afficher(habilite("quality:override"));
    await deplier();

    const entree = await screen.findByRole("link", { name: /revalidation qualité/i });
    expect(await within(entree).findByText("4")).toBeInTheDocument();
  });

  it("n'affiche aucun badge quand la file est vide", async () => {
    countCourses.mockResolvedValue({ total: 0 });
    afficher(habilite("quality:override"));
    await deplier();

    const entree = await screen.findByRole("link", { name: /revalidation qualité/i });
    await waitFor(() => expect(countCourses).toHaveBeenCalled());
    expect(within(entree).queryByText("0")).not.toBeInTheDocument();
  });

  it("n'émet aucun comptage pour qui ne porte pas le pouvoir", async () => {
    afficher(habilite("feedback:read"));
    await deplier();

    await screen.findByRole("link", { name: /retours utilisateurs/i });
    expect(countCourses).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run components/layout/AppNav.test.tsx
```

Attendu : ÉCHEC — aucun « 4 » dans l'entrée, et `countCourses` non défini sur le mock.

- [ ] **Step 3: Write the implementation**

**7a.** Créer `frontend/lib/queries/nav-badges.ts` :

```typescript
"use client";
import { useAdminCoursesCount } from "./admin";

/**
 * Les compteurs annoncés par la navigation (#119).
 *
 * `nav.config.ts` ne porte qu'une **clé** — une table de configuration ne fait
 * pas de requête. La correspondance clé → requête vit ici, et chaque requête
 * n'est émise que si la session porte le pouvoir de l'écran : la nav est montée
 * sur toutes les pages, un comptage inconditionnel le ferait payer à chaque
 * visiteur, y compris anonyme.
 *
 * Une seule clé est branchée pour l'instant. Brancher « Doublons » ou « Retours
 * utilisateurs » tiendra en une ligne ici plus une dans `nav.config.ts` — mais
 * ces écrans rendent aujourd'hui des listes complètes sans route de comptage,
 * et télécharger une liste pour en afficher la taille serait payer cher un
 * chiffre.
 */
export function useNavBadges(pouvoirs: Set<string>): Record<string, number | undefined> {
  const qualite = useAdminCoursesCount({ unreliable: true }, pouvoirs.has("quality:override"));
  return { quality: qualite.data?.total };
}
```

**7b.** Dans `frontend/components/layout/nav.config.ts`, ajouter le champ au type `NavItem` :

```typescript
  /**
   * Clé du compteur affiché en badge, résolue par `useNavBadges`
   * (`lib/queries/nav-badges.ts`). Une **clé**, jamais un nombre : cette table
   * est de la configuration, elle ne fait pas de requête.
   *
   * Le badge est masqué à zéro — un « 0 » permanent est du bruit — et la requête
   * n'est émise que si la session porte le `permission` de l'entrée.
   */
  badge?: string;
```

et poser la clé sur l'entrée qualité :

```typescript
      {
        id: "a-quality",
        label: "Revalidation qualité",
        href: "/admin/quality",
        permission: "quality:override",
        badge: "quality",
      },
```

**7c.** Dans `frontend/components/layout/AppNav.tsx` :

Étendre le type de destination (ligne 31) :

```typescript
type Destination = NavItem & { href: string; count?: number };
```

Importer le hook et l'appeler juste après `const pouvoirs = …`, puis enrichir les items pendant le filtrage :

```typescript
import { useNavBadges } from "@/lib/queries/nav-badges";

// …
  const pouvoirs = new Set(session?.permissions ?? []);
  const badges = useNavBadges(pouvoirs);
  const sections = NAV.filter((s) => rank >= s.minRole)
    .map((s) => ({
      ...s,
      items: s.items
        .filter(
          (i): i is Destination =>
            !!i.href &&
            !i.soon &&
            rank >= (i.minRole ?? ROLE.ANON) &&
            (!i.permission || pouvoirs.has(i.permission)),
        )
        // Le compteur est attaché à la destination plutôt que passé en prop à
        // travers `NavContent` : il suit l'entrée jusqu'aux deux rendus (tuile
        // et ligne dépliée) sans élargir trois signatures au passage.
        .map((i) => (i.badge ? { ...i, count: badges[i.badge] } : i)),
    }))
    .filter((s) => s.items.length > 0);
```

Dans `Tuile`, après l'icône (le rail replié n'a pas de place pour un nombre : une pastille suffit à dire « il y a quelque chose ») :

```tsx
      {Icon && <Icon size={20} />}
      {!!item.count && (
        <span
          aria-hidden
          style={{
            position: "absolute",
            top: 6,
            right: 6,
            width: 7,
            height: 7,
            borderRadius: "var(--tcn-radius-pill)",
            background: "var(--tcn-orange)",
          }}
        />
      )}
      {actif && <span style={barreActive(9)} />}
```

Dans `Entree`, à l'intérieur de `corps`, après le libellé :

```tsx
      <span style={{ flex: 1 }}>{item.label}</span>
      {!!item.count && (
        <span
          style={{
            flex: "none",
            minWidth: 20,
            padding: "1px 6px",
            borderRadius: "var(--tcn-radius-pill)",
            background: "var(--tcn-orange)",
            color: "#fff",
            fontSize: 11,
            fontWeight: 700,
            textAlign: "center",
          }}
        >
          {item.count}
        </span>
      )}
```

Vérifier que `Tuile` porte bien `position: "relative"` (via `tuile(actif)`) ; sinon l'ajouter au style du `Link`, faute de quoi la pastille se positionnerait sur un ancêtre.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd frontend && npx vitest run components/layout/AppNav.test.tsx && npm test && npm run build && npm run lint
```

Attendu : les trois nouveaux tests PASSENT, toute la suite Vitest PASSE, build strict et lint propres.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/queries/nav-badges.ts frontend/components/layout/nav.config.ts frontend/components/layout/AppNav.tsx frontend/components/layout/AppNav.test.tsx
git commit -m "feat(frontend): badge de compteur sur la navigation d'administration (#119)"
```

---

## Vérification finale

- [ ] **Backend complet**

```bash
cd backend && uv run pytest -m "not integration" -q && uv run ruff check .
```

- [ ] **Frontend complet**

```bash
cd frontend && npm test && npm run build && npm run lint
```

- [ ] **Revue manuelle des critères d'acceptation**

Démarrer les deux serveurs (`uv run python scripts/dev_server.py`, `npm run dev`), se connecter avec un compte portant `quality:override`, puis vérifier :

| Critère | Vérification |
| --- | --- |
| AC1 | `/admin/quality` liste les épreuves douteuses, la plus récente en tête ; aucune épreuve « jamais évaluée » n'y figure |
| AC2 | chaque ligne affiche ses anomalies en français |
| AC3 | après un « Marquer OK » avec motif, `SELECT * FROM admin_action_log WHERE action='course.reliability'` rend la ligne, motif compris |
| AC4 | l'épreuve tranchée disparaît de la file sans rechargement manuel |
| AC5 | le badge de l'entrée « Revalidation qualité » affiche le compte, et disparaît à zéro |
| AC6 | les deux suites de tests sont vertes |

- [ ] **Fin de branche** — dans l'ordre : `superpowers:requesting-code-review`, puis le sous-agent `ui-ux-review` (la branche touche `frontend/`), puis `superpowers:verification-before-completion`, puis `superpowers:finishing-a-development-branch`. La description de PR porte `Closes #119`.
