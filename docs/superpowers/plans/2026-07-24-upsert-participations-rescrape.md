# Upsert des participations au ré-import — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre `_Persister` idempotent sur les **valeurs** — un dossard déjà en base voit ses champs rafraîchis (fusion prudente) au lieu d'être ignoré — et propager un compteur `updated` de bout en bout (SSE, batch, bilans CLI, front).

**Architecture:** Point de persistance unique inchangé (`import_service._Persister.add`), commun aux trois entrées (rescrape-db, import-sheet, web SSE). Le persister cesse d'être en insertion seule : il charge les `Participation` de la course (une requête, comme aujourd'hui), apparie par dossard (ou par athlète non ambigu sans dossard), et n'écrit que les champs dont la source apporte une valeur **non vide et différente**. L'identité (`athlete_id`) reste une clé d'appariement, jamais réécrite — la réconciliation d'identité est le périmètre séparé de #66/#67.

**Tech Stack:** Python 3.13, SQLAlchemy 2.0 (sync), pytest, ruff (backend) ; Next.js 16, TypeScript, Vitest + RTL (frontend).

**Spec de référence :** `docs/superpowers/specs/2026-07-14-upsert-participations-rescrape-design.md`

## Global Constraints

- **Aucune dépendance nouvelle** — ni Python ni npm.
- **UI, commentaires, messages en français** (avec accents).
- **Tests unitaires sans réseau** ; le réseau réel est isolé derrière le marker `integration`.
- **TDD strict** : test en premier (RED), implémentation minimale (GREEN), commit.
- **ruff clean** côté backend (`uv run ruff check .`), **ESLint clean** côté frontend.
- Commandes backend depuis `backend/` avec `UV_CACHE_DIR="$TMPDIR/uv-cache"` (cache par défaut en lecture seule dans ce worktree) ; commandes frontend depuis `frontend/`.
- Conventional Commits (`feat:`, `test:`, `refactor:`…).
- **« Vide » se définit strictement** : `None`, `""`, `{}`. **`False` et `0` n'en sont pas** (un `is_relay=False` corrige un `True` erroné).
- **`athlete_id`, `course_id`, `bib_number`** ne sont jamais réécrits par la fusion (clés d'appariement / d'identité).

---

### Task 1 : `participation_repository.update()`

**Files:**
- Modify: `backend/app/repositories/participation_repository.py` (après `create`, ~ligne 79)
- Test: `backend/tests/test_repositories/test_participation_repository.py`

**Interfaces:**
- Consumes: modèle `Participation` (déjà en place).
- Produces: `update(db: Session, participation: Participation, **fields) -> Participation` — écrit les `fields` fournis sur la ligne, `flush`, renvoie la ligne. C'est le **seul** écrivain de mise à jour ; consommé par `_Persister` (Task 2/3).

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter dans `backend/tests/test_repositories/test_participation_repository.py` (créer le fichier s'il n'existe pas, avec l'en-tête ci-dessous) :

```python
from app.models.athlete import Athlete
from app.models.course import Course
from app.repositories import participation_repository


def _athlete_course(db):
    athlete = Athlete(nom="DUPONT", prenom="Jean")
    course = Course(name="Triathlon de Nantes", event_type="triathlon-m", source_url="http://x")
    db.add_all([athlete, course])
    db.flush()
    return athlete, course


def test_update_ecrit_les_champs_fournis(db_session):
    athlete, course = _athlete_course(db_session)
    p = participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id,
        bib_number="1", total_time="01:00:00", status="finisher",
    )

    participation_repository.update(db_session, p, total_time="00:59:00", rank_overall=3)

    refreshed = participation_repository.get(db_session, p.id)
    assert refreshed.total_time == "00:59:00"
    assert refreshed.rank_overall == 3
    assert refreshed.bib_number == "1"  # champ non fourni → inchangé
```

- [ ] **Step 2 : Lancer le test, vérifier l'échec**

Run: `UV_CACHE_DIR="$TMPDIR/uv-cache" uv run pytest tests/test_repositories/test_participation_repository.py::test_update_ecrit_les_champs_fournis -v`
Expected: FAIL — `AttributeError: module 'app.repositories.participation_repository' has no attribute 'update'`

- [ ] **Step 3 : Implémenter `update`**

Dans `backend/app/repositories/participation_repository.py`, juste après `create` :

```python
def update(db: Session, participation: Participation, **fields) -> Participation:
    """Écrit les `fields` fournis sur une participation existante.

    Ne touche que les colonnes passées : le persister a déjà décidé, champ par
    champ, lesquelles la source a le droit de réécrire (fusion prudente).
    """
    for key, value in fields.items():
        setattr(participation, key, value)
    db.flush()
    return participation
```

- [ ] **Step 4 : Lancer le test, vérifier le succès**

Run: `UV_CACHE_DIR="$TMPDIR/uv-cache" uv run pytest tests/test_repositories/test_participation_repository.py -v`
Expected: PASS

- [ ] **Step 5 : Commit**

```bash
git add backend/app/repositories/participation_repository.py backend/tests/test_repositories/test_participation_repository.py
git commit -m "feat(repo): update() pour rafraîchir une participation existante"
```

---

### Task 2 : `_Persister` — upsert prudent sur le chemin dossard

**Files:**
- Modify: `backend/app/services/import_service.py` (classe `_Persister`, lignes 59-136)
- Test: `backend/tests/test_services/test_import_service.py`

**Interfaces:**
- Consumes: `participation_repository.update` (Task 1), `participation_repository.list_for_course`, `mapping.participation_fields`, `mapping.get_or_create_course`, `ScrapedResult.status`, constantes `STATUS_FINISHER`/`STATUS_DNF` de `app.scrapers.base`.
- Produces: `_Persister` expose désormais `self.updated: int` (en plus de `imported`/`skipped`). Helpers de module `_is_empty(value) -> bool`, `_merge_fields(existing, fields) -> dict`, `_resolve_status(existing, scraped, changes) -> str`. Consommés par Task 4 (retours de `import_event`/`iter_import_event`).

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter dans `backend/tests/test_services/test_import_service.py` (le helper `_expire_cache` existe déjà dans ce fichier) :

```python
def test_reimport_rafraichit_un_temps_corrige(db_session, patch_scraper):
    """Un temps corrigé à la source met à jour la participation existante."""
    patch_scraper([_result("1", "DUPONT", total_time="01:59:00", rank_overall=5)])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([_result("1", "DUPONT", total_time="01:58:30", rank_overall=3)])
    out = import_service.import_event(db_session, URL, _settings(), force=True)
    assert out == {"imported": 0, "updated": 1, "skipped": 0}

    parts = participation_repository.list_participations(db_session, page_size=100)
    assert len(parts) == 1
    assert parts[0].total_time == "01:58:30"
    assert parts[0].rank_overall == 3


def test_reimport_valeur_vide_n_ecrase_pas(db_session, patch_scraper):
    """Une valeur vide venue de la source ne remplace jamais une valeur en base."""
    patch_scraper([_result("1", "DUPONT", total_time="01:59:00")])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    # Source temporairement amputée du temps total.
    patch_scraper([_result("1", "DUPONT", total_time="")])
    out = import_service.import_event(db_session, URL, _settings(), force=True)
    assert out == {"imported": 0, "updated": 0, "skipped": 1}

    parts = participation_repository.list_participations(db_session, page_size=100)
    assert parts[0].total_time == "01:59:00"  # survit
    assert parts[0].status == "finisher"       # re-dérivé du temps FUSIONNÉ


def test_reimport_ligne_identique_compte_en_skipped(db_session, patch_scraper):
    """Une ligne inchangée ne déclenche aucun UPDATE : elle compte en skipped."""
    patch_scraper([_result("1", "DUPONT", total_time="01:59:00", rank_overall=2)])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([_result("1", "DUPONT", total_time="01:59:00", rank_overall=2)])
    out = import_service.import_event(db_session, URL, _settings(), force=True)
    assert out == {"imported": 0, "updated": 0, "skipped": 1}


def test_reimport_is_relay_false_corrige_un_true(db_session, patch_scraper):
    """`is_relay=False` n'est pas une valeur vide : il doit corriger un `True` en base."""
    patch_scraper([_result("1", "DUPONT", is_relay=True)])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([_result("1", "DUPONT", is_relay=False)])
    out = import_service.import_event(db_session, URL, _settings(), force=True)
    assert out == {"imported": 0, "updated": 1, "skipped": 0}
    assert participation_repository.list_participations(db_session, page_size=100)[0].is_relay is False


def test_reimport_statut_explicite_ecrase(db_session, patch_scraper):
    """Un statut affirmé par le scraper écrase celui en base."""
    patch_scraper([_result("1", "DUPONT", total_time="01:59:00")])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([_result("1", "DUPONT", total_time="01:59:00", status="DSQ")])
    out = import_service.import_event(db_session, URL, _settings(), force=True)
    assert out == {"imported": 0, "updated": 1, "skipped": 0}
    assert participation_repository.list_participations(db_session, page_size=100)[0].status == "DSQ"


def test_reimport_ajoute_un_nouveau_dossard_et_met_a_jour_l_ancien(db_session, patch_scraper):
    """Mélange : dossard connu corrigé (updated) + dossard neuf (imported)."""
    patch_scraper([_result("1", "DUPONT", total_time="01:59:00")])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([
        _result("1", "DUPONT", total_time="01:58:00"),  # updated
        _result("2", "MARTIN", total_time="02:05:00"),  # imported
    ])
    out = import_service.import_event(db_session, URL, _settings(), force=True)
    assert out == {"imported": 1, "updated": 1, "skipped": 0}
```

- [ ] **Step 2 : Lancer les tests, vérifier l'échec**

Run: `UV_CACHE_DIR="$TMPDIR/uv-cache" uv run pytest tests/test_services/test_import_service.py::test_reimport_rafraichit_un_temps_corrige -v`
Expected: FAIL — le retour vaut `{"imported": 0, "skipped": 1}` (pas de clé `updated`, aucune mise à jour).

- [ ] **Step 3 : Réécrire `_Persister` (chemin dossard) et ajouter les helpers**

Dans `backend/app/services/import_service.py`, ajouter l'import de statut en tête :

```python
from app.scrapers.base import STATUS_DNF, STATUS_FINISHER, ScrapedResult
```

Ajouter les helpers de module avant la classe `_Persister` :

```python
#: Clés d'appariement / d'identité : jamais réécrites par la fusion prudente.
#: `athlete_id` en fait partie — la réconciliation d'identité est le périmètre
#: séparé de #66/#67, pas celui de ce rafraîchissement de valeurs.
_CLES_APPARIEMENT = frozenset({"athlete_id", "course_id", "bib_number"})


def _is_empty(value: object) -> bool:
    """Vide au sens de la fusion prudente : `None`, chaîne vide, dict vide.

    `False` et `0` n'en sont **pas** : un `is_relay=False` est une affirmation du
    scraper, pas une absence, et doit pouvoir corriger un `True` erroné. Un test
    de vérité pythonien (`if value:`) confondrait les deux — d'où l'égalité
    explicite, qui distingue `False`/`0` de `""`/`{}` (`False == {}` est faux).
    """
    return value is None or value == "" or value == {}


def _merge_fields(existing, fields: dict) -> dict:
    """Champs à écrire : source non vide ET différente de la base.

    `status` est exclu ici (traité par `_resolve_status`, car jamais vide) ; les
    clés d'appariement aussi. Comparer avant d'écrire évite des `UPDATE` inutiles
    sur des milliers de lignes inchangées et distingue `updated` de `skipped`.
    """
    changes = {}
    for key, value in fields.items():
        if key in _CLES_APPARIEMENT or key == "status":
            continue
        if _is_empty(value):
            continue
        if getattr(existing, key) != value:
            changes[key] = value
    return changes


def _resolve_status(existing, scraped: ScrapedResult, changes: dict) -> str:
    """Statut fusionné. Un statut explicite du scraper écrase ; sinon on le
    re-dérive du `total_time` **fusionné** (base + écrasement éventuel), jamais du
    scrapé seul : une source ayant perdu le temps ne doit pas basculer un
    finisher en DNF alors que le temps, lui, survit (vide n'écrase pas).
    """
    if scraped.status:
        return scraped.status
    merged_total = changes.get("total_time", existing.total_time)
    return STATUS_FINISHER if merged_total else STATUS_DNF
```

Réécrire la classe `_Persister` — `__init__`, `add`, et une nouvelle méthode `_upsert` ; `finalize` est inchangée :

```python
class _Persister:
    """Persiste les résultats scrapés en **upsert**, avec déduplication.

    Point de persistance unique des trois entrées (rescrape-db, import-sheet, web
    SSE). Deux clés d'appariement, par course :
      - le dossard, quand il existe (`uq_participation_bib`) ;
      - sinon l'athlète, en **multiset** — mais la mise à jour ne s'applique que
        si l'athlète n'a qu'une seule participation sur la course (cf. `add`).

    Une ligne appariée est **fusionnée prudemment** (`_merge_fields`) : la source
    ne réécrit que ses valeurs non vides. `athlete_id` n'est jamais réécrit.
    """

    def __init__(self, db: Session, event_url: str):
        self.db = db
        self.event_url = event_url
        self._by_bib: dict[int, dict[str, "Participation"]] = {}
        self._added_bibs: dict[int, set[str]] = {}
        self._duplicate_bibs: dict[int, int] = {}
        self._without_bib: dict[int, dict[int, list["Participation"]]] = {}
        self._credits: dict[int, dict[int, int]] = {}
        self._updated_single: dict[int, set[int]] = {}
        self._courses: dict[int, Course] = {}
        self.imported = 0
        self.updated = 0
        self.skipped = 0

    def _index_course(self, course_id: int) -> None:
        """Charge et indexe une fois les participations de la course (une requête)."""
        if course_id in self._by_bib:
            return
        rows = participation_repository.list_for_course(self.db, course_id)
        by_bib: dict[str, Participation] = {}
        without: dict[int, list[Participation]] = {}
        for row in rows:
            if row.bib_number:
                by_bib[row.bib_number] = row
            else:
                without.setdefault(row.athlete_id, []).append(row)
        self._by_bib[course_id] = by_bib
        self._added_bibs[course_id] = set()
        self._without_bib[course_id] = without
        self._credits[course_id] = {aid: len(rs) for aid, rs in without.items()}
        self._updated_single[course_id] = set()

    def _upsert(self, existing: "Participation", scraped: ScrapedResult) -> None:
        """Fusionne prudemment une ligne appariée. Compte `updated` ou `skipped`."""
        fields = mapping.participation_fields(
            scraped, athlete_id=existing.athlete_id, course_id=existing.course_id
        )
        changes = _merge_fields(existing, fields)
        status = _resolve_status(existing, scraped, changes)
        if status != existing.status:
            changes["status"] = status
        if changes:
            participation_repository.update(self.db, existing, **changes)
            self.updated += 1
        else:
            self.skipped += 1

    def add(self, scraped: ScrapedResult) -> None:
        course = mapping.get_or_create_course(self.db, scraped, self.event_url)
        self._courses[course.id] = course
        self._index_course(course.id)
        bib = scraped.bib_number or None

        if bib is not None:
            added = self._added_bibs[course.id]
            if bib in added:
                # La source se contredit dans ce scrape : deux lignes, même
                # dossard. La 2e est perdue — anomalie de fiabilité.
                self.skipped += 1
                self._duplicate_bibs[course.id] = self._duplicate_bibs.get(course.id, 0) + 1
                return
            existing = self._by_bib[course.id].get(bib)
            if existing is not None:
                added.add(bib)
                self._upsert(existing, scraped)
                return
            # Dossard neuf : on tombe sur la création commune plus bas.

        athlete = mapping.get_or_create_athlete(self.db, scraped)

        if bib is None:
            existing = self._match_without_bib(course.id, athlete.id)
            if existing is not None:
                self._upsert(existing, scraped)
                return
            if self._credits[course.id].get(athlete.id, 0) > 0:
                self._credits[course.id][athlete.id] -= 1
                self.skipped += 1
                return

        created = participation_repository.create(
            self.db,
            **mapping.participation_fields(
                scraped, athlete_id=athlete.id, course_id=course.id
            ),
        )
        if bib is not None:
            self._added_bibs[course.id].add(bib)
            self._by_bib[course.id][bib] = created
        self.imported += 1

    def _match_without_bib(self, course_id: int, athlete_id: int) -> "Participation | None":
        """Ligne sans dossard à mettre à jour : seulement si l'athlète n'a qu'**une**
        participation sur la course, et pas déjà mise à jour dans ce scrape.

        Deux occurrences ou plus : on ne devine pas quelle ligne source correspond
        à quelle ligne en base, on conserve le skip multiset (cf. `add`).
        """
        rows = self._without_bib[course_id].get(athlete_id, [])
        if len(rows) != 1 or athlete_id in self._updated_single[course_id]:
            return None
        self._updated_single[course_id].add(athlete_id)
        self._credits[course_id][athlete_id] -= 1
        return rows[0]

    def finalize(self) -> None:
        for course_id, course in self._courses.items():
            course_repository.touch_scraped_at(self.db, course)
            report = quality.analyze(
                participation_repository.list_for_course(self.db, course_id),
                duplicate_bibs=self._duplicate_bibs.get(course_id, 0),
            )
            course_repository.set_quality(
                self.db,
                course,
                is_reliable=report.is_reliable,
                quality_issues=report.anomalies,
            )
```

Ajouter l'import du modèle pour l'annotation (en tête de fichier, avec les autres imports de modèles) :

```python
from app.models.participation import Participation
```

- [ ] **Step 4 : Lancer les nouveaux tests, vérifier le succès**

Run: `UV_CACHE_DIR="$TMPDIR/uv-cache" uv run pytest tests/test_services/test_import_service.py -k "reimport_rafraichit or valeur_vide or ligne_identique or is_relay_false or statut_explicite or nouveau_dossard" -v`
Expected: PASS (6 tests)

- [ ] **Step 5 : Adapter les assertions des tests existants au nouveau contrat**

Le retour d'`import_event` porte désormais `updated`. Dans `backend/tests/test_services/test_import_service.py`, mettre à jour les égalités de dict strictes (aucune valeur métier ne change, seule la clé `updated` s'ajoute) :

| Test | Ancienne assertion | Nouvelle assertion |
| --- | --- | --- |
| `test_import_creates_entities` | `out == {"imported": 2, "skipped": 0}` | `out == {"imported": 2, "updated": 0, "skipped": 0}` |
| `test_reimport_after_cache_dedups_by_bib` | `{"imported": 1, "skipped": 1}` | `{"imported": 1, "updated": 0, "skipped": 1}` |
| `test_reimport_apres_cache_ne_compte_pas_les_dossards_deja_en_base` | `{"imported": 1, "skipped": 1}` | `{"imported": 1, "updated": 0, "skipped": 1}` |
| `test_import_signale_une_course_suspecte` | `{"imported": 2, "skipped": 1}` | `{"imported": 2, "updated": 0, "skipped": 1}` |
| `test_import_sans_dossard_cree_les_participations` | `{"imported": 2, "skipped": 0}` | `{"imported": 2, "updated": 0, "skipped": 0}` |
| `test_reimport_sans_dossard_est_idempotent` | `{"imported": 0, "skipped": 2}` | `{"imported": 0, "updated": 0, "skipped": 2}` |
| `test_import_sans_dossard_conserve_les_homonymes` | `{"imported": 2, "skipped": 0}` | `{"imported": 2, "updated": 0, "skipped": 0}` |
| `test_reimport_sans_dossard_conserve_le_nombre_d_homonymes` | `{"imported": 0, "skipped": 2}` | `{"imported": 0, "updated": 0, "skipped": 2}` |
| `test_reimport_sans_dossard_ajoute_une_occurrence_supplementaire` | `{"imported": 1, "skipped": 2}` | `{"imported": 1, "updated": 0, "skipped": 2}` |
| `test_reimport_melange_avec_et_sans_dossard` | `{"imported": 2, "skipped": 2}` | `{"imported": 2, "updated": 0, "skipped": 2}` |
| `test_force_bypasse_le_cache_ttl` | `{"imported": 1, "skipped": 1}` | `{"imported": 1, "updated": 0, "skipped": 1}` |

> Note : `test_reimport_is_cached_and_skips` teste le retour **cached** (`out["cached"] is True`, `out["imported"] == 0`, `out["skipped"] == 2`) par accès indexé — il ne change pas ici (le champ `updated:0` du retour cached est ajouté en Task 4).

- [ ] **Step 6 : Lancer toute la suite import_service, vérifier le succès**

Run: `UV_CACHE_DIR="$TMPDIR/uv-cache" uv run pytest tests/test_services/test_import_service.py -v`
Expected: PASS (tous). Puis `uv run ruff check app/services/import_service.py`.

- [ ] **Step 7 : Commit**

```bash
git add backend/app/services/import_service.py backend/tests/test_services/test_import_service.py
git commit -m "feat(import): upsert prudent des participations par dossard (#68)"
```

---

### Task 3 : `_Persister` — mise à jour sans dossard (athlète non ambigu)

**Files:**
- Modify: aucun code neuf (le chemin sans dossard est déjà écrit en Task 2 via `_match_without_bib`) — cette tâche **verrouille le comportement par des tests dédiés**.
- Test: `backend/tests/test_services/test_import_service.py`

**Interfaces:**
- Consumes: `_Persister` de Task 2 (`_match_without_bib`, `_credits`, `_updated_single`).
- Produces: garanties de non-régression sur le chemin multiset sans dossard.

- [ ] **Step 1 : Écrire les tests qui échouent (ou verrouillent)**

Ajouter dans `backend/tests/test_services/test_import_service.py` :

```python
def test_reimport_sans_dossard_unique_met_a_jour(db_session, patch_scraper):
    """Un athlète sans dossard en un seul exemplaire est mis à jour."""
    patch_scraper([_result("", "CASROUGE", "Patrice", total_time="01:10:00")])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([_result("", "CASROUGE", "Patrice", total_time="01:09:30")])
    out = import_service.import_event(db_session, URL, _settings(), force=True)
    assert out == {"imported": 0, "updated": 1, "skipped": 0}

    parts = participation_repository.list_participations(db_session, page_size=100)
    assert len(parts) == 1
    assert parts[0].total_time == "01:09:30"


def test_reimport_sans_dossard_ambigu_ne_met_pas_a_jour(db_session, patch_scraper):
    """Deux exemplaires du même athlète sans dossard : appariement impossible → skip,
    aucune valeur réécrite (comportement multiset conservé)."""
    patch_scraper([
        _result("", "LACOTTE", "Anais", total_time="01:20:00"),
        _result("", "LACOTTE", "Anais", total_time="01:20:00"),
    ])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([
        _result("", "LACOTTE", "Anais", total_time="01:19:00"),
        _result("", "LACOTTE", "Anais", total_time="01:18:00"),
    ])
    out = import_service.import_event(db_session, URL, _settings(), force=True)
    assert out == {"imported": 0, "updated": 0, "skipped": 2}

    times = sorted(
        p.total_time for p in participation_repository.list_participations(db_session, page_size=100)
    )
    assert times == ["01:20:00", "01:20:00"]  # inchangés : on ne devine pas l'appariement
```

- [ ] **Step 2 : Lancer les tests**

Run: `UV_CACHE_DIR="$TMPDIR/uv-cache" uv run pytest tests/test_services/test_import_service.py -k "sans_dossard_unique or sans_dossard_ambigu" -v`
Expected: PASS directement (le comportement est déjà implémenté en Task 2). Si un test échoue, corriger `_match_without_bib` / le chemin sans dossard de `add` jusqu'au vert — ne pas modifier les tests.

- [ ] **Step 3 : Commit**

```bash
git add backend/tests/test_services/test_import_service.py
git commit -m "test(import): verrouille l'upsert sans dossard (unique vs ambigu) (#68)"
```

---

### Task 4 : Propager `updated` dans `import_service` (retours + phases SSE)

**Files:**
- Modify: `backend/app/services/import_service.py` (`_cached_result`, `import_event`, `iter_import_event`)
- Test: `backend/tests/test_services/test_import_service.py`

**Interfaces:**
- Consumes: `_Persister.updated` (Task 2).
- Produces: `import_event` renvoie `{imported, updated, skipped[, cached]}` ; les phases SSE `saving` et `done` portent `updated` ; le retour cached porte `updated: 0`. Consommé par `batch._import_one` (Task 5) et le front (Task 8).

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter dans `backend/tests/test_services/test_import_service.py` :

```python
def test_iter_import_event_expose_updated(db_session, patch_scraper):
    """Les phases `saving` et `done` du générateur SSE portent `updated`."""
    patch_scraper([_result("1", "DUPONT", total_time="01:59:00")])
    import_service.import_event(db_session, URL, _settings())
    _expire_cache(db_session)

    patch_scraper([_result("1", "DUPONT", total_time="01:58:00")])
    phases = list(import_service.iter_import_event(db_session, URL, _settings(), force=True))

    saving = [p for p in phases if p["phase"] == "saving"]
    assert saving and all("updated" in p for p in saving)
    done = phases[-1]
    assert done["phase"] == "done"
    assert (done["imported"], done["updated"], done["skipped"]) == (0, 1, 0)


def test_cached_return_porte_updated_zero(db_session, patch_scraper):
    """Le retour court-circuité par le cache TTL porte `updated: 0`."""
    patch_scraper([_result("1", "DUPONT")])
    import_service.import_event(db_session, URL, _settings())

    out = import_service.import_event(db_session, URL, _settings())
    assert out["cached"] is True
    assert out["updated"] == 0
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `UV_CACHE_DIR="$TMPDIR/uv-cache" uv run pytest tests/test_services/test_import_service.py::test_iter_import_event_expose_updated tests/test_services/test_import_service.py::test_cached_return_porte_updated_zero -v`
Expected: FAIL — `KeyError: 'updated'`.

- [ ] **Step 3 : Ajouter `updated` aux retours et phases**

Dans `backend/app/services/import_service.py` :

`_cached_result` — ligne du dict de retour :

```python
        return {"imported": 0, "updated": 0, "skipped": count, "cached": True}
```

`import_event` — les deux retours :

```python
    results = _scrape_all(url)
    if not results:
        return {"imported": 0, "updated": 0, "skipped": 0}
```

```python
    return {"imported": persister.imported, "updated": persister.updated, "skipped": persister.skipped}
```

`iter_import_event` — phase `done` du cas vide :

```python
    total = len(results)
    if total == 0:
        yield {"phase": "done", "imported": 0, "updated": 0, "skipped": 0, "total": 0}
        return
```

phase initiale `saving` :

```python
    yield {"phase": "saving", "total": total, "imported": 0, "updated": 0, "skipped": 0, "progress": 0}
```

boucle `saving` :

```python
            if (i + 1) % 20 == 0 or i == total - 1:
                yield {
                    "phase": "saving",
                    "total": total,
                    "imported": persister.imported,
                    "updated": persister.updated,
                    "skipped": persister.skipped,
                    "progress": i + 1,
                }
```

phase `done` finale :

```python
    yield {
        "phase": "done",
        "imported": persister.imported,
        "updated": persister.updated,
        "skipped": persister.skipped,
        "total": total,
    }
```

> Le retour cached du générateur (`yield {"phase": "done", "total": cached["skipped"], **cached}`) hérite automatiquement de `updated: 0` via `**cached` — aucun changement.
> L'endpoint SSE (`app/api/v1/scrape.py`) sérialise ces dicts tels quels (`data: {json.dumps(event)}`) : `updated` circule sans y toucher.

- [ ] **Step 4 : Lancer, vérifier le succès**

Run: `UV_CACHE_DIR="$TMPDIR/uv-cache" uv run pytest tests/test_services/test_import_service.py -v`
Expected: PASS (toute la suite, y compris `test_reimport_is_cached_and_skips` inchangé).

- [ ] **Step 5 : Commit**

```bash
git add backend/app/services/import_service.py backend/tests/test_services/test_import_service.py
git commit -m "feat(import): propage le compteur updated (retours + phases SSE) (#68)"
```

---

### Task 5 : `batch` — collecte et cumul de `updated`

**Files:**
- Modify: `backend/app/services/batch.py` (`BatchTotals`, `_import_one`, `run_batch`)
- Test: `backend/tests/test_services/test_batch.py`

**Interfaces:**
- Consumes: phase `done` portant `updated` (Task 4).
- Produces: `BatchTotals.updated: int` ; `_import_one` renvoie `tuple[int, int, int, str | None]` (imported, updated, skipped, error) ; `run_batch` cumule `totals.updated`. Consommé par les deux `Outcome` (Task 6).

- [ ] **Step 1 : Écrire le test qui échoue**

Regarder d'abord le style existant : `backend/tests/test_services/test_batch.py` monkeypatche `import_service.iter_import_event`. Ajouter un test cohérent avec ce style :

```python
def test_run_batch_cumule_updated(db_session, monkeypatch):
    from app.services import batch, import_service

    def _fake_iter(db, url, settings, force):
        yield {"phase": "saving", "total": 1, "imported": 0, "updated": 1, "skipped": 0, "progress": 1}
        yield {"phase": "done", "imported": 0, "updated": 1, "skipped": 2, "total": 1}

    monkeypatch.setattr(import_service, "iter_import_event", _fake_iter)

    totals = batch.run_batch(
        db_session,
        [batch.BatchItem(url="http://a", label="a"), batch.BatchItem(url="http://b", label="b")],
        _settings(),
        force=True,
        delay=0,
    )
    assert totals.updated == 2
    assert totals.imported == 0
    assert totals.skipped == 4
    assert totals.errors == 0
```

> `_settings()` : réutiliser le helper du fichier `test_batch.py` s'il existe ; sinon `Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)`.

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `UV_CACHE_DIR="$TMPDIR/uv-cache" uv run pytest tests/test_services/test_batch.py::test_run_batch_cumule_updated -v`
Expected: FAIL — `AttributeError: 'BatchTotals' object has no attribute 'updated'`.

- [ ] **Step 3 : Ajouter `updated` au batch**

Dans `backend/app/services/batch.py` — `BatchTotals` :

```python
@dataclass
class BatchTotals:
    """Compteurs cumulés d'un batch. `interrupted` = arrêté par Ctrl-C.

    Deux unités cohabitent, et le bilan doit les nommer : `processed`/`errors`
    comptent des **épreuves**, `imported`/`updated`/`skipped` des **participants**.
    """
    imported: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    processed: int = 0
    interrupted: bool = False
    failures: list[BatchFailure] = field(default_factory=list)
```

`_import_one` — signature, doc, collecte et retour :

```python
def _import_one(
    db: Session,
    url: str,
    settings: Settings,
    *,
    force: bool,
    reporter: ProgressReporter,
) -> tuple[int, int, int, str | None]:
    """Consomme les phases d'une épreuve. Renvoie (imported, updated, skipped, error)."""
    imported = updated = skipped = 0
    error: str | None = None

    for phase in import_service.iter_import_event(db, url, settings, force=force):
        nom = phase.get("phase")
        if nom == "saving":
            _notify(
                partial(
                    reporter.item_progress,
                    phase.get("progress", 0),
                    phase.get("total", 0),
                )
            )
        elif nom == "done":
            imported = phase.get("imported", 0)
            updated = phase.get("updated", 0)
            skipped = phase.get("skipped", 0)
        elif nom == "error":
            error = phase.get("message", "erreur inconnue")

    return imported, updated, skipped, error
```

`run_batch` — dépaquetage, filet d'exception et cumul :

```python
            try:
                imported, updated, skipped, error = _import_one(
                    db, item.url, settings, force=force, reporter=reporter
                )
            except Exception as exc:  # filet : un bug ne doit pas tuer le batch
                logger.warning("Échec import %s : %s", item.url, exc)
                imported = updated = skipped = 0
                error = str(exc)

            if error:
                totals.errors += 1
                totals.failures.append(
                    BatchFailure(url=item.url, label=item.label, message=error)
                )
            else:
                totals.imported += imported
                totals.updated += updated
                totals.skipped += skipped
            totals.processed += 1
            _notify(partial(reporter.item_done, imported, skipped, error))
            _liberer_session(db)
```

> `reporter.item_done` garde sa signature `(imported, skipped, error)` : la progression n'affiche pas `updated` (l'ajouter au `ProgressReporter` déborderait du périmètre — les bilans finaux, eux, le portent). À vérifier au Step 4 qu'aucun test n'attend un 4e argument.

- [ ] **Step 4 : Lancer toute la suite batch, vérifier le succès**

Run: `UV_CACHE_DIR="$TMPDIR/uv-cache" uv run pytest tests/test_services/test_batch.py -v`
Expected: PASS. Si un test existant appelait `_import_one` et dépaquetait 3 valeurs, l'adapter à 4 (imported, updated, skipped, error). Puis `uv run ruff check app/services/batch.py`.

- [ ] **Step 5 : Commit**

```bash
git add backend/app/services/batch.py backend/tests/test_services/test_batch.py
git commit -m "feat(batch): cumule le compteur updated des participations (#68)"
```

---

### Task 6 : `Outcome` — `updated` dans les bilans Sheet et Rescrape

**Files:**
- Modify: `backend/app/services/bulk_import_service.py` (`SheetOutcome` + câblage), `backend/app/services/rescrape_service.py` (`RescrapeOutcome` + câblage)
- Test: `backend/tests/test_services/test_bulk_import_service.py`, `backend/tests/test_services/test_rescrape_service.py`

**Interfaces:**
- Consumes: `BatchTotals.updated` (Task 5).
- Produces: `SheetOutcome.updated: int` et `RescrapeOutcome.updated: int` (champs dataclass → embarqués dans `--json` via `asdict`). Consommé par `cli/reports` (Task 7).

- [ ] **Step 1 : Écrire les tests qui échouent**

Le style de ces fichiers monkeypatche `run_batch` pour renvoyer un `BatchTotals` fabriqué. Ajouter :

Dans `backend/tests/test_services/test_rescrape_service.py` :

```python
def test_rescrape_outcome_porte_updated(db_session, monkeypatch):
    from app.services import batch, rescrape_service
    from app.services.batch import BatchTotals

    monkeypatch.setattr(
        rescrape_service, "run_batch",
        lambda *a, **k: BatchTotals(imported=1, updated=3, skipped=5, processed=1),
    )
    # Une épreuve ciblée explicitement (court-circuite la base).
    out = rescrape_service.run_rescrape_db(
        db_session, _settings(), urls=["http://a"], delay=0,
    )
    assert out.updated == 3
```

Dans `backend/tests/test_services/test_bulk_import_service.py` (adapter l'appel à la signature réelle de `run_import_sheet` utilisée dans ce fichier — un CSV minimal avec un lien supporté existe déjà dans les tests voisins) :

```python
def test_sheet_outcome_porte_updated(db_session, monkeypatch):
    from app.services import bulk_import_service
    from app.services.batch import BatchTotals

    monkeypatch.setattr(
        bulk_import_service, "run_batch",
        lambda *a, **k: BatchTotals(imported=2, updated=4, skipped=1, processed=1),
    )
    csv_text = "Nom,Lien\nDUPONT,https://www.klikego.com/resultats/event/1\n"
    out = bulk_import_service.run_import_sheet(db_session, csv_text, _settings(), delay=0)
    assert out.updated == 4
```

> Vérifier l'en-tête CSV attendu par `sheet_source.parse_sheet_csv` dans les tests voisins et l'aligner ; l'objectif du test est seulement que `updated` du `BatchTotals` remonte dans l'`Outcome`.

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `UV_CACHE_DIR="$TMPDIR/uv-cache" uv run pytest tests/test_services/test_rescrape_service.py::test_rescrape_outcome_porte_updated tests/test_services/test_bulk_import_service.py::test_sheet_outcome_porte_updated -v`
Expected: FAIL — `TypeError` (champ `updated` inconnu) ou `AttributeError`.

- [ ] **Step 3 : Ajouter le champ et le câblage**

Dans `backend/app/services/rescrape_service.py` — `RescrapeOutcome`, ajouter `updated` juste après `imported` :

```python
    total: int = 0
    imported: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
```

et le câblage dans `run_rescrape_db`, après `outcome.imported = totals.imported` :

```python
    outcome.imported = totals.imported
    outcome.updated = totals.updated
    outcome.skipped = totals.skipped
```

Mettre à jour la docstring de classe : `` `total`, `processed` et `errors` comptent des **épreuves** ; `imported`, `updated` et `skipped`, des **participants**. ``

Dans `backend/app/services/bulk_import_service.py` — `SheetOutcome`, ajouter `updated` juste après `imported` :

```python
    imported: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
```

et le câblage dans `run_import_sheet`, après `outcome.imported = totals.imported` :

```python
    outcome.imported = totals.imported
    outcome.updated = totals.updated
    outcome.skipped = totals.skipped
```

Mettre à jour la docstring de classe : `` `unique_supported`, `processed` et `errors` comptent des **épreuves** ; `imported`, `updated` et `skipped`, des **participants**. ``

- [ ] **Step 4 : Lancer, vérifier le succès**

Run: `UV_CACHE_DIR="$TMPDIR/uv-cache" uv run pytest tests/test_services/test_rescrape_service.py tests/test_services/test_bulk_import_service.py -v`
Expected: PASS. Puis `uv run ruff check app/services/`.

- [ ] **Step 5 : Commit**

```bash
git add backend/app/services/rescrape_service.py backend/app/services/bulk_import_service.py backend/tests/test_services/test_rescrape_service.py backend/tests/test_services/test_bulk_import_service.py
git commit -m "feat(batch): expose updated dans SheetOutcome et RescrapeOutcome (#68)"
```

---

### Task 7 : `cli/reports` — ligne « Participants mis à jour »

**Files:**
- Modify: `backend/app/cli/reports.py` (`_lignes_compteurs`)
- Test: `backend/tests/test_cli/test_reports.py`

**Interfaces:**
- Consumes: `Outcome.updated` (Task 6).
- Produces: le rapport texte des deux commandes intercale « Participants mis à jour : N » entre « ajoutés » et « déjà en base ».

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter dans `backend/tests/test_cli/test_reports.py` :

```python
def test_rescrape_report_affiche_les_participants_mis_a_jour():
    from app.cli.reports import render_rescrape_report
    from app.services.rescrape_service import RescrapeOutcome

    out = RescrapeOutcome(total=3, imported=1, updated=7, skipped=900, processed=3)
    texte = render_rescrape_report(out, dry_run=False)
    assert "Participants mis à jour   : 7" in texte
    # Ordre : ajoutés → mis à jour → déjà en base.
    assert texte.index("ajoutés") < texte.index("mis à jour") < texte.index("déjà en base")


def test_sheet_report_affiche_les_participants_mis_a_jour():
    from app.cli.reports import render_sheet_report
    from app.services.bulk_import_service import SheetOutcome

    out = SheetOutcome(unique_supported=2, imported=3, updated=4, skipped=5, processed=2)
    texte = render_sheet_report(out, dry_run=False)
    assert "Participants mis à jour   : 4" in texte
```

> L'alignement : `_ligne` formate sur une colonne de 25 (`f"{libelle:<25} : {valeur}"`). « Participants mis à jour » fait 23 caractères → 2 espaces de remplissage, soit `"Participants mis à jour   : 7"` (colonne 25 + `" : "`). Confirmer le rendu exact au Step 4 si l'assertion d'espacement diffère.

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run: `UV_CACHE_DIR="$TMPDIR/uv-cache" uv run pytest tests/test_cli/test_reports.py::test_rescrape_report_affiche_les_participants_mis_a_jour tests/test_cli/test_reports.py::test_sheet_report_affiche_les_participants_mis_a_jour -v`
Expected: FAIL — la ligne « mis à jour » est absente.

- [ ] **Step 3 : Intercaler la ligne**

Dans `backend/app/cli/reports.py` — `_lignes_compteurs`, entre « ajoutés » et « déjà en base » :

```python
    lignes.append(_ligne("Épreuves en erreur", outcome.errors))
    lignes.append(_ligne("Participants ajoutés", outcome.imported))
    lignes.append(_ligne("Participants mis à jour", outcome.updated))
    lignes.append(_ligne("Participants déjà en base", outcome.skipped))
```

- [ ] **Step 4 : Lancer toute la suite reports, vérifier le succès**

Run: `UV_CACHE_DIR="$TMPDIR/uv-cache" uv run pytest tests/test_cli/test_reports.py -v`
Expected: PASS. Vérifier qu'aucun test existant n'assertait l'**absence** de la ligne « mis à jour » ni un rendu figé du bloc de compteurs ; adapter le cas échéant (ex. un test comparant le bloc entier).

- [ ] **Step 5 : Commit**

```bash
git add backend/app/cli/reports.py backend/tests/test_cli/test_reports.py
git commit -m "feat(cli): ligne « Participants mis à jour » dans les bilans (#68)"
```

---

### Task 8 : Frontend — afficher `updated` dans la progression d'import

**Files:**
- Modify: `frontend/lib/types.ts` (`ImportProgressEvent`), `frontend/hooks/useImportStream.ts` (`ImportState` + réducteurs), `frontend/components/scrape/ImportProgress.tsx`
- Test: `frontend/components/scrape/ImportProgress.test.tsx` (créer)

**Interfaces:**
- Consumes: phases SSE `saving`/`done` portant `updated: number` (Task 4).
- Produces: l'UI d'import affiche les trois compteurs (importés · mis à jour · ignorés).

- [ ] **Step 1 : Écrire le test qui échoue**

Créer `frontend/components/scrape/ImportProgress.test.tsx` :

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ImportProgress } from "./ImportProgress";
import type { ImportState } from "@/hooks/useImportStream";

function state(overrides: Partial<ImportState>): ImportState {
  return {
    running: false, phase: "idle", message: "", total: 0, progress: 0,
    imported: 0, updated: 0, skipped: 0, cached: false, error: null,
    ...overrides,
  };
}

describe("ImportProgress", () => {
  it("affiche les trois compteurs pendant l'enregistrement", () => {
    render(<ImportProgress state={state({ phase: "saving", total: 10, progress: 6, imported: 4, updated: 2, skipped: 1 })} />);
    expect(screen.getByText(/4 ajoutés/)).toBeTruthy();
    expect(screen.getByText(/2 mis à jour/)).toBeTruthy();
    expect(screen.getByText(/1 ignorés/)).toBeTruthy();
  });

  it("récapitule les trois compteurs à la fin", () => {
    render(<ImportProgress state={state({ phase: "done", total: 10, progress: 10, imported: 4, updated: 2, skipped: 4 })} />);
    expect(screen.getByText(/4 ajoutés/)).toBeTruthy();
    expect(screen.getByText(/2 mis à jour/)).toBeTruthy();
    expect(screen.getByText(/4 ignorés/)).toBeTruthy();
  });
});
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run (depuis `frontend/`) : `npm test -- ImportProgress`
Expected: FAIL — `ImportState` n'a pas `updated` (erreur de type) et le composant n'affiche pas « mis à jour ».

- [ ] **Step 3 : Étendre types, hook, composant**

`frontend/lib/types.ts` — ajouter `updated` aux variantes `saving` et `done` :

```ts
export type ImportProgressEvent =
  | { phase: "scraping"; message: string }
  | { phase: "saving"; total: number; imported: number; updated: number; skipped: number; progress: number }
  | { phase: "done"; imported: number; updated: number; skipped: number; total: number; cached?: boolean }
  | { phase: "error"; message: string };
```

`frontend/hooks/useImportStream.ts` — ajouter `updated` à l'état, à `INITIAL`, et aux réducteurs `saving`/`done` :

```ts
export interface ImportState {
  running: boolean;
  phase: ImportProgressEvent["phase"] | "idle";
  message: string;
  total: number;
  progress: number;
  imported: number;
  updated: number;
  skipped: number;
  cached: boolean;
  error: string | null;
}

const INITIAL: ImportState = {
  running: false,
  phase: "idle",
  message: "",
  total: 0,
  progress: 0,
  imported: 0,
  updated: 0,
  skipped: 0,
  cached: false,
  error: null,
};
```

Dans la boucle, brancher `updated` :

```ts
        } else if (ev.phase === "saving") {
          setState((s) => ({
            ...s,
            phase: "saving",
            total: ev.total,
            progress: ev.progress,
            imported: ev.imported,
            updated: ev.updated,
            skipped: ev.skipped,
          }));
        } else if (ev.phase === "done") {
          setState((s) => ({
            ...s,
            running: false,
            phase: "done",
            total: ev.total,
            progress: ev.total,
            imported: ev.imported,
            updated: ev.updated,
            skipped: ev.skipped,
            cached: Boolean(ev.cached),
          }));
        } else if (ev.phase === "error") {
```

`frontend/components/scrape/ImportProgress.tsx` — afficher les trois compteurs :

```tsx
      {state.phase === "saving" && (
        <>
          <div className="flex justify-between">
            <span>Import en cours… {state.progress}/{state.total}</span>
            <span className="text-muted-foreground">
              {state.imported} ajoutés · {state.updated} mis à jour · {state.skipped} ignorés
            </span>
          </div>
          <Progress value={pct} />
        </>
      )}
      {state.phase === "done" && (
        <p className="font-medium text-success">
          {state.cached
            ? `Déjà à jour (${state.skipped} participants en cache).`
            : `Import terminé : ${state.imported} ajoutés, ${state.updated} mis à jour, ${state.skipped} ignorés.`}
        </p>
      )}
```

- [ ] **Step 4 : Lancer les tests, vérifier le succès**

Run (depuis `frontend/`) : `npm test -- ImportProgress`
Expected: PASS. Puis `npm run lint` et `npx tsc --noEmit` (ou `npm run build`) pour confirmer que le typage strict passe.

- [ ] **Step 5 : Commit**

```bash
git add frontend/lib/types.ts frontend/hooks/useImportStream.ts frontend/components/scrape/ImportProgress.tsx frontend/components/scrape/ImportProgress.test.tsx
git commit -m "feat(front): affiche le compteur « mis à jour » à l'import (#68)"
```

---

### Task 9 : Vérification finale (documentation + suite complète)

**Files:**
- Modify: `docs/superpowers/specs/2026-07-14-upsert-participations-rescrape-design.md` (statut), `AGENTS.md` (mention du 3e compteur si pertinent)
- Test: suites complètes backend + frontend

**Interfaces:**
- Consumes: l'ensemble des tâches précédentes.
- Produces: branche prête pour revue / PR.

- [ ] **Step 1 : Suite backend complète, sans réseau**

Run (depuis `backend/`) : `UV_CACHE_DIR="$TMPDIR/uv-cache" uv run pytest -m "not integration" -q`
Expected: PASS (baseline = 666 tests + les tests neufs de ce plan, 0 échec).

- [ ] **Step 2 : Lint backend**

Run : `UV_CACHE_DIR="$TMPDIR/uv-cache" uv run ruff check .`
Expected: `All checks passed!`

- [ ] **Step 3 : Suite frontend + lint + build**

Run (depuis `frontend/`) : `npm test && npm run lint && npm run build`
Expected: tests verts, lint clean, build prod OK.

- [ ] **Step 4 : Marquer la spec comme livrée**

Dans `docs/superpowers/specs/2026-07-14-upsert-participations-rescrape-design.md`, passer l'en-tête `**Statut**` à `implémenté (#68)` et pointer ce plan.

- [ ] **Step 5 : Commit final de documentation**

```bash
git add docs/superpowers/specs/2026-07-14-upsert-participations-rescrape-design.md AGENTS.md
git commit -m "docs: marque l'upsert des participations comme livré (#68)"
```

---

## Notes de conception (rappel de spec, pour l'implémenteur)

- **Point de persistance unique.** Ne pas dupliquer la logique d'upsert : `_Persister.add` est le seul écrivain, partagé par rescrape-db, import-sheet et le web SSE. Le bug de la course en direct (TTL 10 min qui re-scrape mais jetait tout) se répare par ricochet, sans toucher au cache.
- **Fusion prudente, jamais destructrice.** Une valeur vide de la source n'écrase jamais la base. Contrepartie assumée : une suppression volontaire à la source (classement retiré) ne se propage pas — une valeur erronée conservée se corrige à la main, une valeur correcte détruite en masse ne se récupère pas.
- **`athlete_id` hors périmètre.** L'appariement par dossard ne réécrit pas l'athlète : la réconciliation d'identité (nom corrigé, fiche fragmentée) est le domaine séparé de #66/#67. Ici on rafraîchit des **valeurs**, pas une **identité**.
- **Statut à part.** Jamais vide (`derive_status` renvoie toujours un statut), donc la règle « vide n'écrase pas » ne le protège pas : un statut explicite du scraper écrase, un statut absent est re-dérivé du `total_time` **fusionné** (sinon un finisher amputé de son temps basculerait en DNF).
- **`updated` vs `skipped`.** La comparaison champ à champ, nécessaire pour distinguer les deux, évite au passage des milliers d'`UPDATE` inutiles. `skipped` garde son sens (« déjà en base »), précisé en « déjà en base **et à jour** ».
- **Hors périmètre (autres specs) :** suppression des participants disparus de la source ; historisation des corrections (on écrase sans conserver l'ancienne valeur) ; cache TTL (inchangé).
