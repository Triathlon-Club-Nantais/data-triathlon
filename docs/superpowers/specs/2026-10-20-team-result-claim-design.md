# Revendiquer un résultat d'équipe depuis Mon espace (#1739)

Design issu du brainstorming du 20/10/2026. Jalon v0.9.0 (palier 2, gel des
features jeudi 22/10 au soir). Exécution prévue : `subagent-driven-development`.

## Intention

Un adhérent dont le compte est rattaché à sa fiche (#1325) doit pouvoir
retrouver seul un résultat de swimrun, raid ou relais publié sous le **seul nom
d'équipe**, et le faire apparaître sur sa fiche, sans écrire au club. Parcours
court et intuitif : une saisie, un clic.

Ce qui existe déjà :

- #894 : un admin compose un relais (2 à 8 équipiers, table
  `participation_teammates`, `admin_actions.set_teammates`, fenêtre « Attribuer
  aux équipiers »).
- #895 : l'import découpe déjà une équipe en une ligne par équipier quand le
  chronométreur publie les noms.
- #1637 : « Ce résultat est à moi », demande validée par le back-office, qui
  **refuse les relais** (`result_claims.request_claim`, garde `is_relay`).

## Mesuré en prod (lecture seule, 20/10/2026)

- 3 808 résultats de relais sont rangés sur une **fiche d'équipe** (prénom vide,
  nom = nom d'équipe), sans composition, sur 157 épreuves. Volume en hausse :
  348 en 2024, 1 136 en 2025, 2 324 en 2026.
- 3 seulement comptent pour le club ; 87 % n'ont aucun club. Un adhérent ne les
  voit donc pas dans les vues du club : il doit les chercher **par le nom
  d'équipe**.
- Sur ces fiches, le nom d'équipe est porté par `Athlete.nom` ;
  `Participation.team_name` est le plus souvent vide (il n'est rempli qu'à la
  composition ou par certains imports).
- 9 033 autres résultats de relais sont déjà sur des fiches de personnes : hors
  sujet.

## Objectifs

1. Dans la colonne de droite de Mon espace, une carte toujours visible
   « Un résultat d'équipe manque ? » avec un champ de recherche par nom d'équipe
   (option A des maquettes, choisie par l'utilisateur).
2. Les résultats s'affichent sous le champ : nom d'équipe, épreuve, date, rang,
   temps. Un bouton « C'était mon équipe » par ligne envoie la demande en un
   clic ; la ligne affiche alors « Demande envoyée, le club va vérifier ».
3. La demande rejoint la **même file** du back-office que « Ce résultat est à
   moi » (#1637), avec une pastille qui la distingue (`ClaimKind`, troisième
   sorte « Résultat d'équipe »).
4. Valider ajoute la fiche de l'adhérent à la composition de l'équipe (#894).
   Si une composition existe déjà, l'admin tranche à la validation, dans la
   fenêtre « Attribuer aux équipiers » existante.
5. Refuser fonctionne comme pour #1637 (statut refusé visible de l'auteur).

## Non-objectifs

- L'adhérent ne désigne pas ses partenaires lui-même.
- Pas de validation automatique, jamais.
- Pas de demande groupée pour un duo : chaque équipier adhérent envoie la
  sienne ; la seconde validation complète la composition posée par la première.
- La carte ne sert pas à revendiquer un résultat individuel (rôle de #1637).

## Anti-objectifs

- Un résultat qui change de fiche sans qu'un humain du club l'ait validé.
- Exposer par la recherche une identité visée par une opposition RGPD (#1506,
  #1514) ou un résultat en attente de validation (#1615).
- Toucher `frontend/app/(public_restricted)/mon-espace/` (d'autres sessions y
  travaillent cette semaine) : la carte vit dans
  `frontend/components/mon-espace/ColonneDroite.tsx` et un nouveau composant
  frère.

## Contraintes

- Réservé à un compte **rattaché** (`user.athlete_id` non nul), comme #1637.
- Plafond de demandes en attente partagé avec #1637 (`MAX_PENDING`).
- Une demande par compte et résultat (`uq_result_claim_user_participation`).
- Recherche : seulement les résultats de relais (`is_relay` sur la
  participation ou l'épreuve), non rejetés, non en attente de validation, dont
  l'adhérent ne fait pas déjà partie (porteur ou équipier). Le nom d'équipe
  cherché est `team_name` **ou** le nom de la fiche porteuse quand c'est une
  fiche d'équipe.
- Couches : `api → services → repositories`, requêtes dans les repositories
  seulement. API sous `/api/v1`, ajout uniquement (Principe IV).
- TDD non négociable.
- Copie française, vouvoiement, « épreuve » et « athlète » (`frontend/AGENTS.md`).
- Composants `tcn/` pour la carte (écran public).

## Décidé avec l'utilisateur

- Emplacement : carte dans la colonne de droite de Mon espace (option A).
- Parcours : étendre « Ce résultat est à moi », même file back-office.
- Composition existante : l'admin tranche à la validation.
- Voie Superpowers, exécuteur `subagent-driven-development`.

## Ce que fait la validation (décidé par l'utilisateur)

`set_teammates` exige 2 à 8 équipiers. La validation reste **en un clic** et
garde la fiche d'équipe comme « le reste de l'équipe » :

- **Résultat sans composition** (porté par la fiche d'équipe) : la composition
  devient `[fiche de l'adhérent, fiche d'équipe]`. L'adhérent devient porteur,
  la fiche d'équipe reste équipière (donc n'est pas purgée) et `team_name` prend
  le nom de la fiche d'équipe (comportement actuel de `set_teammates`).
- **Composition déjà posée qui contient encore la fiche d'équipe** : la fiche de
  l'adhérent **remplace** la fiche d'équipe s'il reste 2 équipiers ou plus sans
  elle, sinon elle s'ajoute à côté. La fiche d'équipe vidée est alors purgée par
  le mécanisme existant (`delete_orphans_among`). Un duo complet après deux
  validations vaut donc `[adhérent A, adhérent B]`.
- **Composition déjà posée sans fiche d'équipe** (composée par un admin ou par
  #895) : pas d'écriture automatique. L'admin tranche dans « Attribuer aux
  équipiers », prérempli avec la composition actuelle plus l'adhérent, puis la
  demande est close.
- Un admin peut toujours retirer la fiche d'équipe à la main dans « Attribuer aux
  équipiers ».

## Tranché par le concepteur (à relire)

- **Sorte de demande** : une colonne `kind` sur `result_claims` (`result` |
  `team`), avec migration, plutôt qu'une déduction depuis `is_relay`. La garde
  `is_relay` de `request_claim` reste pour la sorte `result` ; la sorte `team`
  n'accepte **que** des relais. `approve` choisit son chemin d'après `kind`.
  `ClaimKind` (pastille du back-office) gagne la troisième sorte.
- **Périmètre de la recherche** : participations de relais, non rejetées, non en
  attente de validation, dont l'adhérent n'est ni porteur ni équipier, et qui
  sont **soit** portées par une fiche d'équipe (prénom vide), **soit** déjà
  composées. Correspondance partielle insensible à la casse et aux accents sur
  `team_name` ou sur le nom de la fiche porteuse. Les relais déjà découpés par
  équipier sur des fiches de personnes (#895, les 9 033) sont exclus : chacun y a
  déjà sa ligne, le geste de #1637 s'y applique. `is_team_label` ne sert pas de
  critère, il ne reconnaît que les libellés « A & B ».
- **Opposition RGPD et résultats en attente** : la recherche n'expose rien de
  plus que le classement public de l'épreuve. Elle applique les mêmes filtres que
  lui (opposition #1506/#1514 sur les équipiers composés, `is_pending_validation`).
- **Indices pour l'admin** : la file montre la composition actuelle et signale si
  la fiche de l'adhérent a déjà un résultat sur l'épreuve (`set_teammates`
  lèverait alors `DuplicateError`, rendu tel quel).
- **État côté adhérent** : la carte lit les demandes du compte (`list_mine`).
  Une demande en attente affiche « Demande envoyée, le club va vérifier » ; une
  demande refusée affiche « Refusée » et ne se renvoie pas (contrainte d'unicité
  existante, comme #1637). Une demande validée disparaît, le résultat est sur la
  fiche.

## Laissé au builder

- Forme exacte de l'endpoint de recherche (sous `/auth/me/…`, longueur minimale
  de saisie, nombre de résultats, plafond de débit).
- Le libellé exact des textes de la carte.
