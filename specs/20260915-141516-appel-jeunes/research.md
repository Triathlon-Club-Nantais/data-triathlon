# Research: Appel de présence jeunes

## D1 — Persistance de l'appel de début

**Decision**: une colonne `present: bool | None` (nullable, défaut `NULL`)
ajoutée à `EntrainementParticipant`, plutôt qu'une table de présence séparée.
`NULL` = pas encore pointé, `True`/`False` = le dernier statut enregistré.

**Rationale**: la granularité voulue — « ce jeune, à cette séance » — est
exactement celle que porte déjà la ligne `EntrainementParticipant`
(`UNIQUE(entrainement_id, jeune_id)`, #868). Une table séparée
`presences(entrainement_id, jeune_id, present)` dupliquerait cette même paire
de clés étrangères sans rien gagner : aucune de ses lignes ne pourrait exister
sans une inscription correspondante, et la contrainte d'unicité serait
retenue deux fois. Le patron déjà présent dans le dépôt pour « une valeur qui
qualifie une relation N-N existante » est d'ajouter la colonne sur la table de
liaison elle-même (`Participation.is_pending_validation` sur la relation
épreuve-participant), jamais une seconde table miroir.

**Alternatives considered**:
- Table `entrainement_presences` séparée — rejetée pour la raison ci-dessus
  (duplication de la paire de FK, deuxième contrainte d'unicité à maintenir en
  cohérence avec la première).
- Enum à trois valeurs (`absent`/`present`/`non_pointe`) plutôt qu'un booléen
  nullable — rejetée : SQLAlchemy représenterait ce troisième état par
  `NULL` de toute façon côté SQLite (pas d'`ENUM` natif), et un booléen
  nullable dit exactement la même chose avec un type déjà répandu dans le
  modèle (`is_pending_validation`, `is_reliable`…). Une colonne
  supplémentaire dédiée à un horodatage du pointage n'est pas retenue non
  plus : rien dans la spec (FR-005 — « seul le dernier statut fait foi, sans
  historique ») n'en a besoin.

## D2 — L'appel de fin n'a aucune écriture ni route dédiée

**Decision**: l'appel de fin est un recalcul **purement frontend** sur les
données déjà rendues par `GET /admin/jeunes/entrainements/{id}` (la liste des
participants et leur `present`). Un composant dédié (`AppelFin.tsx`) filtre
côté client les seuls participants `present === true`, garde une liste de
cases cochées en état React local, et ne fait aucun appel réseau d'écriture.

**Rationale**: FR-007 l'exige explicitement — « son résultat n'a jamais été
conservé ». Poser une route ou une table pour un état qui doit disparaître au
rafraîchissement de l'écran serait une indirection sans bénéfice (Principe
VI) : le seul consommateur de cet état est l'écran qui vient de le produire,
dans la même session d'utilisation. Le composant se remonte (donc réinitialise
son état) à chaque ouverture de l'onglet « Appel de fin », ce qui satisfait
littéralement « repart vierge » (Edge Cases de spec.md) sans code dédié à la
remise à zéro.

**Alternatives considered**:
- Table ou colonne `present_fin` séparée, persistante — rejetée : contredit
  FR-007 explicitement, et doublerait la question déjà tranchée en D1 (où
  stocker un présent/absent par jeune et par séance) pour un état que la
  feature ne demande pas de conserver.
- `sessionStorage` pour survivre à une navigation accidentelle sans tout
  perdre — rejetée : non demandé, ajouterait une source de vérité
  supplémentaire (le stockage navigateur) à synchroniser avec la liste des
  participants réellement inscrits ; l'edge case de spec.md accepte
  explicitement qu'un rafraîchissement reparte à zéro.

## D3 — Notes : aucun second mécanisme

**Decision**: la note de séance devient une colonne `note: str` (Text, défaut
`""`) sur `Entrainement`, écrite via l'endpoint `PATCH` d'entraînement déjà
existant (`EntrainementUpdate`, patron sentinelle `...` déjà en place pour
`lieu`/`type_seance`). La note sur un jeune réutilise tel quel
`POST /admin/profiles/{profile_id}/log-entries` (#867) — aucune route, aucun
schéma, aucune table nouvelle côté notes individuelles.

**Rationale**: l'issue #869 demande explicitement de réutiliser le journal de
bord de #867 plutôt que d'inventer un second mécanisme — la table
`profile_log_entries` (`entry_date`, `text`, `created_by_user_id`) couvre déjà
exactement le besoin (une note datée, attribuée, conservée dans l'historique
du profil). La note de séance, elle, n'a pas d'équivalent existant : elle
n'est pas une propriété d'un jeune mais de la séance entière, donc elle
rejoint le seul objet qui porte déjà ce périmètre, `Entrainement`, plutôt que
d'ouvrir une table à une seule colonne texte pour un besoin qui tient dans un
champ.

**Alternatives considered**:
- Table `entrainement_notes` séparée (plusieurs notes par séance, comme le
  journal d'un jeune) — rejetée : rien dans la spec ne demande un historique
  de notes de séance (une seule note, modifiable), à la différence du journal
  d'un jeune qui est explicitement un historique cumulatif (#867). Une table
  pour une seule valeur par séance serait une indirection sans bénéfice
  mesuré (Principe VI).
- Nouveau type d'entrée dans `profile_log_entries` pour la note de séance (en
  y ajoutant un `entrainement_id` nullable) — rejetée : mélangerait deux
  natures d'observation (le journal d'**un** jeune vs. le rapport d'**une**
  séance) dans la même table, contredisant sa forme actuelle et son usage déjà
  établi par #867.

## D4 — `ParticipantAdd`/`add_participant` généralisés plutôt que dupliqués

**Decision**: `ParticipantAdd` gagne un champ optionnel `present: bool | None
= None` ; `entrainement_repository.add_participant` et
`services/jeunes/entrainements.add_participant` gagnent le même paramètre,
répercuté sur la ligne créée ou existante. Inscrire un jeune non encore
enregistré et le pointer présent, pendant l'appel, se fait donc en un seul
appel API — `POST .../participants` avec `{jeune_id, present: true}`.

**Rationale**: FR-004 (« ajouter un jeune non encore inscrit, l'inscrire au
même geste que son premier pointage ») a deux solutions : deux appels réseau
chaînés (inscrire, puis pointer), ou un seul champ optionnel supplémentaire
sur la route déjà existante. Un encadrant au bord d'un bassin, sur un réseau
mobile incertain, ne doit pas dépendre de la réussite de deux requêtes
successives pour un seul geste utilisateur (mobile-first, Constraints du
plan). Étendre `ParticipantAdd` d'un champ optionnel est strictement additif
(Principe IV) : tout appelant existant qui omet `present` obtient exactement
le comportement actuel (`NULL`, pas de changement de contrat).

**Alternatives considered**:
- Deux appels séquentiels côté frontend (`POST .../participants` puis `PATCH
  .../presence`) — rejetée : fragilise le geste unique de l'utilisateur sur
  un réseau incertain, pour éviter un unique paramètre optionnel côté
  service, qui ne duplique rien (la même fonction, la même ligne écrite).
- Une route dédiée « inscrire et pointer » séparée de `POST .../participants`
  — rejetée : elle ferait deux routes pour un seul geste métier, quand un
  paramètre optionnel suffit et garde `POST .../participants` comme point
  d'entrée unique de l'inscription (cohérent avec son usage déjà existant
  depuis l'écran calendrier, #868, où `present` n'est jamais fourni).

## D5 — Navigation : une section « Jeunes » plutôt que deux

**Decision**: fusionner `a-jeunes` (section « Administration », href
`/admin/jeunes`) et la section racine à item unique `jeunes` (`j-calendrier`,
href `/admin/jeunes/calendrier`) en une seule section `jeunes` à trois items —
profils, calendrier, appel — retirée de la section « Administration ».
Structure calquée sur la section existante « Gestion des utilisateurs »
(`utilisateurs`) : une section dédiée à `minRole: ROLE.CONNECTED`, hors
« Administration », listant plusieurs destinations d'un même domaine RBAC.

**Rationale**: les deux entrées désignaient déjà, sous deux libellés
identiques (« Jeunes »), le même domaine de données — la scission ne reflétait
qu'un accident d'implémentation parallèle (#867 et #868 développées sur deux
branches distinctes de l'epic, chacune ayant ajouté son entrée sans voir
l'autre). `nav.config.ts` étant la description unique de la navigation
(`frontend/AGENTS.md`), deux entrées « Jeunes » visibles au même niveau
auraient obligé l'utilisateur à deviner laquelle mène aux profils et laquelle
au calendrier — l'appel, troisième destination du même domaine, aurait
aggravé la confusion en s'ajoutant à l'une des deux arbitrairement. Le patron
« utilisateurs » (section à `items` multiples, hors « Administration », pour
un domaine RBAC cohérent) est directement transposable : « Jeunes » n'est pas
de l'administration du site, c'est de l'encadrement sportif (commentaire déjà
présent sur la section `jeunes` existante) — ce choix ne change pas, seule la
scission entre profils et calendrier disparaît.

**Alternatives considered**:
- Garder deux sections et ajouter l'appel comme une troisième entrée
  dispersée (sous « Administration » ou à la racine) — rejetée : aggrave la
  duplication déjà signalée par l'agent #868 plutôt que de la corriger, alors
  que l'issue #869 demande explicitement l'unification.
- Fusionner sous la section « Administration » existante (retirer la section
  racine, ajouter les trois items sous `a-jeunes`) — rejetée : contredit le
  commentaire déjà en place sur la section racine (« ce n'est pas de
  l'administration du site, c'est de l'encadrement sportif ») et mélangerait
  des données personnelles de mineurs avec la maintenance technique du
  catalogue d'épreuves.

## D6 — Nommage : `present`/`note`, l'écran reste « l'appel »

**Decision**: la colonne et le champ API s'appellent `present` (anglais,
identifiant technique, Principe I), jamais `presence` ni `is_present` — cet
adjectif est celui que `ParticipantRead`/`PresenceUpdate` portent déjà dans le
plan. Le champ de note de séance s'appelle `note`, sans préfixe. Côté
utilisateur, l'écran et ses deux modes restent nommés « appel » (« appel de
début », « appel de fin ») dans tous les libellés visibles — c'est le mot
qu'emploie l'issue #869 et celui qu'emploient déjà les encadrants du club.

**Rationale**: `present` suit le patron déjà établi par `is_pending_validation`,
`is_reliable` — un adjectif, pas un substantif verbal — et reste cohérent avec
son propre type booléen nullable (D1). « Appel » reste le terme français
métier dans toute l'interface et la documentation produit (Principe I) ; les
identifiants techniques (route `/admin/jeunes/appel`, composants
`AppelPresence`/`AppelFin`) le reprennent tel quel plutôt que de le traduire
en anglais (« roll-call »), parce que ce mot désigne déjà, sans ambiguïté,
l'objet même de la feature dans le vocabulaire du club et de l'issue —
le traduire n'apporterait aucune clarté supplémentaire côté code, et
compliquerait la relecture croisée entre l'issue, la spec et le code.

**Alternatives considered**:
- `is_present` — rejeté : plus long que `present` pour la même information,
  aucun autre booléen du modèle ne porte ce préfixe (`is_pending_validation`
  qualifie un état de workflow, pas une simple présence/absence).
- Nommer les composants `RollCall`/`RollCallEnd` en anglais — rejeté : casserait
  la correspondance directe avec le mot que l'issue, la spec et les encadrants
  emploient déjà, pour un gain de « pureté anglophone » que le Principe I ne
  demande pas (il réserve l'anglais à la couche technique invisible, pas aux
  noms de composants qui désignent un concept métier).

## Migration Alembic

**Decision**: une seule révision `autogenerate` portant les deux colonnes
(`entrainement_participants.present`, `entrainements_jeunes.note`), testée
`upgrade` → `downgrade -1` → `upgrade` avant la PR (patron déjà suivi par
#867/#868).

**Rationale**: les deux colonnes naissent de la même feature et n'ont aucune
dépendance d'ordre entre elles — les regrouper dans une seule révision évite
une révision intermédiaire sans valeur fonctionnelle propre (Principe VI).
