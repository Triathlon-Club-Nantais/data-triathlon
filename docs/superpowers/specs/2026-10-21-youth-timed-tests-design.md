# Tests chronométrés des jeunes et leur progression (#1365)

## Intention

Aucun suivi chiffré des jeunes n'existe : le journal du profil
(`profile_log_entries`) n'accepte que du texte. Un encadrant veut noter qu'un
jeune a fait « 50 m nage en 42,3 » le 3 octobre, puis « 39,8 » le 14 novembre,
et voir la progression sur la fiche du jeune. Palier 3 de v0.9.0 (gel jeudi
22/10 au soir) : la plus petite version qui marche de bout en bout.

## Objectifs

- Enregistrer un test daté : profil, date, épreuve, durée, séance facultative.
- Saisie depuis la fiche jeune (`/encadrement/jeunes/[id]`), pouvoir `jeunes:write`.
- Lecture sur la fiche : une liste et une courbe **par épreuve**, la courbe par
  `components/charts/ProgressionChart.tsx`.
- Suppression d'un test saisi par erreur (`jeunes:write`, avec confirmation).
- Purge avec le profil par `purge-retention` (#1158).
- Tests sans réseau : modèle, purge, API.

## Hors périmètre (issue)

Classements entre jeunes, barèmes FFTri, saisie en masse pendant l'appel.
Ni modification d'un test (on supprime puis on ressaisit), ni pagination, ni
export.

## Décisions de l'utilisateur (21/10)

1. **Épreuve en texte libre**, avec en suggestion (`<datalist>`) les épreuves
   déjà saisies dans le club. Une faute de frappe crée une courbe à part, accepté.
2. **Précision au dixième de seconde.** Saisie « 42,3 », « 7:42,3 » ou
   « 1:02:05 ».
3. **Suppression possible** d'un test, avec confirmation.
4. **Séance facultative** : le formulaire propose les séances **du jeune** à la
   date choisie (celles où il est inscrit) ; aucune proposée s'il n'en a pas.

## Contraintes du projet

- Une seule migration Alembic, rebasée sur `origin/main` juste avant la PR,
  tête unique, `down_revision` écrit dans le corps de la PR.
- Couches `api → services → repositories → DB` ; identifiants typés `DbId`.
- TDD (Principe III). Français pour l'UI et les messages, anglais pour le code.
- Écran couvert par le filtre PostHog des écrans jeunes (#1307) : la fiche est
  sous `/encadrement/jeunes/`, déjà couverte par `YOUTH_PATH`
  (`frontend/lib/posthog.ts`). Rien à ajouter, mais un test le vérifie si aucun
  ne couvre déjà `/encadrement/jeunes/<id>`.

## Le comment, tel que décidé

### Données

Table `profile_measurements`, modèle `ProfileMeasurement`, sur le patron
exact de `ProfileLogEntry` (`app/models/profile_log_entry.py`) :

| Colonne | Type | Note |
| --- | --- | --- |
| `id` | int PK | |
| `profile_id` | FK `personal_profiles.id`, index, non nul | |
| `measured_on` | Date, non nul | date métier du test |
| `event` | String, non nul | épreuve, texte libre débarrassé de ses bords |
| `duration_tenths` | Integer, non nul, > 0 | durée en **dixièmes** de seconde (entier exact, pas de flottant) |
| `training_session_id` | FK `training_sessions.id`, nullable | séance facultative |
| `created_by_user_id` | FK `users.id`, nullable | patron du journal |
| `created_at` | DateTime, `utcnow` | |

*Mon choix* : `duration_tenths` en entier plutôt que des secondes décimales.
L'issue parle de « durée en secondes » ; l'entier en dixièmes donne la
précision voulue sans `Decimal` (que Pydantic v2 sérialise en chaîne) ni
flottant.

- **Purge** : relation `PersonalProfile.measurements` avec
  `cascade="all, delete-orphan"`, comme `log_entries`. `profile_repository.delete`
  l'emporte donc sans code de plus dans `retention_service.purge_expired` ;
  un test de `test_retention_service.py` le prouve.
- **Suppression d'une séance** : la FK `training_session_id` n'a pas
  d'`ondelete` (convention du modèle), donc
  `training_session_repository.delete_training_session` remet à `NULL` le
  `training_session_id` des tests rattachés avant de supprimer la séance. Le
  test reste, sans sa séance. Sans cela, la suppression d'une séance échouerait
  en PostgreSQL.

### API (sous `/api/v1`, routes gardées une à une)

- `POST /admin/profiles/{profile_id}/measurements` (`jeunes:write`), corps
  `{measured_on, event, duration_tenths, training_session_id?}`. Rend
  `ProfileDetailRead` en 201, patron de `add_log_entry`. Validation : `event`
  non vide après retrait des blancs, longueur bornée (*mon choix* : 100) ;
  `duration_tenths` de 1 à 864000 (24 h) ; `training_session_id` `DbId`, et
  s'il est fourni la séance doit exister, être à la même date que
  `measured_on` et compter le jeune parmi ses inscrits, sinon 422 avec un
  message en français.
- `DELETE /admin/profiles/{profile_id}/measurements/{measurement_id}`
  (`jeunes:write`), 204 ; 404 si le test n'existe pas ou n'appartient pas à ce
  profil.
- `ProfileDetailRead.measurements: list[ProfileMeasurementRead] | None`,
  ajout additif, `None` sans `jeunes:read` comme `log_entries` (#1472). Triés
  par épreuve puis date croissante. `ProfileMeasurementRead` :
  `id, measured_on, event, duration_tenths, training_session_id, created_at`.
- **Suggestions d'épreuves** : `GET /admin/profiles/measurement-events`
  (`jeunes:read`), liste triée des épreuves distinctes du club. *Mon choix* :
  une route dédiée plutôt que de les loger dans le détail d'un profil.
- **Séances du jeune à une date** : filtres facultatifs `profile_id` et `date`
  sur `GET /admin/training-sessions` (additifs, absents = réponse inchangée).
- Écritures journalisées par `logger.info` comme `add_log_entry`. *Mon
  choix* : pas d'`audit.record`, le journal de profil n'en fait pas non plus.

### Écran (fiche jeune, `components/admin/ProfileDetail.tsx`)

Une carte « Tests chronométrés » sous le journal de bord :

- Formulaire (si `jeunes:write`) : date (défaut aujourd'hui, `localToday`),
  épreuve (champ avec `<datalist>`), durée (champ texte, `inputMode` décimal,
  formats acceptés `ss,d`, `m:ss,d`, `h:mm:ss,d` ; virgule ou point), séance
  (liste des séances du jeune à cette date, masquée s'il n'y en a aucune).
  Erreur de format en français sous le champ.
- Par épreuve : un titre, `ProgressionChart` sur ses tests, puis la liste
  (date, durée formatée `m:ss,d`, séance s'il y en a une, bouton supprimer
  si `jeunes:write`, confirmation par `useDangerConfirm`).
- État vide : `EmptyState` « Aucun test chronométré ».
- Analyse et mise en forme de la durée dans un utilitaire pur testé
  (`lib/utils/`).

### Courbe

`ProgressionChart` est aujourd'hui lié au pourcentage de classement (graduations
en %, plafond à 100, libellé « Top x % », texte d'aide « Classement au sein du
peloton », état vide « Pas encore assez d'épreuves »). Il se **généralise** par
des props facultatives (format de la valeur, texte d'aide, libellé accessible,
textes de l'état vide) dont les défauts reproduisent exactement le rendu
actuel : la fiche athlète et Mon espace ne changent pas, leurs tests restent
verts sans modification. Une durée plus courte est meilleure, donc l'axe
inversé actuel (petite valeur en haut) convient tel quel. Le plafond à 100 et
la marge minimale de 1 ne valent que pour le pourcentage. Le seuil de trois
points reste : sous trois tests, la liste suffit et l'état vide de la courbe le
dit.

## Précisions (relecture du constructeur)

- `GET /admin/training-sessions` est gardé par `jeunes:read`. Un compte qui
  n'a que `jeunes:write` ne reçoit donc aucune séance proposée et saisit sans
  séance (*mon choix*, aucune route élargie). Les suggestions d'épreuves suivent
  la même règle.
- `TrainingSession.date` est une `Date` sans heure : la comparaison avec
  `measured_on` est une égalité de dates, sans question de fuseau.
- Une seule organisation par installation aujourd'hui
  (`profile_service.default_organisation_id`). Les épreuves suggérées sont
  celles des profils de cette organisation (*mon choix*), ce qui restera juste
  quand l'epic #1677 en ouvrira plusieurs.
- `measurement-events` est déclarée **avant** `/admin/profiles/{profile_id}`
  dans le router.
- Doublons permis (un second essai le même jour) : aucun index unique. Tri par
  date puis `created_at` ; le seuil de trois points compte des tests.
- Toutes les suppressions de séance (unitaire, et les deux de
  `training_recurrence_service`) passent par
  `training_session_repository.delete_training_session` : la remise à `NULL`
  s'y fait une fois pour toutes.
- `event` comparé tel quel, sensible à la casse, après retrait des blancs de
  bord (*mon choix*, décision 1 : les suggestions évitent les variantes).

## Laissé au constructeur

- Le nom exact et la forme des nouvelles props de `ProgressionChart`, et de
  l'identifiant de point (`participationId` aujourd'hui).
- Le découpage en composants de la carte « Tests chronométrés ».
- Les hooks React Query (patron `lib/queries/` existant) et l'invalidation
  après ajout ou suppression.
- Le message exact des erreurs de validation.
