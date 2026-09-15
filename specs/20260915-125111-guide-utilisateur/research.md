# Phase 0 — Research : Guide utilisateur intégré

Aucun `[NEEDS CLARIFICATION]` n'a été laissé dans `spec.md` (le périmètre, le
découpage en issue unique et la priorité avaient déjà été tranchés par
l'utilisateur avant la rédaction). Ce document consolide les décisions de
conception prises en préparant `plan.md`, faute d'ambiguïté nécessitant une
question à l'utilisateur.

## Découpage en pages : 2 pages à sections ancrées, pas 21 routes

- **Decision**: `/guide` (membres) et `/admin/guide` (admin), chacune une
  seule page React avec une section par fonctionnalité, atteignable par ancre
  (`/guide#club`).
- **Rationale**: FR-010 exige un accès direct par URL à chaque section, mais
  ne demande pas 21 routes distinctes. Une ancre satisfait l'exigence à un
  coût bien moindre (2 fichiers `page.tsx` contre 21), cohérent avec le
  Principe VI (YAGNI). Le sommaire (`GuideSommaire.tsx`) sert aussi de table
  des matières visible en haut de page.
- **Alternatives considered**: une route par section (`/guide/dashboard`,
  `/guide/club`, …) — rejetée : 21 fichiers `page.tsx` quasi identiques pour
  un gain nul (l'ancre remplit déjà le besoin de lien direct), et un
  sur-découpage que le Principe VI proscrit explicitement.

## Gating de la section admin du guide

- **Decision** (finale, après deux corrections en implémentation — voir
  historique ci-dessous) : `/admin/guide` vit sous `app/admin/`, gardé par
  `app/admin/layout.tsx`. Le lien d'accès n'est **pas** une entrée de
  `nav.config.ts` : c'est un lien fixe ajouté directement dans
  `app/admin/layout.tsx`, rendu pour toute session qui atteint les pages
  admin (donc détenant déjà au moins un pouvoir, la garde du layout l'exige).
  Aucun `permission` nulle part pour le guide — ni absent d'un item NAV, ni
  union OU : le guide est simplement hors du système de permissions par
  écran.
- **Rationale** : `app/admin/layout.tsx` referme toute session ne détenant
  **aucun** pouvoir admin (`session.permissions.length === 0` →
  redirection vers `/dashboard`, avant même que la page ne s'exécute) — la
  garde n'est donc pas « présence d'une session » mais « présence d'au
  moins un pouvoir ». `AdminIndex` (le sommaire `/admin`) et `AppNav`
  répliquent cette règle **par item de `nav.config.ts`** via `estVisible()`,
  et deux invariants la verrouillent : `AdminIndex.test.tsx` (une session
  sans aucun pouvoir doit voir « Aucun écran d'administration », jamais une
  tuile isolée) et `AppNav.test.tsx` (une section à un seul pouvoir détenu
  se replie sur un lien direct, #482/NAV-2 — dépend du nombre d'items
  *visibles* dans la section). Toute entrée `a-guide` ajoutée à
  `nav.config.ts` compte dans ces deux comptages, qu'elle porte ou non un
  `permission` : sans `permission`, elle casse le premier invariant (visible
  même à une session vide) ; avec un `permission` unique en union OU sur
  tous les pouvoirs admin (la première correction tentée), elle reste
  toujours visible dès qu'un *autre* item de la section l'est aussi — donc
  casse le second invariant, puisque la section n'a alors plus jamais
  exactement un item visible. Les deux approches par entrée NAV sont donc
  rejetées pour la même raison structurelle : `estVisible()` compte des
  items, pas des « types » d'items, et le guide n'est structurellement pas
  un écran comme les autres — c'est de la documentation en lecture seule,
  pas un geste qui écrit des données. Le sortir entièrement de
  `nav.config.ts` — un lien fixe dans le layout, gardé par la même
  condition (≥ 1 pouvoir) que le layout applique déjà — est la seule
  option qui ne perturbe aucun des deux comptages.
- **Alternatives considered** : aucun `permission` sur une entrée
  `nav.config.ts` — rejetée, casse l'état vide d'`AdminIndex` ; un
  `permission` unique en union OU sur une entrée `nav.config.ts` — rejetée
  après implémentation et test, casse le repli #482/NAV-2 dès qu'un admin
  ne détient qu'un seul pouvoir (régression constatée sur
  `AppNav.test.tsx`, corrigée en retirant l'entrée plutôt qu'en cherchant
  une troisième valeur de `permission`) ; un `permission` par section de
  contenu — rejetée, fragmenterait la documentation vue par un admin qui
  n'a qu'une partie des pouvoirs, alors que comprendre l'ensemble du
  back-office est la valeur du guide ; guide unique `/guide` avec sections
  admin masquées côté client par pouvoir — rejetée : un accès direct par
  URL/ancre contournerait un masquage purement client, alors que la garde
  du layout est déjà un rempart serveur existant et éprouvé.

## Stockage du contenu et des captures d'écran

- **Decision**: contenu en dur dans `guide-content.membre.ts` /
  `guide-content.admin.ts` (tableaux TypeScript typés), captures d'écran en
  fichiers statiques sous `frontend/public/guide/{membre,admin}/*.png`,
  référencées par `next/image`.
- **Rationale**: pas de CMS ni de nouvelle table DB pour 21 sections de texte
  qui changent rarement (Principe VI). Next.js sert déjà `public/` sans
  configuration additionnelle ; `next/image` gère le redimensionnement
  responsive gratuitement.
- **Alternatives considered**: stocker le contenu en base (nouvelle table
  `guide_sections`) — rejeté : aucun besoin d'édition à chaud identifié dans
  la demande, et ça ajouterait une couche `api → services → repositories`
  pour du contenu éditorial statique, à l'opposé du Principe VI.

## Interfaces externes

- **Decision**: pas de `contracts/` — la feature n'expose ni API ni CLI, elle
  ne consomme aucune route `/api/v1` existante.
- **Rationale**: le guide est un rendu 100% côté frontend de contenu statique
  packagé avec le build ; rien à documenter comme contrat d'interface.
