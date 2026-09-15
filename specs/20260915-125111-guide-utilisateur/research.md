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

- **Decision**: `/admin/guide` vit sous `app/admin/`, gardé par
  `app/admin/layout.tsx`. L'entrée de navigation `a-guide` porte un
  `permission` unique : l'**union** (OU) de tous les pouvoirs admin déjà
  déclarés dans `nav.config.ts`, pas un `permission` par section de contenu.
- **Rationale révisée** (correction faite en implémentation, #865) :
  `app/admin/layout.tsx` referme déjà toute session ne détenant **aucun**
  pouvoir admin (`session.permissions.length === 0` → redirection vers
  `/dashboard`, avant même que la page ne s'exécute) — la garde n'est donc
  pas « présence d'une session », comme la première rédaction de cette note
  l'affirmait à tort, mais « présence d'au moins un pouvoir ». `AdminIndex`
  (le sommaire `/admin`) et `AppNav` répliquent cette règle **par item** via
  `estVisible()`, et un test verrouille l'invariant : une session sans aucun
  pouvoir doit voir « Aucun écran d'administration » — jamais une tuile
  isolée (`AdminIndex.test.tsx`). Une première version sans `permission` sur
  `a-guide` cassait cet invariant en le rendant visible même à une session
  vide. L'union résout les deux objectifs à la fois : elle reproduit
  exactement ce que la garde du layout vaut déjà (visible dès qu'on tient
  *un* pouvoir, quel qu'il soit), tout en évitant la fragmentation par écran
  que la première version voulait déjà éviter — un admin qui ne détient
  qu'un seul pouvoir voit malgré tout le guide complet, pas seulement sa
  section. Coût assumé, au même titre que le OU déjà posé sur
  `a-maintenance` : la liste doit être tenue à jour si un nouveau pouvoir
  admin apparaît.
- **Alternatives considered**: aucun `permission` (rejeté : casse
  `AdminIndex.test.tsx`, détaillé ci-dessus) ; un `permission` par section de
  contenu — rejeté, fragmenterait la documentation vue par un admin qui n'a
  qu'une partie des pouvoirs, alors que comprendre l'ensemble du back-office
  est la valeur du guide ; guide unique `/guide` avec sections admin masquées
  côté client par pouvoir — rejetée : un accès direct par URL/ancre
  contournerait un masquage purement client, alors que la garde du layout
  est déjà un rempart serveur existant et éprouvé.

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
