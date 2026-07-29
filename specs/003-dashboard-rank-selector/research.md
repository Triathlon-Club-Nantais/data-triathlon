# Research — Sélecteur de type de rang

**Date**: 2026-07-29
**Feature**: `feat/104-dashboard-rank-selector` — spec `specs/003-dashboard-rank-selector/spec.md`.

Ce document consolide les décisions techniques Phase 0. Aucune NEEDS CLARIFICATION résiduelle ; les 3 questions produit ont été tranchées en `/speckit-clarify`. Restent quelques choix d'implémentation qui bénéficient d'être figés ici pour éviter la dérive en tâches.

## Décision 1 — Emplacement de la définition `RankType`

**Décision** : nouveau module `frontend/lib/rank.ts`, sur le patron exact de `frontend/lib/scope.ts` déjà en place.

**Rationale** : le paramètre `?rank=` a la même nature qu'un paramètre transverse existant (`?scope=`, `?sports=`, `?seasons=`) : constantes, parseur strict à partir d'un `string | undefined`, réutilisable côté serveur (RSC) et côté client (toggle). Le pattern `scope.ts` est éprouvé, il regroupe les constantes (`SCOPE_CLUB`, `SCOPE_PARAM`) et la fonction `federalOnlyFromParam`. On y ajoute :

- `export type RankType = "scratch" | "category" | "gender" | "all";`
- `export const RANK_PARAM = "rank";`
- `export const RANK_DEFAULT: RankType = "scratch";`
- `export function rankTypeFromParam(v: string | undefined): RankType;`

`rankTypeFromParam` accepte les 4 valeurs canoniques et retombe silencieusement sur `RANK_DEFAULT` pour toute autre entrée (`undefined`, chaîne vide, valeur inconnue). C'est FR-003 et un edge case explicite.

**Alternatives considérées** :

- **Inline dans `club-aggregate.ts`** : rejeté. Deux pages (`/dashboard`, `/club`) et un composant client (toggle) ont besoin de parser l'URL. Un module central évite la duplication.
- **Sous-répertoire `lib/params/` regroupant scope+rank+seasons** : rejeté. YAGNI (principe VI). Trois fichiers cohabitent déjà à plat dans `lib/`, un quatrième ne motive pas un nouveau niveau d'arborescence.

## Décision 2 — Signature d'API des fonctions de comptage

**Décision** : ajouter un **paramètre optionnel** `rankType?: RankType` à `bestRank`, `rankCounters`, `isPodium`, `isTopN`, `listPodiums`. Défaut = `"all"` (préserve exactement le comportement actuel quand personne ne passe le paramètre).

```ts
export function bestRank(p: Participation, rankType?: RankType): BestRank | null;
export function rankCounters(parts: Participation[], rankType?: RankType): RankCounters;
export function isPodium(p: Participation, rankType?: RankType): boolean;
export function isTopN(p: Participation, n: number, rankType?: RankType): boolean;
export function listPodiums(parts: Participation[], rankType?: RankType): PodiumEntry[];
```

**Rationale** :

- **Rétro-compat locale** : `buildRoster` et `clubSummary` appellent `isPodium(p)` sans paramètre. Avec un défaut à `"all"`, ils continuent de tourner identiquement. Le principe VI (YAGNI) impose de ne pas casser inutilement l'existant.
- **Signature explicite, pas un objet `options`** : quatre fonctions, un seul paramètre supplémentaire — l'objet ajouterait de la friction sans bénéfice.
- **Le mode `"gender"` retourne un couple F+H** pour `rankCounters` (voir décision 3). `bestRank` et `isPodium` restent scalaires : ils travaillent participation par participation, le genre de l'athlète tranche naturellement F ou H (une même participation ne peut être qu'à la fois F ou H, pas les deux).

**Alternatives considérées** :

- **Cinq nouvelles fonctions (`rankCountersScratch`, `rankCountersCategory`…)** : rejeté. Duplique 5 fois la même boucle, viole DRY, force les appelants à `switch` sur le type au lieu de passer une variable — le complexité migre chez l'appelant sans disparaître.
- **Wrapper mémoïsé** : rejeté. Les listes de participations sont petites (max ~5000 tuples déjà chargés en RSC), aucun problème de perf mesuré.

## Décision 3 — Représentation du dédoublement F/H en mode `gender`

**Décision** : `rankCounters` retourne un type discriminé selon le mode.

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

export function rankCounters(parts: Participation[], rankType?: RankType): RankCountersResult;
```

Le champ `kind` permet à `dashboard/page.tsx` et `ClubDashboard.tsx` de faire un simple `switch` sur le résultat et de rendre soit 3 cartes classiques (`scalar`), soit 3 cartes dédoublées (`gender`). Aucune ambiguïté d'interprétation possible.

**Rationale** :

- Un discriminant explicite est le seul moyen simple de représenter deux formes de retour dans TypeScript strict sans casser le typage. Une seule interface avec `women/men` optionnels obligerait chaque appelant à faire des `??` défensifs.
- Le nom `kind` est le canon TS (utilisé dans les union types de `lib/utils/ranking.ts:18` déjà en place).

**Alternatives considérées** :

- **Toujours retourner F+H, et sommer côté appelant en modes non-gender** : rejeté. Absurde de calculer F/H séparément quand le résultat visible est un scalaire global.
- **Une seconde fonction `rankCountersByGender`** : rejeté. Force `dashboard/page.tsx` à un `if/else` sur le mode, plus deux appels différents ; le discriminant fait tout ça en un seul call.

## Décision 4 — Filtrage F/H : quel champ ?

**Décision** : `athlete.gender` (champ existant du DTO `Athlete` — voir `frontend/lib/types.ts`). Convention observée en base : `"F"` pour femme, `"M"` pour homme, chaîne vide ou `null` pour indéterminé.

**Rationale** :

- **Deux valeurs canoniques** avec un troisième cas « inconnu ». Le mode `gender` ne compte pas les athlètes sans genre renseigné (edge case explicite dans la spec).
- **Pas via `rank_gender` seul** : `rank_gender` donne le classement dans le tableau F ou H, mais ne dit pas dans quel des deux. Un athlète non classé garderait `rank_gender = null` sans qu'on sache s'il faut le mettre en F ou en H. C'est `athlete.gender` qui tranche.

**Alternatives considérées** :

- **Inférer depuis `category`** : rejeté. Les catégories mêlent parfois âge et sport (M2, S4, V1), le préfixe de genre n'est pas systématique.

## Décision 5 — Écriture du toggle : client component réutilisant `useTransition`

**Décision** : `RankTypeToggle` est un **client component** (`"use client"`), calqué sur `DisciplineToggle`. Il utilise :

- `useRouter()`, `useSearchParams()`, `usePathname()` de `next/navigation` — identique à `DisciplineToggle`.
- `useTransition()` pour marquer l'état pendant que Next re-fetch la page côté serveur (`data-pending` déjà présent dans le pattern maison).
- Un rendu 4-boutons horizontal, avec un état actif visuellement distinct. Style repris de `SeasonSelector` (radios stylées) plutôt que du checkbox de `DisciplineToggle` : mono-choix mutuellement exclusif = radio group, sémantiquement.

**Rationale** : le paramètre URL doit rester canonique. Un composant serveur ne peut pas écouter les clics du user ; il faut un client component qui `router.push()`. `useTransition` évite le clignotement pendant que RSC recharge la page.

**Alternatives considérées** :

- **Server component avec `<Link>` par bouton** : rejeté. Fonctionne visuellement mais pas d'état pending, pas de `startTransition`. UX moins fluide.
- **Émettre un `<select>` natif** : rejeté. 4 valeurs, mono-choix, un radio group est plus lisible et plus tactile-friendly.

## Décision 6 — Ordre de test (TDD strict, principe III)

Séquence figée pour les tâches :

1. **Rouge d'abord sur `lib/rank.ts`** — parser `rankTypeFromParam` : les 4 valeurs canoniques, défaut sur `undefined`, défaut sur `"foo"`.
2. **Rouge sur `club-aggregate.test.ts`** — nouveaux cas pour `bestRank`, `rankCounters`, `isPodium`, `isTopN`, `listPodiums`, un par mode. Cas edge : athlète sans genre en mode gender, rang manquant, jeu vide.
3. **Rouge sur `RankTypeToggle.test.tsx`** — le toggle rend 4 boutons, marque le bon actif selon `?rank=`, `router.push` sur clic.
4. **Rouge sur `dashboard/page.test.tsx`** — la page lit `?rank=`, passe à `rankCounters`, rend le bon libellé secondaire.
5. **Rouge sur `ClubDashboard.test.tsx`** — la liste des podiums est filtrée par rank.

Puis vert (implémentation), puis lint + build.

**Rationale** : Constitution III est non-négociable, et l'ordre importe — chaque test rouge doit être écrit **avant** l'implémentation qu'il valide. Les fonctions utilitaires (couche la plus basse) sont testées en premier pour donner une API stable aux couches supérieures.

## Ce qui reste hors du plan

- **Persistance en localStorage** — explicitement rejetée dans la spec (Assumptions), pas dans le périmètre.
- **Autres pages** (`/athletes/[id]`, `/resultats`) — hors périmètre explicite. La fiche athlète a sa propre logique de rang (`bestRatio`), non concernée.
- **Migration de `buildRoster` / `clubSummary` vers le nouveau paramètre** — leur défaut à `"all"` (via le paramètre optionnel) laisse leur comportement inchangé. Une extension future est possible mais n'est pas engagée ici (YAGNI).
