# Analytics produit — PostHog

Deux sources écrivent dans le même projet PostHog, cloud **EU** (`eu.posthog.com`,
choix RGPD : les données restent en zone UE) : le **frontend** (#339) et le
**backend** (`backend/app/core/analytics.py`). Un même geste n'est émis que par
l'une des deux : le serveur quand l'événement mesure une opération persistée,
qu'il compte une seule fois et hors de portée des bloqueurs (#1033).

## Câblage frontend

- **Init** — `frontend/lib/posthog.ts`, déclenché par
  `frontend/instrumentation-client.ts` (hook Next.js dédié, tourne avant tout
  rendu client) au repos du navigateur. **`posthog-js` n'est jamais importé
  statiquement** (#1394) : ~100 Ko gzip partaient dans le JS initial de chaque
  page, preview comprise. `withPostHog` le charge par `import()` et l'initialise
  une fois ; un appel antérieur attend l'init, dans l'ordre d'émission, puis
  tout appel devient synchrone. `lib/posthog.test.ts` échoue sur tout import
  de valeur depuis `posthog-js` (`import type` reste permis). Le cookie
  d'accord (`syncConsentCookie`), lui, se pose toujours au chargement, sans
  attendre la bibliothèque. Prix accepté de l'init différée (3 s au plus) :
  une exception levée avant elle, hydratation comprise, échappe à Error
  Tracking, et une visite partie avant elle ne compte pas de page vue. Les web
  vitals, lus en `buffered`, ne perdent rien. Un accord donné avant l'init
  ouvre l'autocapture tout de suite. `/login` charge la bibliothèque dès son
  affichage : chargée au clic, `login_initiated` partirait après la navigation.
  Sans `NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN` /
  `NEXT_PUBLIC_POSTHOG_HOST`, `posthog-js` n'est pas téléchargé : l'app tourne
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
- **Écrans jeunes** (#1307) : sous `/encadrement/jeunes`, le `before_send` de
  `lib/posthog.ts` jette tout événement dont les propriétés portent
  un élément (`$elements`, `$elements_chain` ou `$el_text` : clics, clics
  morts, glissés morts, et ceux qu'une version future de posthog-js ajoutera),
  ainsi que `$copy_autocapture` (texte copié) et `$exception` (un message
  d'erreur peut citer un nom). Le tri suit la forme de l'événement, pas une
  liste de noms. Pages vues, événements métier et cartes de chaleur (des
  coordonnées, sans texte) restent mesurés.
- **URL sans query string ni fragment** (#1530) : le même `before_send` coupe
  `?…` et `#…` de toute propriété dont la clé finit par `url` ou `referrer`, à
  toute profondeur : `$current_url`, `$referrer`, leurs copies `$initial_*`
  (`$set_once`) et `$session_entry_*`, `$external_click_url`, et dans les web
  vitals `$current_url`, `navigationURL` et `attribution.url`. Il en va de
  même des clés finissant par `href` (`attr__href` d'un lien cliqué, relatif
  compris), `filename` et `abs_path` (trace d'exception), des `href="…"` de
  `$elements_chain`, et des clés de `$heatmap_data` (une URL par page), dont
  les points sont fusionnés. Raison : `ResultsFilters` met `name=<athlète>` dans l'URL de
  `/resultats`, `RaceFinishers` la recherche `q=`. **Aucun paramètre n'est
  gardé**, même non identifiant (`seasons`, `scope`, `rank`) : une liste
  blanche se tient à la main et un paramètre ajouté plus tard fuirait par
  défaut ; le choix de saisons a déjà son événement (`season_changed`).
  `$pathname` reste entier : ses identifiants (`/athletes/123`,
  `/encadrement/jeunes/7`) sont des clés numériques opaques, sans nom, que seul un
  accès à l'application relie à une personne, et l'analyse par écran en a
  besoin. Les paramètres de campagne (`utm_*`, `gclid`…) que posthog-js lit
  dans l'URL restent : le club n'en émet pas. Le replay est coupé
  (`disable_session_recording`), rien à y filtrer.
- **Identité de session** : `frontend/app/providers.tsx` (`PostHogSessionSync`).
  Un seul effet observe `useSession()` : `posthog.identify()` dès qu'une
  session existe **et que la mesure détaillée est acceptée**, `posthog.reset()` dès qu'elle repasse à `null` — quelle
  qu'en soit la cause (déconnexion explicite, 401, expiration, révocation
  admin). Centraliser ici plutôt que dans le bouton « Se déconnecter » est ce
  qui couvre les sorties de session qui ne passent pas par ce bouton.
- **Capture** — `frontend/lib/posthog.ts` (`captureEvent`) passe
  `posthog.capture()` par `withPostHog`, donc par la garde sur le token, pour ne pas dupliquer ce `if`
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
- **Consentement côté serveur** (#1359) : le backend ne lit pas `localStorage`.
  Le front recopie l'accord dans le cookie technique `tcn_analytics_consent`
  (`granted`, expire avec l'accord, `syncConsentCookie` de `lib/analytics-consent.ts`,
  appelé à chaque choix et au chargement), qui accompagne toute requête
  `/api/*` puisque le rewrite Next la sert sur la même origine, retour de
  connexion compris. `AnalyticsConsentMiddleware` le lit une fois par requête ;
  sans la valeur `granted`, `capture_event` remplace tout `distinct_id` par
  `ANONYMOUS_DISTINCT_ID` et `set_person_properties` n'envoie rien. La garde
  vit dans ces deux fonctions, pas aux sites d'appel : une route ajoutée plus
  tard en hérite. Hors requête (tâche de fond, CLI), aucun accord n'est connu,
  donc tout part anonyme. Un appel direct au backend Render, sans le cookie,
  reste anonyme lui aussi.
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
| `results_import_started` | `components/scrape/TcnScrapeForm.tsx` | `provider` |
| `results_import_failed` | idem, et `ImportStreamProvider.tsx` écran démonté | `reason` |
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
| `event_scraped` | `scrape.py` | `provider`, `imported`, `updated`, `skipped`, `cached` |
| `event_scrape_failed` | `scrape.py` (SSE) | `provider`, `error_kind` |
| `participation_created` | `participations.py` | `event_type`, `is_relay` |
| `participation_deleted` | `participations.py` | `participation_id` |
| `participation_reassigned` | `admin_data.py` | `participation_id` |
| `participation_teammates_set` | `admin_data.py` | `participation_id`, `teammates` |
| `course_deleted` | `admin_data.py` | `course_id` |
| `athlete_updated` | `admin_data.py` | `fields_changed` |
| `course_source_deleted` | `admin_course_sources.py` | `course_id`, `source_id` |
| `batch_launched` | `admin_batches.py` | `mode`, `dry_run`, `has_limit` |
| `batch_launched_from_file` | `admin_batches.py` | `url_count`, `dry_run` |

**Issue d'un import** (#1367) : `event_scraped` part des deux routes d'import,
la bloquante et le flux SSE (celle de l'interface), `event_scrape_failed` du
flux SSE seul, une fois par import, d'où un taux d'échec par chronométreur.
`provider` est le slug du registre (vide si aucun ne reconnaît l'URL), jamais
l'URL. `error_kind` vaut `invalid_url`, `unsupported_provider`, `scraper`,
`persistence` ou `unexpected`, jamais le message, qui peut citer une URL ou un
nom. `cached` signale un court-circuit du cache TTL, qui n'a rien scrapé et
ne compte donc pas dans un taux de succès. Les deux événements du flux SSE
partent toujours sous
`ANONYMOUS_DISTINCT_ID`, accord donné ou non : le travail tourne dans le thread
de `sse_relay`, hors du contexte de la requête où l'accord a été lu. Côté front,
`results_import_failed` part une seule fois par import, écran monté ou non
(`ImportStreamProvider.test.tsx`).

`feedback_submitted` et `user_logged_out` partaient aussi du front : chaque
envoi et chaque déconnexion comptaient double. Seul l'émetteur serveur reste
(#1033).

**Ni URL brute ni message libre dans une propriété** (#1528) : l'URL peut
porter une query string, le message d'erreur citer une URL ou un nom.
`results_import_started` porte le slug du fournisseur détecté par
`/scrape/detect` (`null` si la détection n'a pas encore répondu ou ne reconnaît
rien), `results_import_failed` une cause fermée, `reason`, qui vaut `lecture`,
`plafond` ou `service` (`motifEchec` de `lib/import-outcome.ts`, la cause qui
choisit déjà le toast). Le détail par type d'erreur serveur vit dans
`event_scrape_failed.error_kind`. Aucune PII athlète dans ces 22 événements : le scraping
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
