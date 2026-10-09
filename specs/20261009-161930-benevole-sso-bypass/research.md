# Research: accès bénévoles par pouvoir SSO (#1272)

## D1. Où admettre l'administrateur

- **Decision**: dans `require_benevole_access` elle-même, en composant `optional_user` puis `authorization.has_permission(db, user, P.BENEVOLE_ACCESS_MANAGE)` ; le cookie n'est vérifié que si cette branche échoue.
- **Rationale**: onze routes portent déjà cette garde ; l'élargir à un endroit couvre toutes les routes, y compris une future, sans qu'une route puisse l'oublier. `optional_user` ne lève pas, donc l'anonyme et la session invalide retombent sur la garde actuelle sans changer le refus.
- **Alternatives considered**: une seconde garde « SSO ou cookie » posée route par route (duplication, risque d'oubli) ; composer `require_permission` (lève 401/403, changerait le refus pour le connecté sans pouvoir, contraire à FR-010) ; un rôle « administrateur » (interdit, FR-017).

## D2. Transporter l'acteur jusqu'au journal

- **Decision**: la garde rend `User | None` (l'administrateur admis, ou `None` pour le cookie). Les routes d'écriture la reçoivent en paramètre et passent `benevole_access.actor_user_id(db, admin)` comme `user_id` aux services `admin_actions`, qui journalisent déjà dans leur transaction.
- **Rationale**: le journal s'écrit dans le service (#935), la route ne fait que choisir l'acteur, comme aujourd'hui avec `system_user_id`. Le compte système n'est résolu que pour une écriture faite au cookie : une lecture n'en dépend pas (inchangé).
- **Alternatives considered**: résoudre l'acteur dans la garde (forcerait la lecture du compte système sur chaque lecture, et ferait échouer une lecture si ce compte manquait) ; `request.state` (état implicite, moins testable).

## D3. Priorité quand pouvoir et cookie coexistent

- **Decision**: le pouvoir est testé d'abord ; l'identité SSO prime (Clarifications).
- **Rationale**: traçabilité individuelle, objet de l'issue.

## D4. Front : formulaire et bouton de déconnexion

- **Decision**: aucune modification d'`AccessGate` ni du chargement : `useFileValidation` n'affiche le formulaire que sur un 401 de la file, que l'administrateur ne reçoit plus. Le bouton « Se déconnecter » est masqué quand `useSession().data?.permissions` contient `benevole_access:manage`.
- **Rationale**: les pouvoirs effectifs exposés par `/auth/me` incluent ceux d'un superutilisateur (`authorization.effective_permissions`), donc le front lit le même critère que la garde, sans liste tenue côté client.
- **Alternatives considered**: un indicateur dans la réponse de la file (changerait le contrat de `GET /benevoles/queue`) ; laisser le bouton (promet une déconnexion qui n'a pas lieu, Clarifications).
