# Distinction solo / relais comme deux courses — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Faire du drapeau relais une composante de l'identité d'une `Course`, pour que « Triathlon M individuel » et « Triathlon M relais » deviennent deux courses distinctes, chez tous les fournisseurs.

**Architecture:** On ajoute `is_relay` à la contrainte d'unicité de `Course` (`uq_course_identity`) et au filtre de recherche du repository, puis on corrige le scraper Klikego pour qu'il déduise le relais du slug `heat`. Côté frontend, un helper partagé `formatEventName(name, isRelay)` suffixe « (Relais) » partout où le `is_relay` de la course est disponible.

**Tech Stack:** Backend FastAPI + SQLAlchemy 2.0 (sync) + Alembic + pytest ; Frontend Next.js 16 + TypeScript + Vitest.

## Global Constraints

- **Langue** : UI, commentaires et messages en **français** (avec accents).
- Commits : **Conventional Commits** (`feat:`, `fix:`, `test:`…).
- Schéma DB : migration **Alembic** (ici hand-written, batch mode pour SQLite).
- Tests unitaires **sans réseau** (le réseau réel est derrière le marker `integration`).
- Backend lint : `ruff check .` doit passer. Frontend : `npm run lint` et `npx tsc` stricts.
- Backend testé via SQLite in-memory : `tests/conftest.py` crée le schéma avec
  `Base.metadata.create_all` à partir des **modèles** (pas via Alembic). La
  contrainte d'unicité doit donc être portée par le **modèle** pour que les tests
  la voient ; la migration ne sert qu'aux bases réelles (Postgres/SQLite de dev).

---

### Task 1 : Identité de Course incluant `is_relay` (modèle + repository + migration)

**Files:**
- Modify: `backend/app/models/course.py:13-15` (UniqueConstraint)
- Modify: `backend/app/repositories/course_repository.py:15-26` (`get_by_identity`)
- Modify: `backend/app/repositories/course_repository.py:29-54` (`get_or_create`)
- Create: `backend/alembic/versions/b2c3d4e5f6a7_course_identity_is_relay.py`
- Test: `backend/tests/test_repositories/test_course_repository.py`
- Test: `backend/tests/test_services/test_mapping.py`

**Interfaces:**
- Consumes : `Course` (modèle SQLAlchemy), fixture `db_session` (conftest), `ScrapedResult`.
- Produces :
  - `course_repository.get_by_identity(db, name, event_date, event_type, is_relay) -> Course | None`
    (ajout du paramètre `is_relay: bool`).
  - `course_repository.get_or_create(...)` inchangé en signature (le param `is_relay` existe déjà),
    mais transmet désormais `is_relay` au lookup.
  - `mapping.get_or_create_course(db, scraped, event_url) -> Course` : inchangé (passe déjà `scraped.is_relay`).

- [ ] **Step 1 : Écrire le test repository qui échoue (deux courses si seul `is_relay` diffère)**

Ajouter à la fin de `backend/tests/test_repositories/test_course_repository.py` :

```python
def test_is_relay_makes_distinct_course(db_session):
    solo = course_repository.get_or_create(
        db_session,
        name="Triathlon de Nantes",
        event_date=date(2026, 5, 16),
        event_type="triathlon-m",
        is_relay=False,
    )
    relais = course_repository.get_or_create(
        db_session,
        name="Triathlon de Nantes",
        event_date=date(2026, 5, 16),
        event_type="triathlon-m",
        is_relay=True,
    )
    assert solo.id != relais.id
    assert solo.is_relay is False
    assert relais.is_relay is True


def test_get_by_identity_discriminates_on_is_relay(db_session):
    course_repository.get_or_create(
        db_session,
        name="Tri Y",
        event_date=date(2026, 6, 1),
        event_type="triathlon-s",
        is_relay=True,
    )
    found_solo = course_repository.get_by_identity(
        db_session, "Tri Y", date(2026, 6, 1), "triathlon-s", is_relay=False
    )
    found_relais = course_repository.get_by_identity(
        db_session, "Tri Y", date(2026, 6, 1), "triathlon-s", is_relay=True
    )
    assert found_solo is None
    assert found_relais is not None
    assert found_relais.is_relay is True
```

- [ ] **Step 2 : Lancer le test, vérifier l'échec**

Run : `cd backend && pytest tests/test_repositories/test_course_repository.py -v`
Expected : `test_get_by_identity_discriminates_on_is_relay` FAIL avec
`TypeError: get_by_identity() got an unexpected keyword argument 'is_relay'`, et
`test_is_relay_makes_distinct_course` FAIL (un seul id, car le lookup ignore `is_relay`).

- [ ] **Step 3 : Ajouter `is_relay` à la contrainte d'unicité du modèle**

Dans `backend/app/models/course.py`, remplacer :

```python
    __table_args__ = (
        UniqueConstraint("name", "event_date", "event_type", name="uq_course_identity"),
    )
```

par :

```python
    __table_args__ = (
        UniqueConstraint(
            "name", "event_date", "event_type", "is_relay", name="uq_course_identity"
        ),
    )
```

- [ ] **Step 4 : Faire discriminer `get_by_identity` / `get_or_create` sur `is_relay`**

Dans `backend/app/repositories/course_repository.py`, remplacer `get_by_identity` :

```python
def get_by_identity(
    db: Session,
    name: str,
    event_date: date | None,
    event_type: str,
    is_relay: bool = False,
) -> Course | None:
    return (
        db.query(Course)
        .filter(
            Course.name == name,
            Course.event_date == event_date,
            Course.event_type == event_type,
            Course.is_relay == is_relay,
        )
        .first()
    )
```

Puis dans `get_or_create`, remplacer la ligne du lookup :

```python
    existing = get_by_identity(db, name, event_date, event_type)
```

par :

```python
    existing = get_by_identity(db, name, event_date, event_type, is_relay)
```

- [ ] **Step 5 : Lancer les tests repository, vérifier qu'ils passent**

Run : `cd backend && pytest tests/test_repositories/test_course_repository.py -v`
Expected : PASS (4 tests, dont les 2 nouveaux). Vérifier que
`test_get_or_create_dedups_on_identity` (qui n'utilise pas `is_relay`) passe toujours
(les deux appels ont `is_relay=False` par défaut → même course).

- [ ] **Step 6 : Écrire le test mapping (lot mixte solo + relais → 2 courses)**

Ajouter à la fin de `backend/tests/test_services/test_mapping.py` :

```python
def test_get_or_create_course_solo_and_relay_are_distinct(db_session):
    solo = _scraped(
        event_name="Triathlon de Nantes",
        event_type="triathlon-m",
        is_relay=False,
    )
    relais = _scraped(
        event_name="Triathlon de Nantes",
        event_type="triathlon-m",
        is_relay=True,
    )
    c_solo = mapping.get_or_create_course(db_session, solo, event_url="http://x")
    c_relais = mapping.get_or_create_course(db_session, relais, event_url="http://x")
    assert c_solo.id != c_relais.id
    assert c_solo.is_relay is False
    assert c_relais.is_relay is True
```

Note : `_scraped` est le helper déjà défini en tête de `test_mapping.py`
(`ScrapedResult(source_url=..., provider="klikego", **kw)`). `db_session` est la
fixture de `tests/conftest.py`.

- [ ] **Step 7 : Lancer le test mapping, vérifier qu'il passe**

Run : `cd backend && pytest tests/test_services/test_mapping.py -v`
Expected : PASS (le test mapping passe sans modifier `mapping.py`, qui transmet déjà `scraped.is_relay`).

- [ ] **Step 8 : Écrire la migration Alembic (schéma seul, batch mode)**

Créer `backend/alembic/versions/b2c3d4e5f6a7_course_identity_is_relay.py` :

```python
"""course identity includes is_relay

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-28 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Recrée la contrainte d'unicité en y ajoutant `is_relay`.
    # batch_alter_table → recréation de table sur SQLite, ALTER sur Postgres.
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.drop_constraint('uq_course_identity', type_='unique')
        batch_op.create_unique_constraint(
            'uq_course_identity',
            ['name', 'event_date', 'event_type', 'is_relay'],
        )


def downgrade() -> None:
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.drop_constraint('uq_course_identity', type_='unique')
        batch_op.create_unique_constraint(
            'uq_course_identity',
            ['name', 'event_date', 'event_type'],
        )
```

- [ ] **Step 9 : Vérifier que la migration s'applique sur une base SQLite neuve**

Run :
```bash
cd backend && python scripts/reset_db.py --no-seed --yes && alembic current
```
Expected : reset OK + `alembic current` affiche `b2c3d4e5f6a7 (head)`. (Le reset
applique `alembic upgrade head` ; aucune erreur de contrainte.)

- [ ] **Step 10 : Lint backend**

Run : `cd backend && ruff check app/models/course.py app/repositories/course_repository.py alembic/versions/b2c3d4e5f6a7_course_identity_is_relay.py`
Expected : `All checks passed!`

- [ ] **Step 11 : Commit**

```bash
git add backend/app/models/course.py backend/app/repositories/course_repository.py \
  backend/alembic/versions/b2c3d4e5f6a7_course_identity_is_relay.py \
  backend/tests/test_repositories/test_course_repository.py \
  backend/tests/test_services/test_mapping.py
git commit -m "fix(backend): is_relay fait partie de l'identité d'une Course (issue #9)"
```

---

### Task 2 : Klikego déduit `is_relay` du slug `heat`

**Files:**
- Modify: `backend/app/scrapers/klikego.py:249-294` (`_parse_search_row`)
- Test: `backend/tests/test_klikego.py`

**Interfaces:**
- Consumes : `_parse_search_row(row, event_id, heat, event_name, slug, rank) -> ScrapedResult`
  (helper de test `_make_search_row` déjà défini dans `test_klikego.py`).
- Produces : `ScrapedResult.is_relay = True` quand `"relais"` apparaît dans le slug `heat`.

- [ ] **Step 1 : Écrire les tests qui échouent (heat relais / individuel)**

Ajouter à la fin de `backend/tests/test_klikego.py` :

```python
def test_parse_search_row_relay_heat_sets_is_relay():
    """Un heat « ...relais » marque tous les résultats du heat comme relais."""
    row = _make_search_row(bib="12", name="DUPONT Jean")
    result = _parse_search_row(
        row, "EVT1", "triathlon-m-relais", "Tri M", "tri-m", rank=1
    )
    assert result.is_relay is True
    assert result.event_type == "triathlon-m"


def test_parse_search_row_individual_heat_not_relay():
    """Un heat « ...individuel » reste solo."""
    row = _make_search_row(bib="13", name="MARTIN Paul")
    result = _parse_search_row(
        row, "EVT1", "triathlon-m-individuel", "Tri M", "tri-m", rank=1
    )
    assert result.is_relay is False
    assert result.event_type == "triathlon-m"


def test_parse_search_row_duathlon_en_relais_heat():
    """Heat « duathlon-s---en-relais » → relais + event_type duathlon-s."""
    row = _make_search_row(bib="14", name="DURAND Eve")
    result = _parse_search_row(
        row, "EVT1", "duathlon-s---en-relais", "Dua S", "dua-s", rank=1
    )
    assert result.is_relay is True
    assert result.event_type == "duathlon-s"
```

- [ ] **Step 2 : Lancer les tests, vérifier l'échec**

Run : `cd backend && pytest tests/test_klikego.py -k "relay or relais or individual" -v`
Expected : les 2 tests « relais » FAIL (`assert False is True`) car `is_relay` reste à `False` ;
le test « individual » passe déjà (`is_relay` défaut `False`).

- [ ] **Step 3 : Déduire `is_relay` dans `_parse_search_row`**

Dans `backend/app/scrapers/klikego.py`, fonction `_parse_search_row`, juste après :

```python
    result.event_name = event_name
    result.event_type = _detect_event_type(heat, slug)
    result.rank_overall = rank
```

ajouter :

```python
    # Un heat Klikego est mono-discipline → drapeau relais uniforme sur ses résultats.
    # Le « s » final de « relais » n'est pas un token de taille → classification intacte.
    result.is_relay = "relais" in (heat or "").lower()
```

- [ ] **Step 4 : Lancer les tests, vérifier qu'ils passent**

Run : `cd backend && pytest tests/test_klikego.py -v`
Expected : PASS (toute la suite Klikego, y compris les 3 nouveaux et l'existant
`test_event_type_detection` inchangé).

- [ ] **Step 5 : Lint backend**

Run : `cd backend && ruff check app/scrapers/klikego.py`
Expected : `All checks passed!`

- [ ] **Step 6 : Commit**

```bash
git add backend/app/scrapers/klikego.py backend/tests/test_klikego.py
git commit -m "fix(scrapers): Klikego déduit is_relay du slug heat (issue #9)"
```

---

### Task 3 : Helper frontend `formatEventName`

**Files:**
- Create: `frontend/lib/utils/event.ts`
- Test: `frontend/lib/utils/event.test.ts`

**Interfaces:**
- Produces : `formatEventName(name: string, isRelay: boolean): string`
  → `"<name> (Relais)"` si `isRelay`, sinon `name` inchangé.

- [ ] **Step 1 : Écrire le test unitaire qui échoue**

Créer `frontend/lib/utils/event.test.ts` :

```ts
import { describe, it, expect } from "vitest";
import { formatEventName } from "./event";

describe("formatEventName", () => {
  it("suffixe « (Relais) » quand isRelay est vrai", () => {
    expect(formatEventName("Triathlon de Nantes", true)).toBe("Triathlon de Nantes (Relais)");
  });
  it("renvoie le nom inchangé quand isRelay est faux", () => {
    expect(formatEventName("Triathlon de Nantes", false)).toBe("Triathlon de Nantes");
  });
});
```

- [ ] **Step 2 : Lancer le test, vérifier l'échec**

Run : `cd frontend && npx vitest run lib/utils/event.test.ts`
Expected : FAIL — `Failed to resolve import "./event"` (le fichier n'existe pas encore).

- [ ] **Step 3 : Implémenter le helper**

Créer `frontend/lib/utils/event.ts` :

```ts
/** Nom d'épreuve affiché, suffixé « (Relais) » quand la course est un relais. */
export function formatEventName(name: string, isRelay: boolean): string {
  return isRelay ? `${name} (Relais)` : name;
}
```

- [ ] **Step 4 : Lancer le test, vérifier qu'il passe**

Run : `cd frontend && npx vitest run lib/utils/event.test.ts`
Expected : PASS (2 tests).

- [ ] **Step 5 : Commit**

```bash
git add frontend/lib/utils/event.ts frontend/lib/utils/event.test.ts
git commit -m "feat(frontend): helper formatEventName pour distinguer les relais (issue #9)"
```

---

### Task 4 : Appliquer `formatEventName` aux affichages de nom d'épreuve

**Files:**
- Modify: `frontend/components/results/EventList.tsx:117`
- Modify: `frontend/components/results/ResultCard.tsx:76-78`
- Modify: `frontend/app/courses/[id]/page.tsx:75`
- Modify: `frontend/components/club/ClubDashboard.tsx:96`
- Test: `frontend/components/results/EventList.test.tsx`

**Interfaces:**
- Consumes : `formatEventName(name, isRelay)` (Task 3).
- Champs disponibles : `EventOut.is_relay`, `Participation.course.is_relay`, `CourseOut.is_relay`
  (tous déjà présents dans `lib/types.ts` — aucun changement de types).

**Périmètre — `MapView` exclu (décision documentée) :** le spec liste « carte
(MapView) », mais le type `GeoEvent` ne porte **pas** `is_relay`, et l'endpoint geo
agrège les courses par nom/lieu (solo + relais de même nom retombent sur le même
marqueur). Le suffixer exigerait un changement backend + type, explicitement hors
périmètre (spec §4 « aucun changement de types », migration « schéma seul »).
`MapView` reste donc inchangé. Tous les autres points du spec sont couverts.

- [ ] **Step 1 : Écrire le test EventList qui échoue (« (Relais) » sur la ligne relais)**

Ajouter un test dans `frontend/components/results/EventList.test.tsx`. D'abord
inspecter le fichier pour réutiliser ses utilitaires de rendu/mocks existants :

Run : `cd frontend && cat components/results/EventList.test.tsx`

Puis ajouter un cas suivant le pattern du fichier (le mock de `useInfiniteEvents`
doit renvoyer un évènement avec `is_relay: true`) :

```tsx
it("affiche « (Relais) » dans le nom d'une épreuve relais", () => {
  // Réutiliser le helper de montage/mock du fichier (ex. renderEventList / mockEvents).
  // L'évènement injecté doit avoir { event_name: "Triathlon de Nantes", is_relay: true }.
  // Attendu : le libellé rendu contient "Triathlon de Nantes (Relais)".
  // expect(screen.getByText("Triathlon de Nantes (Relais)")).toBeInTheDocument();
});
```

> Le contenu exact (montage, mock du hook `useInfiniteEvents`) dépend des
> utilitaires déjà présents dans le fichier — les réutiliser tels quels plutôt que
> d'introduire un nouveau pattern. Le `EventOut` injecté doit porter au minimum
> `id`, `event_name`, `event_type`, `is_relay: true`, `total`, `tcn_count`.

- [ ] **Step 2 : Lancer le test, vérifier l'échec**

Run : `cd frontend && npx vitest run components/results/EventList.test.tsx`
Expected : FAIL — le texte attendu est `"Triathlon de Nantes"` (sans « (Relais) »),
donc `getByText("Triathlon de Nantes (Relais)")` ne trouve rien.

- [ ] **Step 3 : Appliquer le helper dans `EventList.tsx`**

Ajouter l'import en tête de `frontend/components/results/EventList.tsx` (groupe des imports `@/lib/utils`) :

```tsx
import { formatEventName } from "@/lib/utils/event";
```

Remplacer la ligne 117 :

```tsx
                <span className="font-semibold">{ev.event_name}</span>
```

par :

```tsx
                <span className="font-semibold">{formatEventName(ev.event_name, ev.is_relay)}</span>
```

- [ ] **Step 4 : Lancer le test EventList, vérifier qu'il passe**

Run : `cd frontend && npx vitest run components/results/EventList.test.tsx`
Expected : PASS.

- [ ] **Step 5 : Appliquer le helper dans `ResultCard.tsx`**

Ajouter l'import en tête de `frontend/components/results/ResultCard.tsx` :

```tsx
import { formatEventName } from "@/lib/utils/event";
```

Remplacer (lignes 76-78) :

```tsx
          <Link href={`/courses/${c.id}`} className="font-semibold hover:underline">
            {c?.name || "Épreuve inconnue"}
          </Link>
```

par :

```tsx
          <Link href={`/courses/${c.id}`} className="font-semibold hover:underline">
            {c?.name ? formatEventName(c.name, c.is_relay) : "Épreuve inconnue"}
          </Link>
```

- [ ] **Step 6 : Appliquer le helper dans la page détail course**

Ajouter l'import en tête de `frontend/app/courses/[id]/page.tsx` (groupe des imports `@/lib/utils`) :

```tsx
import { formatEventName } from "@/lib/utils/event";
```

Remplacer la ligne 75 :

```tsx
        <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 46, color: "var(--tcn-ink)", lineHeight: 1, marginBottom: 12 }}>{course.name}</div>
```

par :

```tsx
        <div style={{ fontFamily: "var(--tcn-font-display)", fontSize: 46, color: "var(--tcn-ink)", lineHeight: 1, marginBottom: 12 }}>{formatEventName(course.name, course.is_relay)}</div>
```

- [ ] **Step 7 : Appliquer le helper dans `ClubDashboard.tsx`**

Ajouter l'import en tête de `frontend/components/club/ClubDashboard.tsx` (groupe des imports `@/lib/utils`) :

```tsx
import { formatEventName } from "@/lib/utils/event";
```

Remplacer la ligne 96 :

```tsx
                          <span className="truncate">{p.course?.name}</span>
```

par :

```tsx
                          <span className="truncate">{p.course ? formatEventName(p.course.name, p.course.is_relay) : ""}</span>
```

> Vérifier au préalable que `p.course` est typé `CourseOut` (porte `name` et
> `is_relay`). Si `p.course` est optionnel dans le type, le garde `p.course ? … : ""`
> ci-dessus suffit ; sinon simplifier en `formatEventName(p.course.name, p.course.is_relay)`.

- [ ] **Step 8 : Vérifier types, lint et toute la suite Vitest**

Run :
```bash
cd frontend && npx tsc --noEmit && npm run lint && npm test
```
Expected : `tsc` sans erreur, ESLint sans erreur, tous les tests Vitest verts.

- [ ] **Step 9 : Commit**

```bash
git add frontend/components/results/EventList.tsx frontend/components/results/EventList.test.tsx \
  frontend/components/results/ResultCard.tsx frontend/app/courses/[id]/page.tsx \
  frontend/components/club/ClubDashboard.tsx
git commit -m "feat(frontend): affiche « (Relais) » dans les noms d'épreuve (issue #9)"
```

---

## Notes de déploiement (hors code — pour l'exécutant)

- **Dev** : `cd backend && python scripts/reset_db.py` (vide + migre + seed) après merge.
- **Prod (Supabase)** : `alembic upgrade head`, puis **re-scrape** des épreuves
  concernées (la migration est schéma-seul, aucun split de données existant).
- `Participation.is_relay` est **conservé** (alimente le badge, redondant mais non supprimé — hors périmètre).

## Self-review — couverture du spec

- Modèle : contrainte `uq_course_identity` + `is_relay` → Task 1, Step 3 ✓
- Repository `get_by_identity` / `get_or_create` discriminent sur `is_relay` → Task 1, Steps 4-5 ✓
- `mapping.get_or_create_course` inchangé (passe déjà `scraped.is_relay`) → confirmé Task 1, Step 7 ✓
- `Participation.is_relay` conservé → aucune tâche de suppression (voulu) ✓
- Klikego déduit `is_relay` du heat → Task 2 ✓
- Breizh Chrono / TimePulse / Wiclax / Playwright : aucun changement → non couverts par une tâche (voulu) ✓
- Migration Alembic batch (schéma seul) → Task 1, Steps 8-9 ✓
- Helper `formatEventName` → Task 3 ✓
- Application EventList / détail course / vues club / ResultCard → Task 4 ✓
- `MapView` : exclu avec justification (GeoEvent sans `is_relay`, agrégation par nom) → documenté Task 4 ✓
- `lib/types.ts` : aucun changement (`is_relay` déjà présent sur EventOut/CourseOut/Participation) → vérifié, aucune tâche ✓
- Tests repo / klikego / mapping / formatEventName / EventList → Tasks 1-4 ✓
