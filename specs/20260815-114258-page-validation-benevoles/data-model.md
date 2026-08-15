# Data Model: Page de vérification des résultats par les bénévoles

Aucun nouveau schéma de données porté par cette feature — elle **consomme** un
champ produit par #270 et **réutilise** des entités déjà normalisées. La seule
addition est une ligne de données (pas une colonne), détaillée en D2 de
`research.md`.

## Entités consommées (existantes, non modifiées ici)

### Participation (`backend/app/models/participation.py`, sur #270)

Champs pertinents pour cette feature — **tous produits par #270, pas par ici** :

| Champ | Type | Rôle pour #271 |
|---|---|---|
| `is_pending_validation` | `bool` | Pivot de la file : `true` = à traiter, `false` = validé. Cette feature le lit (file) et l'écrit (validation). |
| `evidence_url` | `str \| None` | Pièce justificative affichée au bénévole ; lecture seule ici. |
| `team_name` | `str \| None` | Distingue un résultat collectif ; lecture seule ici. |
| `athlete_id` | `int` (FK) | Écrit par le geste de réattribution (via `admin_actions.reassign_participation`, réutilisé). |
| `course_id` | `int` (FK) | Lu pour résoudre l'épreuve associée ; jamais réécrit directement (le renommage touche `Course`, pas ce FK). |
| `splits`, `total_time`, `category`, `club`, `bib_number` | — | Affichés en lecture seule dans le panneau de correction. |

**Transition d'état** : `is_pending_validation: true → false`, un seul sens.
Cette feature ne réintroduit jamais un résultat validé dans la file (pas de
« dévalidation » demandée par l'issue).

### Course (`backend/app/models/course.py`)

Champ réécrit : le nom (`name`), au travers de `admin_actions.update_course`
déjà existant (réutilisé, pas réécrit). Contrainte d'unicité inchangée
(`name`, `event_date`, `event_type`, `is_relay`) ; la détection de collision est
déjà portée par cette fonction (`course_repository.get_by_identity`).

### Athlete (`backend/app/models/athlete.py`)

Lu pour la recherche de la cible d'une réattribution ; jamais créé depuis cet
écran (cf. spec § Edge Cases). Écriture de `Participation.athlete_id` déléguée
à `admin_actions.reassign_participation`, déjà existant.

### AdminActionLog (`backend/app/models/admin_action_log.py`)

Réutilisé sans modification de schéma. Trois actions y seront journalisées
depuis cette feature, sous le `user_id` du compte système (cf. ci-dessous) :
`course.update` et `participation.reassign` (actions déjà nommées, réutilisées
telles quelles) et une nouvelle action `participation.validate` (geste 4,
propre à cette feature).

## Addition : compte système « bénévoles »

**Une ligne de données dans `users`**, pas une migration de schéma — la table
existe déjà (#114). Créée par une migration Alembic de **données** (`op.execute`
sur un `INSERT` idempotent, ou une fonction dédiée dans `alembic/versions/`),
jamais par le code applicatif à la volée : un compte système ne doit pas
apparaître ou disparaître selon l'ordre des requêtes.

- Aucune ligne `identities` associée : ce compte ne s'authentifie jamais par
  OAuth, il existe uniquement comme cible de `AdminActionLog.user_id`.
- Nom d'affichage reconnaissable dans le journal (ex. « Bénévoles (accès
  partagé) »), pour qu'un futur lecteur du journal d'audit comprenne
  immédiatement qu'une ligne provient de cet accès partagé et non d'un
  administrateur SSO individuel.
- Ne porte aucun rôle RBAC (#115) : il n'en a pas besoin, l'accès à cette
  feature ne passe pas par ce système.

## Aucune nouvelle table

Le mécanisme d'accès (cookie signé, cf. `research.md` §D1) ne persiste rien :
ni jeton, ni tentative de connexion, ni verrou après échecs répétés — hors
périmètre de cette spec faute d'exigence explicite (cf. spec § Assumptions).
