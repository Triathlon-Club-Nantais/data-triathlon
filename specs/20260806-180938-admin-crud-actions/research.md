# Phase 0 — Research : actions d'administration sur les données

**Feature** : `specs/20260806-180938-admin-crud-actions/`
**Date** : 2026-08-06

Aucun `NEEDS CLARIFICATION` n'est entré en Phase 0 : les deux questions ouvertes
de la spec ont été tranchées avant (§Décisions tranchées). Ce document consigne
les décisions **techniques**, chacune vérifiée dans le code du dépôt plutôt que
déduite de l'issue #117 — dont plusieurs affirmations sont périmées.

## Ce que l'issue #117 dit et que le code contredit

| Affirmation de #117 | Constat |
| --- | --- |
| « Tous protégés par `require_role("admin")` » | `require_role` n'existe pas. Le socle #115 livre `require_permission(P.X)` (`app/api/deps.py`) et **nomme un pouvoir, jamais un rôle** (FR-017 de #115). |
| « suppression en cascade — comportement DB à confirmer » | Confirmé, mais **côté ORM** : `Course.participations` porte `cascade="all, delete-orphan"`. Les FK du dépôt n'ont **aucun** `ondelete` — décision documentée dans `app/models/user.py` : `database.py` n'émet pas `PRAGMA foreign_keys=ON`, une contrainte DB serait inerte en SQLite (dev + tests) et active en PostgreSQL, donc divergente. |
| Modèle `AdminActionLog(user_id, action, entity_type, entity_id, timestamp, payload)` | Retenu, à un nom près : `created_at`, comme les six autres modèles du dépôt. `timestamp` n'existe nulle part. |
| « UI : page `/admin/courses` avec liste » | La **liste** n'a rien à écrire : `GET /api/v1/courses` (paginé, `CourseBrief`) existe. Deux lectures réservées s'ajoutent en revanche à l'issue de `/speckit-clarify` (§D7, §D10), qu'aucune route publique ne peut rendre. |

---

## D1 — Où vivent les quatre endpoints

**Décision** : un nouveau module `backend/app/api/v1/admin_data.py`, monté dans
`v1/router.py` comme les autres.

**Rationale** : `admin.py` porte les signalements de chronométreurs, dont
**une route publique** (`POST /admin/pending-providers`, le formulaire du site).
Sa docstring dit explicitement que c'est ce contraste qui interdit toute garde
par préfixe. Y verser quatre routes d'écriture noierait cette nuance dans un
fichier fourre-tout. `admin_roles.py` a déjà créé le précédent : un module admin
par domaine.

**Alternatives rejetées** :
- *Étendre `admin.py`* — mélange une route publique et quatre routes destructives.
- *Un router `/admin` avec `dependencies=[require_permission(...)]`* — interdit
  par FR-018 de #115, et la garde de préfixe casserait le signalement public.

## D2 — Les pouvoirs à ajouter

**Décision** : cinq membres de `P` dans `app/core/permissions.py`, deux
nouvelles fonctionnalités d'affichage.

| Code | Libellé | Fonctionnalité |
| --- | --- | --- |
| `courses:write` | Corriger une épreuve | Épreuves *(nouvelle)* |
| `courses:delete` | Supprimer une épreuve | Épreuves *(nouvelle)* |
| `athletes:read` | Consulter les fiches coureur | Coureurs *(nouvelle)* |
| `athletes:write` | Corriger un coureur | Coureurs *(nouvelle)* |
| `participations:reassign` | Rattacher un résultat | Résultats *(existante)* |

`athletes:read` est né de la clarification du 2026-08-06 (§D10) : il garde la
**date de naissance**, seule donnée personnelle que la feature expose et que
FR-025 interdit de servir sans habilitation. Il ne double aucun pouvoir
existant — la lecture publique des coureurs (`GET /athletes`) reste ouverte et
ne rend pas ce champ.

**Rationale** : ajouter un pouvoir, c'est ajouter un membre à `P` — **aucune
migration**, c'est la propriété centrale du modèle #115. Le dépôt sépare déjà
`participations:write` de `participations:delete` au motif que « créer et
détruire ne sont pas le même geste » ; supprimer une épreuve (destructif,
irréversible, emporte N résultats) et la renommer (réparable) relèvent du même
raisonnement. Le méta-test AST `tests/test_permissions_catalogue.py` verrouille
la cohérence `P` ↔ `ALL`.

**Alternatives rejetées** :
- *Un pouvoir unique `admin:data`* — un modérateur à qui l'on veut confier le
  renommage hériterait de la suppression. Le geste le plus dangereux fixerait le
  seuil des trois autres.
- *Réutiliser `participations:delete` pour la suppression d'épreuve* — le pouvoir
  de retirer **un** résultat n'est pas celui d'en retirer trois mille.

## D3 — Le journal d'audit

**Décision** : modèle `AdminActionLog` + `admin_action_log_repository.py` +
écriture dans le service, **dans la même transaction** que le geste.

**Rationale** : la spec pose que l'action et sa trace sont indissociables
(FR-015). Une transaction unique le rend structurel : le service `flush()`, le
router `commit()` — le patron déjà en place dans `admin.py`. Aucun hook
SQLAlchemy, aucun middleware : un `after_flush` ne connaît pas l'utilisateur de
la requête et devrait aller le chercher dans un `ContextVar`, soit un état
implicite pour économiser quatre appels explicites.

**`entity_id` ne porte aucune FK**, et c'est délibéré : FR-014 exige que la trace
survive à la disparition de ce qu'elle décrit. Une FK vers `courses.id`
interdirait précisément d'enregistrer une suppression. `user_id` porte une FK
(l'auteur, lui, ne disparaît pas), sans `ondelete` — le patron du dépôt.

**Alternatives rejetées** :
- *Table par entité* (`course_action_log`, `athlete_action_log`) — trois tables
  pour un même besoin de relecture chronologique.
- *Log applicatif seul (`logger.info`)* — Sentry n'est pas une base consultable,
  et AC4 demande une trace **requêtable**.
- *Colonnes `before`/`after` typées* — le `payload` JSON couvre les quatre gestes
  sans schéma figé, et le dépôt utilise déjà JSON pour `splits`, `raw_data`,
  `quality_issues`.

## D4 — La cascade de suppression

**Décision** : `db.delete(course)` via un nouveau `course_repository.delete()`.
**Aucune migration**, aucun `ondelete` ajouté.

**Rationale** : `cascade="all, delete-orphan"` est déjà sur la relation ; la
suppression des N participations est acquise et identique en SQLite et en
PostgreSQL. Ajouter `ondelete="CASCADE"` produirait l'inverse de ce qu'on croit :
inerte en dev et en test (pas de `PRAGMA foreign_keys=ON`), actif en prod — donc
un comportement que la suite de tests ne verrait jamais.

**Ceiling assumé** : la cascade ORM charge les participations en mémoire et émet
un `DELETE` par ligne. Pour une épreuve de 3 000 finishers, c'est une poignée de
secondes sur une action ponctuelle d'administration — largement dans le budget.
Un `ponytail:` le nommera dans le repository, avec la sortie (`bulk delete` +
`ondelete` en DB) si le volume change de nature.

## D5 — La purge des fiches coureur orphelines (FR-022)

**Décision** : `athlete_repository.delete_orphans` gagne un paramètre `among`
(les ids candidats) et une variante rendant les ids supprimés ; l'appelant
historique (`rescrape_service`) garde son `int`.

```python
def delete_orphans_among(db, athlete_ids: list[int] | None = None) -> list[int]  # nouveau
def delete_orphans(db) -> int:  # inchangé pour l'appelant, délègue
    return len(delete_orphans_among(db))
```

**Rationale** : la fonction actuelle scanne **toute** la table et renvoie un
compte. Appelée à chaque suppression d'épreuve, elle emporterait aussi des
orphelins préexistants sans rapport avec le geste — invisibles au journal, donc
non traçables (FR-013 exige de nommer les fiches purgées par ricochet). Le
service admin connaît exactement les candidats : les athlètes des participations
qu'il vient de retirer, ou l'athlète source d'un rattachement. Restreindre à ces
ids rend la trace exacte **et** supprime le scan complet.

Un seul appelant existant (`rescrape_service.py:198`), dont le contrat
(`orphans_removed: int`) ne bouge pas.

**Alternatives rejetées** :
- *Appeler `delete_orphans()` tel quel* — trace inexacte, effets de bord hors
  périmètre du geste, scan full-table par action.
- *Dupliquer la requête dans le service admin* — violerait le Principe II (seul
  `repositories/` touche la `Session`).

## D6 — Comment l'unicité est vérifiée

**Décision** : lecture préalable via `athlete_repository.get_by_identity` et
`course_repository.get_by_identity`, puis `DuplicateError` (409) au message
français nommant la fiche en conflit.

**Rationale** : les deux fonctions existent et servent déjà à la déduplication de
l'import. S'en remettre à l'`IntegrityError` de la contrainte donnerait un
message technique anglais, invaliderait la transaction (donc empêcherait
d'écrire quoi que ce soit ensuite) et rendrait impossible de **nommer** la fiche
en conflit, ce qu'exigent FR-005 et FR-021.

La contrainte DB reste le filet de dernier recours ; elle n'est pas le chemin
nominal.

**Cas particulier du rattachement** : FR-006 (« pas deux fois le même coureur sur
la même épreuve ») ne se lit dans aucune contrainte — `uq_participation_bib`
porte sur `(course_id, bib_number)`. Une vérification applicative explicite est
donc nécessaire, via un `exists` dédié dans `participation_repository`.

## D7 — La confirmation destructive (FR-017, FR-026)

**Décision** *(révisée après `/speckit-clarify`)* : une route d'impact réservée,
`GET /api/v1/admin/courses/{id}/deletion-impact`, rendant
`{participations: int, athletes: int}`. Pouvoir : `courses:delete`.

**Rationale** : la version initiale lisait `GET /courses/{id}/summary` (publique,
champ `total`) et n'annonçait donc que les résultats. La clarification du
2026-08-06 a rendu la purge des fiches coureur (FR-022) partie de l'ampleur à
déclarer : une modale qui tait la destruction de fiches coureur sous-déclare un
geste sans annulation. `summary` ne peut pas porter ce compte — c'est un contrat
public, et le nombre d'athlètes menacés n'a aucun sens pour un visiteur.

Le calcul (« athlètes dont **toutes** les participations sont sur cette
épreuve ») vit dans `athlete_repository`, en une requête, et **ne modifie rien**.

**Alternatives rejetées** :
- *Annoncer après coup dans le retour de l'action* — l'admin apprendrait
  l'ampleur une fois la destruction faite.
- *Ajouter le compte à `CourseSummary`* — extension d'un contrat public pour un
  besoin d'administration, et un calcul supplémentaire imposé à chaque
  consultation publique d'épreuve.
- *Calculer côté client* — supposerait de charger tous les résultats et tous les
  historiques des coureurs concernés.

## D10 — La recherche de coureurs pour le rattachement (FR-024, FR-025)

**Décision** *(issue de `/speckit-clarify`)* : une route de lecture réservée,
`GET /api/v1/admin/athletes?search=<terme>`, rendant identité **complète** (dont
`birth_date`), club et nombre de résultats. Nouveau pouvoir `athletes:read`.

**Rationale** : le rattachement est le seul geste où l'admin **choisit** une
entité parmi des quasi-identiques, sans annulation. Sur nom + prénom + club
seuls — tout ce que rend `AthleteBrief` — deux vrais homonymes du même club sont
indiscernables, et le geste censé résorber un doublon fusionnerait deux
personnes distinctes. La date de naissance et le nombre de résultats sont
précisément ce qui les départage.

**Pourquoi ne pas enrichir `GET /athletes` (public)** : y ajouter `birth_date`
publierait la date de naissance de chaque coureur du club sur une route ouverte.
FR-025 l'interdit. Le pouvoir `athletes:read` est **le** garde de cette donnée,
et c'est sa seule raison d'être — le catalogue #115 a déjà `users:read` sur le
même patron.

**Alternatives rejetées** :
- *Réutiliser `GET /athletes?name=`* — aveugle sur les homonymes réels.
- *Champ de saisie d'identifiant* — reporte la reconnaissance hors de l'écran ;
  une faute de frappe rattache le résultat à un inconnu, sans annulation.

## D8 — Le gating d'interface (FR-011)

**Décision** : `useSession().data.permissions.includes("courses:delete")`.
Aucune plomberie nouvelle.

**Rationale** : `SessionUser.permissions: string[]` est déjà exposé par
`GET /auth/me` et typé dans `frontend/lib/types.ts` (#115) — sa docstring dit
qu'il existe pour ça. Le gating d'écran ne protège rien (le serveur reste seul
juge, FR-009) ; il évite de proposer un bouton qui rendra 403.

## D9 — Répartition front

**Décision** : page `frontend/app/admin/courses/page.tsx`, composants dans
`frontend/components/admin/`, mutations dans `lib/queries/admin.ts`, méthodes
dans `lib/api/client.ts`, modales sur `components/ui/dialog.tsx` (shadcn, déjà
installé), retours via `sonner`.

**Rationale** : c'est exactement le chemin de `PendingProvidersTable` — tableau
shadcn, `useMutation` + invalidation, `toast` sur succès et sur échec, et une
fonction `messageDErreur` qui distingue 401 / 403 / panne. Ce composant est le
patron de référence : il documente qu'un 403 affiché comme « liste vide » est
« un écran qui ment ». Les quatre gestes réutilisent la même distinction.

Le layout `/admin` existant (garde d'interface, redirection vers `/login`)
couvre automatiquement `/admin/courses` — il a été écrit pour « les futures
sous-routes d'administration ».
