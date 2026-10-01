# Analytics produit — PostHog

Deux sources écrivent dans le même projet PostHog, cloud **EU** (`eu.posthog.com`,
choix RGPD : les données restent en zone UE) : le **frontend** (#339) et le
**backend** (`backend/app/core/analytics.py`). Un même geste n'est émis que par
l'une des deux : le serveur quand l'événement mesure une opération persistée,
qu'il compte une seule fois et hors de portée des bloqueurs (#1033).

## Câblage frontend

- **Init** — `frontend/instrumentation-client.ts` (hook Next.js dédié, tourne
  avant tout rendu client). Sans `NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN` /
  `NEXT_PUBLIC_POSTHOG_HOST`, `posthog.init()` ne se lance pas : l'app tourne
  normalement, juste sans analytics — et **sans rien logguer**, l'absence de
  variable étant un réglage attendu, pas une erreur (#426). Variables et valeurs :
  `docs/ci-cd.md`.
- **Seule la production est instrumentée.** Le local (variables vides par défaut
  dans `.env.local.example`) et la **preview** (variables non saisies sur le
  projet Vercel `data-triathlon-preview`) n'envoient aucun événement : il
  n'existe qu'un projet PostHog, et y mélanger le trafic de test fausserait les
  statistiques du club. C'est ce qu'a tranché #426, contre son propre titre — le
  constat de départ prenait l'absence de variable en preview pour un oubli de
  configuration.
- **Proxy** — `frontend/next.config.ts` route `/ingest/*` vers PostHog EU au
  lieu d'appeler `eu.i.posthog.com` en direct depuis le navigateur : les
  bloqueurs de pub ciblent le domaine PostHog, pas le domaine du site.
- **Consentement** (#1159) : sans accord, PostHog mesure **sans cookie**
  (`cookieless_mode: "on_reject"`, `opt_out_capturing_by_default`), sans
  autocapture ni `identify()` : la mesure exemptée de consentement par la CNIL.
  `AnalyticsConsentBanner` (layout racine) propose la mesure détaillée ; le
  choix vit dans `localStorage` (`tcn-analytics-consent`, six mois,
  `lib/analytics-consent.ts`) et se change depuis `/confidentialite`. Un accord
  donné en cours de visite ouvre les cookies tout de suite, l'autocapture au
  chargement suivant. **Prérequis** : le mode sans cookie doit être activé dans
  les réglages du projet PostHog, sinon les événements sans cookie sont
  ignorés.
- **Identité de session** : `frontend/app/providers.tsx` (`PostHogSessionSync`).
  Un seul effet observe `useSession()` : `posthog.identify()` dès qu'une
  session existe **et que la mesure détaillée est acceptée**, `posthog.reset()` dès qu'elle repasse à `null` — quelle
  qu'en soit la cause (déconnexion explicite, 401, expiration, révocation
  admin). Centraliser ici plutôt que dans le bouton « Se déconnecter » est ce
  qui couvre les sorties de session qui ne passent pas par ce bouton.
- **Capture** — `frontend/lib/posthog.ts` (`captureEvent`) enveloppe
  `posthog.capture()` d'une garde sur le token, pour ne pas dupliquer ce `if`
  à chaque site d'appel ni laisser `posthog-js` logguer un `console.error` par
  clic quand les variables d'env manquent.

## Câblage backend

- **Init** : `init_posthog`, appelé dans le lifespan de `backend/app/main.py` à
  partir de `POSTHOG_PROJECT_TOKEN`. Vide, aucune capture ne part, sans erreur.
  **Production seule**, comme côté Vercel : la variable reste vide sur le service
  Render de preview (`docs/ci-cd.md`).
- **Capture** : `capture_event(event, distinct_id=…, properties=…)`. Le
  `distinct_id` est `str(user.id)`, le même identifiant que le
  `posthog.identify()` du front, ou `ANONYMOUS_DISTINCT_ID` (`"anonymous"`) sans
  session.
- **Autocapture d'exceptions** : `enable_exception_autocapture=True` (produit
  « Error Tracking ») : toute exception non gérée part avec sa trace complète
  vers le cloud EU. Les `DomainError`, gérées, n'y arrivent jamais. Le choix et
  son risque résiduel sont documentés dans `backend/app/core/analytics.py`.

## Événements suivis

Premier jet d'instrumentation — la liste des événements métier à suivre reste
à affiner avec le club (hors périmètre de #339).

### Frontend (`frontend/`)

| Événement | Où | Props |
|---|---|---|
| `login_initiated` | `app/login/page.tsx` | `provider` |
| `results_import_started` | `components/scrape/TcnScrapeForm.tsx` | `url` |
| `results_import_failed` | idem | `error_message` |
| `results_import_completed` | idem | `imported_count`, `skipped_count`, `course_count` |
| `manual_result_submitted` | `components/scrape/ManualResultForm.tsx` | `event_type` |
| `season_changed` | `components/dashboard/SeasonSelector.tsx` | `season_count`, `seasons` |
| `results_filter_applied` | `components/results/ResultsFilters.tsx` | `filter_count`, `has_*_filter` |
| `error_screen_shown` | `components/tcn/ErrorScreen.tsx` | `digest` |

### Backend (`backend/app/api/v1/`)

| Événement | Où | Props |
|---|---|---|
| `user_logged_in` | `auth.py` | `provider` |
| `user_logged_out` | `auth.py` | — |
| `feedback_submitted` | `feedback.py` | `feedback_type`, `has_page_url`, `is_authenticated` |
| `event_scraped` | `scrape.py` | `provider`, `imported`, `updated`, `skipped` |
| `participation_created` | `participations.py` | `event_type`, `is_relay` |
| `participation_deleted` | `participations.py` | `participation_id` |
| `participation_reassigned` | `admin_data.py` | `participation_id` |
| `participation_teammates_set` | `admin_data.py` | `participation_id`, `teammates` |
| `course_deleted` | `admin_data.py` | `course_id` |
| `athlete_updated` | `admin_data.py` | `fields_changed` |
| `course_source_deleted` | `admin_course_sources.py` | `course_id`, `source_id` |
| `batch_launched` | `admin_batches.py` | `mode`, `dry_run`, `has_limit` |
| `batch_launched_from_file` | `admin_batches.py` | `url_count`, `dry_run` |

`feedback_submitted` et `user_logged_out` partaient aussi du front : chaque
envoi et chaque déconnexion comptaient double. Seul l'émetteur serveur reste
(#1033).

`url` et `error_message` (import) sont déjà visibles ailleurs — l'URL part au
backend via `reportPendingProvider`, l'erreur est déjà affichée à l'écran
(toast + Alert). Aucune PII athlète dans ces 21 événements : le scraping
mono-athlète a été retiré, seul l'import d'épreuve complète existe, et
`athlete_updated` ne porte que les **noms** des champs modifiés.

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
