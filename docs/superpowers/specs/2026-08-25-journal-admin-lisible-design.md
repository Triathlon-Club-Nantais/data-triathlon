# Journal d'administration lisible — design

Issue #501 (`ADM-5` de l'audit UI/UX, `docs/superpowers/specs/2026-08-20-ui-ux-challenge-audit.md` §9).
Impact fort × effort L.

## Problème

`DeleteCourseDialog` promet « Elle restera tracée dans le journal
d'administration » et l'en-tête de `/admin/courses` répète « Ces actions sont
irréversibles et tracées ». Le journal (`AdminActionLog`) existe bien côté
serveur, écrit par 13 gestes distincts (`admin_actions.py`, `course_merge.py`,
`course_review.py`) — mais **aucune route ne le lit, aucun écran ne l'affiche** :
la promesse est invérifiable. Symétriquement, les deux purges totales
(`DELETE /admin/courses`, `DELETE /admin/participations`) chiffrent l'avant
mais rendent un `204` vide — succès annoncé sans quantité.

## Portée

1. Une route de lecture du journal, gardée par un pouvoir dédié.
2. Un écran d'administration qui l'affiche, atteignable depuis la navigation.
3. Un changement de contrat sur les deux routes de purge (`204` → `200` avec
   le décompte réel), et l'affichage de ce décompte dans le message de succès
   — la fusion (`POST /admin/courses/{id}/merge`) le rend déjà côté API, seul
   son toast doit encore l'afficher.

Hors périmètre : la suppression d'une seule épreuve
(`DELETE /admin/courses/{course_id}`) reste en `204` — son ampleur est déjà
annoncée par la confirmation préalable (`CourseDeletionImpact`), et l'issue ne
la cite pas dans la liste des deux routes à changer.

## Backend

### Modèle et repository

`AdminActionLog` gagne une `relationship()` vers `User` (colonne `user_id`
déjà FK `NOT NULL`), sur le patron d'`AllowedEmail.created_by` — c'est ce qui
permet de résoudre un nom d'affichage sans requête séparée par entrée.

`admin_action_log_repository.py` gagne une troisième fonction,
`list_recent(db, *, page, page_size) -> tuple[list[AdminActionLog], int]` :
triée par `id desc` (même raison que `list_for_entity` — deux gestes de la
même transaction partagent l'horodatage à la microseconde près), avec
`joinedload(AdminActionLog.user)` pour éviter un N+1, et le total via
`count()` pour la pagination.

Les deux docstrings suivantes sont **fausses** depuis cette feature et
doivent être corrigées à la même occasion :
- `models/admin_action_log.py:13-14` — « Écriture seule : ni mise à jour, ni
  suppression, ni route de lecture. » → la route de lecture existe désormais ;
  l'invariant qui reste vrai (ni update, ni delete) doit être reformulé seul.
- `repositories/admin_action_log_repository.py:4-6` — « la consultation du
  journal depuis une interface est un besoin distinct, hors du périmètre de
  #117 » → ce besoin est désormais couvert, par #501.

### Permission

Nouveau pouvoir dans `core/permissions.py`, catalogue plat sans migration
(FR-014 de #115) :

```python
FEATURE_ADMIN_LOG = "Journal d'administration"

ADMIN_LOG_READ = Permission(
    "admin_log:read",
    "Consulter le journal d'administration",
    "Voir l'historique des gestes d'administration effectués sur les "
    "données — qui, quoi, quand.",
    FEATURE_ADMIN_LOG,
)
```

Pouvoir dédié plutôt que réutilisation de `courses:delete`/`participations:wipe_all` :
le journal couvre des entités que ces pouvoirs ne gardent pas (corrections de
coureurs, réattributions de résultats, bascules de source), et « qui peut
détruire peut lire son propre geste » n'est vrai que par accident — un
administrateur qui ne corrige que des coureurs doit pouvoir consulter le
journal sans détenir `courses:delete`.

### Schémas

`schemas/admin.py` :

```python
class AdminActionLogEntry(BaseModel):
    id: int
    created_at: datetime
    user_name: str
    action: str
    entity_type: str
    entity_id: int
    payload: dict | None = None

class AdminActionLogPage(BaseModel):
    entries: list[AdminActionLogEntry]
    total: int

class ParticipationsWipeResult(BaseModel):
    participations_deleted: int
    athletes_purged: int
    courses_reset: int

class CoursesWipeResult(BaseModel):
    courses_deleted: int
    athletes_purged: int
```

`user_name` vient de `entry.user.display_name`, sur le patron de
`created_by_name` (`admin_allowed_emails.py:32`) — sans le `| None` de ce
dernier, puisque `user_id` est `NOT NULL` ici (contrairement à
`created_by_user_id`, nullable).

### Routes

Nouveau routeur `api/v1/admin_action_log.py`, même patron de couche mince que
`admin_data.py` :

```python
@router.get("/admin/action-log", response_model=AdminActionLogPage)
def list_action_log(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.ADMIN_LOG_READ)),
):
    entries, total = admin_action_log_repository.list_recent(
        db, page=page, page_size=page_size
    )
    return AdminActionLogPage(
        entries=[_entry(e) for e in entries], total=total
    )
```

Monté dans `v1/router.py` comme les autres routeurs `/admin/*`.

Dans `admin_data.py`, les deux routes de purge changent de contrat — plus de
`status_code=204`, un `response_model` porte le décompte que le service
`admin_actions.py` calcule déjà et ne rendait pas :

```python
@router.delete("/admin/courses", response_model=CoursesWipeResult)
def wipe_all_courses(...):
    resume = admin_actions.wipe_all_courses(db, user_id=user.id)
    db.commit()
    return resume

@router.delete("/admin/participations", response_model=ParticipationsWipeResult)
def wipe_all_participations(...):
    resume = admin_actions.wipe_all_participations(db, user_id=user.id)
    db.commit()
    return resume
```

`admin_actions.wipe_all_courses`/`wipe_all_participations` ne changent pas :
`resume` porte déjà les trois compteurs (`participations.wipe_all` garde même
`courses_reset` en dehors du payload journalisé, en le disant explicitement
dans son commentaire — cf. `admin_actions.py:178-182`, écrit en prévision
exacte de cet appelant).

## Frontend

### Écran

`app/admin/journal/page.tsx` + `components/admin/AdminActionLogTable.tsx`,
patron de `FeedbackTable` (pagination serveur, état de chargement/erreur/vide).
Colonnes : date (`Intl.DateTimeFormat` déjà utilisé ailleurs dans
l'administration), auteur (`user_name`), geste (libellé français), détail
(rendu du payload).

Entrée de navigation dans `nav.config.ts`, section « Administration » :

```ts
{
  id: "a-journal",
  label: "Journal d'administration",
  description:
    "L'historique des gestes d'administration sur les données — qui, quoi, quand. Rien ici ne s'annule.",
  href: "/admin/journal",
  permission: "admin_log:read",
},
```

### Traduction du geste et du détail

`lib/admin-action-log.ts` — deux dictionnaires plats, sur le patron de
`lib/sport-colors.ts` (source unique, pas de duplication) :

- `ACTION_LABELS: Record<string, string>` — les 15 codes existants
  (`course.delete`, `course.update`, `course.merge`, `course.source.switch`,
  `course.rescrape`, `courses.wipe_all`, `participations.wipe_all`,
  `participation.reassign`, `participation.delete`, `participation.validate`,
  `participation.reject`, `participation.unreject`,
  `participation.correct_fields`, `athlete.update`, `course.reliability`) →
  libellé français court. Code inconnu : fallback sur le code brut lui-même
  (un geste futur non traduit reste lisible, juste moins poli).
- `PAYLOAD_KEY_LABELS: Record<string, string>` — les clés déjà nommées dans
  les toasts existants (`participations_deleted`, `athletes_purged`,
  `courses_deleted`, `courses_reset`, `name`, `previous_url`, `new_url`,
  `imported`, `updated`, `skipped`, `reconciled`, `athlete_name`,
  `bib_number`, etc.).

Rendu d'une entrée : si `payload` porte `before`/`after` (les trois gestes de
correction), une ligne par champ modifié, `label(champ) : avant → après` ;
sinon une liste `label(clé) : valeur` sur les autres clés du payload,
fallback sur la clé brute pour toute clé absente du dictionnaire.

### Décomptes réels dans les messages de succès

`lib/api/client.ts` : `wipeAllCourses`/`wipeAllParticipations` changent de
type de retour (`CoursesWipeResult`/`ParticipationsWipeResult` au lieu de
`null`) — `request<T>()` gère déjà la désérialisation JSON, seul le type
générique change.

`WipeCoursesCard.tsx` :
```ts
const resultat = await purge.mutateAsync();
toast.success(
  `${resultat.courses_deleted} épreuve${resultat.courses_deleted === 1 ? "" : "s"} supprimée${resultat.courses_deleted === 1 ? "" : "s"}, ${resultat.athletes_purged} fiche${resultat.athletes_purged === 1 ? "" : "s"} coureur purgée${resultat.athletes_purged === 1 ? "" : "s"}.`,
);
```
Même patron pour `WipeParticipationsCard.tsx` (`participations_deleted`,
`athletes_purged`) et `MergeCoursesDialog.tsx` (`participations_deleted`,
`athletes_purged`, déjà dans `fusion.data` — aucun changement d'API, juste le
texte du toast).

## Tests

- Backend : `list_recent` (ordre, pagination, `joinedload`) ; route
  `GET /admin/action-log` (garde `admin_log:read`, forme de la page) ; les
  deux routes de purge rendent désormais `200` avec le bon décompte (tests
  existants qui asserraient `204`/corps vide à mettre à jour).
- Frontend : `AdminActionLogTable` (rendu des 15 gestes, rendu du diff
  avant/après, pagination) ; les trois toasts de succès modifiés ; entrée de
  nav filtrée par pouvoir (`estVisible`).

## Risques écartés

- **Pas de lien cliquable vers l'entité** : `entity_id` ne porte pas de FK par
  design (une trace doit survivre à ce qu'elle décrit) — un lien pourrait
  pointer dans le vide. Le payload porte déjà les champs lisibles (noms,
  dates) nécessaires sans naviguer.
- **Pas de filtre par entité/geste dans cette itération** : l'issue ne le
  demande pas, et une liste chronologique paginée suffit à répondre à « qui a
  fait quoi, la dernière fois ». Extension possible sans changement de forme
  si un besoin se confirme.
