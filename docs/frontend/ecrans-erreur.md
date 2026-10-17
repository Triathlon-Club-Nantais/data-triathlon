# Écrans d'absence et de panne

Renvoyé depuis `frontend/AGENTS.md`, table « Où lire quoi ».

## Trois écrans d'absence et de panne (#464)

**Trois écrans d'absence et de panne** (#464, `ETAT-1`) — `app/not-found.tsx`,
`app/error.tsx`, `app/global-error.tsx`, la microcopie tenue une seule fois
dans `components/tcn/ErrorScreen.tsx` que les deux derniers partagent. Quatre
points qui se re-cassent facilement :

- **`retry()`, pas `reset()`** (prop stable en Next 16.3). `reset()` re-rend
  sans refaire le fetch, donc « Réessayer » ne pouvait pas guérir la panne la
  plus fréquente ici, le réveil à froid du backend Render.
- **`error.message` ne s'affiche jamais.** Next.js y substitue un paragraphe
  anglais en production, et il peut porter des détails serveur en
  développement. Seul le `digest` sort, nommé « code de l'incident » pour
  qu'un signalement soit rattachable.
- **`FeedbackButton` seulement dans `global-error.tsx`.** Le layout racine
  survit à `error.tsx` et à `not-found.tsx`, son bouton flottant y est donc
  déjà ; il ne survit pas à `global-error.tsx`, qui le remplace — d'où aussi
  l'import explicite de `globals.css`, le `<html lang="fr">`, et les trois
  variables `--font-*` redéclarées : `--tcn-font-body` vaut
  `var(--font-barlow), system-ui, …`, et sans `--font-barlow` **toute** la
  déclaration devient invalide à la substitution (la queue `system-ui` n'est
  jamais atteinte), donc le dernier filet du site s'afficherait en serif.
- **La sortie de l'écran de panne est un `<a>`, et pas vers `/`.** La
  frontière ne se vide que si le **chemin change** ; `/` est l'accueil
  (`redirects()` de `next.config.ts` y renvoie `/`) et la page la plus sujette au réveil à froid, donc
  un `next/link` vers elle depuis sa propre panne serait un clic sans effet.
- **`not-found.tsx` sert deux cas** : les `notFound()` des trois routes
  dynamiques *et* toute URL non matchée. Sa copie doit rester vraie des deux,
  donc « cette page », et l'épreuve supprimée en cause probable et non
  affirmée. Ses sorties évitent `/carte`, masquée du rail (#10, #28) — à
  rouvrir quand ces deux-là lèvent le masque.
- **Une fiche absente répond 200, pas 404, et c'est assumé** (#1064).
  `athletes/[id]`, `courses/[id]`,
  `courses/[id]/participations/[participationId]` et `challenges/[id]` (#1541)
  portent chacune un `loading.tsx` : le 200 part avec le squelette, avant que
  la page n'appelle `notFound()`, et Next ne peut plus le changer (guide
  `streaming.md`, § « The HTTP contract »). Il injecte à la place
  `<meta name="robots" content="noindex">` dans le HTML streamé, ce qui suffit
  contre l'indexation. Un vrai 404 exigerait d'attendre la ressource dans un
  `layout.tsx` de segment, donc de perdre le squelette pendant l'appel lent :
  arbitré contre. `app/not-found-streamed.test.ts` fixe le contrat (frontière
  présente, injection de Next toujours là) ; une sonde ou un vérificateur de
  liens doit donc lire le `noindex`, pas le statut.

Ce que ces trois écrans ne couvrent pas : la coquille 500 statique de Next
(`_global-error.html`), qui reste son texte anglais sans `lang`, et un rendu
serveur en échec dont le corps HTML part vide, les frontières étant rendues
côté client.
