# Design — Content-Security-Policy à nonce sur le frontend

**Date** : 2026-08-18
**Issue** : #448 — volet restant du constat **A05-2** de
`2026-08-16-securite-owasp-audit.md`
**Objet** : poser une CSP à nonce sur le front Next 16, en `Report-Only`, sans
toucher à l'API.
**Statut** : design validé. Le passage en mode **bloquant** n'est pas dans ce
périmètre — il fait l'objet d'une issue de suite, et c'est lui la vraie fin du
constat.

> **Ce document est publié.** `docs/` alimente GitHub Pages et le dépôt est
> public. Il décrit une faiblesse ouverte — l'absence de CSP — en termes
> suffisants pour la corriger, sans mode opératoire d'exploitation.

## Ce que l'on sait avant d'écrire une directive

Mesuré sur la branche `feat/448-csp-nonce` (= `main` + #447 + #441), pas supposé.

**Le navigateur n'appelle que la même origine.** `lib/api/client.ts:49` et
`lib/api/sse.ts:3` pointent sur `/api/v1` en relatif ; aucun `NEXT_PUBLIC_*_URL`
n'existe. PostHog passe par le proxy inverse `/ingest` de #396
(`instrumentation-client.ts`), donc ses événements **et** ses assets sont
même-origine. C'est le piège que l'issue signalait : il est déjà désamorcé, et
`connect-src 'self'` suffit.

**Deux origines tierces, toutes deux des images.** Les tuiles
`*.tile.openstreetmap.org` et trois marqueurs Leaflet sur `unpkg.com`
(`components/map/MapView.tsx:19-21`). Le CSS de Leaflet est empaqueté, les
polices Anton/Barlow sont auto-hébergées par `next/font/google` au build.

**Rien d'exotique dans le front.** Aucune `iframe`, aucun `Worker`, aucun
`createObjectURL`, aucun `dangerouslySetInnerHTML`, pas de `next/image`. La
politique peut donc être serrée sans exception.

**412 attributs `style` en ligne.** Un nonce ne s'applique **jamais** à un
attribut `style` : c'est la seule concession que la politique devra faire.

**Le nonce est lu dans les en-têtes de la *requête*.**
`node_modules/next/dist/server/app-render/app-render.js:209` :

```js
const csp = headers['content-security-policy'] || headers['content-security-policy-report-only'];
const nonce = typeof csp === 'string' ? getScriptNonceFromHeader(csp) : undefined;
```

Deux conséquences décisives :

1. **`Report-Only` injecte bien le nonce** — le nom `…-report-only` est accepté
   au même titre que l'autre. La phase d'observation reflète donc exactement ce
   que ferait le mode bloquant, au lieu d'être une simulation.
2. L'en-tête doit être posé **sur la requête** transmise au renderer, pas
   seulement sur la réponse. Un proxy qui n'écrit que la réponse produit une
   politique correcte et un HTML sans nonce, donc un rapport de violations sur
   les propres scripts de Next.

Et `get-script-nonce-from-header.js` cherche la directive par
`directives.find(dir => dir.startsWith('script-src'))` : une future directive
`script-src-elem` placée **avant** `script-src` volerait la recherche.

## Décisions

| Question | Décision |
| --- | --- |
| Mode | `Content-Security-Policy-Report-Only` seul. Le bloquant est une issue de suite. |
| Collecte des violations | Aucune. Console du navigateur, relevé par une passe manuelle sur la preview. Pas d'endpoint public de collecte. |
| Côté API | **Non touché.** `default-src 'none'` n'est pas gratuit : il casserait `/docs`, que #399 laisse ouvert en preview et en dev. Les réponses sont du JSON et `nosniff` est déjà posé. Décision tracée ici pour ne pas être rejouée. |
| Forme des scripts | Nonce + `'strict-dynamic'`. |
| Emplacement | Politique **entière** dans `frontend/proxy.ts`. |
| Pages statiques | Rendues dynamiques. |

Deux options ont été écartées explicitement.

**La politique scindée** — constantes dans le `headers()` de `next.config.ts`
avec les cinq en-têtes de #396, `script-src` porteur du nonce dans `proxy.ts` —
rangerait mieux, mais deux en-têtes CSP sur une même réponse **se cumulent par
intersection**, chacun évalué séparément : deux sources de vérité, des rapports
en double, un piège de maintenance pour une question de tiroir.

**La voie SRI** (`experimental.sri`) préserverait la génération statique, mais
elle est expérimentale et l'exemple de la doc Next (`script-src 'self'`, sans
nonce ni hash) n'explique pas comment ses propres scripts *inline* de flux RSC
seraient autorisés. À ne pas engager sans mesure préalable.

## La politique

```
default-src 'self';
script-src 'self' 'nonce-{N}' 'strict-dynamic' [dev: 'unsafe-eval'];
style-src 'self' 'nonce-{N}';
style-src-attr 'unsafe-inline';
img-src 'self' data: https://*.tile.openstreetmap.org https://unpkg.com;
font-src 'self';
connect-src 'self';
object-src 'none';
frame-src 'none';
frame-ancestors 'none';
base-uri 'self';
form-action 'self';
[prod: upgrade-insecure-requests]
```

- **`'strict-dynamic'`** rend les listes d'origines inopérantes pour les
  scripts : un script chargé par un script de confiance est autorisé par
  propagation. C'est exactement le cas de `array.js`, que `posthog-js` insère
  lui-même — rien à énumérer — et cela ferme la classe de contournement par
  liste blanche.
- **`style-src-attr 'unsafe-inline'`** est la concession, et elle est bornée aux
  **attributs** : un élément `<style>` ou une feuille reste soumis à `'self'` ou
  au nonce. Écrire `style-src 'unsafe-inline'` à la place ouvrirait les deux.
  Cette concession vivra tant que les 412 attributs `style` existent ; elle est
  léguée à l'issue du mode bloquant.
- **`img-src data:`** pour les SVG inlinés par Tailwind. Pas de `blob:` : rien
  ne crée d'URL d'objet.
- **`'unsafe-eval'` en dev seulement** : React s'en sert pour reconstruire les
  piles d'erreurs serveur dans le navigateur. Ni React ni Next n'en ont besoin
  en production.
- **Pas de `worker-src`** ni de `manifest-src` : `default-src 'self'` couvre, et
  rien n'instancie de `Worker`.

## Emplacement et forme du code

`frontend/proxy.ts` existe depuis #441, où il auto-guérit le cookie de présence
de session. Ses deux `return` précoces court-circuiteraient la CSP : la fonction
est restructurée pour que **la CSP soit le tronc** et le marquage du cookie un
effet de bord sur la réponse.

```ts
export function proxy(request: NextRequest) {
  const nonce = ...;
  const policy = buildCspPolicy(nonce, { dev: process.env.NODE_ENV === "development" });

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("Content-Security-Policy-Report-Only", policy);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy-Report-Only", policy);

  markSessionPresence(request, response); // logique de #441, inchangée
  return response;
}
```

- `buildCspPolicy(nonce, { dev })` est une **fonction pure exportée** : testable
  sans requête, et c'est l'unité naturelle des tests de directives. Les
  identifiants nouveaux sont en anglais (Principe I : la couche technique
  invisible) ; le `porteUneSession` de #441 n'est pas réécrit pour autant.
- Nonce : `crypto.randomUUID()` encodé en base64, comme la doc Next. Frais à
  chaque requête, jamais mis en cache.
- **Pas d'en-tête `x-nonce`.** La doc le pose pour qu'une page puisse lire le
  nonce ; aucun script inline ne nous appartient, donc personne ne le lirait.
  Une ligne à ajouter le jour où ce besoin existe.
- `config.matcher` inchangé. `api`, `_next/static`, `_next/image` et
  `favicon.ico` restent exclus : la CSP ne compte que sur les documents.

## Rendu dynamique

Un nonce ne peut pas exister dans une page générée au build. Les six entrées
encore prérendues sur cette branche livreraient donc des scripts sans nonce :
des violations rapportées à tort, et un mode bloquant qui casserait `/login`.

`app/layout.tsx` devient `async` et fait `await connection()` (de
`next/server`). Le layout racine s'appliquant à tout, l'ensemble des routes
passe en `ƒ`.

**Pas `export const dynamic = "force-dynamic"`.** La doc
(`caching-without-cache-components.md:96-99`) le décrit comme équivalent à
`{ cache: 'no-store', next: { revalidate: 0 } }` sur **chaque** `fetch` plus
`fetchCache = 'force-no-store'` : il annulerait le travail de #352.
`connection()` n'attend que la requête et ne touche pas au Data Cache.

**Coût mesuré**, sortie de `npm run build` sur cette branche : six entrées
perdent leur prérendu — `/` (un simple `redirect("/dashboard")`),
`/_not-found`, `/ajouter` (ISR 30 s / 1 an), `/benevoles`, `/carte`, `/login`.
Les dix-sept autres routes sont **déjà** `ƒ`. Seule `/ajouter` fait un fetch
serveur, et son `next: { revalidate }` explicite (`lib/api/server.ts:44`) vit
dans le Data Cache, indépendant du mode de rendu. Le coût net est donc un rendu
React par requête sur six pages sans données. Ni PPR ni ISR de route n'est
utilisé ailleurs.

## Tests

TDD, rouge d'abord, sur les invariants qui cassent en silence. `proxy.test.ts`
(étendu) et `next.config.test.ts` existent déjà.

1. L'en-tête posé est `Content-Security-Policy-Report-Only` ; le nom bloquant
   est **absent** de la réponse.
2. La politique est présente sur la réponse **et** sur les en-têtes de requête
   transmis à `NextResponse.next` — le mécanisme d'injection du nonce.
3. Deux appels successifs produisent deux nonces différents.
4. Le nonce satisfait la regex de Next elle-même,
   `/^'nonce-([A-Za-z0-9+/_-]+={0,2})'$/`, recopiée depuis
   `get-script-nonce-from-header.js`.
5. `script-src` est la **première** directive dont le nom commence par
   `script-src`, puisque Next la cherche par `startsWith`.
6. `'unsafe-eval'` présent en dev, absent en production.
7. La CSP est posée **même** sur le chemin où la logique de cookie de #441
   sortait tôt ; les tests de #441 passent inchangés.
8. `next.config.ts` ne porte **aucune** clé CSP — garde-fou contre la politique
   scindée écartée plus haut.

Le rendu dynamique ne se teste pas en unitaire : la preuve est la sortie de
`npm run build`, où plus aucun `○` ne subsiste.

## Documentation

`frontend/AGENTS.md` affirme aujourd'hui, dans sa puce `next.config.ts`, que la
CSP n'y est pas « parce qu'elle demande un nonce ». La puce devient « elle vit
dans `proxy.ts` », et `proxy.ts` gagne la sienne — un lecteur qui cherche les
en-têtes de sécurité doit trouver les deux emplacements et la raison de la
séparation.

## Risques

- **La PR est observablement inerte.** `Report-Only` ne bloque rien : aucun
  risque utilisateur, et par symétrie aucune preuve que la politique soit juste
  avant qu'on ait relu les consoles. La vérification est une passe manuelle
  écran par écran sur la preview, y compris la carte, l'import SSE et une
  session connectée.
- **`style-src-attr 'unsafe-inline'`** reste une concession permanente en
  l'état.
- **`connect-src 'self'` dépend du rewrite `/ingest`.** Le retirer un jour
  bloquerait les événements PostHog — en mode bloquant seulement, ce qui laisse
  la marge de le voir.
- **Le mode dev bruitera** : la socket HMR et les rechargements peuvent
  rapporter des violations qui n'existent pas en production. À trier au moment
  du relevé, pas à corriger par des directives permanentes.
