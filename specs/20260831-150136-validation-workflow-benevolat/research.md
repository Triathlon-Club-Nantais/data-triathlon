# Research: Workflow de validation admin des actions de bénévolat (#779)

## D1 — Vocabulaire des statuts : `en_attente`/`validee`/`refusee`

**Décision** : pas les mots anglais du brouillon de l'issue
(« pending/validated/rejected »).

**Rationale** : `VolunteerAction.status` (#778) et
`VolunteerDeclaration.status` (#751) partagent déjà `"en_attente"`/
`"validee"` — introduire un troisième vocabulaire dans le même domaine
« bénévolat » reproduirait la divergence que #778 a explicitement évitée
(recherche d'athlète, noms de schéma). `"refusee"` complète la même série.

## D2 — Une seule permission, pas un couple lecture/décision

**Décision** : `athletes:volunteer_validate` couvre consultation de la file
**et** décision (accepter/refuser) — pas de `_read`/`_manage` séparés comme
`benevolat:read`/`benevolat:manage` (#751).

**Rationale** : l'issue #779 demande explicitement « une nouvelle
permission dédiée » (singulier). Le volume attendu (quota d'un club, pas
une plateforme ouverte) ne justifie pas de séparer qui peut voir de qui
peut décider — contrairement à #751 où lecture et décision servent des
audiences distinctes (rapporté par l'issue #751 elle-même). Nommage
`athletes:*` (pas `volunteer_action:*`) : cohérent avec
`athletes:volunteer_manage`/`athletes:season_validate`, les deux pouvoirs
voisins de la même feature `FEATURE_ATHLETES` (#709).

## D3 — `exists_for_athlete_season` filtre désormais sur `status == "validee"`

**Décision** : modifier la fonction existante
(`volunteer_action_repository.exists_for_athlete_season`) plutôt que d'en
ajouter une nouvelle.

**Rationale** : un seul appelant dans tout le dépôt
(`admin_actions.season_quota`, grep vérifié) — aucun risque de changer un
comportement partagé par accident. Ajouter une deuxième fonction
(`exists_validated_for_athlete_season`) aurait laissé l'ancienne inutilisée
mais toujours exportée, un piège pour un futur appelant qui la
redécouvrirait sans le filtre (Principe VI).

## D4 — Endpoints par id de déclaration, pas par athlète+saison

**Décision** : `POST /admin/volunteer-actions/{action_id}/accept` et
`.../reject`, patron `admin_volunteer_declarations.py` (#751) —
`.../{declaration_id}/validate`.

**Rationale** : une décision porte sur **une ligne précise** du journal
(plusieurs peuvent coexister pour le même `(athlete_id, season)`,
research.md D4 de #709/#778) ; un endpoint scopé athlète+saison ne saurait
pas laquelle instruire. Patron déjà en place et déjà testé sur
`admin_volunteer_declarations.py` — pas de nouvelle forme à inventer.

## D5 — `AdminVolunteerActionOut` distinct de `VolunteerActionSelfOut`

**Décision** : nouveau schéma de réponse pour la file d'admin, avec
`title`/`description` **optionnels** — pas de réutilisation de
`VolunteerActionSelfOut` (#778), dont ces deux champs sont `str` non
nullable.

**Rationale** : FR-001 et l'edge case de spec.md exigent que la file
admin liste **aussi** les lignes créées par le chemin admin existant
(#709), dont `title`/`description` restent `NULL` en base — les sérialiser
via un schéma qui les déclare `str` obligatoires lèverait une erreur de
validation Pydantic. Nommé `AdminVolunteerActionOut`, sur le patron
`AdminVolunteerDeclarationOut` (#751).

## D6 — Refuser une déclaration déjà validée est autorisé

**Décision** : `reject()` accepte les statuts `"en_attente"` **et**
`"validee"` en entrée, jamais un verrou une fois « validée ».

**Rationale** : posé en Assumptions de spec.md — un admin doit pouvoir
revenir sur une acceptation erronée. `accept()`, symétriquement, n'accepte
que `"en_attente"` en entrée significative : pour tout autre statut de
départ — `"validee"` (déjà couvert) **et** `"refusee"` (finding U1 de
`/speckit-analyze`, précisé après coup) —, c'est un no-op, jamais une
erreur ni une transition. Valider une ligne `"refusee"` reste hors
périmètre fonctionnel (aucun FR ne l'exige), mais le comportement du code
sur ce cas n'est plus laissé à l'implémentation : no-op, explicitement.

## D7 — Journal d'administration : `entity_type="athlete"`, pas
`"volunteer_action"`

**Décision** : `admin_action_log_repository.create(..., entity_type=
"athlete", entity_id=athlete_id, payload={"season": ..., "action_id": ...})`
pour `accept`/`reject`.

**Rationale** : cohérent avec l'entrée déjà posée par
`declare_volunteer_action` (#709) — `action="athlete.volunteer_action.create"`,
`entity_type="athlete"`. Utiliser `entity_type="volunteer_action"` (patron
#751) aurait fait diverger deux entrées du même journal pour la même
famille d'objet, sans bénéfice — le patron à suivre ici est celui déjà en
place sur `VolunteerAction`, pas celui de la table voisine et indépendante.
