# Research: Suppression d'une déclaration de crédit de bénévolat

Aucun `[NEEDS CLARIFICATION]` en Technical Context — le périmètre est entièrement
dérivable du code existant (`accept`/`reject` de #779, `DangerConfirm` de #499,
suppression de source de #739). Ce document consigne les décisions et leurs
raisons, pas une exploration ouverte.

## D1 — Emplacement de la route et pouvoir requis

**Decision**: `DELETE /admin/volunteer-actions/{action_id}` dans
`app/api/v1/admin_volunteer_actions.py` (aux côtés de `accept`/`reject`),
gardée par `require_permission(P.ATHLETES_VOLUNTEER_VALIDATE)` — le même
pouvoir, pas un nouveau.

**Rationale**: L'issue #818 le propose par défaut (« pas de nouveau pouvoir
dédié ») ; le pouvoir de validation couvre déjà la même population d'admins
et la même surface de données. Router déjà gardé par ce pouvoir sur ses
trois autres routes — aucune garde nouvelle à raisonner.

**Alternatives considered**: Un pouvoir `athletes:volunteer_delete` dédié —
rejeté par simplicité (Principe VI) : aucun besoin métier de dissocier « qui
valide » de « qui supprime » n'a été formulé, et l'ajouter sans besoin
observé serait spéculatif.

## D2 — Mécanisme de confirmation, par écran

**Decision**: Deux formes d'appel de `DangerConfirm`, selon le contexte de
montage de chaque écran :

- `AdminVolunteerActionsTable.tsx` (file d'attente, montée sous
  `app/admin/benevolat/page.tsx` → `app/admin/layout.tsx`, qui monte déjà
  `DangerConfirmProvider`) : `useDangerConfirm()`, comme le reste du
  back-office.
- `VolunteerActionsList.tsx` (fiche athlète, montée sous
  `app/(public_restricted)/athletes/[id]/page.tsx`, **hors** de tout
  `DangerConfirmProvider` — ce groupe de routes n'en monte aucun) : le
  composant déclaratif `<DangerConfirm>` directement, sans provider.

**Rationale**: `useDangerConfirm()` lève si aucun `DangerConfirmProvider`
n'est monté au-dessus — vérifié dans `DangerConfirm.tsx`. C'est exactement
la situation déjà résolue par `CourseSourcesPanel` (#739, `components/
courses/`), documentée en commentaire dans `DangerConfirm.tsx` comme
« seconde exception » : un composant qui se rend aussi hors back-office
prend la forme déclarative plutôt que d'ajouter un second
`DangerConfirmProvider` à la volée.

**Alternatives considered**: Monter un troisième `DangerConfirmProvider`
propre à `app/(public_restricted)/layout.tsx` — rejeté : la page athlète
n'a besoin de la confirmation que sur un seul geste, la forme déclarative
existe déjà et sert exactement ce cas dans le dépôt.

## D3 — Suppression définitive, pas de corbeille

**Decision**: `DELETE` hard — la ligne est retirée de la table, pas de
colonne `deleted_at` ni de statut supplémentaire.

**Rationale**: Aucun autre geste destructif du dépôt (suppression de source
inactive, #739 ; retrait de rôle) ne garde de corbeille. Introduire un soft-
delete ici serait une abstraction sans besoin exprimé (Principe VI).

**Alternatives considered**: Soft-delete avec statut `supprimee` — rejeté :
`status` porte aujourd'hui trois valeurs significatives pour le workflow de
validation (`en_attente`/`validee`/`refusee`) ; y ajouter un quatrième état
« supprimée mais visible » compliquerait `list_pending`/
`list_validated_for_athlete`/`exists_for_athlete_season` pour un besoin non
demandé.

## D4 — Journalisation

**Decision**: `admin_action_log_repository.create(action="athlete.
volunteer_action.delete", entity_type="athlete", entity_id=action.
athlete_id, payload={"season": ..., "action_id": ..., "status": ...})`,
capturé **avant** la suppression de la ligne (la payload a besoin de
`athlete_id`/`season`/`status`, qui n'existent plus après `delete()`).

**Rationale**: Reprend exactement le patron `accept`/`reject` déjà en place
dans `volunteer_action_service.py` — même `entity_type`/`entity_id`
(`athlete`, pas `volunteer_action` : c'est la fiche de l'athlète qui porte
la trace visible du geste), même forme de payload avec `action_id`. Un
patron différent (façon `course_source.delete`, `entity_type="course_
source"`) casserait la cohérence *au sein du même service* sans raison.

**Alternatives considered**: Journaliser après suppression — impossible
sans capturer les champs nécessaires avant, donc écarté d'emblée plutôt que
comparé.

## D5 — Ressource absente ou déjà supprimée

**Decision**: `NotFoundError("Déclaration introuvable.")`, via le helper
`_action_ou_404` déjà utilisé par `accept`/`reject`/`_action_ou_404`.

**Rationale**: Couvre nativement l'edge case « double suppression » de la
spec (FR-008) — la seconde tentative retombe sur le même 404 qu'une
déclaration qui n'a jamais existé, sans état intermédiaire à gérer.

## D6 — Invalidation du cache front après suppression

**Decision**: Deux mutations distinctes (une par écran), chacune
invalidant la query key de sa propre liste, plus le quota de saison quand
la déclaration était validée :

- File d'attente : invalide `queryKeys.pendingVolunteerActions()` (comme
  `useAcceptVolunteerAction`/`useRejectVolunteerAction`).
- Fiche athlète : invalide `["validated-volunteer-actions", athleteId]`
  (comme `useValidatedVolunteerActions` la lit) **et** `["season-quota",
  athleteId, action.season]` (comme `useValidateSeason`/`useUnvalidateSeason`
  invalident déjà ce même couple) — une déclaration validée supprimée doit
  faire retomber le quota affiché, sans quoi l'admin voit un quota qui ne
  correspond plus à ce qu'il vient de retirer (spec SC-002).

**Rationale**: Suit exactement les query keys et le patron d'invalidation
déjà établis par les mutations voisines (`useAcceptVolunteerAction`,
`useValidateSeason`) — aucune nouvelle clé introduite.
