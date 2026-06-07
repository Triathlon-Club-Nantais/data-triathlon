# Spec & Plan d'implémentation — frontend-v2 (Next.js / shadcn/ui / Tailwind)

> Design validé le 2026-06-07. Cible : nouveau frontend `frontend-v2/` en Next.js
> (App Router) + TypeScript + Tailwind + shadcn/ui, consommant l'API **backend-v2**
> versionnée (`/api/v1`, modèle normalisé Athlete/Course/Participation).

---

## 1. Contexte

Le frontend actuel (`frontend/`, ~2 100 lignes) est en React 18 + Vite, **JSX sans
TypeScript**, sans lib UI, sans routing URL (navigation par `useState`), avec du
prop drilling sur 3 niveaux et des utilitaires dupliqués (cf. `ARCHITECTURE-REVIEW.md`
Axe 4). Il cible l'**ancienne** API (`/api/results`, modèle `Result` plat).

Le backend a été refondu (`backend-v2/`) : API **versionnée `/api/v1`**, modèle
**normalisé** (participations imbriquant athlète + course, `splits` JSON). Le contrat
API change → le frontend doit être réécrit, pas porté.

## 2. Décisions validées

- **Langage** : TypeScript (types des réponses API v1).
- **Rendu / data** : **hybride** — Server Components (RSC) pour les pages en lecture
  (listes, fiches), Client Components + **TanStack Query** pour l'interactif
  (formulaires, import SSE, feed polling, mutations).
- **Périmètre** : parité complète — Ajouter (scrape + import SSE + saisie manuelle),
  Résultats + fiches athlète/course (deep-links), Club + Dashboard + live feed,
  Carte des épreuves.
- **Emplacement** : nouveau dossier `frontend-v2/` ; `frontend/` reste déprécié.
- **Déploiement** : Vercel.

## 3. Stack cible

| Domaine | Choix |
|---------|-------|
| Framework | **Next.js 15** (App Router, React 19) |
| Langage | **TypeScript** strict |
| Style | **Tailwind CSS** (config via `shadcn init`) |
| Composants | **shadcn/ui** (Radix + Tailwind), icônes `lucide-react` |
| Data serveur | TanStack Query v5 (cache, mutations, polling) côté client |
| Formulaires | `react-hook-form` + `zod` + `@hookform/resolvers` |
| Thème | `next-themes` (clair/sombre) |
| Toasts | `sonner` (intégré shadcn) |
| Carte | `react-leaflet` + `leaflet` en **client-only** (`dynamic(..., { ssr:false })`) |
| Tests | `vitest` + `@testing-library/react` + `jsdom` (unitaires/composants) |
| Package manager | `npm` (cohérent avec l'existant) |

## 4. Cible API & contrats TypeScript

Base : `/api/v1`. Endpoints consommés (cf. backend-v2) :

| Usage | Endpoint |
|-------|----------|
| Preview scrape athlète | `POST /scrape` → `ScrapedPreview` |
| Détection provider | `GET /scrape/detect?url=` |
| Import épreuve (bloquant) | `POST /scrape/event` → `{imported, skipped, cached}` |
| Import épreuve (SSE) | `POST /scrape/event/stream` (flux `data:` JSON) |
| Sauver un résultat | `POST /participations` → `ParticipationOut` |
| Liste résultats (filtres) | `GET /participations?name&event_type&club&date_from…&page` |
| Détail / suppression | `GET` / `DELETE /participations/{id}` |
| Recherche athlète | `GET /athletes?name&club` ; fiche `GET /athletes/{id}` |
| Courses / épreuves | `GET /courses`, `/courses/{id}`, `/courses/events` |
| Stats | `GET /stats?club` ; carte `GET /stats/events-geo?club` |
| Admin providers | `POST/GET/DELETE /admin/pending-providers` |

Types TS dans `lib/types.ts` (miroir des schémas Pydantic) :

```ts
export interface AthleteBrief { id: number; nom: string; prenom: string; gender: string; club: string | null }
export interface CourseBrief { id: number; name: string; event_date: string | null; event_type: string;
  provider: string; source_url: string; is_relay: boolean }
export interface Participation { id: number; athlete: AthleteBrief; course: CourseBrief;
  club: string | null; category: string | null; bib_number: string | null;
  rank_overall: number | null; rank_category: number | null; rank_gender: number | null;
  total_time: string | null; status: string; splits: Record<string,string> | null; created_at: string | null }
export interface EventOut { event_name: string; event_date: string | null; event_type: string; total: number; tcn_count: number }
export interface ScrapedPreview { /* shape plat : athlete_name, swim_time… + multiple_matches?: candidats */ }
```

> **Changement clé vs ancien front** : un résultat n'est plus plat. `ResultCard` lit
> `p.athlete.nom`, `p.course.name`, `p.course.event_date`, et **`p.splits`** (dict
> segment→temps) au lieu des champs `swim_time/t1_time/…`.

## 5. Architecture (App Router)

```
frontend-v2/
  app/
    layout.tsx            # <Providers> (QueryClient, ThemeProvider) + <AppHeader>
    page.tsx              # redirect → /dashboard
    ajouter/page.tsx      # (client) scrape + preview + save + import SSE + saisie manuelle
    resultats/page.tsx    # (RSC) liste + filtres (searchParams) ; groupes par épreuve (client)
    athletes/[id]/page.tsx# (RSC) fiche athlète + participations
    courses/[id]/page.tsx # (RSC) fiche course + participants
    club/page.tsx         # (RSC initial + client) stats club, timeline, modal athlète
    dashboard/page.tsx     # (RSC KPIs) + <LiveFeed> (client, polling 15 s)
    carte/page.tsx        # (client-only) carte Leaflet des épreuves géocodées
    admin/page.tsx        # (RSC/client) providers signalés
  components/
    ui/                   # primitives shadcn (button, card, table, dialog, badge, form…)
    layout/AppHeader.tsx  # nav (liens), recherche globale (Command), filtre club, switch thème
    results/ResultCard.tsx, EventGroup.tsx, SportBadge.tsx
    scrape/ScrapeForm.tsx, ImportProgress.tsx (SSE), ManualResultForm.tsx, ProviderDetector.tsx
    club/ClubStats.tsx, AthleteDialog.tsx
    dashboard/Kpis.tsx, LiveFeed.tsx
    admin/PendingProvidersTable.tsx
  lib/
    api/server.ts         # fetch côté RSC (API_URL absolu, cache: 'no-store' où requis)
    api/client.ts         # fetch côté navigateur (rewrite /api → backend)
    api/sse.ts            # importEventStream (lecture ReadableStream → AsyncGenerator)
    types.ts, constants.ts (18 types d'épreuves + labels, depuis l'ancien constants.js)
    queries/              # hooks TanStack : useParticipations, useStats, useImportEvent…
    utils/ date.ts, time.ts, club.ts (isTCN), splits.ts (ordre des segments par sport)
  hooks/ useImportStream.ts, useDebounce.ts
  next.config.ts          # rewrites /api/:path* → backend (dev + prod)
  components.json (shadcn), tailwind config, tsconfig, .env.local.example
  __tests__/ ou *.test.tsx
```

## 6. Mapping fonctionnalités → shadcn

| Vue actuelle | frontend-v2 |
|--------------|-------------|
| `App.jsx` (onglets useState) | `app/layout.tsx` + **routes URL réelles** (deep-link, retour navigateur) |
| Recherche globale | `Command` (cmdk) dans le header → `/resultats?name=` |
| Filtre club (localStorage) | toggle persisté en **cookie** (lisible côté RSC) |
| `ScrapeForm` (612 lignes) | découpé : `ProviderDetector` + `ScrapeForm` + `ImportProgress` + `ManualResultForm` (`react-hook-form`+`zod`) |
| Bandeau SSE | `ImportProgress` avec `Progress` (hook `useImportStream`) |
| `ResultsList`/`EventGroupList` | `EventGroup` (`Accordion`/`Collapsible`) + `Table` + `Badge` + pagination |
| `ResultCard` | `Card` + `Badge`, splits adaptatifs depuis `p.splits` |
| `ClubView` (390 l.) | `ClubStats` (Cards/Tabs) + `AthleteDialog` (`Dialog`) |
| `DashboardView` + `ResultsFeed` | `Kpis` (Cards) + `LiveFeed` (client, `useQuery` `refetchInterval: 15000`) |
| `AdminView` | `PendingProvidersTable` (`Table` + `Button`) |
| `EventHeatmap` (Leaflet) | `app/carte` via `react-leaflet` chargé dynamiquement (`ssr:false`) |

## 7. Couches data

- **RSC** (`lib/api/server.ts`) : `fetch(`${API_URL}/participations…`)` côté serveur,
  `cache: 'no-store'` pour les données vivantes, ou `revalidate` court sinon.
- **Client** (`lib/api/client.ts`) : passe par les **rewrites Next** (`/api/v1/*` →
  backend) ; pas de CORS en dev.
- **TanStack Query** : hooks typés (`useParticipations(filters)`, `useStats(club)`,
  `useImportEvent()`…), mutations avec invalidation (`POST /participations` → invalide
  les listes), `LiveFeed` via `refetchInterval`.
- **SSE** (`lib/api/sse.ts`) : portage de l'`importEventStream` actuel (lecture
  `res.body.getReader()` → `AsyncGenerator`), consommé par `useImportStream` (client).
- **Filtres** = `searchParams` d'URL (partageables, compatibles RSC), pas de state global.

## 8. Plan d'implémentation (phasé)

1. **Scaffold & socle** : `create-next-app` (TS, Tailwind, App Router) ; `shadcn init` ;
   `Providers` (QueryClient + ThemeProvider) ; `next.config` rewrites ; `.env.local` ;
   `lib/types.ts`, `lib/api/{server,client}.ts`, `constants.ts` (ports). Layout + header nu.
2. **Design system & partagés** : header (nav, recherche `Command`, filtre club cookie,
   switch thème), `SportBadge`, `ResultCard`, `EventGroup`, utils (date/time/club/splits).
3. **Ajouter** : `ProviderDetector` + `ScrapeForm` (preview→édition→save) + `ImportProgress`
   (SSE) + `ManualResultForm` (zod). Déclenche l'import épreuve en arrière-plan après save.
4. **Résultats + deep-links** : `/resultats` (RSC liste + filtres URL, groupes client) ;
   pages `/athletes/[id]` et `/courses/[id]` (RSC).
5. **Club + Dashboard + feed** : `/club` (stats, timeline, `AthleteDialog`) ; `/dashboard`
   (KPIs RSC + `LiveFeed` polling) .
6. **Carte** : `/carte` `react-leaflet` client-only sur `/stats/events-geo`.
7. **Finitions** : skeletons/loading.tsx, error.tsx, toasts (`sonner`), responsive mobile,
   a11y (Radix), tests Vitest+RTL (composants critiques : `ResultCard` splits, filtres,
   parsing SSE), `README`, config Vercel. Déprécier `frontend/`.

> Exécution recommandée via le workflow **feature complète** de `docs/WORKFLOW-IA.md`
> (Speckit cadre/planifie, Superpowers exécute en TDD), comme pour backend-v2.

## 9. Tests & vérification

- **Unitaires/composants** (Vitest + RTL) : rendu des splits adaptatifs par sport
  (`p.splits`), construction des filtres URL, parsing du flux SSE, `isTCN`.
- **Manuel end-to-end** : lancer backend-v2 (`uvicorn app.main:app --port 8001`) +
  `npm run dev` (port 3000, rewrites → 8001) ; parcourir : saisie manuelle → apparait
  dans `/resultats` → fiche athlète → stats club → dashboard → carte.
- **Build** : `npm run build` (vérifie le typage strict et le rendu RSC).
- (Option) smoke Playwright sur les parcours clés.

## 10. Déploiement (Vercel) & CORS backend

- Vercel : projet pointant sur `frontend-v2/`. Variables : `API_URL` (RSC, URL interne
  backend Render) et `NEXT_PUBLIC_API_URL`/rewrites pour le client.
- **CORS backend-v2** : ajouter le domaine Vercel à `CORS_ORIGINS` (déjà configurable
  via `Settings`). En dev, les rewrites Next évitent le CORS.

## 11. Hors scope / risques

- **Auth** : aucune (MVP), comme aujourd'hui.
- **Tailwind v4 vs v3** : suivre ce que génère `shadcn init` à l'install (v4 par défaut).
- **Leaflet + SSR** : impérativement client-only (`ssr:false`) pour éviter les erreurs
  d'hydratation (icônes via CDN comme dans l'ancien `EventHeatmap`).
- **Contrat API** : dépend de backend-v2 déployé sous `/api/v1`. Garder les types TS
  alignés sur les schémas Pydantic (source de vérité).
- **i18n** : interface en **français** (accents) — convention projet conservée.
```
