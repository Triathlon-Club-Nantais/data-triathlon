# Audit sur-ingénierie — `frontend/` (2026-08-06)

> Relevé fait à froid sur l'arbre complet de `frontend/` (14 918 lignes de
> `.ts`/`.tsx`/`.mjs`/`.css` hors `node_modules` et `.next`, 40 dépendances),
> branche `ponytail-analyse`. **Appliqué le 2026-08-08** — voir « État
> d'application » en fin de document : 11 entrées sur 14 sont dans le code, deux
> sont refusées avec leur raison, une reste un chantier à trancher.
>
> Périmètre : sur-ingénierie et complexité seulement. Ni bugs, ni sécurité, ni
> performance — ces axes relèvent d'une revue normale.
>
> Pendant côté backend : [`2026-08-06-backend-surengineering-audit.md`](2026-08-06-backend-surengineering-audit.md).

## Comment lire

Chaque ligne nomme ce qui peut être **supprimé** et ce qui le remplace. Les
étiquettes :

| Étiquette | Sens |
|---|---|
| `delete` | code mort, souplesse jamais utilisée, fonctionnalité spéculative. Remplacement : rien. |
| `stdlib` | réimplémentation de ce que la bibliothèque standard livre déjà. |
| `native` | dépendance ou code faisant ce que la plateforme fait déjà. |
| `yagni` | abstraction à une seule implémentation, config que personne ne règle, couche à un seul appelant. |
| `shrink` | même logique, moins de lignes. |

Le classement va de la plus grosse coupe à la plus petite.

## Récapitulatif

| # | Étiquette | Objet | Lignes | Deps | Risque |
|---|---|---|---:|---:|---|
| 1 | `delete` | cascade `command` → `input-group` → `textarea` | −372 | −1 | aucun (jamais rendu) |
| 2 | `yagni` | deux design systems, 7 primitives dupliquées | −485 | — | **élevé — migration, pas un snip** |
| 3 | `delete` | 6 composants orphelins | −303 | — | aucun |
| 4 | `delete` | `ScrapeForm.tsx` + son test | −228 | — | aucun |
| 5 | `delete` | 5 hooks react-query jamais appelés | −47 | — | aucun |
| 6 | `delete` | `next-themes` | −2 | −1 | faible (thème du toaster) |
| 7 | `delete` | `@tanstack/react-query-devtools` | — | −1 | aucun |
| 8 | `native` | `shadcn` en `dependencies` | — | −1 runtime | aucun |
| 9 | `shrink` | `toQuery` recopié client/server | −17 | — | faible |
| 10 | `native` | `AbortController` du keep-warm | −6 | — | faible |
| 11 | `yagni` | `scripts/exit-code.mjs` | −13 | — | aucun |
| 12 | `yagni` | `lib/utils/event.ts` + `raceOrder.ts` | −10 | — | aucun |
| 13 | `shrink` | 28 symboles exportés sans consommateur externe | 0 | — | aucun |
| 14 | `shrink` | docstring dupliquée | −1 | — | aucun |

**Net : ≈ −1 000 lignes, −3 dépendances, +1 sortie du bundle de production.**

Les entrées 1 à 5 (≈ −950 lignes) sont du code que **rien ne rend et rien
n'importe** : elles se coupent sans changer un pixel. L'entrée 2 est d'une autre
nature — c'est le seul chantier du lot.

---

## 1. `delete` — cascade `command` → `input-group` → `textarea`

`components/ui/command.tsx` (196 l.), `components/ui/input-group.tsx` (158 l.),
`components/ui/textarea.tsx` (18 l.).

Trois fichiers de scaffolding shadcn dont rien ne sort, en chaîne fermée :

- `command.tsx` n'est importé **nulle part** ;
- `input-group.tsx` n'est importé que par `command.tsx` ;
- `textarea.tsx` n'est importé que par `input-group.tsx`.

Vérifié par `grep -rn "ui/command\|ui/input-group\|ui/textarea\|from \"cmdk\""`
sur `app`, `components`, `lib`, `hooks`, `test` : les seuls résultats sont les
trois imports internes à la cascade.

Le réflexe est de croire que l'autocomplétion d'athlète s'en sert —
`components/layout/AthletePicker.tsx` (150 l.) est bien une recherche
incrémentale. Elle est construite sur `Avatar`, `Input` et `Modal` de
`@/components/tcn`, pas sur `ui/command`.

**Remplacement : rien.** La dépendance `cmdk` part avec (`command.tsx` est son
unique site d'import).

## 2. `yagni` — deux design systems en parallèle

`components/ui/` (24 composants, shadcn) et `components/tcn/` (14 composants,
« TCN Design System » porté de Claude Design). Sept primitives existent des deux
côtés, et les deux versions sont **activement utilisées** :

| Primitive | `components/ui/` | usages | `components/tcn/` | usages |
|---|---|---:|---|---:|
| Carte | `card.tsx` (103 l.) | 9 | `Card.tsx` | 8 |
| Bouton | `button.tsx` (58 l.) | 8 | `Button.tsx` | 2 |
| Badge | `badge.tsx` (52 l.) | 5 | `Badge.tsx` | 3 |
| Champ | `input.tsx` (20 l.) | 4 | `Input.tsx` | 2 |
| Avatar | `initials-avatar.tsx` (42 l.) | 4 | `Avatar.tsx` | 3 |
| Stat | `stat.tsx` (50 l.) | 3 | `StatCard.tsx` | 3 |
| Dialogue | `dialog.tsx` (160 l.) | 2 | `Modal.tsx` | 1 |

Le côté `ui/` de ces sept paires pèse **485 lignes**. Ce n'est pas du code mort :
c'est une migration inachevée (cf. le remplacement de SPLIT par le TCN Design
System, branche `feat/claude-design-sync`). Le coût réel n'est pas le volume mais
l'arbitrage permanent — chaque nouveau composant demande « lequel des deux ? », et
la réponse est actuellement « les deux ».

**Remplacement** : converger sur un seul système. Ce n'est **pas** une coupe à
faire dans un lot de nettoyage : c'est un chantier à part, avec un choix à
trancher d'abord (le `tcn/` porte l'identité visuelle, le `ui/` porte les
primitives complexes — `dropdown-menu` 268 l., `select` 201 l. — qui n'ont pas
d'équivalent en face).

**À décider avant d'agir** : est-ce que `tcn/` absorbe les primitives complexes,
ou est-ce que `ui/` reçoit les tokens `--tcn-*` ?

## 3. `delete` — 6 composants orphelins

Aucun n'est importé, ni statiquement ni dynamiquement (vérifié par balayage de
tous les fichiers de `app/`, `components/`, `lib/`, `hooks/`).

| Fichier | Lignes | Note |
|---|---:|---|
| `components/results/Leaderboard.tsx` | 108 | remplacé par `RaceFinishers.tsx` (281 l.) |
| `components/ui/accordion.tsx` | 72 | scaffolding shadcn |
| `components/club/AthleteDialog.tsx` | 56 | — |
| `components/ui/separator.tsx` | 25 | les « Separator » du code sont ceux de `dropdown-menu` et `select`, pas celui-ci |
| `components/dashboard/Kpis.tsx` | 22 | — |
| `components/dashboard/LiveFeed.tsx` | 20 | seul consommateur de `useLiveFeed` (cf. n° 5) |

**Remplacement : rien.**

## 4. `delete` — `ScrapeForm.tsx` et son test

`components/scrape/ScrapeForm.tsx` (105 l.) et
`components/scrape/ScrapeForm.test.tsx` (123 l.).

Aucune page ne rend ce composant : `app/ajouter/page.tsx` monte
`TcnScrapeForm` (428 l.), son successeur. Le seul import de `ScrapeForm` vient de
son propre fichier de test — 123 lignes qui valident du code que personne
n'exécute, et qui font passer le composant pour vivant à toute recherche naïve.

Les deux partagent la même structure (import de `ManualResultForm`, appel
`persist`, `save.isPending`) : `TcnScrapeForm` est bien la version reprise, pas un
composant différent.

**Remplacement : rien.**

## 5. `delete` — 5 hooks react-query jamais appelés

| Hook | Fichier | Lignes |
|---|---|---:|
| `useStats` | `lib/queries/stats.ts` | 6 |
| `useLiveFeed` | `lib/queries/stats.ts` | 8 |
| `useCourseParticipations` | `lib/queries/events.ts` | 17 |
| `useDeleteParticipation` | `lib/queries/participations.ts` | 9 |
| `useParticipations` | `lib/queries/participations.ts` | 7 |

`lib/queries/stats.ts` disparaît entièrement (19 l.) : ses deux exports sont
morts. `useLiveFeed` n'avait qu'un appelant, le composant orphelin `LiveFeed.tsx`
(n° 3) — les deux tombent ensemble.

**Remplacement : rien.** Les pages chargent leurs données côté serveur via
`apiServer` (RSC) ; ces hooks sont le vestige de l'époque où le fetch était
client. `useSaveParticipation` reste : il est utilisé.

## 6. `delete` — `next-themes`

`components/ui/sonner.tsx:3,8`. Un seul appel dans tout le dépôt :

```ts
const { theme = "system" } = useTheme()
```

Aucun `<ThemeProvider>` n'est monté dans l'arbre (`app/layout.tsx` n'en a pas), et
`app/globals.css:5` porte le constat : « Mode sombre opt-in via la classe
`.dark` (**jamais posée** → DS clair only) ». Le hook rend donc systématiquement
son défaut, et la dépendance ne fait rien.

**Remplacement** : `theme="light"` en dur dans `sonner.tsx`, la dépendance part.

**Ceiling** : le jour où le mode sombre est branché pour de vrai, `next-themes`
revient — c'est le bon outil. Ce qu'on retire, c'est un provider absent, pas la
capacité.

## 7. `delete` — `@tanstack/react-query-devtools`

`package.json`, section `dependencies`. Zéro import dans tout l'arbre.
`@tanstack/react-query` (14 sites) reste évidemment.

**Remplacement : rien.**

## 8. `native` — `shadcn` en `dependencies`

`package.json`. C'est le CLI de scaffolding (`shadcn add button`), pas du code
exécuté par l'application — et il est déclaré en dépendance **de production**,
donc installé sur Vercel à chaque build.

**Remplacement** : `npx shadcn@latest add …` à la demande. Au minimum, le
déplacer en `devDependencies`. `components.json` (la config du CLI) reste, il ne
coûte rien.

## 9. `shrink` — `toQuery` recopié à l'identique

`lib/api/client.ts:51-63` et `lib/api/server.ts:57-69`. Treize lignes strictement
identiques, plus le bloc de lecture d'erreur (`await res.json().catch(() => ({
detail: res.statusText }))`) répété trois fois entre les deux fichiers.

**Remplacement** : `lib/api/query.ts`. L'arête d'import existe déjà —
`server.ts:2` importe `ApiError` depuis `client.ts`.

**À ne pas fusionner au-delà** : `serverFetch` et `serverFetchAuthed` sont
volontairement deux fonctions (lire les cookies dans `serverFetch` rendrait
dynamiques les six pages publiques prérendues), et `client.ts` vise `/api/v1` en
relatif là où `server.ts` vise `API_URL`. Seul `toQuery` est du copier-coller.

## 10. `native` — l'`AbortController` du keep-warm

`app/api/cron/keep-warm/route.ts:34-35` et `:63-65`. Un `AbortController`, un
`setTimeout`, un `clearTimeout` et un bloc `finally` pour poser un délai.

**Remplacement** — natif depuis Node 18 :

```ts
const res = await fetch(url, {
  signal: AbortSignal.timeout(TIMEOUT_MS),
  cache: "no-store",
});
```

Le `catch` qui distingue `err.name === "AbortError"` reste valide :
`AbortSignal.timeout` rejette avec un `TimeoutError`, à vérifier au moment de la
bascule (le message « délai dépassé » doit continuer de sortir).

## 11. `yagni` — `scripts/exit-code.mjs`

Vingt-et-une lignes, dont dix de commentaire, pour une fonction de six lignes
(`wrapperExitCode`) avec **un seul appelant** (`dev.mjs:77`) et aucun test.

**Remplacement** : inline dans `dev.mjs`, en gardant le commentaire sur la
convention 128+n — c'est lui qui porte l'information (un `pkill` ne doit pas
ressembler à une panne applicative).

## 12. `yagni` — `lib/utils/event.ts` et `lib/utils/raceOrder.ts`

- `lib/utils/event.ts` : 4 lignes, un export, un ternaire
  (`isRelay ? \`${name} (Relais)\` : name`).
- `lib/utils/raceOrder.ts` : 13 lignes, dont 6 de commentaire nécrologique sur
  `orderParticipations` / `countOutcomes` / `isFinisher`, retirés en #163. Reste
  un prédicat d'une ligne.

**Remplacement** : les fusionner dans `lib/utils/format.ts`. Le commentaire de
`raceOrder.ts` mérite d'être conservé — il explique pourquoi ces fonctions ne
doivent pas revenir (elles prenaient le classement entier, appelées sur une
tranche de vingt lignes elles annonceraient « 20 partants » sans erreur).

## 13. `shrink` — 28 symboles exportés sans consommateur externe

`EVENT_TYPE_LABELS`, `PROVIDER_LABELS`, `AUTH_ERROR_LABELS` (`lib/constants.ts`),
`DISCIPLINE_COLORS` (`lib/sport-colors.ts`), `splitSchema`, `SchemaEntry`
(`lib/utils/splits.ts`), `disciplineFamily` (`lib/utils/format.ts`),
`BestRank`, `RankCounters*`, `PodiumEntry`, `ClubSummary`
(`lib/utils/club-aggregate.ts`), `RankRatio*`, `RatioEntry`
(`lib/utils/ranking.ts`), `CourseBrief`, `EventOut`, `RecentItem`,
`CategoryCount`, `ClubCount`, `SessionRole` (`lib/types.ts`).

**Attention — ce n'est pas du code mort.** Tous sont utilisés *à l'intérieur* de
leur propre module (`CourseBrief` par `Participation`, `splitSchema` par les trois
fonctions publiques de `splits.ts`, `EVENT_TYPE_LABELS` par `eventTypeLabel`…).
C'est le mot-clé `export` qui tombe, pas la déclaration : **zéro ligne gagnée**,
mais la surface publique de `lib/` fond de moitié et l'auto-import de l'éditeur
cesse de proposer des internes.

Seule exception réellement morte : **`IconButton`**, exporté par le barrel
`components/tcn/index.ts` et consommé par personne.

## 14. `shrink` — docstring dupliquée

`lib/utils/time.ts:1-2` : le même commentaire `/** Convertit "HH:MM:SS" ou
"MM:SS" en secondes ; null si invalide. */` sur deux lignes consécutives.

---

## Vérifié et écarté

Deux pistes qui paraissaient être des trouvailles et n'en sont pas — notées pour
ne pas les re-signaler :

- **Les tokens `--color-*` de `app/globals.css`** semblent non référencés : aucun
  `var(--color-primary)` dans le code. C'est le fonctionnement de Tailwind v4 —
  `@theme` transforme `--color-primary` en utilitaires `bg-primary` / `text-primary`.
  Faux positif ; un balayage sur `var(--…)` n'est pas la bonne mesure pour ce
  fichier.
- **`components/ui/*` utilisés une seule fois** (`dropdown-menu` 268 l. pour
  `UserMenu`, `select` 201 l. pour deux filtres, `popover` 90 l. pour
  `SeasonSelector`, `sheet` 93 l. pour `AppNav`) : un site d'appel ne fait pas une
  abstraction inutile quand le composant encapsule un primitif accessible
  (`@base-ui/react`). Rien à couper là.

## Ce que l'audit n'a **pas** trouvé à couper

Pour éviter de rejuger ces points au prochain passage :

- **`scripts/backend-url.mjs`** (116 l.) — dense, mais chaque garde répond à un
  bug mesuré : le sondage `isPortAlive` rend la découverte auto-corrigeante (un
  backend tué par `kill -9` laisse son fichier de port derrière lui), et
  `missingBackendEnv` ne comble que ce que personne n'a défini, sans quoi
  `.env.local` deviendrait muet.
- **`lib/api/server.ts`** — `serverFetch` et `serverFetchAuthed` restent deux
  fonctions distinctes délibérément (cf. n° 9).
- **`lib/scope.ts`, `lib/rank.ts`, `lib/labels.ts`, `lib/club.ts`** — chacun tient
  une définition unique partagée par trois sites d'affichage ou plus. Fragmenté,
  mais c'est l'inverse de la duplication.
- **`hooks/useDebounce.ts`** (11 l.) — l'implémentation canonique, rien à retirer.
- **`lib/sport-colors.ts`** — l'en-tête parle encore de « SPLIT », le design
  system remplacé ; le code, lui, est vivant (`eventTypeColor` × 3,
  `tintedStyle` × 3, `avatarColor` × 1). Seul le commentaire est périmé.

## État d'application (2026-08-08)

Appliqué en deux commits, dans l'ordre suggéré ci-dessus.

| # | Objet | État |
|---|---|---|
| 1 | cascade `command` → `input-group` → `textarea` | ✅ supprimée, `cmdk` avec — `84b7ee0` |
| 2 | deux design systems | ⏸️ **chantier**, décision non prise |
| 3 | 6 composants orphelins | ✅ `84b7ee0` |
| 4 | `ScrapeForm.tsx` + son test | ✅ `84b7ee0` |
| 5 | 5 hooks react-query | ✅ `84b7ee0`, plus 3 clés `queryKeys` orphelines |
| 6 | `next-themes` | ✅ `df42070` |
| 7 | `@tanstack/react-query-devtools` | ✅ `84b7ee0` |
| 8 | `shadcn` en `dependencies` | ✅ passé en `devDependencies` — `df42070` |
| 9 | `toQuery` recopié | ✅ `lib/api/query.ts` — `df42070` |
| 10 | `AbortController` du keep-warm | ✅ `AbortSignal.timeout` — `df42070` |
| 11 | `scripts/exit-code.mjs` | ❌ **refusé** (voir ci-dessous) |
| 12 | `lib/utils/event.ts` + `raceOrder.ts` | ❌ **refusé** (voir ci-dessous) |
| 13 | 28 symboles exportés sans consommateur | ✅ 22 dé-exportés — `df42070` |
| 14 | docstring dupliquée | ✅ `df42070` |

**Trois écarts, et leurs raisons.**

- **n° 11 — `exit-code.mjs` a un test.** L'audit le dit « sans test » ;
  `scripts/exit-code.test.mjs` couvre la convention 128+n (SIGTERM → 143,
  SIGKILL → 137, code propagé, `null` → 0). Inliner `wrapperExitCode` dans
  `dev.mjs`, qui spawne un process, la rendrait intestable : on échangerait
  13 lignes contre une régression silencieuse possible sur un code de sortie.
- **n° 12 — la fusion coûte plus qu'elle ne rend.** `lib/utils/` compte douze
  modules mono-sujet (`date`, `season`, `splits`, `table`, `url`,
  `histogram-ticks`…). `event.ts` et `raceOrder.ts` suivent cette convention
  plutôt qu'ils ne l'enfreignent, et les fusionner churnerait huit sites
  d'import et deux fichiers de test pour −1 fichier et zéro ligne de logique.
  Le commentaire nécrologique de `raceOrder.ts` reste où il est.
- **n° 13 — 22 dé-exportés, pas 28.** `CourseBrief` a 22 consommateurs externes
  (l'audit le rangeait à tort parmi les internes), `PodiumScope` et
  `RosterEntry` en ont aussi. Seule mort réelle du lot : la ré-exportation
  d'`IconButton` par le barrel `components/tcn/index.ts` — le composant, lui,
  sert à `Modal`.

**Ce qui reste à trancher.** L'entrée n° 2 — sept primitives en double entre
`components/ui/` et `components/tcn/`, les deux versions activement utilisées.
La question posée par l'audit tient toujours : est-ce que `tcn/` absorbe les
primitives complexes (`dropdown-menu`, `select`), ou est-ce que `ui/` reçoit les
tokens `--tcn-*` ? Tant qu'elle n'a pas de réponse, chaque nouveau composant
repose l'arbitrage.

Note d'application : la suppression de la sentinelle `playwright` côté backend
(entrée n° 5 de l'audit backend) a aussi touché `ProviderDetector.tsx`, qui
déduisait le support de `provider !== "playwright"`. C'est dans `42afcfd`.
