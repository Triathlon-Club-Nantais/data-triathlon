# Tasks: Textes légaux du site (mentions légales, confidentialité, CGU)

**Input**: Design documents from `specs/20261001-150009-legal-pages/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/routes.md

**Tests**: obligatoires (Principe III, TDD). Chaque test est écrit et vu
**échouer** avant le code qu'il couvre.

Chemins relatifs à `frontend/`. Faits juridiques : décision #332
(`docs/superpowers/specs/2026-10-01-base-legale-decision.md`) et
`research.md` §R4, qui priment sur toute reformulation.

## Phase 1: Setup

Aucune : ni dépendance nouvelle, ni configuration.

## Phase 2: Foundational (bloque toutes les stories)

- [ ] T001 [P] Écrire `components/legal/LegalPage.test.tsx` : rend le titre (`h1`), la description, « Dernière mise à jour : 1 octobre 2026 » pour `updatedAt: "2026-10-01"` (élément `<time dateTime="2026-10-01">`), un `h2` par rubrique avec son `id` d'ancre, un sommaire `nav` « Sommaire » quand le document a plus de 4 rubriques et aucun à 4 ou moins
- [ ] T002 [P] Créer les types `LegalDocument` et `LegalSection` dans `components/legal/types.ts` (cf. data-model.md)
- [ ] T003 Implémenter `components/legal/LegalPage.tsx` (`PageShell`, `PageHeader`, sommaire en liens d'ancre `--tcn-orange-deep`, rubriques en `Card` avec `scrollMarginTop`), jusqu'à faire passer T001
- [ ] T004 [P] Créer `components/legal/legal-routes.ts` : la liste ordonnée `{ href, label }` des trois routes du contrat (`contracts/routes.md`)

**Checkpoint** : le gabarit rend n'importe quel `LegalDocument`.

## Phase 3: User Story 1, un non-adhérent lit la politique sans code (P1) 🎯 MVP

**Goal**: la politique de confidentialité est atteignable depuis toute page, sans code d'accès.

**Independent Test**: navigation privée sur `/acces`, lien « Confidentialité » dans le pied de page, la politique s'ouvre complète.

- [ ] T005 [P] [US1] Étendre `app/routes-garde-site.test.ts` : `mentions-legales`, `confidentialite`, `cgu` sont des routes sœurs, absentes du groupe gardé
- [ ] T006 [P] [US1] Écrire `components/legal/LegalLinks.test.tsx` : un `nav` « Informations légales » porte les trois liens, dans l'ordre du contrat, vers les bons `href`
- [ ] T007 [P] [US1] Étendre `components/layout/VersionFooter.test.tsx` : le pied de page contient le `nav` « Informations légales », y compris quand le code d'accès n'est pas saisi
- [ ] T008 [P] [US1] Écrire `components/legal/content/confidentialite.test.tsx` : rubriques présentes et nommées (responsable de traitement ; données collectées avec nom, prénom, sexe, catégorie d'âge, club, temps, classements ; provenance avec les 14 chronométreurs nommés, l'import de fichiers et la saisie manuelle ; finalité et base légale « intérêt légitime » ; durées de conservation dont 12 mois pour les signalements ; destinataires et sous-traitants Vercel, Render, Microsoft Azure, Supabase, GitHub, PostHog ; droits dont l'opposition ; lien `mailto:president@triathlon-club-nantais.com` ; réclamation CNIL avec lien `https://www.cnil.fr/fr/plaintes` ; cookies `tcn_session`, `tcn_site_session`, `tcn-nav-expanded`, `tcn-athlete`)
- [ ] T009 [P] [US1] Ajouter `/confidentialite` → « Politique de confidentialité » dans `app/page-titles.test.tsx`
- [ ] T010 [US1] Rédiger `components/legal/content/confidentialite.tsx` (`LegalDocument`, français courant, chaque article cité expliqué), jusqu'à faire passer T008
- [ ] T011 [US1] Créer `app/confidentialite/page.tsx` (`metadata.title`, rend `LegalPage`), jusqu'à faire passer T005 (pour cette route) et T009
- [ ] T012 [US1] Implémenter `components/legal/LegalLinks.tsx` (`next/link`, `legal-routes.ts`) et le rendre dans le `<footer>` de `components/layout/VersionFooter.tsx`, jusqu'à faire passer T006 et T007

**Checkpoint** : US1 livrable seule ; les liens vers les deux autres pages mènent à une 404 tant que la phase 4 n'est pas faite (ne pas livrer US1 seule en production).

## Phase 4: User Story 2, mentions légales et CGU (P2)

**Goal**: l'adhérent sait qui édite le service et ce qu'il s'engage à faire.

**Independent Test**: depuis n'importe quelle page, les liens « Mentions légales » et « Conditions d'utilisation » ouvrent leurs pages.

- [ ] T013 [P] [US2] Écrire `components/legal/content/mentions-legales.test.tsx` : éditeur Triathlon Club Nantais, adresse 2 boulevard René Coty 44100 Nantes, SIRET 403 516 347 00016, directeur de la publication Aurélien Gantier, hébergeurs Vercel, Render, Microsoft Azure avec leurs adresses, contact `mailto:president@triathlon-club-nantais.com`, renvoi vers la politique de confidentialité
- [ ] T014 [P] [US2] Écrire `components/legal/content/cgu.test.tsx` : objet du site, accès réservé par code, saisie manuelle et engagement du déclarant, validation par un bénévole, signalements, limites de responsabilité sur les données des chronométreurs, demande de correction ou de retrait
- [ ] T015 [P] [US2] Ajouter `/mentions-legales` → « Mentions légales » et `/cgu` → « Conditions d'utilisation » dans `app/page-titles.test.tsx`
- [ ] T016 [US2] Rédiger `components/legal/content/mentions-legales.tsx`, jusqu'à faire passer T013
- [ ] T017 [US2] Rédiger `components/legal/content/cgu.tsx`, jusqu'à faire passer T014
- [ ] T018 [US2] Créer `app/mentions-legales/page.tsx` et `app/cgu/page.tsx`, jusqu'à faire passer T005 et T015

## Phase 5: User Story 3, date de mise à jour (P3)

**Goal**: chaque texte affiche sa date, et une date invalide ne passe pas.

**Independent Test**: chaque page montre « Dernière mise à jour ».

- [ ] T019 [US3] Écrire `components/legal/content/documents.test.ts` : pour chacun des trois documents, `updatedAt` est une date ISO valide, non postérieure au jour du test, et les `id` de rubriques sont uniques ; le faire passer (corriger le contenu si besoin)

## Phase 6: Polish

- [ ] T020 Documenter les textes légaux dans `frontend/AGENTS.md` (où vit le contenu, règle : la date `updatedAt` change dans le même commit que le texte, les faits viennent de la décision #332)
- [ ] T021 Lancer `npm test`, `npm run lint`, `npm run build` dans `frontend/` ; corriger toute régression
- [ ] T022 Vérification manuelle selon `quickstart.md` (navigation privée sur `/acces`, 320 px)

## Dependencies & Execution Order

- Phase 2 bloque tout. T003 dépend de T001 et T002.
- US1 dépend de la phase 2. US2 dépend de la phase 2 et réutilise T005/T012 de US1 (le pied de page porte déjà ses liens).
- US3 dépend des trois contenus (T010, T016, T017).
- Polish en dernier.

## Parallel Example: User Story 1

```text
T005, T006, T007, T008, T009 : cinq fichiers de test distincts, en parallèle.
Puis T010 → T011, et T012 indépendamment.
```

## Implementation Strategy

US1 et US2 se livrent **ensemble** : un lien de pied de page vers une 404
n'est pas livrable. US1 d'abord parce qu'elle porte l'obligation légale (FFA,
2014) ; US2 et US3 complètent avant la PR.
