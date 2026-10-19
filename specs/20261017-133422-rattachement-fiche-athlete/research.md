# Research: Revendiquer sa fiche athlète

## R1. Où vit la demande ?

**Decision**: table `athlete_claims`, `UNIQUE(user_id)`, états `pending` et `rejected`. Validée, la ligne est supprimée et `users.athlete_id` posé.

**Rationale**: le rattachement validé a déjà sa colonne (`users.athlete_id`, N comptes → 1 fiche, #114) que la fusion de fiches déplace et que l'opposition vide. Une ligne par compte rend « une demande au plus » vraie par la base, pas par une lecture préalable. L'historique des décisions est le journal d'administration (#935).

**Alternatives considered**: statut `approved` gardé dans la table (second exemplaire du rattachement, à tenir cohérent avec `users.athlete_id`) ; colonne `claim_status` sur `users` (interdit : aucun statut sur `users`, #115).

## R2. Propriété et suppressions

**Decision**: `athlete_claims.user_id` sans `ondelete`, cascade ORM depuis `User.athlete_claim` (`delete-orphan`), table ajoutée à `user_repository._OWNED_TABLES`. `athlete_claims.athlete_id` en `ON DELETE CASCADE` ; `opposition_service` supprime explicitement les demandes de la fiche (SQLite n'applique pas les FK) ; `athlete_merge` les reporte sur la fiche conservée.

**Rationale**: même patron que `identities`/`user_sessions` côté compte (#1326 lit les références depuis le schéma : une table non déclarée possédée deviendrait une référence obligatoire qui bloquerait la suppression du compte). Côté fiche, patron d'`athlete_aliases` : la demande n'a pas de sens sans sa fiche.

## R3. Indices de la file

**Decision**: pour chaque demande, licencié TCN de la saison en cours rattaché à la fiche (`club_members`, `season = current_season()`, `athlete_id`), présence de l'adresse du compte dans `member_emails` (même règle que `membership`), nombre de comptes déjà rattachés à la fiche. Lus par lot (une requête par indice pour toute la file).

**Rationale**: SC-002, un geste sans autre écran ; la liste d'adhérents devient un indice, conformément à la décision « jamais d'office ».

## R4. Relais vers les surfaces de l'interface

**Decision**: un composant `SessionAthleteSync` (providers) écrit la fiche de la session dans le stock `tcn-athlete` quand elle diffère, et le vide au détachement. Les gestes qui changent d'athlète (choisir, relâcher, invitation) sont masqués pour un compte rattaché.

**Rationale**: sept surfaces lisent `useSelectedAthlete` ; les faire lire la session réécrirait l'arbitrage de `docs/frontend/athlete-retenu.md` sept fois. Le stock reste la seule lecture, sa source change. Le stock ne contient que l'identifiant et le nom de la fiche du titulaire, déjà le cas aujourd'hui.

**Alternatives considered**: `useSelectedAthlete` lit la session d'abord (couple le stock à React Query et à `/auth/me` sur toutes les pages, rendu serveur compris).

## R5. Routes utilisateur

**Decision**: sous `/auth/me` (`POST`/`DELETE /auth/me/athlete-claim`, `DELETE /auth/me/athlete`), à côté de `DELETE /auth/me` (#1326) : elles ne portent que sur soi, exigent une session et rien d'autre.

**Rationale**: le routeur `auth` est exempté de la garde du site, ce qui est juste ici (un compte qui demande sa fiche n'a pas forcément le code) ; la seule information exposée est l'existence d'un identifiant de fiche, déjà publique par les URL.

## R6. Pouvoir

**Decision**: `athlete_claims:review`, `kind` administration, rejoint le catalogue ; la migration ne l'accorde à aucun rôle existant (le superutilisateur le porte d'office, un admin l'accorde depuis l'éditeur de rôles).

**Rationale**: patron des pouvoirs ajoutés depuis #115 (FR-017 : un pouvoir par écran, jamais un rôle).
