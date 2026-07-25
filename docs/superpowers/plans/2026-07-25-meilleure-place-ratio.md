# Meilleure place en ratio — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sur la fiche athlète, rapporter chaque place au nombre de finishers classés de la course (« 42e / 300 — Top 14 % ») et ajouter une tuile « Meilleur ratio » à côté de « Meilleure place ».

**Architecture:** Le backend expose un compte de finishers classés par `(course_id, is_relay)` sur la **seule** route `GET /athletes/{id}`, via une requête d'agrégat bornée aux courses de l'athlète. Le front calcule le pourcentage, applique les replis et fait le rendu — aucune règle de présentation ne descend dans l'API.

**Tech Stack:** Backend Python 3.13 / FastAPI / SQLAlchemy 2.0 sync / pytest (lancé par `uv run`, depuis `backend/`). Front Next.js 16 App Router / TypeScript strict / Vitest + RTL (lancé par `npm`, depuis `frontend/`).

Spec : `docs/superpowers/specs/2026-07-25-meilleure-place-ratio-design.md`
Issue : [#80](https://github.com/Triathlon-Club-Nantais/data-triathlon/issues/80)

## Global Constraints

- Commentaires, libellés d'UI et messages en **français avec accents**.
- Commits en **Conventional Commits** (`feat:`, `fix:`, `test:`…), avec `(#80)` en fin de sujet.
- Tests unitaires **sans réseau**.
- `ParticipationOut` ne doit pas changer : aucune autre route que `GET /athletes/{id}` ne doit voir son payload modifié.
- Le champ front `Participation.course_finishers` est **optionnel** (`?:`) — sinon toutes les fixtures de test existantes (`ResultCard.test.tsx`, `raceOrder.test.ts`, `club-aggregate.test.ts`…) cessent de compiler.
- Population comptée, invariable dans tout le plan : `status == "finisher"` **et** `rank_overall IS NOT NULL`, groupée par `(course_id, is_relay)`.
- Replis d'affichage, invariables : pas de ratio si `rank_overall` absent, si le compte est absent, si `rank > total`, ou si `total < 2`.

## Structure des fichiers

| Fichier | Rôle |
| --- | --- |
| `backend/app/repositories/participation_repository.py` | + `finishers_count_by_group()` — seule couche qui touche la Session |
| `backend/app/schemas/participation.py` | + `AthleteParticipationOut` (sous-classe, `ParticipationOut` intact) |
| `backend/app/api/v1/athletes.py` | assemble compte + participations dans la réponse |
| `backend/tests/test_repositories/test_participation_repository.py` | tests de l'agrégat |
| `backend/tests/test_api/test_other_api.py` | test de la route enrichie |
| `frontend/lib/types.ts` | + `course_finishers?: number \| null` sur `Participation` |
| `frontend/lib/utils/ranking.ts` (créé) | `rankRatio()` / `bestRatio()` — logique pure du ratio |
| `frontend/lib/utils/ranking.test.ts` (créé) | tests de la logique pure |
| `frontend/lib/utils/format.ts` | + `ordinalFr()` — module de formatage existant |
| `frontend/lib/utils/format.test.ts` (créé) | tests de `ordinalFr` (le module n'a pas encore de test) |
| `frontend/components/tcn/StatCard.tsx` | + prop `hint` (variant `default`) |
| `frontend/components/tcn/StatCard.test.tsx` (créé) | tests du `hint` |
| `frontend/app/athletes/[id]/page.tsx` | tuile « Meilleur ratio » + colonne « Place » enrichie |
| `frontend/app/athletes/[id]/page.test.tsx` (créé) | test de page |

---

### Task 1: Agrégat des finishers classés (repository)

**Files:**
- Modify: `backend/app/repositories/participation_repository.py` (ajout après `count_for_course`, ligne 56)
- Test: `backend/tests/test_repositories/test_participation_repository.py`

**Interfaces:**
- Consumes: rien.
- Produces: `finishers_count_by_group(db: Session, course_ids: Iterable[int]) -> dict[tuple[int, bool], int]` — clé `(course_id, is_relay)`, valeur = nombre de finishers classés. Les clés sans finisher classé sont **absentes** du dictionnaire (pas de `0`).

Contexte : `STATUS_FINISHER = "finisher"` vit dans `app/scrapers/base.py` et est déjà importé par les services (`quality.py`, `mapping.py`). L'importer ici évite de dupliquer la chaîne — c'est une constante de domaine, pas un appel de couche.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à la fin de `backend/tests/test_repositories/test_participation_repository.py` :

```python
def test_finishers_count_by_group_separe_solos_et_relais(db_session):
    athlete, course = _setup(db_session)
    relayeur = athlete_repository.get_or_create(
        db_session, nom="MARTIN", prenom="Paul", club="TCN"
    )
    participation_repository.create(
        db_session,
        athlete_id=athlete.id,
        course_id=course.id,
        bib_number="1",
        status="finisher",
        rank_overall=1,
        is_relay=False,
    )
    participation_repository.create(
        db_session,
        athlete_id=relayeur.id,
        course_id=course.id,
        bib_number="2",
        status="finisher",
        rank_overall=1,
        is_relay=True,
    )
    db_session.flush()

    counts = participation_repository.finishers_count_by_group(db_session, [course.id])

    assert counts == {(course.id, False): 1, (course.id, True): 1}


def test_finishers_count_by_group_exclut_non_finishers_et_non_classes(db_session):
    athlete, course = _setup(db_session)
    abandon = athlete_repository.get_or_create(
        db_session, nom="MARTIN", prenom="Paul", club="TCN"
    )
    sans_rang = athlete_repository.get_or_create(
        db_session, nom="DURAND", prenom="Luc", club="TCN"
    )
    participation_repository.create(
        db_session,
        athlete_id=athlete.id,
        course_id=course.id,
        bib_number="1",
        status="finisher",
        rank_overall=1,
        is_relay=False,
    )
    participation_repository.create(
        db_session,
        athlete_id=abandon.id,
        course_id=course.id,
        bib_number="2",
        status="DNF",
        rank_overall=None,
        is_relay=False,
    )
    participation_repository.create(
        db_session,
        athlete_id=sans_rang.id,
        course_id=course.id,
        bib_number="3",
        status="finisher",
        rank_overall=None,
        is_relay=False,
    )
    db_session.flush()

    counts = participation_repository.finishers_count_by_group(db_session, [course.id])

    assert counts == {(course.id, False): 1}


def test_finishers_count_by_group_sans_finisher_classe_ne_produit_pas_de_cle(db_session):
    athlete, course = _setup(db_session)
    participation_repository.create(
        db_session,
        athlete_id=athlete.id,
        course_id=course.id,
        bib_number="1",
        status="DNS",
        rank_overall=None,
        is_relay=False,
    )
    db_session.flush()

    assert participation_repository.finishers_count_by_group(db_session, [course.id]) == {}


def test_finishers_count_by_group_sans_ids_ne_requete_pas(db_session):
    assert participation_repository.finishers_count_by_group(db_session, []) == {}
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Depuis `backend/` :
`uv run pytest tests/test_repositories/test_participation_repository.py -k finishers_count -v`
Attendu : 4 ERROR/FAIL avec `AttributeError: module 'app.repositories.participation_repository' has no attribute 'finishers_count_by_group'`.

- [ ] **Step 3: Implémenter l'agrégat**

Dans `backend/app/repositories/participation_repository.py`, ajouter `from collections.abc import Iterable` en tête des imports stdlib (avant `from datetime import date`) et `from app.scrapers.base import STATUS_FINISHER` avec les imports `app.` (après `from app.models.participation import Participation`), puis insérer après `count_for_course` :

```python
def finishers_count_by_group(
    db: Session, course_ids: Iterable[int]
) -> dict[tuple[int, bool], int]:
    """Nombre de finishers classés par (course, solo/relais).

    Seule population comparable à `rank_overall` : les DNF/DNS/DSQ n'ont pas de
    rang, et solos et relais sont classés séparément (deux « rang 1 » légitimes
    dans une même course, cf. `services/quality.py`). Un groupe sans finisher
    classé est absent du résultat — l'appelant distingue « zéro classé » de
    « compte inconnu ».
    """
    ids = list(dict.fromkeys(course_ids))
    if not ids:
        return {}
    rows = (
        db.query(
            Participation.course_id,
            Participation.is_relay,
            func.count(Participation.id),
        )
        .filter(
            Participation.course_id.in_(ids),
            func.lower(Participation.status) == STATUS_FINISHER,
            Participation.rank_overall.isnot(None),
        )
        .group_by(Participation.course_id, Participation.is_relay)
        .all()
    )
    return {(course_id, bool(is_relay)): count for course_id, is_relay, count in rows}
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

`uv run pytest tests/test_repositories/test_participation_repository.py -v` → tous PASS.
Puis `uv run ruff check .` → aucune erreur.

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/participation_repository.py backend/tests/test_repositories/test_participation_repository.py
git commit -m "feat(repo): compte les finishers classés par course et par groupe (#80)"
```

---

### Task 2: Exposer le compte sur `GET /athletes/{id}`

**Files:**
- Modify: `backend/app/schemas/participation.py` (après `ParticipationOut`, ligne 28)
- Modify: `backend/app/api/v1/athletes.py:25-34`
- Test: `backend/tests/test_api/test_other_api.py`

**Interfaces:**
- Consumes: `participation_repository.finishers_count_by_group(db, course_ids) -> dict[tuple[int, bool], int]` (Task 1).
- Produces: le JSON de `GET /api/v1/athletes/{id}` gagne `participations[].course_finishers: int | null`. `null` quand le groupe n'a aucun finisher classé.

- [ ] **Step 1: Écrire le test qui échoue**

Ajouter à la fin de `backend/tests/test_api/test_other_api.py` (le fichier construit ses données via `client.post`, on garde ce style) :

```python
def test_athlete_detail_expose_le_nombre_de_finishers_classes(client):
    client.post("/api/v1/participations", json={**_payload(bib="1"), "rank_overall": 1})
    client.post(
        "/api/v1/participations",
        json={**_payload(bib="2", nom="MARTIN"), "rank_overall": 2},
    )
    client.post(
        "/api/v1/participations",
        json={**_payload(bib="3", nom="DURAND"), "rank_overall": None},
    )

    athletes = client.get("/api/v1/athletes", params={"name": "dupont"}).json()
    detail = client.get(f"/api/v1/athletes/{athletes[0]['id']}").json()

    participation = detail["participations"][0]
    assert participation["rank_overall"] == 1
    # DURAND a un temps mais pas de rang : hors du classement.
    assert participation["course_finishers"] == 2
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

`uv run pytest tests/test_api/test_other_api.py -k finishers -v`
Attendu : FAIL avec `KeyError: 'course_finishers'`.

- [ ] **Step 3: Ajouter le schéma**

Dans `backend/app/schemas/participation.py`, après la classe `ParticipationOut` :

```python
class AthleteParticipationOut(ParticipationOut):
    """Participation vue depuis la fiche athlète : porte la taille du classement.

    `course_finishers` = nombre de finishers classés de la course, dans le même
    groupe solo/relais. `None` si le groupe n'a aucun classé. Champ réservé à la
    fiche athlète : le mettre sur `ParticipationOut` ferait payer l'agrégat aux
    routes de liste, qui n'en ont pas l'usage.
    """

    course_finishers: int | None = None
```

- [ ] **Step 4: Câbler la route**

Remplacer intégralement le corps de `get_athlete` dans `backend/app/api/v1/athletes.py`, et ajouter `AthleteParticipationOut` à l'import depuis `app.schemas.participation` :

```python
@router.get("/athletes/{athlete_id}")
def get_athlete(athlete_id: int, db: Session = Depends(get_db)):
    athlete = athlete_repository.get(db, athlete_id)
    if not athlete:
        raise NotFoundError("Athlète introuvable")
    participations = participation_repository.list_for_athlete(db, athlete_id)
    counts = participation_repository.finishers_count_by_group(
        db, [p.course_id for p in participations]
    )
    items = []
    for p in participations:
        item = AthleteParticipationOut.model_validate(p)
        item.course_finishers = counts.get((p.course_id, bool(p.is_relay)))
        items.append(item)
    return {"athlete": AthleteBrief.model_validate(athlete), "participations": items}
```

La ligne d'import devient :

```python
from app.schemas.participation import AthleteParticipationOut
```

(`ParticipationOut` n'est plus référencé dans ce fichier — le retirer de l'import, sinon `ruff` signalera F401.)

- [ ] **Step 5: Lancer les tests pour vérifier qu'ils passent**

`uv run pytest tests/test_api -v` → tous PASS (dont `test_athletes_search_and_detail`, qui garantit la non-régression du reste du payload).
Puis `uv run pytest -m "not integration" -q` → suite complète verte, et `uv run ruff check .`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/participation.py backend/app/api/v1/athletes.py backend/tests/test_api/test_other_api.py
git commit -m "feat(api): expose le nombre de finishers classés sur la fiche athlète (#80)"
```

---

### Task 3: Logique du ratio côté front

**Files:**
- Modify: `frontend/lib/types.ts:29-43` (interface `Participation`)
- Create: `frontend/lib/utils/ranking.ts`
- Create: `frontend/lib/utils/ranking.test.ts`

**Interfaces:**
- Consumes: le champ `course_finishers` du JSON (Task 2).
- Produces:
  - `interface RankRatio { rank: number; total: number; percent: number }`
  - `rankRatio(p: Participation): RankRatio | null`
  - `interface RatioEntry { participation: Participation; ratio: RankRatio }`
  - `bestRatio(parts: Participation[]): RatioEntry | null`

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `frontend/lib/utils/ranking.test.ts` :

```ts
import { describe, it, expect } from "vitest";
import { rankRatio, bestRatio } from "./ranking";
import type { Participation } from "@/lib/types";

function part(over: Partial<Participation> & { id: number }): Participation {
  return {
    id: over.id,
    athlete: { id: 1, nom: "DUPONT", prenom: "Jean", gender: "M", club: "TCN" },
    course: {
      id: 1,
      name: "Tri Z",
      event_date: "2026-05-16",
      event_type: "triathlon-m",
      provider: "manuel",
      source_url: "",
      is_relay: false,
    },
    club: "TCN",
    category: null,
    bib_number: null,
    rank_overall: over.rank_overall ?? null,
    rank_category: null,
    rank_gender: null,
    total_time: "01:59:00",
    status: "finisher",
    is_relay: false,
    splits: null,
    created_at: null,
    course_finishers: over.course_finishers,
  };
}

describe("rankRatio", () => {
  it("rapporte la place au nombre de classés", () => {
    expect(rankRatio(part({ id: 1, rank_overall: 42, course_finishers: 300 }))).toEqual({
      rank: 42,
      total: 300,
      percent: 14,
    });
    expect(rankRatio(part({ id: 2, rank_overall: 20, course_finishers: 80 }))).toEqual({
      rank: 20,
      total: 80,
      percent: 25,
    });
  });

  it("arrondit au supérieur : jamais de « Top 0 % »", () => {
    expect(rankRatio(part({ id: 1, rank_overall: 1, course_finishers: 300 }))?.percent).toBe(1);
  });

  it("renvoie null sans place", () => {
    expect(rankRatio(part({ id: 1, rank_overall: null, course_finishers: 300 }))).toBeNull();
  });

  it("renvoie null sans compte de classés", () => {
    expect(rankRatio(part({ id: 1, rank_overall: 42, course_finishers: null }))).toBeNull();
    expect(rankRatio(part({ id: 2, rank_overall: 42 }))).toBeNull();
  });

  it("renvoie null quand la place dépasse le compte (import partiel)", () => {
    expect(rankRatio(part({ id: 1, rank_overall: 42, course_finishers: 20 }))).toBeNull();
  });

  it("renvoie null sous deux classés : un « 1er sur 1 » ne dit rien", () => {
    expect(rankRatio(part({ id: 1, rank_overall: 1, course_finishers: 1 }))).toBeNull();
  });
});

describe("bestRatio", () => {
  it("retient le meilleur ratio, pas la meilleure place", () => {
    const best = bestRatio([
      part({ id: 1, rank_overall: 42, course_finishers: 300 }),
      part({ id: 2, rank_overall: 20, course_finishers: 80 }),
    ]);
    expect(best?.participation.id).toBe(1);
    expect(best?.ratio.percent).toBe(14);
  });

  it("départage deux ratios égaux par la place absolue", () => {
    const best = bestRatio([
      part({ id: 1, rank_overall: 20, course_finishers: 200 }),
      part({ id: 2, rank_overall: 10, course_finishers: 100 }),
    ]);
    expect(best?.participation.id).toBe(2);
  });

  it("ignore les participations sans ratio exploitable", () => {
    expect(bestRatio([part({ id: 1, rank_overall: 42, course_finishers: 20 })])).toBeNull();
    expect(bestRatio([])).toBeNull();
  });
});
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Depuis `frontend/` : `npx vitest run lib/utils/ranking.test.ts`
Attendu : FAIL — `Failed to resolve import "./ranking"`.

- [ ] **Step 3: Ajouter le champ au type partagé**

Dans `frontend/lib/types.ts`, interface `Participation`, après `created_at: string | null;` :

```ts
  // Nombre de finishers classés de la course (même groupe solo/relais).
  // Servi par la seule route /athletes/{id} — d'où l'optionnalité.
  course_finishers?: number | null;
```

- [ ] **Step 4: Écrire l'implémentation minimale**

Créer `frontend/lib/utils/ranking.ts` :

```ts
// Ratio place / nombre de classés d'une participation. Fonctions pures et testables.
import type { Participation } from "@/lib/types";

export interface RankRatio {
  rank: number;
  total: number;
  /** Percentile arrondi au supérieur : 42e sur 300 → 14 (« Top 14 % »). */
  percent: number;
}

// Sous deux classés, le ratio ne signale qu'un import partiel.
const MIN_CLASSES = 2;

/** Ratio d'une participation, ou `null` si les données ne le permettent pas. */
export function rankRatio(p: Participation): RankRatio | null {
  const rank = p.rank_overall;
  const total = p.course_finishers ?? null;
  if (rank == null || rank < 1) return null;
  if (total == null || total < MIN_CLASSES) return null;
  // Import partiel : plus de rangs que de classés en base. Un « Top 210 % »
  // serait pire que pas de ratio du tout.
  if (rank > total) return null;
  return { rank, total, percent: Math.ceil((rank / total) * 100) };
}

export interface RatioEntry {
  participation: Participation;
  ratio: RankRatio;
}

/** Meilleure performance rapportée au champ de la course (ratio brut, non arrondi). */
export function bestRatio(parts: Participation[]): RatioEntry | null {
  let best: RatioEntry | null = null;
  for (const participation of parts) {
    const ratio = rankRatio(participation);
    if (!ratio) continue;
    if (!best) {
      best = { participation, ratio };
      continue;
    }
    const candidate = ratio.rank / ratio.total;
    const incumbent = best.ratio.rank / best.ratio.total;
    if (candidate < incumbent || (candidate === incumbent && ratio.rank < best.ratio.rank)) {
      best = { participation, ratio };
    }
  }
  return best;
}
```

- [ ] **Step 5: Lancer les tests pour vérifier qu'ils passent**

`npx vitest run lib/utils/ranking.test.ts` → 9 tests PASS.
Puis `npm test` → suite complète verte (le champ optionnel ne doit casser aucune fixture existante).

- [ ] **Step 6: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/utils/ranking.ts frontend/lib/utils/ranking.test.ts
git commit -m "feat(front): calcule le ratio place / classés d'une participation (#80)"
```

---

### Task 4: `ordinalFr` et sous-ligne `hint` du StatCard

**Files:**
- Modify: `frontend/lib/utils/format.ts` (ajout en fin de fichier)
- Create: `frontend/lib/utils/format.test.ts`
- Modify: `frontend/components/tcn/StatCard.tsx:4-22` (signature) et `:62-81` (variant `default`)
- Create: `frontend/components/tcn/StatCard.test.tsx`

**Interfaces:**
- Consumes: rien.
- Produces:
  - `ordinalFr(n: number): string` — `1` → `"1er"`, `42` → `"42e"`.
  - `StatCard` accepte `hint?: ReactNode`, rendu sous le trait orange du variant `default` uniquement.

Pourquoi un ordinal : le `hint` est une phrase (« 42e sur 300 »), pas une pastille. Le `PlaceBadge` de la colonne « Place » garde son nombre nu — il est partagé avec la fiche course, on ne change pas son rendu.

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `frontend/lib/utils/format.test.ts` :

```ts
import { describe, it, expect } from "vitest";
import { ordinalFr } from "./format";

describe("ordinalFr", () => {
  it("écrit « 1er » pour la première place", () => {
    expect(ordinalFr(1)).toBe("1er");
  });

  it("écrit « ne » pour les autres places", () => {
    expect(ordinalFr(2)).toBe("2e");
    expect(ordinalFr(42)).toBe("42e");
    expect(ordinalFr(300)).toBe("300e");
  });
});
```

Créer `frontend/components/tcn/StatCard.test.tsx` :

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatCard } from "./StatCard";

describe("StatCard", () => {
  it("affiche la sous-ligne quand un hint est fourni", () => {
    render(<StatCard label="Meilleur ratio" value="Top 14%" hint="42e sur 300" />);

    expect(screen.getByText("Top 14%")).toBeInTheDocument();
    expect(screen.getByText("42e sur 300")).toBeInTheDocument();
  });

  it("n'affiche aucune sous-ligne sans hint", () => {
    render(<StatCard label="Top 10" value={3} />);

    expect(screen.queryByText("42e sur 300")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

`npx vitest run lib/utils/format.test.ts components/tcn/StatCard.test.tsx`
Attendu : `format.test.ts` FAIL (`ordinalFr` non exporté), `StatCard.test.tsx` FAIL sur le premier test (« 42e sur 300 » introuvable).

- [ ] **Step 3: Implémenter `ordinalFr`**

En fin de `frontend/lib/utils/format.ts` :

```ts
/** Ordinal français d'un classement : 1 → « 1er », 42 → « 42e ». */
export function ordinalFr(n: number): string {
  return n === 1 ? "1er" : `${n}e`;
}
```

- [ ] **Step 4: Ajouter la prop `hint` au StatCard**

Dans `frontend/components/tcn/StatCard.tsx`, ajouter `hint = null,` aux paramètres déstructurés (après `delta = null,`) et `hint?: ReactNode;` au type (après `delta?: ReactNode;`). Puis, dans le `return` du variant `default`, remplacer le bloc `accent` de fin par :

```tsx
      {accent ? (
        <div style={{ height: 4, width: 48, background: "var(--tcn-orange)", borderRadius: 999, marginTop: 8 }} />
      ) : null}
      {hint ? (
        <div style={{ marginTop: 8, fontSize: 13, fontWeight: 600, color: "var(--tcn-text-faint)" }}>
          {hint}
        </div>
      ) : null}
```

Mettre à jour le commentaire de tête du composant :

```tsx
/** Tuile KPI TCN. `hero` utilise le dégradé orange, `hint` ajoute une sous-ligne. */
```

Le variant `hero` n'est pas touché : il a déjà son `delta`.

- [ ] **Step 5: Lancer les tests pour vérifier qu'ils passent**

`npx vitest run lib/utils/format.test.ts components/tcn/StatCard.test.tsx` → tous PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/lib/utils/format.ts frontend/lib/utils/format.test.ts frontend/components/tcn/StatCard.tsx frontend/components/tcn/StatCard.test.tsx
git commit -m "feat(front): sous-ligne hint du StatCard et ordinal français (#80)"
```

---

### Task 5: Fiche athlète — tuile « Meilleur ratio » et colonne « Place »

**Files:**
- Modify: `frontend/app/athletes/[id]/page.tsx` (constante `COLS` ligne 11, bloc tuiles lignes 44-49, colonne « Place » ligne 71)
- Create: `frontend/app/athletes/[id]/page.test.tsx`

**Interfaces:**
- Consumes: `bestRatio(parts) -> RatioEntry | null` et `rankRatio(p) -> RankRatio | null` (Task 3) ; `ordinalFr(n) -> string` (Task 4) ; `StatCard` prop `hint` (Task 4) ; `course_finishers` du payload (Task 2).
- Produces: rien (feuille de l'arbre).

- [ ] **Step 1: Écrire le test qui échoue**

Créer `frontend/app/athletes/[id]/page.test.tsx` :

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Participation } from "@/lib/types";

const getAthlete = vi.fn();

vi.mock("@/lib/api/server", () => ({
  apiServer: { getAthlete: (id: number) => getAthlete(id) },
}));

vi.mock("next/navigation", () => ({ notFound: vi.fn() }));

import AthletePage from "./page";

const ATHLETE = { id: 7, nom: "DUPONT", prenom: "Jean", gender: "M", club: "TCN" };

function part(over: Partial<Participation> & { id: number }): Participation {
  return {
    id: over.id,
    athlete: ATHLETE,
    course: {
      id: over.id,
      name: over.course?.name ?? `Course ${over.id}`,
      event_date: "2026-05-16",
      event_type: "triathlon-m",
      provider: "manuel",
      source_url: "",
      is_relay: false,
    },
    club: "TCN",
    category: null,
    bib_number: null,
    rank_overall: over.rank_overall ?? null,
    rank_category: null,
    rank_gender: null,
    total_time: "01:59:00",
    status: "finisher",
    is_relay: false,
    splits: null,
    created_at: null,
    course_finishers: over.course_finishers,
  };
}

async function renderAthlete(participations: Participation[]) {
  getAthlete.mockResolvedValue({ athlete: ATHLETE, participations });
  const ui = await AthletePage({ params: Promise.resolve({ id: "7" }) });
  return render(ui);
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AthletePage", () => {
  it("retient le meilleur ratio, pas la meilleure place", async () => {
    await renderAthlete([
      part({ id: 1, rank_overall: 42, course_finishers: 300 }),
      part({ id: 2, rank_overall: 20, course_finishers: 80 }),
    ]);

    expect(screen.getByText("Meilleur ratio")).toBeInTheDocument();
    expect(screen.getByText("Top 14%")).toBeInTheDocument();
    expect(screen.getByText("42e sur 300")).toBeInTheDocument();
    // La tuile « Meilleure place » garde le rang absolu minimum. `getAllByText`
    // car « 20 » apparaît aussi dans la pastille de la ligne correspondante.
    expect(screen.getAllByText("20").length).toBeGreaterThan(0);
  });

  it("affiche le nombre de classés à côté de la place, dans le tableau", async () => {
    await renderAthlete([part({ id: 1, rank_overall: 42, course_finishers: 300 })]);

    expect(screen.getByText("/300")).toBeInTheDocument();
  });

  it("retombe sur la place seule quand le classement est incohérent", async () => {
    await renderAthlete([part({ id: 1, rank_overall: 42, course_finishers: 20 })]);

    // Ni le « /N » de la ligne, ni un percentile : la place reste seule.
    expect(screen.queryByText("/20")).not.toBeInTheDocument();
    expect(screen.queryByText(/^Top \d+%$/)).not.toBeInTheDocument();
    expect(screen.getByText("Meilleur ratio")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

`npx vitest run app/athletes/\[id\]/page.test.tsx`
Attendu : FAIL — « Meilleur ratio » introuvable.

- [ ] **Step 3: Câbler la page**

Dans `frontend/app/athletes/[id]/page.tsx` :

a) Ajouter aux imports :

```tsx
import { formatToken, ordinalFr } from "@/lib/utils/format";
import { bestRatio, rankRatio } from "@/lib/utils/ranking";
```

(la ligne `import { formatToken } from "@/lib/utils/format";` existante est remplacée par celle ci-dessus)

b) Élargir la colonne « Place » — la constante `COLS` passe de `90px` à `120px` sur l'avant-dernière colonne :

```tsx
const COLS = "120px 1fr 150px 90px 120px 120px 28px";
```

c) Après `const top10 = …`, ajouter :

```tsx
  const topRatio = bestRatio(participations);
```

d) Remplacer le bloc des tuiles (`<div className="mb-6 grid …">`) par :

```tsx
      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <StatCard label="Épreuves" value={participations.length} accent={false} />
        <StatCard label="Meilleure place" value={best ?? "—"} valueColor="var(--tcn-orange)" accent={false} />
        <StatCard
          label="Meilleur ratio"
          value={topRatio ? `Top ${topRatio.ratio.percent}%` : "—"}
          hint={topRatio ? `${ordinalFr(topRatio.ratio.rank)} sur ${topRatio.ratio.total}` : null}
          valueColor="var(--tcn-orange)"
          accent={false}
        />
        <StatCard label="Top 10" value={top10} accent={false} />
        <StatCard label="Format favori" value={favFormat} accent={false} />
      </div>
```

e) Remplacer la cellule « Place » de la ligne de tableau :

```tsx
                  <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
                    {p.rank_overall != null ? (
                      <>
                        <PlaceBadge place={p.rank_overall} />
                        {rankRatio(p) ? (
                          <span style={{ fontSize: 13, fontWeight: 600, color: "var(--tcn-text-faint)" }}>
                            /{rankRatio(p)!.total}
                          </span>
                        ) : null}
                      </>
                    ) : (
                      <span style={{ color: "var(--tcn-text-faint)" }}>—</span>
                    )}
                  </div>
```

- [ ] **Step 4: Lancer le test pour vérifier qu'il passe**

`npx vitest run app/athletes/\[id\]/page.test.tsx` → 3 tests PASS.

- [ ] **Step 5: Vérifier l'ensemble du front**

Depuis `frontend/` :
- `npm test` → suite complète verte.
- `npm run lint` → aucune erreur.
- `npm run build` → build prod OK (TypeScript strict : c'est ici que se verrait une incohérence de type sur `course_finishers`).

- [ ] **Step 6: Commit**

```bash
git add frontend/app/athletes/
git commit -m "feat(front): affiche le ratio et le nombre de classés sur la fiche athlète (#80)"
```

---

### Task 6: Vérification de bout en bout et documentation

**Files:**
- Modify: `docs/superpowers/specs/2026-07-25-meilleure-place-ratio-design.md` (mention de livraison)

- [ ] **Step 1: Lancer les deux suites**

Depuis `backend/` : `uv run pytest -m "not integration" -q` puis `uv run ruff check .`
Depuis `frontend/` : `npm test` puis `npm run lint` puis `npm run build`
Attendu : tout vert. Reporter la sortie réelle — pas de « ça devrait passer ».

- [ ] **Step 2: Vérifier le rendu réel**

Depuis `backend/` : `uv run uvicorn app.main:app --reload --port 8001`
Depuis `frontend/` : `npm run dev`, puis ouvrir `http://localhost:3000/athletes/<id>` sur un athlète ayant plusieurs courses.
Vérifier : les 5 tuiles tiennent sur la grille (mobile 2 colonnes, desktop 5), « Meilleur ratio » affiche un `Top n%` cohérent avec son hint, la colonne « Place » affiche `42 /300` sans déborder.

- [ ] **Step 3: Marquer la spec comme livrée**

Ajouter en fin de `docs/superpowers/specs/2026-07-25-meilleure-place-ratio-design.md` :

```markdown
## Statut

Livré (issue #80).
```

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-07-25-meilleure-place-ratio-design.md
git commit -m "docs: marque le ratio de la meilleure place comme livré (#80)"
```

---

## Auto-revue

**Couverture de la spec** — chaque décision de la spec a sa tâche :
population comptée (Task 1), exposition sur la seule route athlète (Task 2),
replis `rank > total` / `total < 2` (Task 3), deux tuiles distinctes (Tasks 4-5),
colonne « Place » enrichie (Task 5), périmètre limité à la fiche athlète
(aucune tâche ne touche `/resultats` ni `/courses`), tests backend et front
(Tasks 1, 2, 3, 4, 5).

**Écart assumé vis-à-vis de la spec** — la maquette de la spec écrivait
`[42e] /300` dans le tableau ; le plan garde `[42] /300`, car `PlaceBadge` est
partagé avec la fiche course et n'a jamais porté d'ordinal. L'ordinal reste où
il forme une phrase : le `hint` de la tuile (« 42e sur 300 »).

**Cohérence des types** — `finishers_count_by_group` renvoie
`dict[tuple[int, bool], int]`, lu par Task 2 avec la clé `(p.course_id, bool(p.is_relay))` ;
`course_finishers` est `int | None` côté Pydantic et `number | null` optionnel côté
TS ; `rankRatio` renvoie `RankRatio | null`, `bestRatio` renvoie `RatioEntry | null`
dont le champ `ratio` est un `RankRatio` — les usages de Task 5
(`topRatio.ratio.percent`, `topRatio.ratio.rank`, `topRatio.ratio.total`) collent.
