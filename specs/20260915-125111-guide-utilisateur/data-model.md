# Phase 1 — Data Model : Guide utilisateur intégré

Aucune donnée persistée (pas de DB, pas d'API) : la seule « entité » est la
forme du contenu statique consommé par le rendu.

## GuideSection (type TypeScript, pas une table)

Défini une fois dans `components/guide/types.ts`, instancié dans
`guide-content.membre.ts` et `guide-content.admin.ts`.

| Champ | Type | Règle |
|---|---|---|
| `id` | `string` | Slug utilisé comme ancre (`#club`) — unique dans son fichier de contenu |
| `titre` | `string` | Nom de la fonctionnalité, en français |
| `etapes` | `string[]` | Instructions concises, une entrée par étape courte (FR-006 : pas de pavé de texte) |
| `casUsage` | `string` | Ce que l'utilisateur cherche à accomplir (FR-008), une à deux phrases |
| `captures` | `{ src: string; alt: string; placeholder?: boolean }[]` | Au moins un élément (FR-007) — `src` pointe sous `public/guide/`. `placeholder: true` (15 sections admin, #874) fait apparaître « Capture à venir » à la fois dans un badge visuel et dans l'`alt` — la mention doit atteindre un lecteur d'écran, pas seulement l'image |

## Validation

- `guide-content.membre.test.ts` / `guide-content.admin.test.ts` vérifient,
  pour chaque fichier de contenu, que `etapes.length >= 1`, `casUsage` non
  vide et `captures.length >= 1` pour toute section (FR-006/FR-007/FR-008) et
  que la liste couvre exactement les 6 identifiants membres et les 15
  identifiants admin attendus (SC-001) — pas plus, pas moins, pour qu'un
  oubli ou un doublon échoue au lieu de passer en silence. Ils vérifient
  aussi que chaque `captures[].src` résout vers un fichier réellement présent
  sous `public/`, pour qu'un chemin mal orthographié échoue au test plutôt
  qu'en 404 silencieux une fois en prod (revue de code, #865).
- Pas de state transitions : le contenu est statique, pas de cycle de vie.
