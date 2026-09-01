# Research: Retrait du bouton admin de déclaration de bénévolat (#780)

## D1 — Retrait complet du chemin, pas seulement de l'affichage

**Décision** : retirer, dans cet ordre de dépendance, le bouton frontend,
la route, la fonction de service, la fonction repository `create()`, et le
pouvoir `athletes:volunteer_manage`.

**Rationale** : `athletes:volunteer_manage` ne garde qu'**une seule**
ressource dans tout le dépôt (`POST /admin/athletes/{athlete_id}/
volunteer-actions`, grep vérifié). Le laisser dans le catalogue sans garde
ferait échouer `test_permissions_catalogue.py::
test_chaque_pouvoir_du_catalogue_garde_au_moins_une_ressource` — le dépôt
vérifie déjà « pas de chemin mort » par un test, pas seulement par
convention (AGENTS.md, § Protéger une ressource : « Ajouter un pouvoir,
c'est ajouter un membre à P et lui poser une garde » — la réciproque vaut
au retrait). Cohérent avec le principe du projet de ne pas garder de
compatibilité ascendante inutile.

## D2 — Aucune migration de schéma, colonnes restent nullables

**Décision** : `title`/`description` de `VolunteerAction` restent
nullables — aucun changement de `backend/app/models/volunteer_action.py`
ni nouvelle révision Alembic.

**Rationale** : des lignes existent déjà en base (ou peuvent exister),
créées par le chemin admin avant son retrait, avec `title`/`description`
à `NULL`. Rien dans #780 n'exige de les réécrire ou de resserrer la
contrainte — la nullabilité protège des données historiques réelles, pas
un chemin de code encore actif (spec.md Assumptions).

## D3 — Tests de `create()` : distinguer ce qui teste la fonction retirée
de ce qui teste un comportement qui survit

**Décision** : dans `test_volunteer_action_repository.py`,
- les tests qui vérifient le comportement propre de `create()` (les quatre
  champs du contrat, plusieurs déclarations pour le même athlète/saison)
  sont **réécrits** sur `create_pending()` (#778) quand l'invariant testé
  survit au retrait (le journal autorise toujours plusieurs lignes pour le
  même `(athlete_id, season)`, research.md D4 de #709/#778) ;
- `test_create_laisse_title_description_a_none_et_status_au_defaut`, qui
  vérifie spécifiquement la tolérance à `title`/`description` `NULL`,
  est **adapté** pour construire le modèle `VolunteerAction` directement
  (`VolunteerAction(athlete_id=..., season=..., declared_by_user_id=...)`,
  sans passer par un repository) — ce test protège désormais des données
  **historiques**, pas un chemin de code actif ; il doit donc cesser de
  dépendre d'une fonction qui n'existe plus, tout en continuant de prouver
  que la colonne accepte `NULL` sans lever.

## D4 — Les tests #779/#781 qui simulaient « une ligne créée par l'admin »
suivent la même règle D3

**Décision** : `test_admin_volunteer_actions_api.py` (2 usages de
`repository.create()`, #779/#781) sont adaptés pour construire le modèle
directement plutôt que d'appeler `create()`.

**Rationale** : ces tests protègent la représentation en lecture de lignes
historiques sans titre ni description dans la file d'attente (#779) et la
liste des actions validées (#781) — un besoin qui **survit** au retrait de
#780 (FR-004/SC-002 de cette spec), même si le moyen de les fabriquer en
test change.

## D5 — Retrait complet côté frontend, pas de flag mort

**Décision** : retirer `DeclarerBenevolat` et `peutDeclarerBenevolat` de
`SeasonValidationPanel.tsx`, `useDeclareVolunteerAction`
(`lib/queries/admin.ts`), `declareVolunteerAction` (`lib/api/client.ts`),
et l'interface `VolunteerAction` (`lib/types.ts`) si elle devient
orpheline après ces retraits (grep de contrôle en fin de tâche).

**Rationale** : même principe que D1, côté frontend — un hook ou un
type qu'aucun composant n'appelle plus est un chemin mort, sans garde de
test dédiée ici (contrairement au catalogue de pouvoirs backend), mais
contraire au même principe de simplicité (Principe VI).

## D6 — `ValiderSaison` et l'indicateur de quota restent inchangés

**Décision** : aucune modification de `ValiderSaison` (bouton « Valider la
saison », indicateur `X/3 épreuves validées · bénévolat déclaré/non
déclaré`) — seul `peutValiderSaison` (`athletes:season_validate`) régit
sa visibilité, pouvoir distinct et hors périmètre (FR-002).

**Rationale** : #709 pose déjà ces deux pouvoirs comme indépendants
(commentaire du composant : « deux sections indépendantes »). Le texte
« bénévolat déclaré/non déclaré » de l'indicateur continue de lire
`has_volunteer_action` (calculé par `season_quota`, inchangé par #780) —
aucune dépendance au bouton retiré.
