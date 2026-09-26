# Parcours de lecture — contributeur frontend

Bienvenue. Ce parcours te fait ouvrir, dans l'ordre, les fichiers qui structurent
le front `data-triathlon`. Chaque étape est courte : ce qu'on voit, pourquoi
c'est structurant, et vers où pointer si tu veux creuser. Rien n'est dupliqué de
`AGENTS.md` — on y renvoie systématiquement.

Rappel de cadrage : ce tour cible un contributeur **frontend uniquement**
(Next.js, TypeScript, composants). Tu ne toucheras pas au backend Python. **Si
tu es en fait fullstack ou backend, arrête ici et relance `/onboard` avec le
bon profil** — un autre parcours te fera visiter FastAPI, les scrapers et la
CLI.

## 1. La stack en 30 secondes

Ouvre `AGENTS.md` (racine) et lis la puce **Frontend** de la section « Stack ».
Résumé : Next.js 16 (App Router) + TypeScript strict + Tailwind + shadcn/ui,
qui consomme le backend FastAPI sous `/api/v1`. Rien à installer côté Python
pour bosser sur le front — `npm run dev` (port 3000 ou le suivant libre)
suffit, avec le backend du worktree déjà lancé (`task b:dev`), dont il lit
le port dans `.dev-backend.json`.

## 2. AGENTS.md : les sections qui te concernent

Depuis `AGENTS.md`, lis en priorité :

- **Architecture frontend** — la carte de `frontend/app/`, `frontend/components/`
  et `frontend/lib/api/`. C'est ta table des matières.
- **Portée club et disciplines** — les deux paramètres transverses
  `scope=club` et `federal_only=true` que tu passeras aux endpoints de lecture.
  Comprends bien : ce sont **des choix du front**, pas des défauts imposés
  par l'API.

Le reste (backend, scrapers, CLI) est utile en survol mais n'est pas ton
terrain de jeu.

## 3. La constitution (`.specify/memory/constitution.md`)

Six principes non-négociables. Trois te concernent directement :

- **Principe I — Langue** : français pour tout ce qui est visible (UI,
  libellés, messages), English pour les identifiants, noms de tests, commits
  techniques, noms de fichiers. Un composant s'appelle `ResultCard.tsx`, son
  bouton affiche « Voir les résultats ».
- **Principe IV — Contrats API stables** : l'API est figée sous `/api/v1`.
  Tu ne négocies pas un changement de payload sans qu'une v2 soit décidée
  côté backend. En attendant, tu consommes ce que l'API rend.
- **Principe V — Neutralité des paramètres** : `scope`, `federal_only`,
  `seasons` ont un **défaut neutre** côté API. C'est le **front** qui les
  active (toggle « Inclure les autres disciplines », onglet « Club »). Ne
  jamais supposer un défaut « intelligent » de l'API.

## 4. La configuration Next.js — `frontend/next.config.ts`

Trois choses à comprendre :

- **Rewrites** : toute requête `/api/*` du front est redirigée vers
  `BACKEND_URL`, que `scripts/dev.mjs` injecte en dev depuis `.dev-backend.json`. Tu appelles donc
  `/api/v1/...` depuis ton code React comme si c'était local — Next.js proxifie.
- **`output: "standalone"`** : build autonome pour l'image Docker (déploiement
  Vercel-compatible aussi).
- **`BACKEND_URL`** : rien à régler en local. `npm run dev` la découvre depuis
  le `.dev-backend.json` publié par le backend du worktree ; ne la poser dans
  `frontend/.env.local` que pour viser délibérément un autre backend
  (`docs/dev-multi-worktree.md`).

## 5. App Router — la structure `frontend/app/`

Chaque sous-dossier est une route. Les pages de résultats vivent sous le
groupe `app/(public_restricted)/`, invisible dans l'URL et gardé par le code
d'accès du site (#509). Fais le tour rapide :

- `app/(public_restricted)/dashboard/` — page d'accueil du club : agrégats, KPIs, tendances.
- `app/(public_restricted)/resultats/` — liste des résultats avec filtres (recherche, sport, date).
- `app/(public_restricted)/athletes/[id]/` — fiche athlète (route dynamique).
- `app/(public_restricted)/courses/[id]/` — fiche épreuve avec le classement.
- `app/(public_restricted)/club/` — vue club (podiums, composition, saison en cours).
- `app/(public_restricted)/carte/` — carte Leaflet des épreuves géolocalisées.
- `app/(public_restricted)/ajouter/` — formulaire d'import (colle une URL → SSE).
- `app/admin/` — outils d'administration (import de masse, providers en attente), hors du groupe.
- `app/api/cron/keep-warm/` — seule route API Next : le proxy `/api/*` est un rewrite.
- `app/layout.tsx` — chrome commun (nav, providers React Query, thèmes).
- `app/providers.tsx` — contextes globaux (React Query, next-themes).

Ouvre **deux** pages représentatives pour prendre le pli :

- `app/(public_restricted)/dashboard/page.tsx` — agrégats avec toggles (scope, federal_only).
- `app/(public_restricted)/resultats/page.tsx` — liste + filtres.

## 6. Le client API — `frontend/lib/api/client.ts`

C'est **le** point d'entrée unique vers `/api/v1`. Tu y trouveras un
`apiClient` qui expose des fonctions typées (`detectProvider`, `importEvent`,
`listEvents`, `getAthlete`, `getStats`, …). Convention : chaque fonction
retourne un DTO importé de `lib/types.ts`, jamais un `any`.

Quand tu ajoutes un nouvel appel, tu suis le même patron : une fonction dans
`apiClient`, un type de retour dans `lib/types.ts`, aucun `fetch` sauvage
ailleurs dans le code.

Note : `frontend/lib/api/server.ts` existe pour les Server Components (fetch
côté serveur au rendu) — même convention, contexte différent.

## 7. Le streaming SSE — `frontend/lib/api/sse.ts`

C'est ce qui alimente la barre de progression de l'import en direct. Le
backend expose un endpoint qui pousse un flux d'événements (une phase par
étape : `starting`, `parsing`, `writing`, `done`, `error`), et le front les
consomme via un `AsyncGenerator<ImportProgressEvent>`. Regarde le fichier —
il fait 35 lignes, le pattern est court.

Côté serveur, la logique est dans `import_service.iter_import_event()` (cité
dans `backend/app/cli/AGENTS.md`) — tu n'ouvres pas ce fichier, mais
tu sais qu'un nouveau champ dans le stream demande une coordination avec un
contributeur backend.

## 8. Les types partagés — `frontend/lib/types.ts`

Les DTOs TypeScript qui reflètent les schémas Pydantic backend :
`AthleteDetail`, `CourseDetail`, `EventPage`, `Participation`, `Stats`,
`ImportProgressEvent`, `PendingProvider`, `ScrapedPreview`, `Season`, etc.

Une leçon structurante (issue #76, voir `AGENTS.md` § « Portée club et
disciplines ») : le champ `is_tcn` d'un DTO est **calculé côté backend**
par `app/core/club.py`. Tu le **consommes** — tu ne le recalcules **pas**
en front à partir du nom du club. Le jour où trois listes se contredisent,
c'est le front qui commence à mentir. Passe par `scope=club` à l'endpoint
si tu veux filtrer.

## 9. Les composants — `frontend/components/`

Organisation par domaine :

- `components/ui/` — briques shadcn/ui (bouton, card, table, dialog…). Tu les
  utilises ; tu n'en ajoutes que si shadcn n'en propose pas.
- `components/scrape/` — `TcnScrapeForm` (import par URL, progression SSE
  comprise), `ProviderDetector`, `ManualResultForm`.
- `components/results/` — `ResultCard`, `EventList`, `RaceFinishers`,
  `ResultsFilters`, `SportBadge`, `StatusBadge`.
- `components/club/` — `ClubDashboard`, `PodiumsList`, `ClubComposition`,
  `RosterApercu`.
- `components/dashboard/` — `StatCardsRank`, `MaSaison`, `RecentCourses`,
  `SeasonSelector`.
- `components/map/` — `MapView` (Leaflet, chargement dynamique côté client).
- `components/charts/` — `BarList`, `MonthlyTrend`.
- `components/admin/`, `components/tcn/`, `components/layout/` — utilitaires.

## 10. Un composant caractéristique

Deux choix — ouvre au moins l'un :

- `frontend/hooks/useImportStream.ts` — consomme `importEventStream()`
  (`lib/api/sse.ts`) par un `for await`, et `TcnScrapeForm` en rend l'état.
  C'est le pattern de référence pour tout futur composant qui doit lire un
  stream.
- `frontend/components/dashboard/StatCardsRank.tsx` — rend les agrégats de
  `/api/v1/stats` que la page demande avec `scope` et `federal_only` explicites.
  Bon exemple de la « neutralité par défaut » du Principe V appliquée depuis
  l'UI.

## 11. Les tests — Vitest + React Testing Library

Convention : `*.test.tsx` à côté du composant (ex :
`components/results/ResultCard.test.tsx`, `components/scrape/TcnScrapeForm.test.tsx`).
Setup dans `frontend/test/` et `frontend/vitest.config.ts`.

Commandes (depuis `frontend/`) :

- `npm test` — Vitest run (mode CI, non-watch).
- `npm run test:watch` — mode watch pour le développement.
- `npm run build` — build de production, valide le TypeScript strict et le RSC.
- `npm run lint` — ESLint.

Le TDD (Principe III) vaut aussi pour toi : test rouge → composant → vert.

## 12. Contrats API consommés — la référence courte

Sous forme de contrat (méthode + chemin + payload attendu). Pas de code Python
à lire ; ces contrats sont figés par le Principe IV.

- `GET /api/v1/stats?scope=club&federal_only=true`
  → agrégats du dashboard : compteurs, `by_type`, `by_month`, `recent`.
- `GET /api/v1/courses?…` — liste paginée d'épreuves avec filtres
  (nom, type, date, saison).
- `GET /api/v1/athletes/{id}` — fiche athlète (participations, meilleurs
  temps, palmarès).
- `GET /api/v1/courses/{id}` — fiche course avec classement complet.
- `POST /api/v1/scrape/detect?url=…` — détection du provider depuis une URL.
- `POST /api/v1/scrape/event` — import synchrone (retourne un `ImportResult`).
- `POST /api/v1/scrape/event/stream` — import SSE (retourne un flux
  d'`ImportProgressEvent`).

Rappel Principe IV : ces endpoints sont versionnés `/api/v1`. Un changement
de sémantique motive une v2, jamais une modif silencieuse.

## 13. Déploiement

Le front tourne sur Vercel. Deux variables d'environnement à connaître :
`BACKEND_URL` (utilisée par les rewrites Next.js côté serveur) et `API_URL`
(pour les Server Components). Détails dans le `README.md` racine.

## 14. Et maintenant ?

Deux ressources pour enchaîner :

- `docs/WORKFLOW-IA.md` — les trois voies : Speckit (`/speckit-specify` …
  `/speckit-implement`), Superpowers (`brainstorming` → `writing-plans` →
  exécution), ou « sans plan » (bugfix, typo, un ou deux fichiers). Les deux
  premières ne se croisent jamais.
- Une première contribution accessible : ajouter un filtre à
  `app/resultats/page.tsx` (par sport, par saison), ou un composant graphique
  dans `frontend/components/charts/` (ex : répartition par distance).

Lance `/speckit-specify` avec un énoncé court en français si tu veux passer
par le cycle guidé, ou `git checkout -b fix/…` directement pour un bugfix
minimal. Bon voyage.
