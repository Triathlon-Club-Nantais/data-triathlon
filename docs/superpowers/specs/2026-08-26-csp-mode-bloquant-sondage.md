# Sondage — passage de la CSP en mode bloquant (#570)

**Date** : 2026-08-26. **Environnement** : preview Vercel
(`data-triathlon-tcn-preview.vercel.app`), déploiement `v0.5.0-366-g4580c28`,
politique en `Content-Security-Policy-Report-Only`. Jamais en `npm run dev` :
la socket HMR y rapporte des violations qui n'existent pas en production.

**Ce qui prime** : ce fichier consigne ce qui a été mesuré. Toute divergence
avec le code se tranche en re-sondant, pas en arbitrant sur le papier.

## Méthode

Le relevé n'a **pas** été fait à la console DevTools. Les violations CSP ne
passent pas par l'API `console.*` et n'apparaissent donc pas dans les outils
d'automatisation ; elles ont été captées par un écouteur
`document.addEventListener('securitypolicyviolation', …)` posé dans la page,
qui donne la directive violée, l'URI bloquée et le `fichier:ligne`.

**Témoin positif** : l'insertion d'un `<style>` non signé a bien produit
`style-src-elem | inline`. L'écouteur mesure donc quelque chose.

**Angle mort assumé** : l'écouteur ne peut être posé qu'après le chargement du
document, donc les violations du **tout premier** chargement (chunks du layout
racine) lui échappent. Elles sont couvertes autrement : les trois `<style>`
non signés présents dans le DOM ont été inventoriés page par page, ce qui les
attrape quel que soit leur instant d'injection.

## Ce qui a sonné : trois causes, toutes traitées

| Source | Directive | Sortie retenue |
| --- | --- | --- |
| `sonner@2.0.8` — injecte sa feuille à l'import, au niveau module | `style-src-elem` | deux hashes épinglés dans `style-src` |
| `@base-ui/react` — injecte `.base-ui-disable-scrollbar` au montage d'un popup | `style-src-elem` | nonce transmis par `CSPProvider` |
| `zod@4` — sonde `new Function("")` pour activer son JIT | `script-src` (`eval`) | `z.config({ jitless: true })` |

### sonner — les deux temps d'une même injection

Déjà décrit par #570. Confirmé hors navigateur : les deux hashes se
reproduisent depuis `node_modules/sonner/dist/index.mjs`,
`sha256-47DEQpj8…` pour le `<style>` encore vide et `sha256-StEaX+…` pour le
CSS de 14 916 octets. Le second **dérive à chaque montée de version**, d'où le
test de `proxy.test.ts` qui les recalcule et échoue à la dérive.

### Base UI — trouvaille du relevé, absente de l'issue

Un `<style>` de 107 octets, `.base-ui-disable-scrollbar{scrollbar-width:none}`
et sa variante `::-webkit-scrollbar`, injecté à l'ouverture du premier
sélecteur de `/athletes/[id]`. React le déduplique (`precedence`), donc il ne
sonne **qu'une fois par chargement** — ce qui explique qu'il ne se reproduise
pas en rouvrant un autre sélecteur.

Base UI expose `CSPProvider` (prop `nonce`) exactement pour ça : sortie
préférée à un hash, parce qu'elle ne dérive pas. En mode bloquant sans elle,
les barres de défilement réapparaissent sous chaque popup.

### zod — la sonde qui se rapporte elle-même

`allowsEval` (`node_modules/zod/v4/core/util.cjs`) tente `new Function("")` et
**rattrape** l'échec : la validation continue de marcher en mode bloquant. Mais
le navigateur rapporte la tentative avant que zod ne l'attrape, donc la console
de chaque utilisateur de `/ajouter` criait une violation `script-src`. `jitless`
court-circuite la sonde ; sans `'unsafe-eval'` le JIT n'aurait de toute façon
jamais servi.

## Ce qui n'a rien produit

Une page muette est un résultat : elle borne ce qui restait à corriger.

- **Écrans parcourus sans violation** : `/carte`, `/dashboard` (filtres,
  disciplines, bascules de rang), `/resultats` (recherche, tri, dépliage d'un
  groupe, filtrage par athlète), `/club`, `/club/athletes`, une fiche athlète
  (`/athletes/27142`, ses deux sélecteurs), une fiche résultat
  (`/courses/340/participations/85788`), `/benevoles`, `/login`, `/ajouter`.
- **Dialogues et palettes** : sélecteur « Mon athlète », modale de retour
  utilisateur — rien.
- **Rendu serveur propre sur onze routes** (`/benevoles`, `/carte`, `/login`,
  `/ajouter`, `/dashboard`, `/resultats`, `/club`, `/club/athletes`, `/acces`,
  `/admin`, `/athletes/[id]`, `/courses/[id]`) : **zéro** `<script>` sans
  nonce, zéro `<style>` dans le HTML, et le `<link rel="stylesheet">` signé.
  #448 n'avait vérifié que quatre de ces routes.
- **`img-src`** : les deux origines tierces sondées directement — une tuile
  `tile.openstreetmap.org` et un marqueur Leaflet `unpkg.com` chargés dans la
  page — passent. La carte elle-même n'a pas pu être vue peuplée : la preview
  ne géolocalise aucune épreuve (« Aucune épreuve géolocalisée »).
- **`connect-src`** : le flux SSE n'a pas été déclenché (lancer un import écrit
  dans la base de preview). Vérifié en lecture à la place : `lib/api/sse.ts`
  vise `/api/v1`, chemin **relatif**, donc même origine. `connect-src 'self'`
  tient sans exception.

## Ce qui reste hors du relevé

- **Session connectée** (`/admin`, gestes destructifs, toasts) : non parcourue,
  faute d'identifiants SSO. Trois raisons de la juger couverte sans elle : son
  HTML serveur est propre (relevé ci-dessus), ses toasts sont `sonner`, et ses
  dialogues sont Base UI — les trois causes traitées.
- **PostHog en production.** La preview n'envoie rien à PostHog (#426), donc
  aucun relevé fait ici n'en dit quoi que ce soit. Vérifié en lecture :
  `instrumentation-client.ts` pose `api_host: "/ingest"`, donc même origine via
  le rewrite de #396 — `ui_host` ne sert qu'à des liens, pas à des requêtes.
  **Risque résiduel nommé, non couvert** : si le projet PostHog active un jour
  les sondages ou les visites guidées, `@posthog/browser-common` injecte un
  `<style>` non signé. La sortie existe déjà côté PostHog
  (`prepare_external_dependency_stylesheet`), elle n'est pas posée — rien ne
  l'utilise aujourd'hui.

## Second relevé — en mode **bloquant**, en local (review de la PR #639)

Le premier relevé était en `Report-Only` : il disait ce qui *serait* bloqué. La
review a demandé la preuve que l'app tient une fois la politique appliquée, et
la question était fondée — **aucune preview n'est construite par PR** (les
déploiements ne partent que de `main`), donc le mode bloquant n'était
observable nulle part avant la fusion. Refait ici sur un **build de
production** (`next build` + `next start`, `NODE_ENV=production`, donc la même
politique qu'en production), backend de dev en face.

**Témoin positif, et il mesure le bon mode** : un `<style>` non signé est
rapporté `style-src-elem` avec `disposition: "enforce"` — pas `report` — et son
`sheet` reste `null`. Le blocage est réel.

**L'angle mort du premier relevé est levé.** Plutôt que d'inventorier les
`<style>` à la main, le second détecte l'état : un `<style>` bloqué a
`sheet === null`. Ce test est vrai quel que soit l'instant de l'injection, y
compris avant la pose de l'écouteur — c'est ce qui manquait.

### Rendu serveur : 25 routes, pas 11

Toutes les routes de l'app (les 13 d'`/admin` comprises) relues sur le serveur
de production. **Zéro** `<script>` sans nonce, **zéro** `<style>` sans nonce,
**zéro** feuille sans nonce, et **zéro** gestionnaire en ligne (`on*=`) — ce
dernier n'avait jamais été vérifié, alors qu'il tomberait sous `script-src`
faute de `script-src-attr`.

### Runtime : rien ne casse

- `/dashboard`, `/resultats`, `/carte`, `/club`, `/club/athletes`, `/benevoles`,
  `/login`, `/ajouter` : un seul `<style>` par page, celui de `sonner`,
  **appliqué** (97 règles dans la CSSOM). Aucune violation.
- **Popup Base UI** (sélecteur « Discipline » de `/resultats`) : ouvert, rendu
  correct, et son `.base-ui-disable-scrollbar` est **appliqué** — `CSPProvider`
  le signe. C'était le cas qui casse du visible.
- **Dialogue de retour utilisateur** : ouvert, fond et carte rendus, aucune
  violation.
- **`zod` sur `/ajouter`** : validation d'une URL invalide, message d'erreur
  français affiché, **aucune violation `script-src`** — `jitless` tient.
- **`iframe`** : refusée, `frame-src 'none'` s'applique.

### Les deux hashes de sonner, prouvés par rejeu

Le CSS de `sonner` a été **réinjecté à la main**, dans les deux temps de
`__insertCSS` (`<style>` vide attaché, puis rempli), sur un élément **sans
nonce** : accepté, 97 règles, aucune violation. Les deux hashes correspondent
donc au contenu réellement servi — et le témoin, lui, est bien bloqué. La liste
n'est pas incomplète : elle est exacte.

**Pourquoi aucun hash de script** : `script-src` porte le nonce et
`'strict-dynamic'`. Un hash sert à signer un script hors de portée d'un nonce ;
il n'en existe aucun ici (25 routes le montrent), et tout ce que ces scripts
insèrent ensuite est autorisé par propagation. Épingler des hashes de script
reviendrait à figer une liste qui dériverait à chaque build pour couvrir ce qui
l'est déjà.

### `img-src`, sondé en mode bloquant

Tuile `tile.openstreetmap.org` et marqueur Leaflet `unpkg.com` : chargés. Une
origine non listée : **bloquée**, `img-src | enforce`. La directive s'applique
dans les deux sens.

### Ce que ce second relevé ne couvre toujours pas

- **Session SSO connectée** : `/admin` redirige vers `/login` sans identifiants.
  Le rendu serveur de ses 13 routes est propre, ses toasts sont `sonner`, ses
  dialogues sont Base UI — les trois causes traitées.
- **Carte peuplée** : base de dev vide, aucune tuile réelle affichée. `img-src`
  a été sondé directement à la place (ci-dessus).
- **PostHog en production** : inchangé, cf. section suivante.

## Le point tranché

**`style-src-attr 'unsafe-inline'` est assumé comme définitif.** La concession
est bornée aux **attributs** `style`, dont le front porte 412 ; un nonce ne
s'applique jamais à un attribut, et écrire `style-src 'unsafe-inline'` à la
place ouvrirait aussi les éléments `<style>` et les feuilles. La supprimer
supposerait de retirer les 412 attributs du front, chantier sans rapport avec
la politique. #448 l'avait léguée, #570 la fige.

**Le piège écarté** : ajouter `'unsafe-inline'` à `style-src` pour le cas
`sonner` n'aurait rien réglé — CSP niveau 3 impose au navigateur d'ignorer
`'unsafe-inline'` dès qu'un nonce ou un hash est présent dans la même
directive, et `style-src` en porte un.
