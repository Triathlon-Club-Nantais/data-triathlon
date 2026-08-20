# Contrat d'API — actions d'administration sur la page d'un coureur (#439)

Trois ressources sont touchées, **aucune n'est créée**. Une seule voit son
schéma d'entrée changer, et par addition d'un champ optionnel.

Rappel du Principe IV : `/api/v1` est publié. Chemins, verbes et codes de statut
ci-dessous sont **inchangés**.

## 1. `PATCH /api/v1/admin/athletes/{athlete_id}` — un champ ajouté

**Pouvoir** : `athletes:write` (inchangé)
**Réponse** : `200` `AdminAthleteRead` (inchangée — elle porte déjà `club`)

### Corps — `AdminAthleteUpdate`

| Champ | Type | Avant | Après |
| --- | --- | --- | --- |
| `nom` | `str` (`min_length=1`) | optionnel | inchangé |
| `prenom` | `str` (`min_length=1`) | optionnel | inchangé |
| `birth_date` | `date \| null` | optionnel, `null` = valeur | inchangé |
| `club` | `str \| null` (`min_length=1`) | **absent** | **optionnel, `null` = valeur** |

`club` rejoint `_NULLABLES` : `{"club": null}` est une mise à `NULL` légitime —
« ce coureur n'a pas de club actuel » (US3-AC2). Il porte **aussi** un
`min_length=1`, et les deux ne se contredisent pas : `null` est la forme correcte
du geste « retirer le club », un `""` détrempé par `str_strip_whitespace` est un
`422`. Sans ce `min_length`, la chaîne vide serait rangée comme un libellé de
club à part entière, présent dans les regroupements par club.

Les règles héritées de `_PatchNonVide` tiennent : un corps `{}` reste un `422`,
et un `null` sur un champ non nullable reste un `422`.

### Exemples

```http
PATCH /api/v1/admin/athletes/42
{"nom": "Lemée", "prenom": "Jean-Marc"}
→ 200  (identité corrigée ; club et club_locked intacts)

PATCH /api/v1/admin/athletes/42
{"club": "Triathlon Club Nantais"}
→ 200  (club corrigé ; club_locked passe à true)

PATCH /api/v1/admin/athletes/42
{"club": null}
→ 200  (plus de club actuel ; club_locked passe à true)

PATCH /api/v1/admin/athletes/42
{"club": "   "}                        # détrempé en "" par str_strip_whitespace
→ 422  (« sans club » s'écrit null, jamais "")

PATCH /api/v1/admin/athletes/42
{"nom": "Dupont"}                      # identité déjà portée par la fiche #77
→ 409  {"detail": "Un coureur porte déjà cette identité (fiche #77)."}
       rien n'est modifié, rien n'est journalisé
```

### Effets

- Journal : `action="athlete.update"`, `payload={"before": …, "after": …}` — les
  instantanés portent désormais **quatre** champs, `club` inclus.
- `club_locked` passe à `true` **si et seulement si** la valeur écrite de `club`
  diffère de l'ancienne (data-model.md, INV-3/INV-4).
- Une demande sans effet retourne `200` sans écrire au journal ni poser le
  drapeau.
- `capture_event("athlete_updated", properties={"fields_changed": …})` :
  inchangé, `club` apparaîtra naturellement dans la liste.

### Ce qui n'est **pas** exposé

`club_locked` n'est dans aucun DTO — ni `AthleteBrief` (public), ni
`AdminAthleteRead` (gardé). Aucun écran n'en a besoin (research.md, D2), et
INV-5 le vérifie.

### Effet de bord sur l'inventaire des pouvoirs

`athletes:write` s'annonce aujourd'hui « Rectifier le nom, le prénom ou la date de
naissance d'une fiche coureur » (`core/permissions.py`). Le club rejoint cette
liste : la **description** doit le dire, sinon l'écran de composition des rôles
sous-annonce ce que le pouvoir permet. Le `code` et le `label` ne changent pas —
le code traverse la base, il est gelé.

## 2. `DELETE /api/v1/participations/{participation_id}` — corps réécrit, contrat identique

**Pouvoir** : `participations:delete` (inchangé)
**Réponse** : `204`, sans corps (inchangée)
**Introuvable** : `404` `{"detail": "Résultat introuvable"}` (inchangée)

### Ce qui change — à l'intérieur seulement

| | Avant | Après |
| --- | --- | --- |
| Suppression | `db.delete(row)` **dans la route** | `participation_repository.delete(db, participation)` |
| Orchestration | aucune | `admin_actions.delete_participation(db, participation_id=…, user_id=…)` |
| Journal | **aucune entrée** | `action="participation.delete"` |
| Dépendance de garde | `_: User` (identité jetée) | `user: User` (nécessaire au journal) |
| Transaction | `commit` dans la route | `flush` dans le service, `commit` dans la route |

Deux écarts comblés : la route ne touche plus la Session (Principe II) et le
geste le plus irréversible de l'API laisse enfin une trace (FR-014). Le contrat
observable, lui, ne bouge pas d'un octet.

### Effets

- Journal : `payload` porte de quoi relire ce qui a disparu — coureur, épreuve,
  place, temps. Un id seul serait illisible : la ligne n'existe plus.
- **Le coureur n'est pas supprimé**, même s'il ne lui reste aucun résultat
  (FR-012). Aucune purge de fiche orpheline, contrairement à
  `reassign_participation` (research.md, D5).
- `capture_event("participation_deleted", …)`, par cohérence avec les onze autres
  gestes d'administration.
- Suppression concurrente : le second appelant reçoit `404`, et rien n'est
  journalisé pour lui (FR-014, FR-016).

## 3. `POST /api/v1/admin/participations/{participation_id}/reassign` — inchangée

**Pouvoir** : `participations:reassign`
**Corps** : `ParticipationReassign` → `{"athlete_id": int}`
**Réponse** : `200`

Aucun changement. Rappelée ici parce que la feature la consomme, et parce que
deux de ses comportements sont des exigences de la spec qu'il faut **ne pas
casser** :

- **Idempotence** : réattribuer vers le coureur qui porte déjà le résultat
  n'écrit rien et ne journalise rien (US4-AC2, FR-014).
- **Deux pouvoirs pour un geste, mais un seul garde** : la route ne garde que
  `participations:reassign` et **ne change pas** (Principe IV). Le couplage avec
  `athletes:read` est une règle de **visibilité** (FR-004, FR-020) : il porte sur
  les écrans, pas sur la garde. La ressource que le sélecteur consomme,
  `GET /admin/athletes?search=`, garde `athletes:read` de son côté — c'est elle qui
  rend le couplage nécessaire, et elle ne bouge pas non plus.
- **Purge des fiches orphelines** : la fiche source vidée par la réattribution
  est supprimée. C'est voulu ici — la fiche est un fantôme né d'une mauvaise
  attribution — et c'est précisément ce qu'on **ne** fait **pas** en cas de
  simple suppression (D5).

Conséquence d'écran : après une réattribution qui vide la fiche courante, la page
que l'administrateur regarde n'existe plus. `router.refresh()` la fera basculer
sur son état « introuvable », que la page gère déjà (FR-016).

## 4. Ressources consommées, non modifiées

| Ressource | Pouvoir | Usage dans la feature |
| --- | --- | --- |
| `GET /api/v1/athletes/{id}` | aucun | rendu serveur de la page, via `serverFetch` — **inchangé**, c'est ce qui tient SC-004 |
| `GET /api/v1/admin/athletes/{id}` | `athletes:read` | pré-remplir la date de naissance dans la modale d'identité, **seulement** si le pouvoir est porté (D7) |
| `GET /api/v1/admin/athletes?search=` | `athletes:read` | sélecteur de coureur cible pour la réattribution (D6) |
| `GET /api/v1/auth/session` | connecté | lecture cliente des pouvoirs ; aucun appel pour un visiteur anonyme (D11) |

## Autorisation — la règle qui vaut pour les quatre gestes

Chaque route garde son pouvoir par `require_permission(P.X)`, **route par
route** ; aucun garde de préfixe de routeur. Un appelant qui contourne
l'interface reçoit `403` et **rien n'est modifié ni journalisé** (FR-009,
US5-AC5). Le masquage d'un bouton n'est pas une protection : il évite d'annoncer
un geste qui échouerait.
