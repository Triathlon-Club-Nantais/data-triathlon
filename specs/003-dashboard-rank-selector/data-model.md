# Data Model — Sélecteur de type de rang

**Feature** : `feat/104-dashboard-rank-selector`
**Nature** : purement frontend. Aucun changement de schéma DB, aucun changement d'API.

Ce document liste les types TypeScript ajoutés ou modifiés, avec leurs invariants et transitions d'état. Les entités backend (`Participation`, `Athlete`, `Course`) sont **inchangées** — voir `backend/app/models/` pour leur définition canonique.

## Types nouveaux — `frontend/lib/rank.ts`

### `RankType`

```ts
export type RankType = "scratch" | "category" | "gender" | "all";
```

**Invariant** : les seules 4 valeurs autorisées dans l'URL et propagées dans les fonctions de comptage. Toute autre valeur (entrée URL, mutation manuelle) est traitée comme `RANK_DEFAULT`.

### `RANK_PARAM` et `RANK_DEFAULT`

```ts
export const RANK_PARAM = "rank";               // clé de l'URL : ?rank=…
export const RANK_DEFAULT: RankType = "scratch"; // FR-003, cas d'usage AG
```

### `rankTypeFromParam(v)`

```ts
export function rankTypeFromParam(v: string | undefined): RankType;
```

**Contrat** :

| Entrée | Sortie |
|---|---|
| `"scratch"` | `"scratch"` |
| `"category"` | `"category"` |
| `"gender"` | `"gender"` |
| `"all"` | `"all"` |
| `undefined` | `"scratch"` (défaut) |
| `""` (chaîne vide) | `"scratch"` (défaut) |
| `"foo"`, `"women"`, `"CATEGORY"`, autre | `"scratch"` (défaut) |

Pas de casse insensible, pas d'alias : les 4 valeurs canoniques exactes, tout le reste retombe sur le défaut. Simplicité (principe VI).

## Types modifiés — `frontend/lib/utils/club-aggregate.ts`

### `bestRank` — signature enrichie

```ts
export function bestRank(p: Participation, rankType?: RankType): BestRank | null;
```

**Comportement par mode** :

| `rankType` | Rang comparé | `scope` retourné |
|---|---|---|
| `"scratch"` | `p.rank_overall` seul | toujours `"overall"` |
| `"category"` | `p.rank_category` seul | toujours `"category"` |
| `"gender"` | `p.rank_gender` seul | toujours `"gender"` |
| `"all"` ou `undefined` | `min(rank_overall, rank_gender, rank_category)` (ignore les `null`) | `"overall"` \| `"gender"` \| `"category"` selon lequel est minimum |

**Invariants** :

- `null` retourné si le rang du mode sélectionné est absent (ex. `"scratch"` sur une participation sans `rank_overall`).
- L'ordre de départage en `"all"` reste l'ordre actuel (`overall` > `gender` > `category` en cas d'égalité, via l'ordre du tableau `candidates`).

### `RankCountersScalar` / `RankCountersGender` / `RankCountersResult`

```ts
export interface RankCountersScalar {
  kind: "scalar";
  victories: number;
  podiums: number;
  top10: number;
}

export interface RankCountersGender {
  kind: "gender";
  women: { victories: number; podiums: number; top10: number };
  men:   { victories: number; podiums: number; top10: number };
}

export type RankCountersResult = RankCountersScalar | RankCountersGender;
```

**Discriminant `kind`** : permet un `switch` exhaustif dans les composants consommateurs. TypeScript strict impose que chaque branche soit couverte.

**Invariants** :

| Mode | `kind` retourné | Contenu |
|---|---|---|
| `"scratch"` | `"scalar"` | compte sur `rank_overall` |
| `"category"` | `"scalar"` | compte sur `rank_category` |
| `"gender"` | `"gender"` | `women.*` = participations `athlete.gender === "F"` avec `rank_gender ≤ 1/3/10`, `men.*` = idem `"M"` |
| `"all"` ou `undefined` | `"scalar"` | compte sur `min(rank_overall, rank_gender, rank_category)` (identique à l'actuel) |

**Athlète sans genre** en mode `"gender"` : ne compte **pas** (ni dans `women`, ni dans `men`). Choix explicité en spec (Edge Cases).

### `rankCounters` — signature enrichie

```ts
export function rankCounters(parts: Participation[], rankType?: RankType): RankCountersResult;
```

### `isPodium`, `isTopN` — signatures enrichies

```ts
export function isPodium(p: Participation, rankType?: RankType): boolean;
export function isTopN(p: Participation, n: number, rankType?: RankType): boolean;
```

Se ramènent à `bestRank(p, rankType)` puis test du seuil (`rank ≤ 3` ou `rank ≤ n`). En mode `"gender"`, un athlète sans genre est déjà exclu par `bestRank` (car `rank_gender` peut être absent) ; cas doublé de ceinture ici — on filtre aussi sur `athlete.gender` non vide pour éviter tout faux positif si `rank_gender` était présent sans genre renseigné (cas malformé côté DTO).

### `listPodiums` — signature enrichie

```ts
export function listPodiums(parts: Participation[], rankType?: RankType): PodiumEntry[];
```

Filtre les entrées selon `bestPodiumRank(p, rankType)`. Le champ `best.scope` de chaque entrée reflète le mode :

- mode `"scratch"` → toutes les entrées ont `scope: "overall"`
- mode `"category"` → toutes ont `scope: "category"`
- mode `"gender"` → toutes ont `scope: "gender"`
- mode `"all"` → mélange (comportement actuel)

Le composant `ClubDashboard.tsx` continue de rendre le badge `SCOPE_LABEL[best.scope]`. En mode `"gender"`, ce badge affichera « Genre » ; on peut vouloir enrichir avec F/H directement dans l'item (facultatif, sortira en tâche si nécessaire).

## Types inchangés

- `Participation`, `Athlete`, `Course` — inchangés côté frontend (`frontend/lib/types.ts`) et backend.
- `BestRank`, `PodiumScope`, `RankCounters` (l'ancien scalar-only), `PodiumEntry` — préservés, sont les briques réutilisées.

## Diagramme des dépendances

```
frontend/lib/rank.ts                (NEW)
        │
        ├─→ frontend/lib/utils/club-aggregate.ts (MODIFIED — RankType param)
        │       │
        │       ├─→ dashboard/page.tsx (MODIFIED)
        │       └─→ components/club/ClubDashboard.tsx (MODIFIED)
        │
        └─→ components/layout/RankTypeToggle.tsx (NEW)
                │
                ├─→ dashboard/page.tsx (MODIFIED — monte le toggle)
                └─→ app/club/page.tsx (MODIFIED — monte le toggle)
```

Aucun cycle. Aucune couche de plus.
