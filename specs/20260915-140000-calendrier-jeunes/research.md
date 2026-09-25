# Research: Calendrier des entraînements jeunes

## Nom des tables/modèles

**Decision**: `Entrainement` (table `entrainements_jeunes`) et
`EntrainementParticipant` (table `entrainement_participants`).

**Rationale**: le domaine n'a qu'une seule notion de séance dans ce lot — pas
de distinction match/entraînement, pas de récurrence — donc un nom simple
suffit. `entrainements_jeunes` plutôt que `entrainements` tout court pour la
table SQL : l'epic #863 est bornée aux jeunes, et un futur calendrier adulte
(hors périmètre, non demandé) ne collisionnerait pas sur le nom. Le modèle
Python, lui, reste `Entrainement` (pas de préfixe) : il vit déjà sous un
module dédié (`app/models/entrainement.py`), le préfixe serait redondant avec
l'emplacement — même arbitrage que `Group`/`groups` vs. une hypothétique
`OrganisationGroup`.

**Révision (revue de la PR #876)** : décision renversée. Le préfixe
« jeunes » figeait la population dans le schéma, à rebours de l'arbitrage D1
des profils (`personal_profiles`, générique). Tables `training_sessions` et
`training_participants`, colonne `profile_id`, modèle `TrainingSession` :
une extension aux adultes n'aura ni table à doubler ni colonne à renommer,
la restriction aux jeunes restant dans la garde `jeunes:*`.

**Alternatives considered**:
- `Seance`/`seances_jeunes` — rejeté, moins spécifique que « entraînement » et
  n'apporte rien : l'issue #868 dit « entraînement » explicitement.
- Réutiliser une table `courses` existante avec un `event_type` dédié —
  rejeté : `Course` porte tout le modèle de compétition (résultats, sources,
  splits) qui n'a aucun sens ici, et sa contrainte d'unicité
  (`name, event_date, event_type, is_relay`) ne correspond à rien dans ce
  domaine. Détourner un modèle existant pour une notion sans rapport violerait
  le Principe VI (simplicité) autant que la lisibilité du modèle normalisé
  documenté dans `backend/app/models/AGENTS.md`.

## Champs de `Entrainement`

**Decision**: `date` (obligatoire), `heure_debut` (optionnel), `lieu`
(optionnel, texte libre), `type_seance` (optionnel, texte libre).

**Rationale**: l'issue demande explicitement « date, éventuellement
lieu/type ». `heure_debut` est ajouté au-delà de la demande littérale mais
reste la plus petite extension qui rend le calendrier utilisable : sans elle,
deux séances le même jour (matin/soir, un groupe d'âge puis un autre) sont
indiscernables dans la liste et ne peuvent pas être triées de façon stable —
c'est un besoin fonctionnel de la US1 (« calendrier »), pas une anticipation
spéculative. Elle reste optionnelle, au même titre que lieu et type.
`type_seance` et `lieu` restent du texte libre (`String`) : aucune
nomenclature fermée n'a été demandée, et en fermer une maintenant serait une
anticipation non justifiée (Principe VI) — cohérent avec `Course.format_label`
qui suit le même choix pour un besoin comparable.

**Alternatives considered**:
- `type_seance` en énumération fermée (natation/vélo/course à pied/renforcement…)
  — rejeté : aucune liste n'a été fournie par l'issue ni le produit, et une
  énumération se resserre plus facilement qu'elle ne s'assouplit après coup.
- Pas de `heure_debut` — rejeté pour la raison ci-dessus (tri et lisibilité de
  deux séances le même jour).

## Modélisation des participants inscrits

**Decision**: table de liaison `EntrainementParticipant`
(`entrainement_id`, `jeune_id`), `UNIQUE(entrainement_id, jeune_id)`, sur le
patron exact de `UserGroup` (#197) — la paire `(user, group)` déjà en place
dans le dépôt pour une relation d'appartenance équivalente.

**Rationale**: c'est la structure la plus simple qui satisfait « un
entraînement a une liste de participants inscrits » : une ligne = une
inscription, l'idempotence portée par la contrainte d'unicité en base (jamais
par une lecture préalable, cf. la règle déjà établie pour `UserGroup`/
`user_roles` — deux exploitants concurrents la franchiraient tous deux).

**Alternatives considered**:
- Une colonne JSON de participants sur `Entrainement` — rejeté : interdit
  toute contrainte d'unicité portable, toute jointure pour compter les
  inscriptions d'un jeune sur la saison (besoin déjà anticipé par #869), et
  contredit le modèle normalisé déjà en place pour toute relation N-N du
  dépôt (`UserGroup`, `UserRole`, `RolePermission`).

## Dépendance sur le profil jeune (#867)

**Mise à jour post-merge** : #867 a mergé sa table de profils
(`personal_profiles`) dans `epic/863-jeunes` pendant l'implémentation de ce
lot. La contrainte de clé étrangère, initialement différée (cf. Decision
ci-dessous, conservée pour l'historique), a été **resserrée** à ce moment-là :
`EntrainementParticipant.jeune_id` porte désormais
`ForeignKey("personal_profiles.id")`, posée directement dans la migration
d'origine (`e3649cbee16c`, rebasée sur `1d49a862cc7f`) puisque cette révision
n'était pas encore partagée ailleurs — pas de migration de suivi séparée.

**Decision (au moment de l'écriture, avant le merge de #867)** :
`EntrainementParticipant.jeune_id` était une colonne `Integer`
**indexée mais sans contrainte de clé étrangère** pour ce lot. Elle référençait
par convention le futur `jeunes.id` de #867. Une migration de suivi devait
ajouter la contrainte une fois la table cible en base — c'est ce qui a été
fait, directement dans cette même migration plutôt qu'une nouvelle, cf.
ci-dessus.

**Rationale**: #867 (profils jeunes) et #868 (ce lot) sont deux sous-issues
parallèles de l'epic #863, chacune sur sa propre branche partant de la même
base (`epic/863-jeunes`) — ni l'une ni l'autre n'a mergé l'autre au moment de
l'implémentation. Faire dépendre ce lot de la table de #867 bloquerait
l'avancement du modèle « entraînement », que l'issue #868 demande
explicitement de ne pas bloquer (« la liste des tâches devrait pouvoir avancer
sur le modèle entraînement indépendamment du détail du profil »). Créer ici
une table `jeunes` provisoire aurait le défaut inverse : elle collisionnerait
presque certainement avec celle que #867 pose en parallèle (même domaine, même
nom probable), obligeant l'une des deux PR à une migration de fusion délicate
au moment du merge dans `epic/863-jeunes`. Une colonne non contrainte est le
compromis le plus simple : le modèle « entraînement » et ses routes
CRUD/consultation sont pleinement fonctionnels et testables dès ce lot (avec
des `jeune_id` entiers arbitraires dans les tests), et resserrer l'intégrité
référentielle est une migration additive, jamais destructive, une fois #867
en place.

**Alternatives considered**:
- Table `jeunes` minimale provisoire créée par ce lot, avec FK réelle —
  rejeté : risque de collision de migration avec #867 documenté ci-dessus,
  pour un bénéfice (intégrité référentielle immédiate) que les tests
  n'exigent pas dans ce périmètre.
- Bloquer #868 jusqu'au merge de #867 — rejeté explicitement par l'issue.

## Emplacement de l'écran frontend

**Decision**: `frontend/app/admin/jeunes/calendrier/page.tsx`, section de
navigation « Jeunes » nouvelle dans `nav.config.ts`, gardée par
`jeunes:read`.

**Rationale**: les données jeunes sont personnelles et sensibles (mineurs),
fermées par pouvoir RBAC quel que soit le rôle par ailleurs (cf.
`core/permissions.py`, commentaire de `FEATURE_JEUNES`) — c'est la même
famille que « Groupes d'appartenance » ou « Rôles des utilisateurs », jamais
le groupe de routes `(public_restricted)` du mot de passe site (qui protège
des écrans publics, pas des données de back-office). `app/admin/jeunes/`
plutôt qu'une nouvelle racine hors `/admin` : cohérent avec tous les écrans de
back-office existants, et `app/admin/layout.tsx` porte déjà la garde SSO dont
ce nouvel écran a besoin (une session existe, RBAC décide ensuite route par
route côté API — la garde client n'étant jamais la sécurité).

**Alternatives considered**: une route racine `/jeunes` — rejetée, elle
laisserait croire à un écran public alors que le pouvoir requis le ferme à
quiconque n'est pas encadrant.
