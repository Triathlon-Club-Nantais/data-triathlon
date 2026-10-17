# Accueil carrefour : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. In this repo the user names the executor; never default.

**Goal:** `/` devient un accueil carrefour (bandeau « direct » du club et tuiles d'espaces), le tableau de bord personnel passe à `/mon-espace`, et un endpoint `/club/last-outing` fournit la dernière sortie du club.

**Architecture:** Un endpoint backend réutilise les requêtes agrégées de `/stats` restreintes à une fenêtre de dates. Côté front, la page `/` est rendue serveur (aucune session lue) et compose un bandeau serveur, des chiffres animés client et des tuiles dont celles liées à la session se montent côté client.

**Tech Stack:** FastAPI, SQLAlchemy 2 sync, Pydantic v2, pytest ; Next.js 16 App Router, TypeScript, React Query, vitest + RTL.

**Spec:** `docs/superpowers/specs/2026-10-17-accueil-carrefour-design.md` (epic #1618).

## Global Constraints

- Copie visible en **français**, vouvoiement, « épreuve » (jamais « course ») et « athlète » (`frontend/AGENTS.md`). Identifiants, tests et messages de commit en anglais.
- Pas de tiret pour ponctuer une phrase dans la copie ni les commentaires (virgule, point ou parenthèses).
- Couches backend : `api → services → repositories`. Seuls les repositories construisent des requêtes. Un service n'importe aucun symbole `_privé` d'un autre service.
- `/api/v1` : ajout d'endpoint uniquement, aucune modification d'un endpoint existant (Principe IV).
- Pas de compatibilité ascendante : `/dashboard` est supprimé sans redirection.
- Écrans publics : composants `components/tcn/`, jetons `--tcn-*`, cible tactile 44 px (`tcn-cible-tactile`), anneau de focus opaque `--tcn-orange`.
- Session côté client seulement sur les écrans rendus serveur publics (`useSession` dans les composants client du rail, comme `AppNav`).
- Commentaires seulement pour une contrainte non évidente.
- Commits Conventional Commits, sans trailer `Co-Authored-By`.

**Amendement à la spec (appliqué en Task 1) :** la réponse de `/club/last-outing` est `{ end_date, events, athletes, podiums }`. Un `start` égal à « veille de `end` » serait faux quand on n'a couru que le samedi ; seule la date de la dernière course sert à l'affichage.

## Workflow git (epic)

- Branche d'intégration `epic/1618-accueil-carrefour`, créée depuis `docs/accueil-carrefour` (qui porte la spec et ce plan, et part de `main`), puis poussée.
- Une branche et une PR par sous-issue, basées sur la branche d'epic, corps avec `Refs #1618` et `Closes #<sous-issue>` : Tasks 1-2 → #1619, Task 3 → #1620, Tasks 4-7 → #1621.
- PR parapluie `epic/1618-accueil-carrefour` → `main` avec `Closes #1618` à la fin.

## File Structure

| Fichier | Rôle |
| --- | --- |
| `backend/app/repositories/participation_repository.py` | `dates` en filtre commun des stats ; `latest_club_event_date` |
| `backend/app/services/stats_service.py` | `get_last_outing` |
| `backend/app/schemas/club.py` | `ClubLastOuting` |
| `backend/app/api/v1/club.py` | `GET /club/last-outing` |
| `backend/tests/test_services/test_last_outing.py` | tests du service |
| `backend/tests/test_api/test_club_api.py` | tests d'API |
| `frontend/app/(public_restricted)/mon-espace/*` | page personnelle (déplacée de `dashboard/`) |
| `frontend/lib/types.ts`, `frontend/lib/api/server.ts` | type et appel `getClubLastOuting` |
| `frontend/lib/home.ts` (+ test) | logique pure du bandeau (titre de sortie, histogramme) |
| `frontend/lib/queries/nav-badges.ts` | `totalATraiter`, partagé par `AppNav` et la tuile |
| `frontend/components/home/ChiffreAnime.tsx` (+ test) | chiffre animé client |
| `frontend/components/home/BandeauDirect.tsx` (+ test) | bandeau orange serveur |
| `frontend/components/home/TuilesEspaces.tsx` (+ test) | tuiles d'espaces (serveur + client) |
| `frontend/app/(public_restricted)/page.tsx` (+ test) | l'accueil |

---

### Task 1: Last outing in the repository and service (#1619)

**Files:**
- Modify: `backend/app/repositories/participation_repository.py` (`_stats_filters` ~l.1062, `stats_totals` ~l.1078, `stats_rank_rows` ~l.1200)
- Modify: `backend/app/services/stats_service.py`
- Modify: `docs/superpowers/specs/2026-10-17-accueil-carrefour-design.md` (amendement de la réponse)
- Test: `backend/tests/test_services/test_last_outing.py`

**Interfaces:**
- Produces: `participation_repository.latest_club_event_date(db, *, season: int, federal_only: bool = False) -> date | None`
- Produces: `stats_totals(..., dates: tuple[date, date] | None = None)` et `stats_rank_rows(..., dates=...)`
- Produces: `stats_service.get_last_outing(db, *, federal_only: bool = False) -> dict | None`, clés `end_date: date`, `events: int`, `athletes: int`, `podiums: int`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_services/test_last_outing.py` :

```python
from datetime import date, datetime

import pytest

from app.core import season
from app.repositories import athlete_repository, course_repository, participation_repository
from app.services import stats_service


@pytest.fixture(autouse=True)
def _october_2026(monkeypatch):
    monkeypatch.setattr(season, "utcnow", lambda: datetime(2026, 10, 15, 12, 0, 0))


def _race(db, day, *, nom="DUPONT", club="TCN", event_type="triathlon-m", name=None, pending=False, **ranks):
    athlete = athlete_repository.get_or_create(db, nom=nom, prenom="Jean", club=club)
    course = course_repository.get_or_create(
        db, name=name or f"Tri {day.isoformat()} {event_type}", event_date=day, event_type=event_type
    )
    participation_repository.create(
        db, athlete_id=athlete.id, course_id=course.id, bib_number=nom, club=club,
        status="finisher", is_pending_validation=pending, **ranks,
    )
    db.flush()


def test_no_tcn_race_this_season_gives_none(db_session):
    _race(db_session, date(2026, 6, 1))
    _race(db_session, date(2026, 10, 11), club="ASPTT", nom="AUTRE")
    assert stats_service.get_last_outing(db_session) is None


def test_saturday_and_sunday_form_one_outing(db_session):
    _race(db_session, date(2026, 9, 20), nom="ANCIEN")
    _race(db_session, date(2026, 10, 10), nom="SAMEDI")
    _race(db_session, date(2026, 10, 11), nom="DIMANCHE")
    _race(db_session, date(2026, 10, 11), nom="DIMANCHE2", name="Tri du dimanche bis")

    outing = stats_service.get_last_outing(db_session)

    assert outing == {"end_date": date(2026, 10, 11), "events": 3, "athletes": 3, "podiums": 0}


def test_an_isolated_weekday_race_is_its_own_outing(db_session):
    _race(db_session, date(2026, 10, 10), nom="SAMEDI")
    _race(db_session, date(2026, 10, 14), nom="MERCREDI")

    outing = stats_service.get_last_outing(db_session)

    assert outing["end_date"] == date(2026, 10, 14)
    assert (outing["events"], outing["athletes"]) == (1, 1)


def test_pending_results_are_ignored(db_session):
    _race(db_session, date(2026, 10, 11), nom="VALIDE")
    _race(db_session, date(2026, 10, 12), nom="ATTENTE", pending=True)

    assert stats_service.get_last_outing(db_session)["end_date"] == date(2026, 10, 11)


def test_podiums_match_the_all_ranks_counter(db_session):
    _race(db_session, date(2026, 10, 11), nom="PREMIER", rank_overall=2)
    _race(db_session, date(2026, 10, 11), nom="CATEGORIE", rank_category=1, rank_overall=40)
    _race(db_session, date(2026, 10, 11), nom="LOIN", rank_overall=25)

    outing = stats_service.get_last_outing(db_session)
    stats = stats_service.get_stats(db_session, club_only=True, seasons=[2026])

    assert outing["podiums"] == 2 == stats["rank_counters"]["all"]["podiums"]


def test_federal_only_skips_non_federal_races(db_session):
    _race(db_session, date(2026, 10, 11), nom="TRI")
    _race(db_session, date(2026, 10, 12), nom="TRAIL", event_type="trail")

    assert stats_service.get_last_outing(db_session)["end_date"] == date(2026, 10, 12)
    assert stats_service.get_last_outing(db_session, federal_only=True)["end_date"] == date(2026, 10, 11)
```

- [ ] **Step 2: Run them to verify they fail**

Run (from `backend/`): `uv run pytest tests/test_services/test_last_outing.py -n 0 -q`
Expected: FAIL with `AttributeError: module 'app.services.stats_service' has no attribute 'get_last_outing'`

- [ ] **Step 3: Add the date window to the shared stats filters**

In `participation_repository.py`, extend `_stats_filters` and the two callers (keep every other caller unchanged, `dates` defaults to `None`):

```python
def _stats_filters(
    q, *, club_only: bool, seasons: list[int] | None, federal_only: bool,
    dates: tuple[date, date] | None = None,
):
    ...  # existing body unchanged, then before `return q`:
    if dates:
        q = q.filter(Course.event_date >= dates[0], Course.event_date <= dates[1])
    return q
```

In `stats_totals` and `stats_rank_rows`: add the keyword `dates: tuple[date, date] | None = None`, change the join condition to `if seasons or federal_only or dates:` and pass `dates=dates` to `_stats_filters`.

Add, after `stats_rank_rows`:

```python
def latest_club_event_date(db: Session, *, season: int, federal_only: bool = False) -> date | None:
    """Date de la dernière épreuve de `season` portant un résultat TCN validé (#1619)."""
    q = (
        db.query(func.max(Course.event_date))
        .select_from(Participation)
        .join(Course, Participation.course_id == Course.id)
        .filter(validated_clause(Participation.is_pending_validation))
    )
    q = _stats_filters(q, club_only=True, seasons=[season], federal_only=federal_only)
    return q.scalar()
```

- [ ] **Step 4: Add the service**

In `stats_service.py`, add `from datetime import timedelta` with the imports and:

```python
def get_last_outing(db: Session, *, federal_only: bool = False) -> dict | None:
    """Dernière sortie du club dans la saison en cours (#1619).

    La fenêtre `[d − 1 jour, d]` réunit samedi et dimanche ; `podiums` passe par
    `_rank_counters`, pour ne jamais diverger du compteur « tous rangs » de /club.
    """
    current = season_module.current_season()
    end = participation_repository.latest_club_event_date(db, season=current, federal_only=federal_only)
    if end is None:
        return None
    filters = {
        "club_only": True,
        "seasons": [current],
        "federal_only": federal_only,
        "dates": (end - timedelta(days=1), end),
    }
    _total, athletes, events = participation_repository.stats_totals(db, **filters)
    rows = participation_repository.stats_rank_rows(db, **filters)
    return {
        "end_date": end,
        "events": events,
        "athletes": athletes,
        "podiums": _rank_counters(rows)["all"]["podiums"],
    }
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_services/test_last_outing.py -n 0 -q` then `uv run pytest -m "not integration" -q` and `uv run ruff check .`
Expected: all PASS (no existing stats test changes).

- [ ] **Step 6: Amend the spec**

In the spec, section « Nouvel endpoint », replace the JSON example by `{ "end_date": "2026-09-06", "events": 3, "athletes": 48, "podiums": 9 }` and add one line: « `end_date` est la date de la dernière course ; la fenêtre n'est pas renvoyée (un samedi seul ferait mentir une date de début). »

- [ ] **Step 7: Commit**

```bash
git add backend/app/repositories/participation_repository.py backend/app/services/stats_service.py backend/tests/test_services/test_last_outing.py docs/superpowers/specs/2026-10-17-accueil-carrefour-design.md
git commit -m "feat(club): compute the club's last outing (#1619)"
```

### Task 2: `GET /api/v1/club/last-outing` (#1619)

**Files:**
- Modify: `backend/app/schemas/club.py`
- Modify: `backend/app/api/v1/club.py`
- Test: `backend/tests/test_api/test_club_api.py`

**Interfaces:**
- Consumes: `stats_service.get_last_outing` (Task 1)
- Produces: `GET /api/v1/club/last-outing?federal_only=` → `{"end_date": "YYYY-MM-DD", "events": int, "athletes": int, "podiums": int}` or `null`

- [ ] **Step 1: Write the failing tests** (append to `test_club_api.py`)

```python
def test_last_outing_is_null_without_any_race(client, db_session, monkeypatch):
    monkeypatch.setattr(season, "utcnow", lambda: datetime(2026, 10, 15, 12, 0, 0))

    resp = client.get("/api/v1/club/last-outing")

    assert resp.status_code == 200
    assert resp.json() is None


def test_last_outing_shape(client, db_session, monkeypatch):
    monkeypatch.setattr(season, "utcnow", lambda: datetime(2026, 10, 15, 12, 0, 0))
    ath = athlete_repository.get_or_create(db_session, nom="A", prenom="Alice", club="TCN")
    course = course_repository.get_or_create(
        db_session, name="C", event_date=date(2026, 10, 11), event_type="triathlon-m"
    )
    participation_repository.create(
        db_session, athlete_id=ath.id, course_id=course.id, bib_number="1",
        club="TCN", status="finisher", rank_overall=1,
    )
    db_session.commit()

    resp = client.get("/api/v1/club/last-outing?federal_only=true")

    assert resp.status_code == 200
    assert resp.json() == {"end_date": "2026-10-11", "events": 1, "athletes": 1, "podiums": 1}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_api/test_club_api.py -k last_outing -n 0 -q`
Expected: FAIL with 404.

- [ ] **Step 3: Implement**

`schemas/club.py` (add `from datetime import date as Date` at the top):

```python
class ClubLastOuting(BaseModel):
    """Dernière sortie du club : la course la plus récente et sa veille (#1619)."""

    end_date: Date
    events: int
    athletes: int
    podiums: int
```

`api/v1/club.py`: import `ClubLastOuting` and `stats_service` (`from app.services import club_service, stats_service`), then:

```python
@router.get("/club/last-outing", response_model=ClubLastOuting | None)
def get_club_last_outing(
    federal_only: bool = Query(
        False,
        description="Exclut les disciplines hors fédération triathlon (trail, course à pied, cyclisme).",
    ),
    db: Session = Depends(get_db),
):
    """Dernière sortie du club dans la saison en cours, `null` sans course TCN (#1619)."""
    return stats_service.get_last_outing(db, federal_only=federal_only)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_api/test_club_api.py -n 0 -q`, then `uv run pytest -m "not integration" -q`, `uv run ruff check .`
Expected: PASS.

- [ ] **Step 5: Commit and open the #1619 PR**

```bash
git add backend/app/schemas/club.py backend/app/api/v1/club.py backend/tests/test_api/test_club_api.py
git commit -m "feat(club): expose the club's last outing (#1619)"
```

PR into `epic/1618-accueil-carrefour`, body `Refs #1618` / `Closes #1619`.

### Task 3: Move the personal dashboard to `/mon-espace` (#1620)

**Files:**
- Move: `frontend/app/(public_restricted)/dashboard/{page,page.test,loading,loading.test}.tsx` → `frontend/app/(public_restricted)/mon-espace/`
- Modify: `frontend/next.config.ts:55-58`, `frontend/components/layout/nav.config.ts:144,178`, `frontend/components/layout/AppNav.tsx:213-218,280-305,452`, `frontend/app/not-found.tsx:39`, `frontend/components/admin/NoAdminAccess.tsx:19`, and every test or comment listed by the grep below
- Test: `frontend/app/(public_restricted)/mon-espace/page.test.tsx`, `frontend/components/layout/nav.config.test.ts`, `frontend/components/layout/AppNav.test.tsx`

**Interfaces:**
- Produces: route `/mon-espace`; nav item `{ id: "accueil", href: "/" }` and `{ id: "monespace", href: "/mon-espace" }`; `SPACES.public.home === "/"`

- [ ] **Step 1: Move the files with git** (from repo root)

```bash
git mv "frontend/app/(public_restricted)/dashboard" "frontend/app/(public_restricted)/mon-espace"
```

- [ ] **Step 2: Update the tests first (failing)**

In `mon-espace/page.test.tsx`: rename the `describe` to `MonEspacePage`, replace every `/dashboard` with `/mon-espace`, and add:

```tsx
it("drops the « Le club » card, the home page now leads to the club (#1620)", async () => {
  await renderPage();
  expect(screen.queryByRole("heading", { name: "Le club" })).not.toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
});
```

(use the file's existing render helper name in place of `renderPage`).

In `nav.config.test.ts`, add:

```ts
it("leads home to / and adds Mon espace to the public space (#1620)", () => {
  const items = NAV.flatMap((s) => s.items);
  expect(items.find((i) => i.id === "accueil")).toMatchObject({ label: "Accueil", href: "/", bottomBar: true });
  expect(items.find((i) => i.id === "monespace")).toMatchObject({ label: "Mon espace", href: "/mon-espace" });
  expect(items.some((i) => i.href === "/dashboard")).toBe(false);
  expect(SPACES.public.home).toBe("/");
});
```

Then, from `frontend/`, list the remaining references: `grep -rn '/dashboard' app components lib test next.config.ts`. For each **test** expectation, apply the mapping: a link that means « accueil » (logo, `not-found`, `NoAdminAccess`, `ErrorScreen`, `providers` redirection for a session without power, bottom bar « Accueil ») expects `/`; a link that means the personal season (`SeasonEmptyState` « voir la saison en cours » on the personal page) expects `/mon-espace`. Imports from `@/components/dashboard/...` are a folder name and stay. `app/routes-garde-site.test.ts:46` lists the route folders guarded by the site password: replace `"dashboard"` with `"mon-espace"`. The guide's `id: "dashboard"` (`components/guide/`) is a guide section id, not a route: leave it.

Run: `npx vitest run app components lib`
Expected: the updated tests FAIL.

- [ ] **Step 3: Implement**

`mon-espace/page.tsx`:
- `export const metadata: Metadata = { title: "Mon espace" };`
- `voirSaisonEnCoursHref`: return `qs ? \`/mon-espace?${qs}\` : "/mon-espace"`.
- Delete the `<Card className="mt-4">…Le club…</Card>` block, then the now unused `isCurrentSeasonSelected`, `clubHref`, `Link` and `Card` imports.

`nav.config.ts`:

```ts
public: { label: "Consulter", icon: LayoutGrid, home: "/" },
```

```ts
{ id: "accueil", label: "Accueil", href: "/", icon: LayoutGrid, bottomBar: true },
{ id: "monespace", label: "Mon espace", href: "/mon-espace", icon: UserRound },
```

(import `UserRound` from `lucide-react` with the other icons).

`AppNav.tsx`: `isActive` becomes `return pathname === href;` and its comment line about `/dashboard` is removed; the three logo links `href="/dashboard"` become `href="/"`; the `prefetch={false}` comment says « vers `/` ».

`next.config.ts`: until the home page exists (Task 7), keep `/` reachable:

```ts
async redirects() {
  // Provisoire (#1620) : l'accueil carrefour (#1621) remplacera cette redirection.
  return [{ source: "/", destination: "/mon-espace", permanent: false }];
},
```

`not-found.tsx`, `NoAdminAccess.tsx`: `href="/"`, link text unchanged if it says « accueil », otherwise « Retour à l'accueil ».

Comments mentioning `/dashboard` (`StatCard`, `ErrorScreen`, `RecentCourses`, `SeasonSelector`, `RankTypeToggle`, `InvitationAthlete`, `ClubDashboard`, `server.ts`, `providers.tsx`, `club/athletes/page.tsx`): replace `/dashboard` with `/mon-espace`, or with `/` where the comment is about the home page. Docs: `grep -rn '/dashboard' ../docs/frontend` and apply the same mapping.

- [ ] **Step 4: Verify**

Run (from `frontend/`): `npx vitest run`, `npm run lint`, `npx tsc --noEmit -p .`, and `grep -rn '/dashboard' app components lib test next.config.ts ../docs/frontend`
Expected: tests and lint PASS; the grep prints nothing.

- [ ] **Step 5: Commit and open the #1620 PR**

```bash
git add -A frontend docs/frontend
git commit -m "feat(nav): move the personal dashboard to /mon-espace (#1620)"
```

PR into the epic branch, `Refs #1618` / `Closes #1620`.

### Task 4: Home data layer (#1621)

**Files:**
- Modify: `frontend/lib/types.ts`, `frontend/lib/api/server.ts`, `frontend/lib/queries/nav-badges.ts`, `frontend/components/layout/AppNav.tsx:169-172`
- Create: `frontend/lib/home.ts`
- Test: `frontend/lib/home.test.ts`, `frontend/lib/queries/nav-badges.test.ts` (create if absent)

**Interfaces:**
- Produces: `type ClubLastOuting = { end_date: string; events: number; athletes: number; podiums: number }`
- Produces: `apiServer.getClubLastOuting(opts: { federal_only?: boolean }, fetchOpts?: FetchOpts): Promise<ClubLastOuting | null>`
- Produces: `titreSortie(endDate: string, today: Date): string` → `"Ce week-end"` or `"Dernière sortie · 6 sept."`
- Produces: `moisDeSaison(byMonth: Record<string, number>, season: number): { mois: string; libelle: string; valeur: number }[]` (12 mois, septembre à août)
- Produces: `totalATraiter(items: { group?: string; count?: number }[]): number | undefined`

- [ ] **Step 1: Write the failing tests**

`lib/home.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { moisDeSaison, titreSortie } from "./home";

describe("titreSortie", () => {
  it("says « Ce week-end » within 7 days", () => {
    expect(titreSortie("2026-10-11", new Date("2026-10-15T12:00:00"))).toBe("Ce week-end");
    expect(titreSortie("2026-10-11", new Date("2026-10-17T23:00:00"))).toBe("Ce week-end");
  });

  it("dates an older outing", () => {
    expect(titreSortie("2026-09-06", new Date("2026-10-15T12:00:00"))).toBe("Dernière sortie · 6 sept.");
  });
});

describe("moisDeSaison", () => {
  it("lays the twelve season months out from September, zero when empty", () => {
    const mois = moisDeSaison({ "2026-09": 40, "2026-11": 5, "2025-12": 99 }, 2026);
    expect(mois).toHaveLength(12);
    expect(mois[0]).toEqual({ mois: "2026-09", libelle: "sept.", valeur: 40 });
    expect(mois[1].valeur).toBe(0);
    expect(mois[2].valeur).toBe(5);
    expect(mois[11].mois).toBe("2027-08");
  });
});
```

`lib/queries/nav-badges.test.ts` (add the case):

```ts
import { TO_HANDLE } from "@/components/layout/nav.config";
import { totalATraiter } from "./nav-badges";

it("sums the « À traiter » counts, undefined when none is known", () => {
  expect(totalATraiter([{ group: TO_HANDLE, count: 3 }, { group: TO_HANDLE, count: 4 }, { group: "Autre", count: 9 }])).toBe(7);
  expect(totalATraiter([{ group: TO_HANDLE }])).toBeUndefined();
});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `npx vitest run lib/home.test.ts lib/queries/nav-badges.test.ts`
Expected: FAIL (module/function not found).

- [ ] **Step 3: Implement**

`lib/types.ts`:

```ts
/** Dernière sortie du club (#1619) : `null` côté API quand la saison n'a aucune course TCN. */
export interface ClubLastOuting {
  end_date: string;
  events: number;
  athletes: number;
  podiums: number;
}
```

`lib/api/server.ts`, next to `getClubBestTimes` (import the type):

```ts
  /** Dernière sortie du club dans la saison en cours (#1619), `null` sans course TCN. */
  getClubLastOuting: (opts: { federal_only?: boolean } = {}, fetchOpts: FetchOpts = {}) =>
    serverFetch<ClubLastOuting | null>(`/club/last-outing${toQuery(opts)}`, fetchOpts),
```

`lib/home.ts`:

```ts
const MOIS_COURTS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];

/** « Ce week-end » jusqu'à 7 jours après la dernière course, sinon sa date. */
export function titreSortie(endDate: string, today: Date): string {
  const [annee, mois, jour] = endDate.split("-").map(Number);
  const fin = new Date(annee, mois - 1, jour);
  const jours = Math.floor((today.getTime() - fin.getTime()) / 86_400_000);
  return jours < 7 ? "Ce week-end" : `Dernière sortie · ${jour} ${MOIS_COURTS[mois - 1]}`;
}

/** Les douze mois de la saison `season` (septembre à août), à zéro quand vides. */
export function moisDeSaison(byMonth: Record<string, number>, season: number) {
  return Array.from({ length: 12 }, (_, i) => {
    const annee = season + Math.floor((8 + i) / 12);
    const index = (8 + i) % 12;
    const mois = `${annee}-${String(index + 1).padStart(2, "0")}`;
    return { mois, libelle: MOIS_COURTS[index], valeur: byMonth[mois] ?? 0 };
  });
}
```

`lib/queries/nav-badges.ts` (import `TO_HANDLE` from `@/components/layout/nav.config`):

```ts
/** Total « À traiter » du back-office : la pastille du sommaire et de sa tuile d'accueil. */
export function totalATraiter(items: { group?: string; count?: number }[]): number | undefined {
  const connus = items.filter((i) => i.group === TO_HANDLE && i.count !== undefined);
  return connus.length > 0 ? connus.reduce((somme, i) => somme + (i.count ?? 0), 0) : undefined;
}
```

`AppNav.tsx` lines 169-172 become:

```ts
const countAdmin = totalATraiter(toutesSections.flatMap((s) => s.items));
```

(import `totalATraiter`; remove `compteurAdmin`). If `nav-badges.ts` importing `nav.config.ts` creates a cycle, move `TO_HANDLE` import usage by passing the group name instead: `totalATraiter(items, TO_HANDLE)`.

- [ ] **Step 4: Run the tests**

Run: `npx vitest run lib components/layout`
Expected: PASS (AppNav tests unchanged).

- [ ] **Step 5: Commit**

```bash
git add frontend/lib frontend/components/layout/AppNav.tsx
git commit -m "feat(home): add the last outing client call and the home page helpers (#1621)"
```

### Task 5: The « direct » banner (#1621)

**Files:**
- Create: `frontend/components/home/ChiffreAnime.tsx`, `frontend/components/home/BandeauDirect.tsx`
- Test: `frontend/components/home/ChiffreAnime.test.tsx`, `frontend/components/home/BandeauDirect.test.tsx`

**Interfaces:**
- Consumes: `ClubLastOuting`, `titreSortie`, `moisDeSaison` (Task 4), `CLUB_NAME`, `CLUB_NAME_SHORT` (`lib/club.ts`), `seasonLabel` (`lib/utils/season.ts`), `formatCount`, `motCompte`, `plural` (`lib/utils/format.ts`)
- Produces: `<ChiffreAnime valeur={number} />` (client) ; `<BandeauDirect sortie={ClubLastOuting | null} stats={Stats} season={number} today={Date} />` (server-safe, no hook)

- [ ] **Step 1: Write the failing tests**

`ChiffreAnime.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChiffreAnime } from "./ChiffreAnime";

function reducedMotion(matches: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({ matches, media: query, addEventListener() {}, removeEventListener() {} }));
}

describe("ChiffreAnime", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders the final value straight away under reduced motion", () => {
    reducedMotion(true);
    render(<ChiffreAnime valeur={1234} />);
    expect(screen.getByText("1 234")).toBeInTheDocument();
  });

  it("exposes the final value to assistive tech while it animates", () => {
    reducedMotion(false);
    render(<ChiffreAnime valeur={48} />);
    expect(screen.getByText("48", { selector: ".sr-only" })).toBeInTheDocument();
  });
});
```

`BandeauDirect.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Stats } from "@/lib/types";
import { BandeauDirect } from "./BandeauDirect";

vi.stubGlobal("matchMedia", (query: string) => ({ matches: true, media: query, addEventListener() {}, removeEventListener() {} }));

const bucket = { victories: 0, podiums: 0, top10: 0 };
const STATS: Stats = {
  total: 312, athletes: 87, events: 14, by_type: {}, recent: [],
  by_month: { "2026-09": 120, "2026-10": 192 },
  rank_counters: { scratch: bucket, category: bucket, all: { ...bucket, podiums: 27 }, gender: { women: bucket, men: bucket } },
};
const TODAY = new Date("2026-10-15T12:00:00");

describe("BandeauDirect", () => {
  it("shows a recent outing as « Ce week-end » with its figures", () => {
    render(<BandeauDirect sortie={{ end_date: "2026-10-11", events: 3, athletes: 48, podiums: 9 }} stats={STATS} season={2026} today={TODAY} />);
    expect(screen.getByText("Ce week-end")).toBeInTheDocument();
    expect(screen.getByText("48 TCN")).toBeInTheDocument();
    expect(screen.getByText(/3 épreuves · 9 podiums/)).toBeInTheDocument();
  });

  it("dates an older outing", () => {
    render(<BandeauDirect sortie={{ end_date: "2026-09-06", events: 1, athletes: 5, podiums: 0 }} stats={STATS} season={2026} today={TODAY} />);
    expect(screen.getByText("Dernière sortie · 6 sept.")).toBeInTheDocument();
  });

  it("falls back when the season has no outing yet, season figures stay", () => {
    render(<BandeauDirect sortie={null} stats={STATS} season={2026} today={TODAY} />);
    expect(screen.getByText("Pas encore de course cette saison")).toBeInTheDocument();
    expect(screen.getByText("312")).toBeInTheDocument();
    expect(screen.getByText("27")).toBeInTheDocument();
  });

  it("summarises the monthly chart for screen readers", () => {
    render(<BandeauDirect sortie={null} stats={STATS} season={2026} today={TODAY} />);
    expect(screen.getByRole("img", { name: /Résultats par mois.*sept\. : 120.*oct\. : 192/ })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `npx vitest run components/home`
Expected: FAIL (modules not found).

- [ ] **Step 3: Implement `ChiffreAnime.tsx`**

```tsx
"use client";
import { useEffect, useState } from "react";
import { formatCount } from "@/lib/utils/format";

const DUREE_MS = 900;

/** Monte de 0 à `valeur` au premier affichage ; valeur finale directe sous `prefers-reduced-motion`. */
export function ChiffreAnime({ valeur }: { valeur: number }) {
  const [affiche, setAffiche] = useState(valeur);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || valeur === 0) return;
    const debut = performance.now();
    let frame = requestAnimationFrame(function pas(maintenant) {
      const t = Math.min(1, (maintenant - debut) / DUREE_MS);
      setAffiche(Math.round(valeur * (1 - (1 - t) ** 3)));
      if (t < 1) frame = requestAnimationFrame(pas);
    });
    setAffiche(0);
    return () => cancelAnimationFrame(frame);
  }, [valeur]);

  if (affiche === valeur) return <>{formatCount(valeur)}</>;
  return (
    <>
      <span aria-hidden="true">{formatCount(affiche)}</span>
      <span className="sr-only">{formatCount(valeur)}</span>
    </>
  );
}
```

Check that `formatCount(1234)` renders `"1 234"` with the narrow no-break space used by the codebase; if it uses ` `, write the test expectation with that character.

- [ ] **Step 4: Implement `BandeauDirect.tsx`**

```tsx
import { CLUB_NAME, CLUB_NAME_SHORT } from "@/lib/club";
import { moisDeSaison, titreSortie } from "@/lib/home";
import type { ClubLastOuting, Stats } from "@/lib/types";
import { formatCount, motCompte } from "@/lib/utils/format";
import { seasonLabel } from "@/lib/utils/season";
import { ChiffreAnime } from "./ChiffreAnime";

const display = { fontFamily: "var(--tcn-font-display)", fontWeight: 400, lineHeight: 1 } as const;

function Chiffre({ valeur, libelle }: { valeur: number; libelle: string }) {
  return (
    <div>
      <div style={{ ...display, fontSize: 28 }}>{formatCount(valeur)}</div>
      <div style={{ fontSize: 13, fontWeight: 700 }}>{libelle}</div>
    </div>
  );
}

function Histogramme({ stats, season }: { stats: Stats; season: number }) {
  const mois = moisDeSaison(stats.by_month, season);
  const max = Math.max(1, ...mois.map((m) => m.valeur));
  const resume = mois.filter((m) => m.valeur > 0).map((m) => `${m.libelle} : ${m.valeur}`).join(", ");
  return (
    <figure role="img" aria-label={`Résultats par mois. ${resume || "Aucun pour l'instant"}.`} style={{ margin: 0 }}>
      <div aria-hidden="true" style={{ display: "flex", alignItems: "flex-end", gap: 4, height: 72 }}>
        {mois.map((m) => (
          <span key={m.mois} style={{ flex: 1, height: `${Math.max(4, (m.valeur / max) * 100)}%`, borderRadius: 3, background: m.valeur ? "rgba(255,255,255,.9)" : "rgba(255,255,255,.25)" }} />
        ))}
      </div>
      <figcaption aria-hidden="true" style={{ fontSize: 12, fontWeight: 700, marginTop: 6 }}>Résultats par mois</figcaption>
    </figure>
  );
}

/** Le pouls du club en tête d'accueil (#1621) : dernière sortie, saison, mois. */
export function BandeauDirect({ sortie, stats, season, today }: { sortie: ClubLastOuting | null; stats: Stats; season: number; today: Date }) {
  return (
    <section
      aria-labelledby="bandeau-direct-titre"
      style={{ background: "var(--tcn-orange-grad)", color: "#fff", borderRadius: "var(--tcn-radius-xl)", padding: "24px clamp(18px, 4vw, 32px)", boxShadow: "var(--tcn-shadow-orange-lg)" }}
    >
      <h1 id="bandeau-direct-titre" style={{ margin: 0, fontSize: 12, fontWeight: 800, letterSpacing: ".06em", textTransform: "uppercase" }}>
        {CLUB_NAME} · {seasonLabel(season)}
      </h1>
      <div className="mt-4 grid gap-6 md:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] md:items-end">
        <div>
          {sortie ? (
            <>
              <p style={{ margin: 0, fontWeight: 800 }}>{titreSortie(sortie.end_date, today)}</p>
              <p style={{ ...display, margin: "6px 0 0", fontSize: "clamp(40px, 9vw, 64px)" }}>
                <ChiffreAnime valeur={sortie.athletes} /> {CLUB_NAME_SHORT}
              </p>
              <p style={{ margin: "6px 0 0", fontWeight: 700 }}>
                {motCompte(sortie.events, "épreuve")} · {motCompte(sortie.podiums, "podium")}
              </p>
            </>
          ) : (
            <p style={{ ...display, margin: 0, fontSize: 28 }}>Pas encore de course cette saison</p>
          )}
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap", marginTop: 20 }}>
            <Chiffre valeur={stats.total} libelle="résultats" />
            <Chiffre valeur={stats.athletes} libelle="athlètes" />
            <Chiffre valeur={stats.rank_counters.all.podiums} libelle="podiums" />
          </div>
        </div>
        <Histogramme stats={stats} season={season} />
      </div>
    </section>
  );
}
```

Verify the white text on `--tcn-orange-grad` keeps 4.5:1 for the 12-13 px labels (the gradient was darkened for white text, #299; if a token measurement says otherwise, raise the labels to 14 px bold, which counts as large text at 3:1 only from 18.66 px, so prefer checking `--tcn-orange-grad` stops in `globals.css` and stating the ratio in the PR).

`seasonLabel` returns « Saison 2026 — 2027 »: if the eyebrow reads oddly as « Triathlon Club Nantais · Saison 2026 — 2027 », keep it; do not add a new formatter.

- [ ] **Step 5: Run the tests**

Run: `npx vitest run components/home`, `npm run lint`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/home
git commit -m "feat(home): add the club's live banner (#1621)"
```

### Task 6: Space tiles (#1621)

**Files:**
- Create: `frontend/components/home/TuilesEspaces.tsx`
- Test: `frontend/components/home/TuilesEspaces.test.tsx`

**Interfaces:**
- Consumes: `useSession` (`lib/queries/auth`), `useNavBadges`, `totalATraiter`, `libelleCompteur` (`lib/queries/nav-badges`), `NAV`, `estVisible`, `ROLE` (`components/layout/nav.config`), `useSelectedAthlete`, `nomComplet` (`components/layout/AthletePicker`), `Card` (`components/tcn`)
- Produces: `<TuilesEspaces derniereEpreuve={{ nom: string; date: string | null } | null} podiumsSaison={number} />`

- [ ] **Step 1: Write the failing tests**

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SessionUser } from "@/lib/types";

const { getSession, getAdminBadgeCounts } = vi.hoisted(() => ({ getSession: vi.fn(), getAdminBadgeCounts: vi.fn() }));
vi.mock("@/lib/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/client")>()),
  apiClient: { getSession, getAdminBadgeCounts },
}));
const athlete = vi.hoisted(() => ({ current: null as null | { id: number; prenom: string; nom: string } }));
vi.mock("@/components/layout/AthletePicker", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/components/layout/AthletePicker")>()),
  useSelectedAthlete: () => athlete.current,
}));

import { TuilesEspaces } from "./TuilesEspaces";

const BASE: SessionUser = {
  id: 1, email: "moi@exemple.fr", display_name: "Moi", created_at: "2026-01-01T00:00:00Z",
  permissions: [], roles: [], groups: [], can_administer: false, can_supervise: false,
};

function afficher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <TuilesEspaces derniereEpreuve={{ nom: "Tri de Saint-Gilles M", date: "2026-10-11" }} podiumsSaison={27} />
    </QueryClientProvider>,
  );
}

describe("TuilesEspaces", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    athlete.current = null;
    getAdminBadgeCounts.mockResolvedValue({});
  });

  it("links every visitor to Résultats, Club and Mon espace, with their fresh line", async () => {
    getSession.mockResolvedValue(null);
    afficher();
    expect(screen.getByRole("link", { name: /Résultats.*Tri de Saint-Gilles M/ })).toHaveAttribute("href", "/resultats");
    expect(screen.getByRole("link", { name: /Club.*27 podiums/ })).toHaveAttribute("href", "/club");
    expect(screen.getByRole("link", { name: /Mon espace.*Choisissez votre nom/ })).toHaveAttribute("href", "/mon-espace");
  });

  it("names the selected athlete on the Mon espace tile", () => {
    getSession.mockResolvedValue(null);
    athlete.current = { id: 7, prenom: "Léa", nom: "Écuyer" };
    afficher();
    expect(screen.getByRole("link", { name: /Mon espace.*Léa Écuyer/ })).toBeInTheDocument();
  });

  it("shows no reserved tile without power, nor while the session is read", async () => {
    getSession.mockReturnValue(new Promise(() => {}));
    afficher();
    expect(screen.queryByRole("link", { name: /Encadrement|Back-office/ })).not.toBeInTheDocument();
  });

  it("adds Encadrement and Back-office with its « à traiter » badge for those who hold them", async () => {
    getSession.mockResolvedValue({ ...BASE, can_supervise: true, can_administer: true, permissions: ["quality:override"] });
    getAdminBadgeCounts.mockResolvedValue({ qualite: 4 });
    afficher();
    expect(await screen.findByRole("link", { name: /Encadrement/ })).toHaveAttribute("href", "/encadrement");
    expect(await screen.findByRole("link", { name: /Back-office/ })).toHaveAttribute("href", "/admin");
  });
});
```

Before running, open `lib/queries/admin.ts` (or wherever `useAdminBadgeCounts` lives) and use the exact `apiClient` method name and the badge keys it returns; adjust `getAdminBadgeCounts` and `{ qualite: 4 }` accordingly, and assert the badge text `4` inside the Back-office link once the key is right.

- [ ] **Step 2: Run them to verify they fail**

Run: `npx vitest run components/home/TuilesEspaces.test.tsx`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `TuilesEspaces.tsx`**

```tsx
"use client";
import Link from "next/link";
import type { ReactNode } from "react";
import { Card } from "@/components/tcn";
import { nomComplet, useSelectedAthlete } from "@/components/layout/AthletePicker";
import { NAV, ROLE, estVisible } from "@/components/layout/nav.config";
import { useSession } from "@/lib/queries/auth";
import { libelleCompteur, totalATraiter, useNavBadges } from "@/lib/queries/nav-badges";
import { formatDate } from "@/lib/utils/date";
import { motCompte } from "@/lib/utils/format";

function Tuile({ href, titre, ligne, badge }: { href: string; titre: string; ligne?: ReactNode; badge?: ReactNode }) {
  return (
    <Link href={href} className="tcn-tuile-espace block rounded-[var(--tcn-radius-xl)]">
      <Card style={{ height: "100%" }}>
        <div className="flex items-center justify-between gap-2">
          <span style={{ fontFamily: "var(--tcn-font-display)", fontSize: 22, color: "var(--tcn-ink)" }}>{titre}</span>
          <span aria-hidden="true" className="text-accent-ink" style={{ fontWeight: 800 }}>→</span>
        </div>
        {(ligne || badge) && (
          <div className="mt-1 flex items-center gap-2" style={{ fontSize: 14, color: "var(--tcn-text-muted)" }}>
            {badge}
            {ligne}
          </div>
        )}
      </Card>
    </Link>
  );
}

/** Les portes de l'accueil (#1621) ; les espaces réservés n'apparaissent qu'une fois la session lue. */
export function TuilesEspaces({ derniereEpreuve, podiumsSaison }: { derniereEpreuve: { nom: string; date: string | null } | null; podiumsSaison: number }) {
  const { data: session } = useSession();
  const athlete = useSelectedAthlete();
  const { counts } = useNavBadges(Boolean(session?.can_administer));
  const pouvoirs = new Set(session?.permissions ?? []);
  const aTraiter = session?.can_administer
    ? totalATraiter(
        NAV.flatMap((s) => s.items)
          .filter((i) => estVisible(i, pouvoirs, ROLE.CONNECTED))
          .map((i) => (i.badge ? { ...i, count: counts[i.badge] } : i)),
      )
    : undefined;

  return (
    <nav aria-label="Espaces" className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <Tuile
        href="/resultats"
        titre="Résultats"
        ligne={derniereEpreuve ? `${derniereEpreuve.nom}${derniereEpreuve.date ? ` · ${formatDate(derniereEpreuve.date)}` : ""}` : "Toutes les épreuves du club"}
      />
      <Tuile href="/club" titre="Club" ligne={`${motCompte(podiumsSaison, "podium")} cette saison`} />
      <Tuile href="/mon-espace" titre="Mon espace" ligne={athlete ? nomComplet(athlete) : "Choisissez votre nom"} />
      {session?.can_supervise && <Tuile href="/encadrement" titre="Encadrement" ligne="Jeunes, appel, bénévolat" />}
      {session?.can_administer && (
        <Tuile
          href="/admin"
          titre="Back-office"
          badge={aTraiter ? <span aria-label={libelleCompteur("backoffice", aTraiter)} className="rounded-full px-2 text-xs font-extrabold text-white" style={{ background: "var(--tcn-orange-deeper)" }}>{aTraiter}</span> : undefined}
          ligne="À traiter, données, paramétrage"
        />
      )}
    </nav>
  );
}
```

Add to `app/globals.css`, next to `.tcn-cible-tactile`:

```css
/* Tuile d'espace de l'accueil (#1621) : survol visible sur --tcn-fill, focus opaque. */
.tcn-tuile-espace { min-height: 44px; transition: transform var(--tcn-dur-fast); }
.tcn-tuile-espace:hover { transform: translateY(-2px); }
.tcn-tuile-espace:hover > * { background: var(--tcn-orange-08); }
.tcn-tuile-espace:focus-visible { outline: 2px solid var(--tcn-orange); outline-offset: 2px; }
@media (prefers-reduced-motion: reduce) { .tcn-tuile-espace:hover { transform: none; } }
```

Check `nomComplet`'s real signature in `AthletePicker.tsx` and the `PickedAthlete` field names before writing the test fixture; adapt `athlete.current` to them.

- [ ] **Step 4: Run the tests**

Run: `npx vitest run components/home`, `npm run lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/home/TuilesEspaces.tsx frontend/components/home/TuilesEspaces.test.tsx frontend/app/globals.css
git commit -m "feat(home): add the space tiles (#1621)"
```

### Task 7: The home page at `/` (#1621)

**Files:**
- Create: `frontend/app/(public_restricted)/page.tsx`, `frontend/app/(public_restricted)/page.test.tsx`
- Modify: `frontend/next.config.ts` (remove the provisional redirect), `frontend/app/page-titles.test.tsx` (title of `/`), `frontend/components/layout/AppNav.test.tsx` if it asserted the redirect

**Interfaces:**
- Consumes: `apiServer.getStats`, `apiServer.listEvents`, `apiServer.getClubLastOuting`, `SHORT_REVALIDATE_SECONDS`, `SCOPE_CLUB`, `federalOnlyFromParam`, `currentSeason`, `BandeauDirect`, `TuilesEspaces`, `PageShell`

- [ ] **Step 1: Write the failing test**

`app/(public_restricted)/page.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Stats } from "@/lib/types";

const getStats = vi.fn();
const listEvents = vi.fn();
const getClubLastOuting = vi.fn();
vi.mock("@/lib/api/server", () => ({
  apiServer: {
    getStats: (o: unknown, f?: unknown) => getStats(o, f),
    listEvents: (o: unknown, f?: unknown) => listEvents(o, f),
    getClubLastOuting: (o: unknown, f?: unknown) => getClubLastOuting(o, f),
  },
  SHORT_REVALIDATE_SECONDS: 30,
}));
vi.mock("@/components/home/TuilesEspaces", () => ({ TuilesEspaces: () => <nav aria-label="Espaces" /> }));
vi.stubGlobal("matchMedia", (q: string) => ({ matches: true, media: q, addEventListener() {}, removeEventListener() {} }));

import HomePage from "./page";

const bucket = { victories: 0, podiums: 0, top10: 0 };
const STATS: Stats = { total: 312, athletes: 87, events: 14, by_type: {}, by_month: {}, recent: [], rank_counters: { scratch: bucket, category: bucket, all: bucket, gender: { women: bucket, men: bucket } } };

async function afficher(sp: Record<string, string> = {}) {
  const ui = await HomePage({ searchParams: Promise.resolve(sp) });
  return render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>);
}

describe("HomePage", () => {
  it("renders the live banner and the space tiles from the club's season", async () => {
    getStats.mockResolvedValue(STATS);
    listEvents.mockResolvedValue({ items: [], total_events: 0, total_participations: 0 });
    getClubLastOuting.mockResolvedValue(null);

    await afficher();

    expect(screen.getByRole("heading", { level: 1, name: /Triathlon Club Nantais/ })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Espaces" })).toBeInTheDocument();
    expect(getStats).toHaveBeenCalledWith(expect.objectContaining({ scope: "club", federal_only: false }), { revalidateSeconds: 30 });
    expect(getClubLastOuting).toHaveBeenCalledWith({ federal_only: false }, { revalidateSeconds: 30 });
  });

  it("keeps the season figures when the last outing call fails", async () => {
    getStats.mockResolvedValue(STATS);
    listEvents.mockResolvedValue({ items: [], total_events: 0, total_participations: 0 });
    getClubLastOuting.mockRejectedValue(new Error("down"));

    await afficher();

    expect(screen.getByText("Pas encore de course cette saison")).toBeInTheDocument();
    expect(screen.getByText("312")).toBeInTheDocument();
  });
});
```

Check `SCOPE_CLUB`'s value in `lib/scope.ts` and use it in the `objectContaining` if it is not `"club"`.

- [ ] **Step 2: Run it to verify it fails**

Run: `npx vitest run "app/(public_restricted)/page.test.tsx"`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement the page**

```tsx
import type { Metadata } from "next";
import { BandeauDirect } from "@/components/home/BandeauDirect";
import { TuilesEspaces } from "@/components/home/TuilesEspaces";
import { PageShell } from "@/components/layout/PageShell";
import { apiServer, SHORT_REVALIDATE_SECONDS } from "@/lib/api/server";
import { SCOPE_CLUB, federalOnlyFromParam } from "@/lib/scope";
import { sortEventsByDateDesc } from "@/lib/utils/event";
import { currentSeason } from "@/lib/utils/season";

export const metadata: Metadata = { title: "Accueil" };

export default async function HomePage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const sp = await searchParams;
  const federal_only = federalOnlyFromParam(sp.sports);
  const season = currentSeason();
  const revalidateOpts = { revalidateSeconds: SHORT_REVALIDATE_SECONDS };

  const [stats, eventsPage, sortie] = await Promise.all([
    apiServer.getStats({ scope: SCOPE_CLUB, seasons: [season], federal_only }, revalidateOpts),
    apiServer.listEvents({ scope: SCOPE_CLUB, federal_only, page_size: 1 }, revalidateOpts),
    // Décor de l'accueil : sa panne ne doit pas emporter la page.
    apiServer.getClubLastOuting({ federal_only }, revalidateOpts).catch(() => null),
  ]);
  const derniere = sortEventsByDateDesc(eventsPage.items)[0];

  return (
    <PageShell>
      <BandeauDirect sortie={sortie} stats={stats} season={season} today={new Date()} />
      <TuilesEspaces
        derniereEpreuve={derniere ? { nom: derniere.event_name, date: derniere.event_date } : null}
        podiumsSaison={stats.rank_counters.all.podiums}
      />
    </PageShell>
  );
}
```

`new Date()` in a cached server render is the render time, refreshed every `SHORT_REVALIDATE_SECONDS`: enough for a 7-day threshold.

`next.config.ts`: delete the `redirects()` entry for `/` (remove `redirects()` entirely if it becomes empty) and its comment.

`app/page-titles.test.tsx`: add `/` → « Accueil » following the file's pattern.

- [ ] **Step 4: Verify**

Run: `npx vitest run`, `npm run lint`, `npx tsc --noEmit -p .`, `npm run build`
Expected: PASS; the build lists `/` and `/mon-espace`, not `/dashboard`.

- [ ] **Step 5: Commit and open the #1621 PR**

```bash
git add -A frontend
git commit -m "feat(home): turn / into a hub with the club's live banner and space tiles (#1621)"
```

PR into the epic branch, `Refs #1618` / `Closes #1621`.

### End of epic

- [ ] Code review (`requesting-code-review`), then `ui-ux-review` on the epic branch (user-triggered), fixes.
- [ ] Preview check at 360 px and desktop: `/`, `/mon-espace`, `/club`, navigation from each tile.
- [ ] PR `epic/1618-accueil-carrefour` → `main`, `Closes #1618`.
