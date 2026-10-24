# En-têtes de sécurité et CSP

Renvoyé depuis `frontend/AGENTS.md`, table « Où lire quoi ».

## `next.config.ts` : en-têtes de sécurité (#396)

`next.config.ts` — rewrites (`/api/*`, proxy PostHog) **et** `headers()` : les
en-têtes de sécurité posés sur `/:path*`, rewrites comprises (#396). Ils ne
couvrent que ce qui passe par Next : les backends Render étant joignables en
direct, `backend/app/core/security_headers.py` en est le jumeau. La CSP n'y est
**pas** — elle vit dans `proxy.ts` (#448) : `headers()` ne sert que des
constantes, or un nonce se génère par requête.

## `proxy.ts` : CSP et cookie de présence (#448, #427)

`proxy.ts` — le proxy Next (nom que Next 16 donne à l'ancien `middleware.ts`).
Deux charges, dans cet ordre : la **CSP entière** (#448) et le marquage du
cookie de présence (#427). Trois pièges :

- La politique n'est **pas** scindée avec `next.config.ts` : deux en-têtes CSP
  sur une réponse se cumulent **par intersection**, chacun évalué séparément —
  ce serait deux sources de vérité et des rapports en double.
- Elle est posée sur les en-têtes de la **requête** transmise au renderer,
  autant que sur la réponse : c'est là que Next lit le nonce. N'écrire que la
  réponse donne une politique correcte et un HTML sans nonce.
- La CSP est le **tronc** de la fonction, le cookie un effet de bord : une
  sortie précoce la court-circuiterait pour la majorité des visiteurs.
- `router.refresh()` rejoue le layout racine avec le nonce d'une **nouvelle**
  requête, que la CSP du document ignore : un nonce lu côté client se fige
  sur le premier rendu (`StableCSPProvider`, #570), sans quoi le premier
  `<style>` de Base UI inséré après un geste admin part en violation.
- Les violations remontent au backend (#1168) : `report-to` (avec l'en-tête
  `Reporting-Endpoints`) et `report-uri` visent `POST /api/v1/csp-reports`,
  qui les écrit dans ses logs (`CSP violation directive=…`). La route est
  exemptée de la garde du site : le navigateur envoie sans cookies. Brave
  n'envoie **aucun** rapport ; un relevé se fait dans Chromium ou Firefox.

En `Content-Security-Policy`, donc **bloquante** (#570), après une observation
en `Report-Only` restée sans violation en production
(`docs/superpowers/specs/2026-10-24-csp-violations-sondage.md`). Les deux
hashes de `style-src` restent : ils signent la feuille que `sonner` injecte à
l'import, sans quoi les toasts perdraient leur style. Une nouvelle source de
style ou de script en ligne est désormais **bloquée**, plus seulement
rapportée : la vérifier sur la preview avant la fusion. `upgrade-insecure-requests`,
ignoré en `Report-Only`, est actif. Corollaire du nonce : `await connection()` dans `app/layout.tsx`
rend **toute** route dynamique, un nonce ne pouvant exister dans une page
générée au build. Ne pas y substituer `dynamic = "force-dynamic"`, qui
annulerait le cache de fetch de #352.
