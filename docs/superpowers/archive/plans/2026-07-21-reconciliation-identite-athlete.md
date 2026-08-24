# Réconciliation de l'identité d'athlète au re-scrape — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Faire de `rescrape-db` un outil qui **réconcilie l'identité d'athlète** sur les participations déjà en base — réassigner `participation.athlete_id` quand la graphie stockée a divergé de la graphie corrigée — puis nettoie les fiches d'athlète vidées.

**Architecture :** Le repli de `_Persister.add` (jusqu'ici « dossard connu → sortie sèche ») résout désormais l'athlète et, s'il diffère, réassigne la participation. Le comptage remonte le long de la chaîne existante `import_service → batch → rescrape_service` jusqu'au bilan CLI. Un balayage des orphelins en fin de batch supprime les fiches vidées. `--dry-run` change de nature : il scrape mais n'écrit rien (rollback au lieu de commit).

**Tech Stack :** Python 3.13, uv, SQLAlchemy 2.0 (sync), Typer, pytest. Backend sous `backend/`, toutes les commandes se lancent depuis `backend/` via `uv run`.

## Global Constraints

- **Langue** : code, commentaires, messages et libellés de bilan en **français avec accents**.
- **Tests sans réseau** : aucun test de ce plan ne touche le réseau réel (pas de marker `integration`). Les scrapers sont doublés par monkeypatch de `import_service.registry_scrape_event_all`.
- **stdout parsable** : le rapport texte et la progression ne changent pas de flux. `--json` reste exclusif (stdout = la seule ligne JSON).
- **Unités nommées dans le bilan** : on compte des **participations** et des **athlètes**, jamais des « lignes ». Chaque libellé porte son unité.
- **Frontière stricte** : la réconciliation réécrit `participation.athlete_id` **et lui seul**. Temps, rangs, statuts, splits d'une participation existante restent intouchés.
- **Garde des ambigus** : ne **jamais** appliquer une correction qui viderait le prénom d'un athlète.
- **Couche d'accès DB** : seuls les `repositories/*` touchent la `Session`. Les services orchestrent, la CLI est une couche mince.
- Commits en **Conventional Commits** (`feat:`, `fix:`, `test:`, `refactor:`, `docs:`).

**Préalable déjà acquis (hors périmètre de ce plan) :** le correctif du parser `split_athlete_name` (branche « Prénom NOM » incluant les particules) et sa garde vivante de non-régression sont **déjà en base de code** — `app/scrapers/utils.py:122-128` et `tests/test_scrapers_utils.py:71` (`split_athlete_name("Jean DE LA TOUR") == ("DE LA TOUR", "Jean")`). Ne pas les réécrire.

---

## Aperçu de la structure de fichiers

| Fichier | Rôle dans ce plan |
| --- | --- |
| `app/repositories/participation_repository.py` | + `existing_participations_for_course` (snapshot dossard → Participation). |
| `app/repositories/athlete_repository.py` | + `resolve` (get_or_create qui dit s'il a créé) ; get_or_create délègue ; + `delete_orphans`. |
| `app/services/mapping.py` | + `resolve_athlete` ; get_or_create_athlete délègue. |
| `app/services/import_service.py` | Cœur : `Reassignment`, `_identite`, réécriture de `_Persister.add`, `_Persister._reconcile`, flag `persist`, sortie enrichie (`reconciled`, `reassignments`). |
| `app/services/batch.py` | `_ItemResult`, `BatchTotals` enrichi, `_import_one`/`run_batch` propagent `reconciled`/`reassignments` et `persist`. |
| `app/services/rescrape_service.py` | `RescrapeOutcome` enrichi + `IdentiteReconciliee`, agrégation, nettoyage des orphelins, dry-run qui scrape sans persister. |
| `app/cli/reports.py` | Bloc « réconciliation » dans le rapport rescrape. |
| `AGENTS.md` | Acte les 3 changements de comportement. |

---

### Task 1 : `existing_participations_for_course` (snapshot pour le repli)

**Files:**
- Modify: `app/repositories/participation_repository.py` (après `existing_bibs_for_course`, ~ligne 56)
- Test: `tests/test_repositories/test_participation_repository.py`

**Interfaces:**
- Produces : `existing_participations_for_course(db: Session, course_id: int) -> dict[str, Participation]` — dossard → Participation (athlète joint), pour les participations à dossard non nul.
- `existing_bibs_for_course` reste inchangée (toujours utilisée par `_cached_result`).

- [ ] **Step 1: Écrire le test qui échoue**

Dans `tests/test_repositories/test_participation_repository.py`, ajouter à la fin :

```python
def test_existing_participations_for_course_indexe_par_dossard(db_session):
    from app.repositories import athlete_repository, course_repository, participation_repository

    course = course_repository.get_or_create(
        db_session, name="Tri", event_date=None, event_type="triathlon-m",
        source_url="https://k/1", provider="klikego",
    )
    athlete = athlete_repository.get_or_create(db_session, nom="DUPONT", prenom="Jean")
    db_session.flush()
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="42",
    )
    # Une participation sans dossard ne doit pas figurer dans l'index.
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number=None,
    )
    db_session.flush()

    index = participation_repository.existing_participations_for_course(db_session, course.id)
    assert set(index) == {"42"}
    assert index["42"].athlete.nom == "DUPONT"
```

- [ ] **Step 2: Lancer le test pour vérifier l'échec**

Run: `uv run pytest tests/test_repositories/test_participation_repository.py::test_existing_participations_for_course_indexe_par_dossard -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'existing_participations_for_course'`.

- [ ] **Step 3: Implémenter la méthode**

Dans `app/repositories/participation_repository.py`, juste après `existing_bibs_for_course` (ligne 55), ajouter — et compléter l'import `joinedload` (déjà présent ligne 6) :

```python
def existing_participations_for_course(
    db: Session, course_id: int
) -> dict[str, Participation]:
    """Participations à dossard déjà en base pour une course, indexées par dossard.

    Le repli de réconciliation (`import_service._Persister`) a besoin de la
    **participation** (pour réassigner son `athlete_id`), pas seulement de son
    dossard : `existing_bibs_for_course` ne suffit plus. L'athlète est joint
    d'emblée — la garde des ambigus lit son prénom sans requête supplémentaire.
    """
    rows = (
        db.query(Participation)
        .options(joinedload(Participation.athlete))
        .filter(Participation.course_id == course_id, Participation.bib_number.isnot(None))
        .all()
    )
    return {p.bib_number: p for p in rows}
```

- [ ] **Step 4: Lancer le test pour vérifier le succès**

Run: `uv run pytest tests/test_repositories/test_participation_repository.py -v`
Expected: PASS (tous les tests du fichier).

- [ ] **Step 5: Commit**

```bash
git add app/repositories/participation_repository.py tests/test_repositories/test_participation_repository.py
git commit -m "feat(repositories): snapshot dossard -> Participation pour la réconciliation"
```

---

### Task 2 : `resolve` (get_or_create qui signale la création) + `mapping.resolve_athlete`

**Files:**
- Modify: `app/repositories/athlete_repository.py:30-56` (refactor `get_or_create` sur `resolve`)
- Modify: `app/services/mapping.py:99-107` (`get_or_create_athlete` délègue, + `resolve_athlete`)
- Test: `tests/test_repositories/test_athlete_repository.py`, `tests/test_services/test_mapping.py`

**Interfaces:**
- Produces : `athlete_repository.resolve(db, *, nom, prenom="", gender="", birth_date=None, club=None) -> tuple[Athlete, bool]` — le bool est `True` si l'athlète vient d'être **créé**, `False` s'il **préexistait** (⇒ fusion).
- Produces : `mapping.resolve_athlete(db, scraped) -> tuple[Athlete, bool]`.
- `get_or_create` / `get_or_create_athlete` conservent leur signature et leur comportement (délèguent à `resolve`).

- [ ] **Step 1: Écrire les tests qui échouent**

Dans `tests/test_repositories/test_athlete_repository.py`, ajouter :

```python
def test_resolve_signale_creation_puis_reutilisation(db_session):
    a1, cree1 = athlete_repository.resolve(db_session, nom="ROUX", prenom="Alexis")
    assert cree1 is True
    a2, cree2 = athlete_repository.resolve(db_session, nom="ROUX", prenom="Alexis")
    assert cree2 is False
    assert a2.id == a1.id
```

Dans `tests/test_services/test_mapping.py`, ajouter (adapter l'import de `ScrapedResult` au style du fichier) :

```python
def test_resolve_athlete_reporte_le_drapeau_de_creation(db_session):
    from app.scrapers.base import ScrapedResult
    from app.services import mapping

    scraped = ScrapedResult(
        source_url="http://d", provider="klikego",
        athlete_name="LE BERRE", athlete_firstname="Audrey",
        event_name="Tri", event_type="triathlon-m",
    )
    _, cree = mapping.resolve_athlete(db_session, scraped)
    assert cree is True
    _, cree2 = mapping.resolve_athlete(db_session, scraped)
    assert cree2 is False
```

- [ ] **Step 2: Lancer les tests pour vérifier l'échec**

Run: `uv run pytest tests/test_repositories/test_athlete_repository.py::test_resolve_signale_creation_puis_reutilisation tests/test_services/test_mapping.py::test_resolve_athlete_reporte_le_drapeau_de_creation -v`
Expected: FAIL — `AttributeError` sur `resolve` / `resolve_athlete`.

- [ ] **Step 3: Implémenter `resolve` et faire déléguer `get_or_create`**

Dans `app/repositories/athlete_repository.py`, remplacer le corps de `get_or_create` (lignes 30-56) par :

```python
def resolve(
    db: Session,
    *,
    nom: str,
    prenom: str = "",
    gender: str = "",
    birth_date: date | None = None,
    club: str | None = None,
) -> tuple[Athlete, bool]:
    """Retourne (athlète, créé) : `créé` est True si la ligne vient d'être créée.

    Le repli de réconciliation distingue un **renommage** (cible créée) d'une
    **fusion** (cible préexistante) ; ce drapeau est la seule information qui les
    sépare. `get_or_create` reste le point d'entrée quand le drapeau n'importe pas.
    """
    existing = get_by_identity(db, nom, prenom, birth_date)
    if existing:
        # Met à jour le club courant si l'info est plus récente
        if club and existing.club != club:
            existing.club = club
        return existing, False

    athlete = Athlete(
        nom=(nom or "").strip(),
        prenom=(prenom or "").strip(),
        gender=gender or "",
        birth_date=birth_date,
        club=club,
    )
    db.add(athlete)
    db.flush()  # peuple athlete.id sans commit (la transaction est gérée par le service)
    return athlete, True


def get_or_create(
    db: Session,
    *,
    nom: str,
    prenom: str = "",
    gender: str = "",
    birth_date: date | None = None,
    club: str | None = None,
) -> Athlete:
    """Retourne l'athlète existant (dédoublonné) ou en crée un nouveau (flush pour l'id)."""
    athlete, _ = resolve(
        db, nom=nom, prenom=prenom, gender=gender, birth_date=birth_date, club=club
    )
    return athlete
```

Dans `app/services/mapping.py`, remplacer `get_or_create_athlete` (lignes 99-107) par :

```python
def resolve_athlete(db: Session, scraped: ScrapedResult) -> tuple[Athlete, bool]:
    """Athlète dédoublonné + drapeau « créé » (True = renommage, False = fusion)."""
    return athlete_repository.resolve(
        db,
        nom=scraped.athlete_name,
        prenom=scraped.athlete_firstname,
        gender=scraped.gender,
        club=scraped.club or None,
    )


def get_or_create_athlete(db: Session, scraped: ScrapedResult) -> Athlete:
    """Athlète dédoublonné par nom + prénom (+ date de naissance si connue)."""
    athlete, _ = resolve_athlete(db, scraped)
    return athlete
```

- [ ] **Step 4: Lancer les tests pour vérifier le succès**

Run: `uv run pytest tests/test_repositories/test_athlete_repository.py tests/test_services/test_mapping.py -v`
Expected: PASS (les tests existants de dédoublonnage restent verts — le comportement est inchangé).

- [ ] **Step 5: Commit**

```bash
git add app/repositories/athlete_repository.py app/services/mapping.py tests/test_repositories/test_athlete_repository.py tests/test_services/test_mapping.py
git commit -m "refactor(services): resolve() distingue création et réutilisation d'athlète"
```

---

### Task 3 : Réconciliation dans `_Persister.add` (le cœur)

**Files:**
- Modify: `app/services/import_service.py` (nouveau dataclass + helper ~ligne 22 ; `_Persister.__init__`, `add`, `_reconcile` ~lignes 59-136 ; retours de `import_event`/`iter_import_event`)
- Test: `tests/test_services/test_import_service.py`

**Interfaces:**
- Consumes : `participation_repository.existing_participations_for_course` (Task 1), `mapping.resolve_athlete` (Task 2).
- Produces : `import_service.Reassignment(ancien: str, nouveau: str, fusion: bool)` — dataclass gelé ; labels `"NOM | Prénom"`.
- Produces : `_Persister` expose `self.reconciled: int` et `self.reassignments: list[Reassignment]`.
- Produces : `import_event(...)` renvoie un dict avec en plus `"reconciled": int`.
- Produces : la phase `done` de `iter_import_event` porte en plus `"reconciled": int` et `"reassignments": list[Reassignment]`.

- [ ] **Step 1: Écrire les tests qui échouent**

Dans `tests/test_services/test_import_service.py`, ajouter à la fin :

```python
# ---------------------------------------------------------------------------
# Réconciliation d'identité au re-scrape (issue #66)
# ---------------------------------------------------------------------------

def test_dossard_connu_athlete_divergent_est_reconcilie(db_session, patch_scraper):
    """La graphie fautive stockée est réassignée vers la graphie corrigée."""
    patch_scraper([_result("1", "BERRE", "Audrey LE")])
    import_service.import_event(db_session, URL, _settings())

    # Même dossard, identité corrigée. force=True : re-scrape malgré le cache frais.
    patch_scraper([_result("1", "LE BERRE", "Audrey")])
    out = import_service.import_event(db_session, URL, _settings(), force=True)

    assert out["reconciled"] == 1
    assert out["imported"] == 0
    parts = participation_repository.list_participations(db_session, page_size=100)
    assert len(parts) == 1
    assert (parts[0].athlete.nom, parts[0].athlete.prenom) == ("LE BERRE", "Audrey")


def test_dossard_connu_meme_athlete_reste_un_skip(db_session, patch_scraper):
    """Identité inchangée : aucune réassignation, `skipped` comme aujourd'hui."""
    patch_scraper([_result("1", "LE BERRE", "Audrey")])
    import_service.import_event(db_session, URL, _settings())

    patch_scraper([_result("1", "LE BERRE", "Audrey")])
    out = import_service.import_event(db_session, URL, _settings(), force=True)

    assert out["reconciled"] == 0
    assert out["skipped"] == 1


def test_reconciliation_fusionne_vers_un_athlete_existant(db_session, patch_scraper):
    """La cible corrigée existe déjà (autre course) → fusion, pas de création."""
    from app.repositories import athlete_repository

    # La graphie fautive, sur l'épreuve à re-scraper.
    patch_scraper([_result("1", "BERRE", "Audrey LE")])
    import_service.import_event(db_session, URL, _settings())
    # La graphie correcte existe déjà, portée par une autre épreuve.
    url2 = "https://www.klikego.com/resultats/event/999"
    patch_scraper([_result("7", "LE BERRE", "Audrey", event_name="Autre Tri")])
    import_service.import_event(db_session, url2, _settings())

    nb_athletes = len(athlete_repository.search(db_session, page_size=500))

    # Re-scrape de la 1re épreuve : la graphie fautive fusionne vers l'existante.
    patch_scraper([_result("1", "LE BERRE", "Audrey")])
    phases = list(import_service.iter_import_event(db_session, URL, _settings(), force=True))
    done = phases[-1]

    assert done["reconciled"] == 1
    assert done["reassignments"][0].fusion is True
    assert done["reassignments"][0].ancien == "BERRE | Audrey LE"
    assert done["reassignments"][0].nouveau == "LE BERRE | Audrey"
    # Aucun athlète créé : fusion, pas renommage.
    assert len(athlete_repository.search(db_session, page_size=500)) == nb_athletes


def test_reconciliation_ne_vide_jamais_le_prenom(db_session, patch_scraper):
    """Garde des ambigus : une correction qui viderait le prénom est refusée."""
    # Prénom stocké en majuscules par un fournisseur à champs séparés.
    patch_scraper([_result("1", "BERGE", "LOLA")])
    import_service.import_event(db_session, URL, _settings())

    # Le re-scrape produirait ("LOLA BERGE", "") — destruction du prénom.
    patch_scraper([_result("1", "LOLA BERGE", "")])
    out = import_service.import_event(db_session, URL, _settings(), force=True)

    assert out["reconciled"] == 0
    assert out["skipped"] == 1
    parts = participation_repository.list_participations(db_session, page_size=100)
    assert (parts[0].athlete.nom, parts[0].athlete.prenom) == ("BERGE", "LOLA")
```

- [ ] **Step 2: Lancer les tests pour vérifier l'échec**

Run: `uv run pytest tests/test_services/test_import_service.py -k "reconcil or dossard_connu or vide_jamais" -v`
Expected: FAIL — `KeyError: 'reconciled'` (les nouvelles clés n'existent pas encore).

- [ ] **Step 3: Ajouter `Reassignment` et `_identite`**

Dans `app/services/import_service.py`, après les imports (après ligne 22, sous `logger = ...`), ajouter :

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Reassignment:
    """Une identité réconciliée : ancienne graphie → nouvelle, et sa nature.

    `fusion` = True quand la cible corrigée préexistait (deux fiches en une),
    False quand elle vient d'être créée (simple renommage). Labels figés à la
    réassignation : ils survivent au rollback d'un dry-run.
    """
    ancien: str
    nouveau: str
    fusion: bool


def _identite(athlete) -> str:
    """Libellé d'identité pour le bilan : « NOM | Prénom »."""
    return f"{athlete.nom} | {athlete.prenom}"
```

- [ ] **Step 4: Réécrire `_Persister` (init, add, _reconcile)**

Dans `app/services/import_service.py`, dans `_Persister.__init__` (lignes 71-80), remplacer l'attribut `self._bibs` et ajouter les compteurs de réconciliation :

```python
    def __init__(self, db: Session, event_url: str):
        self.db = db
        self.event_url = event_url
        #: Snapshot pré-import (dossard → Participation), par course.
        self._existing: dict[int, dict[str, Participation]] = {}
        self._added_bibs: dict[int, set[str]] = {}
        #: Dossards préexistants déjà réconciliés dans cet import (anti double-comptage).
        self._reconciled_bibs: dict[int, set[str]] = {}
        self._duplicate_bibs: dict[int, int] = {}
        self._athlete_credits: dict[int, dict[int, int]] = {}
        self._courses: dict[int, Course] = {}
        self.imported = 0
        self.skipped = 0
        self.reconciled = 0
        self.reassignments: list[Reassignment] = []
```

Remplacer la méthode `add` (lignes 82-122) par :

```python
    def add(self, scraped: ScrapedResult) -> None:
        course = mapping.get_or_create_course(self.db, scraped, self.event_url)
        self._courses[course.id] = course
        bib = scraped.bib_number or None

        if bib is not None:
            existing = self._existing.setdefault(
                course.id,
                participation_repository.existing_participations_for_course(
                    self.db, course.id
                ),
            )
            added = self._added_bibs.setdefault(course.id, set())
            seen = self._reconciled_bibs.setdefault(course.id, set())
            if bib in existing:
                # Dossard persisté avant cet import → repli de réconciliation.
                if bib in seen:
                    # 2e occurrence source d'un dossard préexistant : skip bénin,
                    # comportement historique (pas une anomalie de fiabilité).
                    self.skipped += 1
                else:
                    self._reconcile(scraped, existing[bib])
                    seen.add(bib)
                return
            if bib in added:
                # 2e occurrence d'un dossard NOUVEAU dans cet import : la source se
                # contredit, la ligne est perdue (cf. services/quality.py).
                self.skipped += 1
                self._duplicate_bibs[course.id] = self._duplicate_bibs.get(course.id, 0) + 1
                return

        # Sans dossard, l'identité repose sur l'athlète : il faut le résoudre d'abord.
        athlete = mapping.get_or_create_athlete(self.db, scraped)
        if bib is None:
            credits = self._athlete_credits.setdefault(
                course.id,
                participation_repository.athlete_counts_without_bib(self.db, course.id),
            )
            if credits.get(athlete.id, 0) > 0:
                credits[athlete.id] -= 1
                self.skipped += 1
                return

        participation_repository.create(
            self.db,
            **mapping.participation_fields(
                scraped, athlete_id=athlete.id, course_id=course.id
            ),
        )
        if bib is not None:
            self._added_bibs[course.id].add(bib)
        self.imported += 1

    def _reconcile(self, scraped: ScrapedResult, participation: Participation) -> None:
        """Réassigne l'athlète d'une participation existante si sa graphie a divergé.

        Ne touche QUE `athlete_id` (via la relation, pour un déplacement propre
        entre fiches sans déclencher le cascade delete-orphan). Compte
        « réconciliée » quand l'athlète change, « skipped » sinon. Garde des
        ambigus : jamais une correction qui viderait le prénom.
        """
        athlete, cree = mapping.resolve_athlete(self.db, scraped)
        if athlete.id == participation.athlete_id:
            self.skipped += 1
            return
        ancien = participation.athlete
        if not (athlete.prenom or "").strip() and (ancien.prenom or "").strip():
            # « BERGE | LOLA » → « LOLA BERGE |  » : refusé, on garde l'existant.
            self.skipped += 1
            return
        reassignment = Reassignment(
            ancien=_identite(ancien), nouveau=_identite(athlete), fusion=not cree
        )
        participation.athlete = athlete
        self.reconciled += 1
        self.reassignments.append(reassignment)
```

- [ ] **Step 5: Enrichir les sorties de `import_event` et `iter_import_event`**

Dans `app/services/import_service.py`, remplacer le `return` final de `import_event` (ligne 176) par :

```python
    return {
        "imported": persister.imported,
        "skipped": persister.skipped,
        "reconciled": persister.reconciled,
    }
```

Et la phase `done` finale de `iter_import_event` (lignes 234-239) par :

```python
    yield {
        "phase": "done",
        "imported": persister.imported,
        "skipped": persister.skipped,
        "reconciled": persister.reconciled,
        "reassignments": persister.reassignments,
        "total": total,
    }
```

- [ ] **Step 6: Lancer les tests pour vérifier le succès**

Run: `uv run pytest tests/test_services/test_import_service.py -v`
Expected: PASS — les 4 nouveaux tests **et** tous les tests existants du fichier (dédoublonnage par dossard, sans dossard, homonymes, fiabilité) restent verts.

- [ ] **Step 7: Commit**

```bash
git add app/services/import_service.py tests/test_services/test_import_service.py
git commit -m "feat(services): réconcilier l'identité d'athlète sur dossard connu au re-scrape"
```

---

### Task 4 : Propager `reconciled` / `reassignments` dans le batch

**Files:**
- Modify: `app/services/batch.py` (nouveau `_ItemResult`, `BatchTotals` ~lignes 43-59, `_import_one` ~lignes 125-157, `run_batch` ~lignes 178-198)
- Test: `tests/test_services/test_batch.py`

**Interfaces:**
- Consumes : la phase `done` de `iter_import_event` (`reconciled`, `reassignments`) — Task 3.
- Produces : `BatchTotals` gagne `reconciled: int = 0` et `reassignments: list[Reassignment] = field(default_factory=list)`.

- [ ] **Step 1: Écrire le test qui échoue**

Dans `tests/test_services/test_batch.py`, ajouter (adapter aux fixtures du fichier — `db_session`, `_settings`, monkeypatch de `import_service.iter_import_event`) :

```python
def test_run_batch_cumule_les_reconciliations(db_session, monkeypatch):
    from app.services import batch, import_service
    from app.services.import_service import Reassignment

    def _iter(db, url, settings, force=False):
        yield {
            "phase": "done", "imported": 0, "skipped": 0, "total": 1,
            "reconciled": 1,
            "reassignments": [Reassignment("BERRE | Audrey LE", "LE BERRE | Audrey", False)],
        }

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    items = [batch.BatchItem(url="https://k/1", label="klikego · A")]
    totals = batch.run_batch(db_session, items, _settings(), force=True, delay=0.0)

    assert totals.reconciled == 1
    assert totals.reassignments == [
        Reassignment("BERRE | Audrey LE", "LE BERRE | Audrey", False)
    ]
```

*(Si `test_batch.py` n'a pas de `_settings`, réutiliser le même helper que `test_rescrape_service.py` : `Settings(cache_ttl_in_progress_seconds=600, cache_ttl_finished_seconds=2592000)`.)*

- [ ] **Step 2: Lancer le test pour vérifier l'échec**

Run: `uv run pytest tests/test_services/test_batch.py::test_run_batch_cumule_les_reconciliations -v`
Expected: FAIL — `AttributeError: 'BatchTotals' object has no attribute 'reconciled'`.

- [ ] **Step 3: Enrichir `BatchTotals` et ajouter `_ItemResult`**

Dans `app/services/batch.py`, ajouter l'import (près de la ligne 17) :

```python
from app.services.import_service import Reassignment
```

Dans `BatchTotals` (après le champ `failures`, ligne 59), ajouter :

```python
    #: Participations réconciliées (identité réassignée) sur l'ensemble du batch.
    reconciled: int = 0
    #: Détail des réassignations, cumulé dans l'ordre du batch (léger : ~1 par
    #: participation réconciliée, pas une ligne par participation traitée).
    reassignments: list[Reassignment] = field(default_factory=list)
```

Après la définition de `BatchTotals`, ajouter le résultat par épreuve :

```python
@dataclass
class _ItemResult:
    """Ce qu'une épreuve rapporte au batch. `error` non nul = épreuve fautive."""
    imported: int = 0
    skipped: int = 0
    error: str | None = None
    reconciled: int = 0
    reassignments: list[Reassignment] = field(default_factory=list)
```

- [ ] **Step 4: Réécrire `_import_one` pour renvoyer `_ItemResult`**

Remplacer `_import_one` (lignes 125-157) par :

```python
def _import_one(
    db: Session,
    url: str,
    settings: Settings,
    *,
    force: bool,
    persist: bool,
    reporter: ProgressReporter,
) -> _ItemResult:
    """Consomme les phases d'une épreuve et en fait un `_ItemResult`.

    `iter_import_event` *yield* une phase `error` au lieu de lever : c'est cette
    phase qui porte l'échec, pas une exception. `persist=False` (dry-run) fait
    scraper l'épreuve sans rien écrire.
    """
    result = _ItemResult()

    for phase in import_service.iter_import_event(
        db, url, settings, force=force, persist=persist
    ):
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
            result.imported = phase.get("imported", 0)
            result.skipped = phase.get("skipped", 0)
            result.reconciled = phase.get("reconciled", 0)
            result.reassignments = phase.get("reassignments", [])
        elif nom == "error":
            result.error = phase.get("message", "erreur inconnue")

    return result
```

*(Note : le paramètre `persist` de `iter_import_event` est ajouté en Task 6 ; le default `True` y sera défini, donc ce code compile dès maintenant si Task 6 suit — mais l'appel passe `persist=persist`, valeur fournie par `run_batch` ci-dessous.)*

- [ ] **Step 5: Réécrire le corps de la boucle de `run_batch`**

Dans `run_batch`, changer la signature pour accepter `persist` (défaut `True`, rétro-compatible pour `import-sheet`) :

```python
def run_batch(
    db: Session,
    items: list[BatchItem],
    settings: Settings,
    *,
    force: bool,
    persist: bool = True,
    delay: float = 1.0,
    reporter: ProgressReporter | None = None,
) -> BatchTotals:
```

Puis remplacer le bloc `try/except`/agrégation (lignes 180-198) par :

```python
            try:
                result = _import_one(
                    db, item.url, settings, force=force, persist=persist, reporter=reporter
                )
            except Exception as exc:  # filet : un bug ne doit pas tuer le batch
                logger.warning("Échec import %s : %s", item.url, exc)
                result = _ItemResult(error=str(exc))

            if result.error:
                totals.errors += 1
                totals.failures.append(
                    BatchFailure(url=item.url, label=item.label, message=result.error)
                )
            else:
                totals.imported += result.imported
                totals.skipped += result.skipped
                totals.reconciled += result.reconciled
                totals.reassignments.extend(result.reassignments)
            totals.processed += 1  # tentée et allée au bout, réussie ou non
            _notify(partial(reporter.item_done, result.imported, result.skipped, result.error))
            _liberer_session(db)
```

- [ ] **Step 6: Lancer les tests pour vérifier le succès**

Run: `uv run pytest tests/test_services/test_batch.py -v`
Expected: PASS — le nouveau test **et** les tests existants du batch. (Ce step échouera à l'exécution tant que Task 6 n'a pas ajouté le paramètre `persist` à `iter_import_event` ; voir la note du Step 4. Si l'ordre d'exécution le pose problème, exécuter Task 6 juste après ce step, avant de committer — mais le code du batch, lui, est complet et correct ici.)

> **Ordre d'implémentation :** pour garder chaque tâche verte à son commit, **fusionner l'ajout du paramètre `persist` à `iter_import_event` (Task 6, Step 3) dans cette tâche** si vous exécutez en séquence stricte. Le plan les sépare par responsabilité (batch vs. sémantique dry-run), mais `iter_import_event(persist=...)` est leur point de couture. La solution recommandée : faire Task 6 Step 3 (signature `persist` + commit/rollback) **avant** ce Step 6.

- [ ] **Step 7: Commit**

```bash
git add app/services/batch.py tests/test_services/test_batch.py
git commit -m "feat(services): le batch cumule les réconciliations d'identité"
```

---

### Task 5 : `delete_orphans` (nettoyage des fiches vidées)

**Files:**
- Modify: `app/repositories/athlete_repository.py` (nouvelle fonction en fin de fichier)
- Test: `tests/test_repositories/test_athlete_repository.py`

**Interfaces:**
- Produces : `athlete_repository.delete_orphans(db: Session) -> int` — supprime les athlètes sans aucune participation, renvoie le nombre supprimé. Ne commit pas (le service possède la transaction).

- [ ] **Step 1: Écrire les tests qui échouent**

Dans `tests/test_repositories/test_athlete_repository.py`, ajouter :

```python
def _course_avec_participation(db_session, nom_athlete):
    from app.repositories import course_repository, participation_repository

    course = course_repository.get_or_create(
        db_session, name="Tri", event_date=None, event_type="triathlon-m",
        source_url="https://k/x", provider="klikego",
    )
    athlete = athlete_repository.get_or_create(db_session, nom=nom_athlete, prenom="X")
    db_session.flush()
    participation_repository.create(
        db_session, athlete_id=athlete.id, course_id=course.id, bib_number="1",
    )
    db_session.flush()
    return athlete


def test_delete_orphans_supprime_les_sans_participation(db_session):
    rattache = _course_avec_participation(db_session, "RATTACHE")
    orphelin = athlete_repository.get_or_create(db_session, nom="ORPHELIN", prenom="O")
    db_session.flush()

    n = athlete_repository.delete_orphans(db_session)

    assert n == 1
    assert athlete_repository.get(db_session, orphelin.id) is None
    assert athlete_repository.get(db_session, rattache.id) is not None


def test_delete_orphans_no_op_sur_base_saine(db_session):
    """Garde de non-régression : 0 orphelin aujourd'hui → la règle n'emporte rien."""
    _course_avec_participation(db_session, "RATTACHE")

    assert athlete_repository.delete_orphans(db_session) == 0
```

- [ ] **Step 2: Lancer les tests pour vérifier l'échec**

Run: `uv run pytest tests/test_repositories/test_athlete_repository.py -k delete_orphans -v`
Expected: FAIL — `AttributeError: ... has no attribute 'delete_orphans'`.

- [ ] **Step 3: Implémenter `delete_orphans`**

Dans `app/repositories/athlete_repository.py`, ajouter en fin de fichier — et compléter l'import du modèle `Participation` en tête :

```python
from app.models.participation import Participation
```

```python
def delete_orphans(db: Session) -> int:
    """Supprime les athlètes sans aucune participation. Renvoie le nombre supprimé.

    `Participation.athlete_id` est la **seule** FK vers `Athlete` : un athlète
    sans participation n'est plus référencé nulle part. La base compte 0 orphelin
    en régime normal, donc la règle est un no-op sur l'existant — elle ne peut
    emporter que ce que la réconciliation vient de libérer. Appelée **une fois**
    en fin de batch (jamais par épreuve : un orphelin après l'épreuve A peut être
    ré-attaché par l'épreuve B).
    """
    rows = (
        db.query(Athlete.id)
        .outerjoin(Participation, Participation.athlete_id == Athlete.id)
        .filter(Participation.id.is_(None))
        .all()
    )
    orphan_ids = [r[0] for r in rows]
    if not orphan_ids:
        return 0
    db.query(Athlete).filter(Athlete.id.in_(orphan_ids)).delete(synchronize_session=False)
    return len(orphan_ids)
```

- [ ] **Step 4: Lancer les tests pour vérifier le succès**

Run: `uv run pytest tests/test_repositories/test_athlete_repository.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/repositories/athlete_repository.py tests/test_repositories/test_athlete_repository.py
git commit -m "feat(repositories): supprimer les athlètes orphelins (fiches vidées)"
```

---

### Task 6 : `--dry-run` scrape sans persister (flag `persist`)

**Files:**
- Modify: `app/services/import_service.py` (`import_event` et `iter_import_event` : param `persist`, commit vs rollback)
- Test: `tests/test_services/test_import_service.py`

**Interfaces:**
- Produces : `import_event(db, url, settings, force=False, persist=True)` et `iter_import_event(db, url, settings, force=False, persist=True)`. Quand `persist=False`, la transaction est **annulée** (`db.rollback()`) au lieu d'être committée, après avoir traversé tout le chemin de persistance.

- [ ] **Step 1: Écrire les tests qui échouent**

Dans `tests/test_services/test_import_service.py`, ajouter :

```python
def test_persist_false_scrape_mais_n_ecrit_rien(db_session, patch_scraper):
    """Dry-run : le scrape a lieu, les compteurs sont calculés, rien n'est persisté."""
    patch_scraper([_result("1", "DUPONT"), _result("2", "MARTIN")])

    out = import_service.import_event(db_session, URL, _settings(), persist=False)

    assert out["imported"] == 2  # calculé
    db_session.expire_all()
    assert participation_repository.list_participations(db_session, page_size=100) == []
    assert course_repository.list_all(db_session) == []


def test_iter_persist_false_annule_la_transaction(db_session, patch_scraper):
    patch_scraper([_result("1", "DUPONT")])

    phases = list(
        import_service.iter_import_event(db_session, URL, _settings(), persist=False)
    )

    assert phases[-1]["phase"] == "done"
    assert phases[-1]["imported"] == 1
    db_session.expire_all()
    assert participation_repository.list_participations(db_session, page_size=100) == []
```

- [ ] **Step 2: Lancer les tests pour vérifier l'échec**

Run: `uv run pytest tests/test_services/test_import_service.py -k "persist_false" -v`
Expected: FAIL — `TypeError: import_event() got an unexpected keyword argument 'persist'`.

- [ ] **Step 3: Ajouter le paramètre `persist` et brancher commit/rollback**

Dans `app/services/import_service.py`, `import_event` — signature (ligne 149) :

```python
def import_event(
    db: Session, url: str, settings: Settings, force: bool = False, persist: bool = True
) -> dict:
```

Dans son bloc `try` (lignes 166-174), remplacer `db.commit()` par la clôture conditionnelle :

```python
    persister = _Persister(db, url)
    try:
        for scraped in results:
            persister.add(scraped)
        persister.finalize()
        if persist:
            db.commit()
        else:
            db.rollback()  # dry-run : traverser la persistance, ne rien écrire
    except Exception:
        db.rollback()
        logger.exception("Rollback de l'import %s", url)
        raise ScraperError("Erreur lors de l'enregistrement des résultats.") from None
```

Dans `iter_import_event` — signature (lignes 179-181) :

```python
def iter_import_event(
    db: Session, url: str, settings: Settings, force: bool = False, persist: bool = True
) -> Iterator[dict]:
```

Dans son bloc `try` (lignes 215-232), remplacer `db.commit()` de même :

```python
    try:
        for i, scraped in enumerate(results):
            persister.add(scraped)
            if (i + 1) % 20 == 0 or i == total - 1:
                yield {
                    "phase": "saving",
                    "total": total,
                    "imported": persister.imported,
                    "skipped": persister.skipped,
                    "progress": i + 1,
                }
        persister.finalize()
        if persist:
            db.commit()
        else:
            db.rollback()  # dry-run : traverser la persistance, ne rien écrire
    except Exception:
        db.rollback()
        logger.exception("Rollback de l'import streaming %s", url)
        yield {"phase": "error", "message": "Erreur lors de l'enregistrement des résultats."}
        return
```

- [ ] **Step 4: Lancer les tests pour vérifier le succès**

Run: `uv run pytest tests/test_services/test_import_service.py tests/test_services/test_batch.py -v`
Expected: PASS — les nouveaux tests dry-run, plus le batch (le paramètre `persist` attendu par `_import_one` existe désormais).

- [ ] **Step 5: Commit**

```bash
git add app/services/import_service.py tests/test_services/test_import_service.py
git commit -m "feat(services): persist=False fait scraper sans écrire (base du dry-run)"
```

---

### Task 7 : `rescrape_service` — bilan enrichi, agrégation, orphelins, dry-run

**Files:**
- Modify: `app/services/rescrape_service.py` (imports, `IdentiteReconciliee`, `RescrapeOutcome`, `run_rescrape_db`)
- Test: `tests/test_services/test_rescrape_service.py` (nouveaux tests **et** mise à jour des tests dry-run existants)

**Interfaces:**
- Consumes : `BatchTotals.reconciled` / `.reassignments` (Task 4), `run_batch(persist=...)` (Task 4/6), `athlete_repository.delete_orphans` (Task 5).
- Produces : `rescrape_service.IdentiteReconciliee(ancien: str, nouveau: str, participations: int)`.
- Produces : `RescrapeOutcome` gagne `reconciled: int`, `merged: int`, `orphans_removed: int`, `dry_run: bool`, `reconciliations: list[IdentiteReconciliee]`. `echec_total` renvoie `False` en dry-run.

- [ ] **Step 1: Écrire / mettre à jour les tests**

Dans `tests/test_services/test_rescrape_service.py`, ajouter un helper prénom-paramétré et les nouveaux tests :

```python
def _scraped_nomme(bib: str, nom: str, prenom: str) -> ScrapedResult:
    return ScrapedResult(
        source_url="http://detail", provider="klikego",
        athlete_name=nom, athlete_firstname=prenom, bib_number=bib,
        event_name="Triathlon de Nantes", event_date=date(2026, 5, 16),
        event_type="triathlon-m", total_time="01:59:00",
    )


def test_rescrape_reconcilie_et_supprime_les_orphelins(db_session, monkeypatch):
    url = "https://www.klikego.com/resultats/event/123"

    def _scraper(resultats):
        monkeypatch.setattr(
            import_service, "registry_scrape_event_all", lambda _u: resultats
        )

    # Graphie fautive en base.
    _scraper([_scraped_nomme("1", "BERRE", "Audrey LE")])
    import_service.import_event(db_session, url, _settings())

    # Re-scrape avec la graphie corrigée.
    _scraper([_scraped_nomme("1", "LE BERRE", "Audrey")])
    out = rescrape_service.run_rescrape_db(db_session, _settings(), delay=0.0)

    assert out.reconciled == 1
    assert out.orphans_removed == 1  # l'ancienne fiche, vidée
    assert out.merged == 0           # cible créée : renommage, pas fusion
    assert out.reconciliations == [
        rescrape_service.IdentiteReconciliee(
            ancien="BERRE | Audrey LE", nouveau="LE BERRE | Audrey", participations=1
        )
    ]


def test_rescrape_dry_run_scrape_mais_ne_persiste_rien(db_session, monkeypatch):
    url = "https://www.klikego.com/resultats/event/123"

    def _scraper(resultats):
        monkeypatch.setattr(
            import_service, "registry_scrape_event_all", lambda _u: resultats
        )

    _scraper([_scraped_nomme("1", "BERRE", "Audrey LE")])
    import_service.import_event(db_session, url, _settings())

    _scraper([_scraped_nomme("1", "LE BERRE", "Audrey")])
    out = rescrape_service.run_rescrape_db(db_session, _settings(), dry_run=True, delay=0.0)

    assert out.reconciled == 1          # calculé
    assert out.reconciliations          # détail non vide
    assert out.orphans_removed == 0     # rien créé, rien à nettoyer
    assert out.echec_total is False     # un dry-run ne peut jamais échouer
    # Rien persisté : la participation pointe toujours sur l'ancienne identité.
    db_session.expire_all()
    parts = participation_repository.list_participations(db_session, page_size=100)
    assert (parts[0].athlete.nom, parts[0].athlete.prenom) == ("BERRE", "Audrey LE")
```

Puis **mettre à jour les tests dry-run existants** qui supposaient « aucun scrape en dry-run » :

- `test_run_rescrape_dry_run_liste_sans_scraper` (lignes 39-52) — remplacer par :

```python
def test_run_rescrape_dry_run_liste_les_urls_et_ne_persiste_pas(db_session, monkeypatch):
    """Le dry-run scrape désormais (persist=False), mais liste toujours les URLs."""
    _course(db_session, "A", "https://k/1")
    persist_vus: list[bool] = []

    def _iter(db, url, settings, force=False, persist=True):
        persist_vus.append(persist)
        yield {"phase": "done", "imported": 0, "skipped": 0, "reconciled": 0,
               "reassignments": [], "total": 0}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    out = rescrape_service.run_rescrape_db(db_session, _settings(), dry_run=True, delay=0.0)
    assert persist_vus == [False]        # scrapé, mais sans persister
    assert out.dry_run_urls == ["https://k/1"]
    assert out.total == 1
```

- `test_run_rescrape_dry_run_liste_les_urls_uniques` (lignes 128-137) — ajouter un `_iter` monkeypatché (persist-aware, comme ci-dessus) pour éviter le réseau, en gardant les assertions sur `out.total == 2` et `out.dry_run_urls`.

- `test_run_rescrape_dry_run_n_est_jamais_un_echec_total` (lignes 236-243) — remplacer par une version qui monkeypatche `iter_import_event` pour *échouer*, prouvant que le dry-run reste `echec_total is False` malgré des erreurs de scrape :

```python
def test_run_rescrape_dry_run_n_est_jamais_un_echec_total(db_session, monkeypatch):
    _course(db_session, "A", "https://k/1")

    def _iter(db, url, settings, force=False, persist=True):
        yield {"phase": "error", "message": "503"}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    out = rescrape_service.run_rescrape_db(db_session, _settings(), dry_run=True, delay=0.0)
    assert out.echec_total is False
```

- `test_mode_urls_dry_run_liste_sans_scraper` (lignes 327-338) — remplacer l'`_iter` qui `raise AssertionError` par un `_iter` persist-aware, et vérifier `persist=False` reçu :

```python
def test_mode_urls_dry_run_scrape_sans_persister(db_session, monkeypatch):
    persist_vus: list[bool] = []

    def _iter(db, url, settings, force=False, persist=True):
        persist_vus.append(persist)
        yield {"phase": "done", "imported": 0, "skipped": 0, "reconciled": 0,
               "reassignments": [], "total": 0}

    monkeypatch.setattr(import_service, "iter_import_event", _iter)

    out = rescrape_service.run_rescrape_db(
        db_session, _settings(), dry_run=True, delay=0.0, urls=["https://k/1"]
    )
    assert persist_vus == [False]
    assert out.dry_run_urls == ["https://k/1"]
    assert out.total == 1
```

- Enfin, **mettre à jour tous les autres doubles `_iter` du fichier** pour accepter le paramètre `persist` (ajouter `persist=True` à leur signature) et yielder `reconciled`/`reassignments` — sinon `run_rescrape_db` (qui passe `persist=...` et lit ces clés) casse. Les doubles concernés renvoient déjà un `done` ; ajouter `"reconciled": 0, "reassignments": []` à chacun et `persist=True` à chaque signature `def _iter(...)`.

- [ ] **Step 2: Lancer les tests pour vérifier l'échec**

Run: `uv run pytest tests/test_services/test_rescrape_service.py -k "reconcilie or dry_run_scrape" -v`
Expected: FAIL — `AttributeError` sur `IdentiteReconciliee` / champs manquants de `RescrapeOutcome`.

- [ ] **Step 3: Enrichir `RescrapeOutcome` et ajouter `IdentiteReconciliee`**

Dans `app/services/rescrape_service.py`, compléter les imports en tête :

```python
from collections import Counter

from app.repositories import athlete_repository, course_repository
```

Après les imports, ajouter le dataclass de détail :

```python
@dataclass(frozen=True)
class IdentiteReconciliee:
    """Une identité corrigée et son volume : « ancien -> nouveau (N participations) ».

    Agrégée par paire (ancien, nouveau) : bornée aux seules réconciliations,
    donc légère — comme `failures`. Reprise telle quelle dans `--json` via
    `asdict()`.
    """
    ancien: str
    nouveau: str
    participations: int
```

Dans `RescrapeOutcome` (après le champ `failures`, ligne 80), ajouter :

```python
    #: Participations réconciliées (identité réassignée).
    reconciled: int = 0
    #: Athlètes fusionnés (cible corrigée préexistante — pas un simple renommage).
    merged: int = 0
    #: Athlètes orphelins supprimés en fin de batch (fiches vidées).
    orphans_removed: int = 0
    #: Dry-run : le batch a scrapé sans persister. Neutralise `echec_total`.
    dry_run: bool = False
    #: Détail des identités réconciliées (ancien -> nouveau, volume).
    reconciliations: list[IdentiteReconciliee] = field(default_factory=list)
```

Remplacer la propriété `echec_total` (lignes 82-92) pour neutraliser le dry-run :

```python
    @property
    def echec_total(self) -> bool:
        """Toutes les épreuves ciblées ont échoué (cf. `batch.est_echec_total`).

        Un dry-run ne persiste rien : il ne peut jamais être un échec total, même
        si des scrapes échouent (règle « un dry-run sort toujours en 0 »).
        """
        if self.dry_run:
            return False
        return est_echec_total(epreuves=self.total, errors=self.errors)
```

- [ ] **Step 4: Réécrire `run_rescrape_db` (dry-run qui scrape, agrégation, orphelins)**

Remplacer le corps de `run_rescrape_db` à partir de la construction de `outcome` (lignes 136-151) par :

```python
    outcome = RescrapeOutcome(total=len(items), dry_run=dry_run)
    if dry_run:
        # Charge utile réservée au dry-run : hors dry-run, embarquer l'URL de
        # chaque épreuve gonflerait la sortie --json de plusieurs dizaines de Ko.
        outcome.dry_run_urls = [item.url for item in items]

    totals = run_batch(
        db, items, settings, force=True, persist=not dry_run, delay=delay, reporter=reporter
    )

    outcome.imported = totals.imported
    outcome.skipped = totals.skipped
    outcome.errors = totals.errors
    outcome.failures = totals.failures
    outcome.processed = totals.processed
    outcome.interrupted = totals.interrupted

    outcome.reconciled = totals.reconciled
    outcome.merged = len({r.ancien for r in totals.reassignments if r.fusion})
    compteur = Counter((r.ancien, r.nouveau) for r in totals.reassignments)
    outcome.reconciliations = [
        IdentiteReconciliee(ancien=ancien, nouveau=nouveau, participations=n)
        for (ancien, nouveau), n in compteur.items()
    ]

    # Nettoyage des orphelins : une seule fois, après tout le batch, et jamais en
    # dry-run (rien n'a été persisté, donc aucune fiche n'a été vidée).
    if not dry_run:
        outcome.orphans_removed = athlete_repository.delete_orphans(db)
        db.commit()

    return outcome
```

Vérifier que l'import `from app.services import sheet_source` reste et que `course_repository` est bien importé (ajouté au Step 3).

- [ ] **Step 5: Lancer les tests pour vérifier le succès**

Run: `uv run pytest tests/test_services/test_rescrape_service.py -v`
Expected: PASS — les nouveaux tests **et** tous les tests mis à jour.

- [ ] **Step 6: Commit**

```bash
git add app/services/rescrape_service.py tests/test_services/test_rescrape_service.py
git commit -m "feat(services): bilan de réconciliation, nettoyage des orphelins, dry-run qui scrape"
```

---

### Task 8 : Rapport CLI — bloc « réconciliation »

**Files:**
- Modify: `app/cli/reports.py` (`_lignes_reconciliation`, appels dans `render_rescrape_report`)
- Test: `tests/test_cli/test_reports.py`

**Interfaces:**
- Consumes : `RescrapeOutcome.reconciled` / `.merged` / `.orphans_removed` / `.reconciliations` (Task 7).
- Le bloc apparaît dans les **deux** modes (dry-run et réel) dès qu'il y a au moins une réconciliation.

- [ ] **Step 1: Écrire les tests qui échouent**

Dans `tests/test_cli/test_reports.py`, ajouter :

```python
def test_rapport_rescrape_affiche_le_bloc_de_reconciliation():
    from app.services.rescrape_service import IdentiteReconciliee

    out = RescrapeOutcome(
        total=1, imported=0, skipped=3, processed=1,
        reconciled=12, merged=1, orphans_removed=5,
        reconciliations=[
            IdentiteReconciliee(
                ancien="BERRE | Audrey LE", nouveau="LE BERRE | Audrey", participations=12
            )
        ],
    )
    texte = render_rescrape_report(out, dry_run=False)

    assert "Participations réconciliées" in texte
    assert "Athlètes fusionnés" in texte
    assert "Athlètes orphelins supprimés" in texte
    assert "Identités réconciliées (détail) :" in texte
    assert "  - BERRE | Audrey LE  ->  LE BERRE | Audrey   (12 participations)" in texte


def test_rapport_rescrape_sans_reconciliation_masque_le_bloc():
    out = RescrapeOutcome(total=1, imported=2, skipped=0, processed=1)
    texte = render_rescrape_report(out, dry_run=False)

    assert "réconciliées" not in texte
    assert "orphelins" not in texte
```

- [ ] **Step 2: Lancer les tests pour vérifier l'échec**

Run: `uv run pytest tests/test_cli/test_reports.py -k reconciliation -v`
Expected: FAIL — le bloc n'est pas rendu.

- [ ] **Step 3: Ajouter `_lignes_reconciliation` et l'appeler**

Dans `app/cli/reports.py`, après `_lignes_echecs` (ligne 77), ajouter :

```python
def _lignes_reconciliation(outcome: RescrapeOutcome) -> list[str]:
    """Le bilan de réconciliation d'identité (issue #66), borné aux réassignations.

    Unités nommées : on compte des **participations** et des **athlètes**, jamais
    des « lignes ». Masqué quand rien n'a été réconcilié.
    """
    if not outcome.reconciled:
        return []
    lignes = [
        _ligne("Participations réconciliées", outcome.reconciled),
        _ligne("Athlètes fusionnés", outcome.merged),
        _ligne("Athlètes orphelins supprimés", outcome.orphans_removed),
        "Identités réconciliées (détail) :",
    ]
    lignes.extend(
        f"  - {r.ancien}  ->  {r.nouveau}   ({r.participations} participations)"
        for r in outcome.reconciliations
    )
    return lignes
```

Dans `render_rescrape_report`, ajouter l'appel avant le `return` (après la branche `if dry_run: ... else: ...`, ligne 111) :

```python
    lignes.extend(_lignes_reconciliation(outcome))
    return "\n".join(lignes)
```

- [ ] **Step 4: Lancer les tests pour vérifier le succès**

Run: `uv run pytest tests/test_cli/test_reports.py -v`
Expected: PASS (nouveaux tests + tous les tests reports existants).

- [ ] **Step 5: Commit**

```bash
git add app/cli/reports.py tests/test_cli/test_reports.py
git commit -m "feat(cli): bloc de réconciliation d'identité dans le bilan rescrape-db"
```

---

### Task 9 : Documentation — `AGENTS.md`

**Files:**
- Modify: `AGENTS.md` (section « Sorties de la CLI » / `rescrape-db`)

**Interfaces:** aucune — documentation.

- [ ] **Step 1: Acter les trois changements de comportement**

Dans `AGENTS.md`, à la fin de la sous-section qui décrit `rescrape-db` (juste après le paragraphe « Détail des épreuves en erreur », avant « ### Conventions scrapers »), ajouter :

```markdown
**Réconciliation de l'identité d'athlète** (issue #66) : `rescrape-db` n'est plus
purement additif. Sur un dossard déjà en base, il **résout l'athlète** et, si la
graphie stockée a divergé de la graphie corrigée, **réassigne
`participation.athlete_id`** — puis supprime en fin de batch les fiches d'athlète
ainsi vidées (`athlete_repository.delete_orphans`, no-op sur une base sans
orphelin). Le bilan compte, unités nommées : « Participations réconciliées »,
« Athlètes fusionnés », « Athlètes orphelins supprimés », avec le détail
`ancien -> nouveau (N participations)` — repris dans `--json`.

Il ne réconcilie **que** l'identité : temps, rangs, statuts et splits d'une
participation existante restent intouchés. Ce silence sur les valeurs est
délibéré (idempotence contre additivité : une autre question, une autre issue).
Garde structurante : une correction qui **viderait le prénom** n'est jamais
appliquée (cas « JP ROUX » / prénoms stockés en majuscules).

`--dry-run` a changé de nature : il **scrape désormais** (le prix d'un aperçu
véritable) et **ne persiste rien** (rollback au lieu de commit). Il rend le détail
`avant -> après` sans écrire. `--limit` / `--url` le bornent. Un dry-run sort
toujours en code 0.
```

- [ ] **Step 2: Vérifier la cohérence**

Run: `grep -n "réconcili" AGENTS.md`
Expected: les nouvelles lignes apparaissent ; le vocabulaire (« épreuves » / « participants ») reste cohérent avec le reste de la section.

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md
git commit -m "docs: rescrape-db réconcilie l'identité d'athlète et dry-run scrape sans persister"
```

---

## Vérification finale

- [ ] **Suite complète sans réseau**

Run: `uv run pytest -m "not integration"`
Expected: PASS (≈510 tests + les nouveaux). Aucun test réseau déclenché.

- [ ] **Lint**

Run: `uv run ruff check .`
Expected: aucune erreur.

---

## Self-Review (vérifié à l'écriture)

**Couverture du spec :**
- §4.1 (repli de `_Persister.add`, `existing_participations_for_course`, coût assumé) → Tasks 1, 3.
- §4.2 (orphelins, nettoyage une fois en fin de batch, no-op sur base saine) → Tasks 5, 7.
- §4.3 (dry-run D1 : scrape sans persister, flag descendu jusqu'à `_import_one`) → Tasks 4, 6, 7.
- §4.4 (bilan : champs de `RescrapeOutcome`, `--json` via `asdict`, unités nommées) → Tasks 7, 8.
- §5 (tous les tests du tableau) → Task 3 (divergent/identique/fusion/garde), Task 5 (orphelins ×2), Task 7 (dry-run), et la garde vivante `split_athlete_name` **déjà présente** (préalable).
- §6 (doc `AGENTS.md`, 3 points) → Task 9.
- §7 (ce que la conception ne fait pas) : non implémenté par construction (frontière stricte sur `athlete_id`, garde des ambigus). Cohérent.

**Cohérence des types :** `Reassignment(ancien, nouveau, fusion)` défini en Task 3, consommé identiquement en Tasks 4 et 7 ; `IdentiteReconciliee(ancien, nouveau, participations)` défini en Task 7, consommé en Task 8. `resolve(...) -> tuple[Athlete, bool]` (Task 2) et son drapeau `cree` (= `not fusion`) utilisés en Task 3. `run_batch(persist=...)` (Task 4) et `iter_import_event(persist=...)` (Task 6) : point de couture signalé explicitement dans la note de Task 4.

**Pas de placeholder :** chaque step porte le code complet ou la commande exacte avec sa sortie attendue.
