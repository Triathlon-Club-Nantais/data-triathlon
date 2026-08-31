# Research: Formulaire public de déclaration de bénévolat (#778)

## D1 — Étendre `VolunteerAction`, pas créer une table de plus

**Décision** : ajouter `title`/`description`/`status` à `VolunteerAction`
(`athlete_id`, quota de saison), pas les rattacher à `VolunteerDeclaration`
(#751, `user_id`, trace de vie associative).

**Rationale** : les deux entités répondent à des besoins distincts malgré la
ressemblance de surface — l'une crédite le quota de saison d'un *athlète*
(y compris un athlète sans compte), l'autre trace l'activité d'un *membre
connecté*. Décidé avec l'utilisateur (voir conversation) après avoir
explicitement signalé le chevauchement de PR #769.

**Alternatives rejetées** : fusionner dans `VolunteerDeclaration` en ajoutant
un `athlete_id` optionnel — rejeté, aurait rouvert la spec de #751 tout juste
mergée et mélangé deux cycles de validation (l'un lié à un quota, l'autre non)
dans une seule table.

## D2 — Recherche d'athlète : réutiliser `GET /athletes`, pas une nouvelle route

**Décision** : le nouveau formulaire interroge la route publique existante
`GET /api/v1/athletes?name=` (déjà utilisée par la page `/athletes` et sans
garde RBAC), pas `GET /benevoles/athletes` ni une route inédite.

**Rationale** : `GET /athletes` est déjà accessible à la population visée
(un adhérent qui a atteint `/benevolat` a déjà franchi `require_site_access`,
seule garde de cette route). Le twin `/benevoles/athletes` existe
précisément parce que la population bénévoles n'a **pas** cette garde
(`client.ts:611-617`) — un problème que #778 n'a pas, puisque sa page vit
déjà sous `(public_restricted)`. Créer une troisième route de recherche
identique aurait violé le Principe VI (YAGNI) sans bénéfice : mêmes
résultats (`AthleteBrief`, pas de date de naissance), même filtre nom/prénom
insensible casse/accents (`athlete_repository.search` → `name_filter`).

**Alternatives rejetées** :
- Nouvelle route `GET /volunteer-actions/athletes` dupliquant
  `athlete_repository.search` — rejetée, aucune différence de comportement
  ne le justifie.
- `GET /athletes/search` (palette ⌘K, tri par pertinence + `participation_count`)
  — rejetée, plus lourde que nécessaire (jointure de comptage) pour un simple
  champ de recherche de formulaire ; `GET /athletes` suffit et c'est ce que
  `AthleteBrief` (sans champ superflu) sert déjà.

## D3 — Nouvelles colonnes nullables, pour ne pas casser le bouton admin existant

**Décision** : `title`/`description` sont `nullable=True` au niveau DB ;
l'obligation « non vide » (FR-004) n'est imposée que par le schéma Pydantic
du **nouveau** endpoint self-service.

**Rationale** : FR-008 interdit de toucher le bouton admin existant
(`SeasonValidationPanel.DeclarerBenevolat` → `POST /admin/athletes/{id}/
volunteer-actions` → `admin_actions.declare_volunteer_action` →
`volunteer_action_repository.create`), qui ne fournit aujourd'hui ni titre ni
description. Des colonnes `NOT NULL` sans défaut auraient cassé cet appel dès
la migration appliquée.

## D4 — `status` non nullable, défaut `"en_attente"` au niveau DB

**Décision** : `status` est `NOT NULL`, `server_default="en_attente"` — donc
posé automatiquement sur les lignes déjà existantes (backfill de migration)
et sur celles créées par le bouton admin non modifié, sans changement de code
sur ce chemin.

**Rationale** : contrairement à `title`/`description`, `status` a une valeur
par défaut sensée pour toute ligne, ancienne ou nouvelle — poser un défaut au
niveau DB évite tout `NULL` à gérer plus tard (#779, quand le statut devient
significatif pour le quota). Valeurs `"en_attente"` / `"validee"` alignées sur
le vocabulaire déjà choisi par #751 (`VolunteerDeclaration.status`) — pas de
couplage entre les deux tables, seulement une cohérence de nommage dans le
domaine « bénévolat » du dépôt.

## D5 — Saison dérivée côté serveur, pas transmise par le client

**Décision** : le nouvel endpoint calcule `season` via
`app/core/season.current_season()`, il ne le lit pas dans le corps de la
requête (contrairement à l'endpoint admin existant, `VolunteerActionCreate.
season`, qui reste tel quel — FR-008).

**Rationale** : le spec (§Assumptions) exclut tout sélecteur de saison dans
le nouveau formulaire — il n'y a donc aucune valeur légitime que le client
pourrait vouloir transmettre. Dériver côté serveur retire un champ
manipulable sans bénéfice fonctionnel.

## D6 — Pas d'entrée `AdminActionLog`

**Décision** : la création via le nouveau formulaire ne journalise rien dans
`AdminActionLog`.

**Rationale** : ce journal trace l'exercice d'un **pouvoir** RBAC
(`admin_actions.py`, `benevole_access`…). Le nouveau geste n'exige aucun
pouvoir — même patron que `volunteer_declaration_service.create_self`, qui ne
journalise pas non plus l'auto-déclaration (seuls `create_for_other`,
`validate` et `delete_any`, tous réservés à `benevolat:manage`, le font).

## D7 — Emplacement UI : nouvelle section sur `/benevolat`, pas une nouvelle route

**Décision** : le formulaire s'ajoute comme une **seconde section**, sous son
propre intitulé, sur la page existante `(public_restricted)/benevolat` —
pas une nouvelle route.

**Rationale** : cette page porte déjà la garde de session (`useSession`,
invite à se connecter sinon) que #778 requiert à l'identique (FR-003/FR-005).
Dupliquer cette garde sur une nouvelle route pour une seule section
supplémentaire n'ajoute rien (Principe VI). Les deux sections restent
visuellement et sémantiquement distinctes (intitulés différents : « Déclarer
mon activité » vs « Créditer un athlète pour le quota de saison ») pour ne
pas laisser croire à un seul et même mécanisme.

**Alternative rejetée** : fiche athlète (`/athletes/{id}`) — rejetée par
l'issue elle-même (« pas nécessairement la fiche athlète »), et parce que le
geste part d'une recherche d'athlète, pas d'une fiche déjà ouverte.
