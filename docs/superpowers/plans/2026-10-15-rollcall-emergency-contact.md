# Contact d'urgence sur la carte de l'appel (#1405)

**Goal:** chaque carte de l'appel (`AppelPresence.tsx`) affiche le contact
d'urgence du jeune, numéro rendu en lien `tel:`, sans quitter l'appel.

**Architecture:** le détail de séance ajoute `emergency_contact` à chaque
participant (profil déjà chargé en `selectinload`, aucune requête de plus).
Donnée personnelle : seul un porteur de `jeunes:read` la reçoit. Le `GET` est
déjà gardé par ce pouvoir ; les routes d'écriture (`jeunes:write`) rendent le
même détail, donc elles posent `null` quand l'acteur ne porte pas `jeunes:read`.
Côté front, `EmergencyContact` sort de `ProfileDetail.tsx` vers un composant
partagé, réutilisé par la carte.

## Task 1: backend, champ et garde

- [ ] Test API : le `GET` du détail rend `emergency_contact` par participant.
- [ ] Test API : une session `jeunes:write` seule reçoit `emergency_contact: null`
      dans la réponse d'un `POST .../participants` et d'un `PATCH .../presence`.
- [ ] Test service : `training_session_detail_view` rend le contact, ou `None`
      sans le pouvoir.
- [ ] Implémenter : paramètre `with_emergency_contact` de
      `training_session_detail_view`, `ParticipantRead.emergency_contact: str | None`,
      routes d'écriture via `authorization.has_permission(db, actor, P.JEUNES_READ)`.
- [ ] `rtk uv run pytest -m "not integration"`, `uv run ruff check .`

## Task 2: frontend, composant partagé et carte

- [ ] Test vitest de `EmergencyContact` : numéro en lien `tel:` classe
      `ph-no-capture`, vide non rendu.
- [ ] Test vitest de `AppelPresence` : contact avec numéro en lien `tel:` sur
      la carte, contact vide ou `null` non rendu.
- [ ] Extraire `EmergencyContact` vers `components/admin/jeunes/EmergencyContact.tsx`,
      vide rendu `null` ; la fiche garde son `—` à l'appel.
- [ ] Type `TrainingParticipant.emergency_contact: string | null`, fixtures à jour.
- [ ] `npm test`, `npm run lint`, `npm run build`
