# Analytics produit — PostHog

Intégré côté `frontend/` uniquement (#339). Cloud **EU** (`eu.posthog.com`) — choix
RGPD, les données restent en zone UE.

## Câblage

- **Init** — `frontend/instrumentation-client.ts` (hook Next.js dédié, tourne
  avant tout rendu client). Sans `NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN` /
  `NEXT_PUBLIC_POSTHOG_HOST`, `posthog.init()` ne se lance pas : l'app tourne
  normalement, juste sans analytics — utile en local, où ces variables restent
  vides par défaut (`.env.local.example`). Variables et valeurs en prod/preview :
  `docs/ci-cd.md`.
- **Proxy** — `frontend/next.config.ts` route `/ingest/*` vers PostHog EU au
  lieu d'appeler `eu.i.posthog.com` en direct depuis le navigateur : les
  bloqueurs de pub ciblent le domaine PostHog, pas le domaine du site.
- **Identité de session** — `frontend/app/providers.tsx` (`PostHogSessionSync`).
  Un seul effet observe `useSession()` : `posthog.identify()` dès qu'une
  session existe, `posthog.reset()` dès qu'elle repasse à `null` — quelle
  qu'en soit la cause (déconnexion explicite, 401, expiration, révocation
  admin). Centraliser ici plutôt que dans le bouton « Se déconnecter » est ce
  qui couvre les sorties de session qui ne passent pas par ce bouton.
- **Capture** — `frontend/lib/posthog.ts` (`captureEvent`) enveloppe
  `posthog.capture()` d'une garde sur le token, pour ne pas dupliquer ce `if`
  à chaque site d'appel ni laisser `posthog-js` logguer un `console.error` par
  clic quand les variables d'env manquent.

## Événements suivis

Premier jet d'instrumentation — la liste des événements métier à suivre reste
à affiner avec le club (hors périmètre de #339).

| Événement | Où | Props |
|---|---|---|
| `login_initiated` | `app/login/page.tsx` | `provider` |
| `user_logged_out` | `components/auth/UserMenu.tsx` | — |
| `results_import_started` | `components/scrape/TcnScrapeForm.tsx` | `url` |
| `results_import_failed` | idem | `error_message` |
| `results_import_completed` | idem | `imported_count`, `skipped_count`, `course_count` |
| `manual_result_submitted` | `components/scrape/ManualResultForm.tsx` | `event_type` |
| `season_changed` | `components/dashboard/SeasonSelector.tsx` | `season_count`, `seasons` |
| `results_filter_applied` | `components/results/ResultsFilters.tsx` | `filter_count`, `has_*_filter` |
| `feedback_submitted` | `components/tcn/FeedbackButton.tsx` | `feedback_type` |

`url` et `error_message` (import) sont déjà visibles ailleurs — l'URL part au
backend via `reportPendingProvider`, l'erreur est déjà affichée à l'écran
(toast + Alert). Aucune PII athlète dans les 8 événements : le scraping
mono-athlète a été retiré (voir mémoire projet), seul l'import d'épreuve
complète existe.

`login_initiated` seul a besoin d'un transport spécial
(`{ transport: "sendBeacon", send_instantly: true }`) : le clic déclenche une
navigation `<a href>` immédiate vers le backend, qui court-circuiterait la
file batchée par défaut de `posthog-js`.

## Self-driving (hors scope #339)

PostHog propose une couche d'ops automatisée (scouts, Replay Vision, inbox de
signaux) au-delà du simple SDK. Sa configuration a été posée via l'assistant
PostHog et documentée dans `docs/local/posthog-self-driving-report.md`
(gitignoré — état d'un dashboard externe, pas une contractuelle du dépôt ;
régénérable en relançant l'assistant PostHog si besoin).
