# Plan : rôles du club (#1654)

Design : `docs/superpowers/specs/2026-10-19-roles-club-design.md`. Exécution : `executing-plans`, en ligne, commits directs sur `epic/1312-member-accounts`.

## Tâche 1 : test de la migration (rouge)

- `backend/tests/test_migrations.py` :
  - le test « exactement trois rôles système » devient « les trois rôles système restent système » (ils sont toujours là, `is_system`, globaux) ;
  - nouveau test : après `head`, les quatre rôles existent, globaux, non système, non superutilisateurs, avec exactement leur composition ; chaque code est du catalogue ; aucun ne porte un pouvoir réservé au superutilisateur ;
  - nouveau test : un rôle `bureau` créé à la main avant la migration n'est ni dupliqué ni recomposé ;
  - nouveau test : descente puis remontée.
- Lancer, constater l'échec.

## Tâche 2 : migration

- `alembic revision -m "club roles (#1654)"` chaînée sur la tête de l'epic ; constante `CLUB_ROLES`, insertion des rôles absents et de leurs pouvoirs ; descente qui supprime les rôles semés non attribués.
- Tests verts.

## Tâche 3 : guide

- Section « Droits des rôles » du guide d'administration (`frontend/components/guide/guide-content.admin.ts`) : une étape qui décrit les rôles fournis et pour qui ; test du guide si besoin.

## Tâche 4 : vérification et livraison

- Suites backend et frontend, ruff, lint.
- Commit, push, `Closes #1654` dans la description de #1379, carte « In review ».
