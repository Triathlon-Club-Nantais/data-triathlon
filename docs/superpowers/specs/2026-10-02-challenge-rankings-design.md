# Classements Challenge liés à plusieurs épreuves (#1008)

Design validé le 2026-10-02. Voie Superpowers.

## Problème

Certains événements publient, en plus de leurs épreuves, un classement
« Challenge » qui cumule les résultats d'un même athlète sur plusieurs épreuves
du même jour. Le modèle ne connaît que des `Course` indépendantes : un Challenge
est importé comme une épreuve de plus. Mesuré en prod (#973, point 3), MEDOC
ATLANTIQUE FRENCHMAN 2026 (Klikego) :

- 286 « START CHALLENGE (XS - M - L) », typée `triathlon-l`, 52 lignes, toutes
  déjà présentes dans 284, 288 et 285 ;
- 287 « SUPER CHALLENGE (XS - M - L - XXL) », typée `triathlon-xl`, 15 lignes,
  toutes déjà présentes dans 283, 284, 285 et 288.

Le `total_time` y est un cumul (participation 72453 : 06:50:33). Chaque athlète
est compté une fois de trop, et les compteurs, `federal_only`, la validation de
saison, les stats par format et les agrégats L/XL sont faussés.

Cas voisins connus, au nom sans énumération de tailles : Chronoweb « Challenge
1er Tour / 2ème Tour » (Duathlon de Toulouse 2024), un heat ProLiveSport
« Challenge » de 57 partants.

## Décisions

| Question | Décision |
| --- | --- |
| Ambition | Conserver les lignes Challenge et les afficher. |
| Détection | Automatique à l'import, aucune conversion manuelle. |
| Règle | Nom contenant « challenge » **et** recouvrement des athlètes avec au moins deux autres épreuves du même jour. |
| Modèle | Tables dédiées : une ligne Challenge n'est pas une `Participation`. |

Le modèle à tables dédiées garantit l'exclusion par construction : aucune des
requêtes de compteurs, `federal_only`, saison, stats, podiums ou roster n'a à
être modifiée, et aucune requête future ne peut oublier une clause. Le coût est
borné : la liste des sites qui suivent un athlète (section 3) est finie et
verrouillée par des tests.

## 1. Modèle de données

Une migration Alembic crée trois tables.

**`challenges`**

- `id`, `name`, `event_date`, `source_url`, `scraped_at` ;
- `UniqueConstraint(name, event_date)`, comme l'identité d'une `Course`.

**`challenge_courses`**

- `challenge_id` (FK `challenges.id`, `ondelete=CASCADE`) et `course_id`
  (FK `courses.id`, `ondelete=CASCADE`), en clé primaire composée ;
- supprimer une épreuve détache le Challenge sans le supprimer.

**`challenge_results`**

- `id`, `challenge_id` (FK, `ondelete=CASCADE`), `athlete_id` (FK
  `athletes.id`, `ondelete=RESTRICT`), `bib_number`, `rank_overall`,
  `rank_gender`, `rank_category`, `total_time` (cumulé, chaîne comme
  `Participation.total_time`), `status`, `raw_data` ;
- `UniqueConstraint(challenge_id, bib_number)`.

Le modèle ne porte ni `event_type`, ni splits, ni validation
(`is_pending_validation`) : une ligne Challenge n'entre dans aucun quota ni
aucune statistique. L'athlète est résolu par le même `mapping` que les
participations, donc la même fiche est reliée.

## 2. Flux d'import

Le point d'insertion est `persist_steps` (`backend/app/services/import_service.py`),
seul point d'entrée de la persistance, re-scrape admin compris.

1. **Mise à l'écart par le nom.** Avant `_Persister`, les lignes dont le nom de
   heat contient « challenge » (insensible à la casse et aux accents) sont
   retirées de `results` et gardées à part. Le prédicat `heat_is_challenge(name)`
   vit dans `backend/app/scrapers/utils.py`, à côté de `heat_is_relay`.
2. **Persistance normale** des autres heats, inchangée.
3. **Test de recouvrement, mesuré en base.** Une fois les épreuves écrites, on
   résout l'athlète de chaque ligne mise à l'écart par le `mapping` habituel.
   Les épreuves candidates sont les `Course` de la même `event_date`, quelle que
   soit leur URL : cela couvre aussi les heats frères non re-scrapés (cache du
   fan-out Klikego). Le groupe de lignes d'un heat est un Challenge si **au
   moins 90 %** de ses athlètes figurent dans **au moins deux** épreuves
   candidates. On écrit alors `challenges`, `challenge_results`, et
   `challenge_courses` vers chaque épreuve candidate où figurent **au moins
   50 %** de ses athlètes.
4. **Échec du test** (relais « La Baule - Challenge », Challenge isolé) : les
   lignes repartent dans le flux normal et deviennent une `Course`, comme
   aujourd'hui. Aucune perte.
5. **Re-import** : upsert sur `(name, event_date)` pour le Challenge et sur
   `(challenge_id, bib_number)` pour ses lignes ; les liens vers les épreuves
   sont recalculés.

Le résumé d'import (`persist_results`) gagne un compteur `challenges`, pour que
l'admin voie que le heat n'a pas disparu.

Les seuils (90 %, 2 épreuves, 50 %) sont des constantes nommées du module de
détection.

### Reprise de l'existant

Commande CLI `requalify-challenges`, sur le modèle de
`purge-timepulse-duplicates`, en `--dry-run` par défaut. Elle applique le même
test aux `Course` déjà en base dont le nom passe `heat_is_challenge`, convertit
leurs participations en `challenge_results`, supprime la `Course` puis recompte
les compteurs des épreuves touchées. Sortie parsable conforme à
`backend/app/cli/AGENTS.md`. Elle sert sur la prod après déploiement, pour 286,
287 et les autres cas.

## 3. Raccordement à l'athlète

`challenge_results.athlete_id` est en `ondelete=RESTRICT` : une fiche porteuse
de lignes Challenge ne peut pas disparaître en silence. Sites à brancher,
chacun couvert par un test :

- **Nettoyage des orphelins** (`athlete_repository`, requêtes de détection et
  de suppression des fiches sans participation) : une fiche référencée par
  `challenge_results` n'est pas orpheline.
- **Opposition RGPD** (`opposition_service._appearances` et `_anonymise`) : les
  lignes Challenge figurent dans l'aperçu et sont réattribuées à l'athlète
  anonyme, `raw_data` vidé.
- **Fusion d'athlètes** (`athlete_merge.py`, PR #1176 ouverte) : la fusion
  déplace aussi les lignes Challenge. Si #1176 est fusionnée avant cette
  branche, cette branche l'ajoute ; sinon le point est signalé sur #1176.
- **Purge de rétention** : rien, elle ne touche pas aux résultats.

## 4. API et front

Tous les champs sont additifs : aucune rupture de `/api/v1` (Principe IV).

- **Fiche athlète** : `GET /athletes/{id}` gagne `challenges`, liste de
  { `id`, `name`, `event_date`, `rank_overall`, `ranked_count`, `total_time`,
  `courses` : [{ `id`, `name` }] }. Le front affiche une section « Challenges »
  sous le tableau des épreuves, seulement si la liste est non vide, par
  exemple « Start Challenge (XS · M · L) : 1er / 52, 06:50:33 », avec des liens
  vers les épreuves. Aucune tuile ni aucun graphique ne la consomme.
- **Page d'épreuve** : `GET /courses/{id}/summary` gagne `challenges`, liste de
  { `id`, `name`, `ranked_count` }. Le front affiche un encart « Cette épreuve
  compte pour : … ».
- **Classement d'un Challenge** : `GET /challenges/{id}` rend le Challenge, ses
  épreuves liées et ses lignes classées ; la page `/challenges/[id]` affiche un
  tableau simple (rang, athlète, temps cumulé).

## Hors périmètre

- L'admin des Challenges (édition, suppression, conversion manuelle).
- Les agrégats inter-événements sans « challenge » dans le nom (`vendoman`).
- Toute statistique ou record calculé sur les lignes Challenge.

## Tests

- Unitaires : `heat_is_challenge` ; seuils de recouvrement (89 % / 90 %, une
  seule épreuve recouverte) ; échec du test qui retombe en `Course`.
- Import de bout en bout sur un lot façon Klikego (heats XS, M, L et un
  Challenge) : un `Challenge` créé et lié, compteurs, `federal_only` et stats
  identiques à un import sans le heat Challenge ; re-import idempotent.
- CLI de reprise : `--dry-run` n'écrit rien ; l'exécution réelle convertit,
  supprime la `Course` et recompte.
- Garde des orphelins et opposition RGPD avec des lignes Challenge.
- API : les trois réponses ci-dessus.
- Front (vitest) : section de la fiche athlète, encart de la page d'épreuve,
  page de classement.
