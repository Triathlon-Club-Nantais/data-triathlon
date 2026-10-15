# Chargement différé de posthog-js (#1394)

**Objectif** : sortir `posthog-js` des `rootMainFiles` du build, sans rien changer aux comportements de production.

**Architecture** : `lib/posthog.ts` devient le seul point d'entrée. Il charge `posthog-js` par `import()` et l'initialise une fois (`loadPostHog`), puis sert les appels par `withPostHog(use)` : direct si l'instance est prête, sinon chaînés sur la promesse de chargement (ordre conservé, rien de perdu). Partout ailleurs, `posthog-js` n'est plus importé que pour ses types. `instrumentation-client.ts` garde `syncConsentCookie()` synchrone et déclenche le chargement au repos du navigateur. Sans variables `NEXT_PUBLIC_POSTHOG_*`, `withPostHog` sort avant l'`import()` : aucun octet téléchargé.

**Variante du paquet** : on garde `posthog-js` complet. La variante allégée retire des extensions (web vitals, exceptions, clics morts) qu'il faudrait réenregistrer à la main ; le gain du critère tient sans elle.

## Tâches

1. **Test de structure (rouge)** : `lib/posthog.test.ts` vérifie qu'aucun fichier source hors tests n'importe `posthog-js` autrement qu'en `import type`.
2. **Tests de comportement (rouge)** :
   - `captureEvent` avant chargement : l'appel ne plante pas et l'événement part une fois l'instance prête, dans l'ordre.
   - sans variables : `posthog-js` n'est jamais évalué (fabrique du mock jamais appelée).
   - `instrumentation-client` : `syncConsentCookie` reste synchrone, `init` arrive après chargement avec la même configuration (tests existants passés en `waitFor`).
   - `saveConsent`, `PostHogSessionSync`, `login_initiated` : mêmes assertions, attendues de façon asynchrone.
3. **Implémentation** : `loadPostHog`/`withPostHog` dans `lib/posthog.ts` (configuration d'`init` et `before_send` jeunes déplacés depuis `instrumentation-client.ts`), `analytics-consent.ts` et `providers.tsx` passent par `withPostHog`.
4. **Doc** : `docs/analytics-posthog.md`, câblage frontend.
5. **Mesure** : `npm run build` avant/après, somme gzip des `rootMainFiles` et JS initial de `/cgu`.
