# Research: Compteurs de saison distincts + validation humaine du quota club

**Feature**: `specs/20260828-134141-club-season-counters/spec.md`

## D1 — Séparer la sélection du roster du filtrage des compteurs

**Constat** : `athlete_repository.list_with_season_participation_count`
(`backend/app/repositories/athlete_repository.py:286-328`) utilise
`club_only` pour **deux choses à la fois** : filtrer les *lignes de
participation* comptées (`tcn_clause(Participation.club)`) et, via la
jointure interne, décider **quels athlètes apparaissent** dans la liste
`/club/athletes`. C'est exactement le « double emploi » relevé par l'issue.

Ailleurs dans le dépôt, la sélection d'un roster club utilise
`tcn_clause(Athlete.club)` — le club **actuel** de l'athlète, corrigible par
un admin (`club_locked`) — pas le libellé publié sur chaque résultat :
`athlete_repository.search()` (`GET /athletes?scope=club`, ligne 152). C'est
un critère plus robuste pour « qui appartient au club » : il ne dépend pas de
ce qu'un fournisseur de chronométrage a choisi de publier sur une ligne de
résultat donnée, et n'exclut donc jamais un membre confirmé du club faute
d'affiliation publiée sur *cette* saison.

**Decision** : `list_with_season_participation_count` bascule la sélection du
roster sur `tcn_clause(Athlete.club)` quand `club_only=True`, et retire le
filtre `tcn_clause(Participation.club)` de la clause `WHERE`/jointure. Ce
dernier ne sert plus qu'au calcul du troisième compteur (D2), en `CASE`
conditionnel dans l'agrégation — pas en filtre de lignes.

**Alternatives rejetées** :
- Garder `Participation.club` pour la sélection et corriger seulement
  l'affichage : laisse un angle mort (un membre du club sans aucune
  participation étiquetée club cette saison resterait invisible sur
  `/club/athletes`, pas seulement sous-compté) — contraire à l'intention de
  l'issue.
- Introduire un troisième paramètre distinguant explicitement les deux
  usages sans changer le critère de sélection : ne résout pas l'angle mort
  ci-dessus, complique la signature sans bénéfice.

## D2 — Calcul des trois compteurs en une seule requête agrégée

**Decision** : remplacer le filtre unique `validated_clause(...)` de la
requête par trois expressions d'agrégation calculées ensemble (`func.count`
et `func.sum(case(...))` sur les mêmes lignes jointes, un seul aller
base — pas trois requêtes) :

- `total_count` = `count(Participation.id)` sur les lignes jointes (season +
  federal_only appliqués, **aucun** filtre de validation ni de club) → FR-001.
- `validated_count` = `sum(case(validated_clause(Participation.is_pending_validation), 1, else 0))`
  → FR-002.
- `club_affiliated_count` = `sum(case(and_(validated_clause(...), tcn_clause(Participation.club)), 1, else 0))`
  → FR-003, exactement le calcul actuel (comportement conservé, D1 ne change
  que la sélection du roster, pas cette valeur).

`validated_clause` (`app/core/validation.py:20`) renvoie déjà une expression
SQLAlchemy booléenne (`column.is_(False)`), directement utilisable dans
`case()`.

**Rationale** : une seule requête agrégée reste dans le même ordre de
grandeur que l'actuelle (même jointure, même `group_by`), pas de N+1, cohérent
avec Principe VI (simplicité) et avec l'historique du dépôt sur
`_club_roster_requete` (agrégation entièrement en SQL, jamais de participation
individuelle chargée côté Python).

## D3 — Contrat API : additif, pas de rupture de `/api/v1`

**Decision** : `GET /api/v1/athletes/season-activity`
(`AthleteSeasonActivity`, `app/schemas/athlete.py:24`) gagne trois nouveaux
champs (`total_count`, `validated_count`, `club_affiliated_count`) et
**conserve** `participation_count` inchangé (valeur et sémantique actuelles).
Le frontend bascule son affichage principal sur `total_count` ; les deux
autres alimentent le détail (FR-004). `participation_count` n'est ni renommé
ni retiré dans cette PR.

**Rationale** : Principe IV interdit une modification silencieuse d'un champ
publié sous `/api/v1` — la retirer motiverait une v2, hors de proportion pour
ce changement. Ajouter trois champs nommés est strictement additif, donc
conforme sans réserve. Aucune ligne de Constitution Check n'est en ⚠️ de ce
fait.

## D4 — `VolunteerAction` : journal, sans lien obligatoire à une épreuve

**Decision** (confirmé en clarification, session 2026-08-28) : plusieurs
déclarations peuvent coexister pour le même athlète et la même saison — pas
d'indicateur unique. Le barème (FR-012) est satisfait dès qu'il en existe
**au moins une**. Pas de colonne `course_id` : aucune exigence de la spec ne
la requiert, et l'ajouter maintenant serait une abstraction spéculative
(Principe VI). Une déclaration est : `athlete_id`, `season` (année de début,
même convention que `core/season.py`), `declared_by_user_id`, `created_at`.
Aucune suppression n'est exposée (cohérent avec `AdminActionLog`, lecture
seule après écriture, et avec les Edge Cases de la spec).

## D5 — `SeasonValidation` : l'existence de la ligne porte le statut

**Decision** : une ligne unique par `(athlete_id, season)` — sa présence
**signifie** « saison validée ». La valider crée la ligne ; la dévalider
(confirmé en clarification) la **supprime**. Colonnes : `athlete_id`,
`season`, `validated_by_user_id`, `validated_at`.

**Alternatives rejetées** :
- Un champ `is_validated: bool` avec la ligne toujours présente : ajoute un
  état à synchroniser sans bénéfice — l'historique complet (qui, quand, dans
  quel sens) vit déjà dans `AdminActionLog` (D6), pas besoin de le dupliquer
  dans la ligne de statut elle-même. Existence-de-ligne est la version la
  plus simple qui satisfait FR-009/FR-010/FR-013 (Principe VI).

## D6 — Traçabilité via `AdminActionLog`, patron existant

**Decision** : chaque déclaration de bénévolat (`athlete.volunteer_action.create`)
et chaque validation/dévalidation de saison
(`athlete.season_validation.create` / `athlete.season_validation.delete`)
appelle `admin_action_log_repository.create` dans la **même transaction** que
l'écriture métier — même patron que `delete_course`
(`app/services/admin_actions.py:93-129`) : `entity_type="athlete"`,
`entity_id=<athlete_id>`, `payload` porte la saison et, pour la
dévalidation, un résumé de ce qui est retiré (cohérent avec FR-008/FR-013).
Pas de commit explicite dans le repository (le routeur commite, comme
partout ailleurs).

## D7 — Deux pouvoirs RBAC dédiés, dans `FEATURE_ATHLETES`

**Decision** : ajouter à `app/core/permissions.py` (catalogue `P`, pas de
migration — Principe de conception du module) :

- `ATHLETES_VOLUNTEER_MANAGE = "athletes:volunteer_manage"` — déclarer une
  action de bénévolat (FR-007).
- `ATHLETES_SEASON_VALIDATE = "athletes:season_validate"` — valider ou
  dévalider la saison d'un athlète (FR-009, FR-013).

Deux codes distincts, pas un seul : un titulaire peut avoir l'un sans
l'autre (assumption de la spec), même logique que `BATCH_RUN`/`BATCH_READ`
déjà présents dans le catalogue (lancer une reprise vs. relire un bilan —
deux gestes de portée différente).

## D8 — Emplacement des nouvelles routes et de l'UI d'écriture

**Decision** : les routes d'écriture (déclarer un bénévolat, valider/dévalider
une saison) rejoignent `app/api/v1/admin_data.py`, qui porte déjà
`GET/PATCH /admin/athletes/{athlete_id}` sous `require_permission(P.ATHLETES_WRITE)`
— même router, même fiche athlète, pattern identique. Nouvelles routes :

- `POST /admin/athletes/{athlete_id}/volunteer-actions` (`P.ATHLETES_VOLUNTEER_MANAGE`)
- `POST /admin/athletes/{athlete_id}/season-validations` (`P.ATHLETES_SEASON_VALIDATE`)
- `DELETE /admin/athletes/{athlete_id}/season-validations/{season}` (`P.ATHLETES_SEASON_VALIDATE`)

Côté front, l'action rejoint la fiche athlète publique (`/athletes/[id]`),
au même endroit que `ParticipationAdminActions.tsx` — actions d'admin
gardées côté client par `useSession()`, jamais la seule garde (le serveur
revérifie via `require_permission`).

Lecture des compteurs et du statut de validation : reste sur
`GET /athletes/season-activity`, déjà public (aucune garde aujourd'hui),
cohérent avec FR-015 (lecture ouverte à qui a déjà accès à `/club/athletes`).

## D9 — Statut de validation et sélection multi-saison

**Constat** : `SeasonSelector` (`frontend/components/dashboard/SeasonSelector.tsx`)
permet de sélectionner **plusieurs** saisons à la fois sur `/club/athletes`
(`seasons=2024,2025`), agrégées par `season_clause` (OR de plages de dates).
`SeasonValidation`, elle, est par construction mono-saison (FR-010).

**Decision** : `season_validated` (et le tri/filtre associé, FR-014) n'est
renseigné que lorsque **exactement une** saison est sélectionnée ; `null`
sinon, et le tri/filtre par statut de validation est désactivé côté UI dans
ce cas. Cohérent avec le texte déjà voté de FR-014 (« pour la saison
**actuellement affichée** », singulier) — aucune réouverture de la
clarification nécessaire.

## D10 — FR-005 (autres emplacements) : portée déjà unique

**Constat vérifié** : `grep -rn "list_with_season_participation_count"
backend/app` ne remonte qu'un seul appelant,
`app/api/v1/athletes.py` (`GET /athletes/season-activity`), lui-même
consommé uniquement par `/club/athletes`. FR-005 ne demande donc aucun
changement supplémentaire dans cette itération — aucun autre endroit de
l'UI n'affiche aujourd'hui ce compteur ambigu.
