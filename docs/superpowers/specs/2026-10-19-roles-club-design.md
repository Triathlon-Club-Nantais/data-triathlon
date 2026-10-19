# Rôles du club : bureau, bénévoles data, validation, encadrement (#1654)

## Intention

Avec les comptes membres (epic #1312), beaucoup de comptes existent, tous sans rôle. Le club va confier des droits à certains : bureau, bénévoles qui entretiennent les données, validation des saisies, encadrants jeunes. Les trois rôles semés au premier jour (`admin`, `validator`, `moderator`, #115) ne couvrent pas ces profils, et `athlete_claims:review` (#1325) n'est porté par aucun rôle. Le mainteneur a demandé de partir sans questions et d'ajuster ensuite : les choix ci-dessous sont les miens, marqués comme tels.

## Objectifs

- Semer quatre rôles nouveaux, cohérents et documentés, par une migration Alembic.
- Les décrire dans le guide d'administration.
- Un test qui fige la composition semée et la borne au catalogue.

## Non-objectifs

- Recomposer `admin`, `validator`, `moderator` : leur composition est une donnée d'exploitation (#115, FR-041), aucune migration ne la réécrit.
- Attribuer un rôle à qui que ce soit : l'attribution reste un geste de l'écran « Rôles des utilisateurs ».
- Changer la garde de non-amplification ou l'invariant du dernier administrateur.

## Anti-objectifs

- Un rôle non superutilisateur qui porterait un geste irréversible sur toute la base, ou le pouvoir de distribuer des rôles.
- Une migration qui écraserait un rôle déjà créé à la main sous le même slug.

## Les rôles (mes choix)

| Slug | Nom | Pouvoirs |
|---|---|---|
| `bureau` | Bureau | `users:read`, `roles:read`, `admin_log:read`, `allowed_emails:manage`, `site_access:manage`, `benevole_access:manage`, `groups:read`, `groups:write`, `groups:assign`, `member_emails:manage`, `club_members:manage`, `athlete_claims:review`, `oppositions:manage`, `feedback:read`, `feedback:manage`, `pages:preview` |
| `data` | Bénévole data | `quality:override`, `pending_providers:read`, `pending_providers:handle`, `courses:write`, `courses:sources`, `athletes:read`, `athletes:write`, `participations:reassign`, `club_aliases:manage`, `counter_scope:manage`, `batch:read`, `feedback:read`, `athlete_claims:review`, `pages:preview` |
| `validation` | Validation | `athletes:season_validate`, `athletes:volunteer_validate`, `benevole_access:manage` |
| `encadrant` | Encadrant jeunes | `jeunes:read`, `jeunes:write` |

- `athlete_claims:review` au bureau **et** aux bénévoles data : les homonymes sont leur quotidien.
- Restent au seul superutilisateur : `courses:delete`, `courses:wipe_all`, `participations:delete`, `participations:wipe_all`, `batch:run`, `roles:write`, `roles:assign`, `sessions:revoke`.
- `validator` et `moderator` restent tels quels (leurs titulaires ne perdent rien) ; `data` les recouvre, l'admin peut les retirer à la main plus tard.
- Les rôles se cumulent nativement (`user_roles`).

## Contraintes et décisions de construction (mes choix)

- Rôles **globaux** (`organisation_id` nul, comme les trois premiers), `is_system = False` : le club peut les renommer, les recomposer ou les supprimer depuis l'écran.
- Migration **idempotente** : un slug déjà présent n'est ni recréé ni recomposé. La descente supprime les quatre rôles seulement s'ils ne sont attribués à personne (sinon elle ne touche à rien de ces rôles).
- La composition vit dans la migration (figée à sa date), pas dans le code applicatif : un rôle édité à chaud ne doit pas être « corrigé » par le code.

## Laissé au constructeur

- Les libellés de description des rôles et la rédaction de la section du guide.
