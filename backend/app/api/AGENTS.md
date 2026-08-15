# API de lecture : portée club, disciplines, pagination

## Portée club et disciplines

Deux paramètres traversent l'API de lecture, sur le même patron que `seasons` :

- `scope=club` — restreint aux membres du TCN. Remplace l'ancien `club`, un
  texte libre cherché en sous-chaîne : c'est lui qui laissait la définition du
  club chez l'appelant, et un `%nantais%` comptait les clubs d'athlétisme
  nantais (#76).
- `federal_only=true` — retire les disciplines hors fédération triathlon
  (`trail`, `course-a-pied*`, `cyclisme*`). **Défaut à `false` : l'API reste
  neutre.** Ce sont le dashboard et la page club qui l'activent, via le toggle
  « Inclure les autres disciplines ». Un défaut à `true` amputerait
  silencieusement tout futur appelant.

## Résultats en attente de validation : exclus par construction (#270)

Un résultat créé par `POST /participations` porte `is_pending_validation=True`
(forcé par la route, jamais par le client) et reste invisible de tout agrégat
public jusqu'à ce qu'un bénévole le valide — sa seule surface d'affichage est
la fiche de son athlète (FR-019). **Aucun paramètre pour lever l'exclusion** :
contrairement à `scope`/`federal_only`, ce n'est pas une préférence
d'affichage mais un invariant d'intégrité, et le Principe V est en violation
assumée sur ce point (justifiée dans `plan.md` §Complexity Tracking de la
feature).

`app/core/validation.py` (`is_pending`/`validated_clause`) est le point
**unique** de la règle, sur le patron de `core/club.tcn_clause` et
`core/discipline.federal_clause`. Appliqué à cinq fonctions de
`participation_repository.py` :

| Fonction | Alimente |
| --- | --- |
| `_apply_filters` | `list_participations`, et via `_grouped_events_query` : `events_with_counts`/`events_page` |
| `for_stats` | tableau de bord, page club, podiums (calculés côté front sur ces données) |
| `list_page_for_course` | classement paginé d'une épreuve |
| `summary_rows_for_course` | synthèse d'épreuve |
| `finishers_count_by_group` | `course_finishers` de la fiche athlète |

**Délibérément absente** de six autres fonctions : `list_for_athlete` (la
surface voulue par FR-019 — la filtrer viderait la feature de son objet),
`list_for_course` (chemin d'import, pas d'affichage), `count_for_athlete`
(purge des fiches orphelines, #117), `count_for_course`/`delete_for_course`
(gestes d'administration), `count_bibs_absent_from` (aperçu de fusion, #286)
et `existing_bibs_for_course` (dédoublonnage d'import). Verrouillé par un test
**comportemental** (une participation pendante + une validée, assertion par
fonction publique) dans `tests/test_repositories/test_pending_exclusion.py` —
pas par lecture AST : `_apply_filters` est un helper partagé par trois
fonctions publiques, qu'un lecteur d'appels statique attribuerait mal.

## Classement d'une épreuve : paginé, et l'ordre est en base (#163)

`GET /courses/{id}` rendait **tout** le classement — 1811 participations, 1,15 Mo
sur l'épreuve du ticket. Il est désormais **paginé par défaut** (20), avec
`page`, `q` (nom ou prénom) et `scope`. Mesuré : 1178 Ko → 14,6 Ko, soit 81×.

Trois choses à ne pas défaire :

- **`page_size=all` est l'échappatoire, et elle est contractuelle.** C'est elle
  qui rend le changement de défaut acceptable au regard du Principe IV : rien de
  ce que la route rendait ne devient inatteignable. La retirer ferait de ce
  changement la « modification silencieuse de v1 » que la constitution proscrit.
  Toute autre valeur hors de 1–200 est une erreur d'usage (422), jamais une
  interprétation silencieuse. La clé de réponse reste `participations`, pas
  `items`.
- **L'ordre d'affichage est une propriété de la requête**, plus du navigateur.
  Il vivait dans `raceOrder.orderParticipations` pendant que le SQL triait sur
  `rank_overall` seul : invisible tant que tout arrivait d'un coup, faux dès
  qu'on découpe. `participation_repository._ordre_affichage` en est la **seule**
  définition — finishers par rang (non classés en fin), puis DNF, DSQ, DNS par
  temps (temps absents en fin), départage par nom. `orderParticipations` et
  `countOutcomes` ont été **supprimées**, pas seulement débranchées : appelées
  sur une tranche de vingt lignes, elles trieraient dans le vide et annonceraient
  « 20 partants », sans erreur. Les clés « valeur absente » de l'`ORDER BY` sont
  des booléens `0/1` et non un `NULLS LAST` — SQLite place les `NULL` en tête,
  PostgreSQL en queue. `list_for_course` n'est **pas** touchée : elle sert le
  chemin d'import (`import_service`, `quality.analyze`), pas l'affichage.
- **`GET /courses/{id}/summary` n'accepte aucun paramètre.** La synthèse porte
  sur l'épreuve entière — décomptes ventilés, genre, catégories (8), clubs (9),
  histogramme, `split_keys` — et c'est ce qui garantit que chercher un nom ne
  fait pas tomber l'histogramme à une barre. Elle fixe aussi les colonnes de
  splits du tableau : les déduire des vingt lignes affichées les ferait changer
  d'une page à l'autre. Une seule requête, six colonnes, aucun objet ORM
  hydraté ; l'agrégation est en Python parce que l'histogramme n'a pas
  d'expression SQL portable (les temps sont des chaînes `HH:MM:SS`) et que
  `is_tcn` est une liste blanche Python. Les ex æquo de catégories et de clubs
  sont départagés par libellé : `Counter.most_common` les ordonnait par ordre de
  lecture en base, donc par ordre d'import.

**La recherche par nom est la seule du projet insensible aux accents.** `ilike`
ignore la casse, jamais les accents, sur les **deux** moteurs — mesuré,
`lower('LEMÉE') LIKE '%lemee%'` vaut faux, y compris avec le listener Unicode de
`core/database.py`, qui rend `lemée` et non `lemee` (ce sont deux choses
distinctes, ne pas les confondre). D'où `core/text.deaccent`, enregistrée comme
fonction SQLite `unaccent` à la connexion, et l'extension `unaccent` côté
PostgreSQL (migration `d5e6f7a8b9c0`, sur le patron de celle de `pg_trgm`) :
même nom des deux côtés, donc une seule expression dans le repository. Aucun
index n'est utilisable de ce fait, sans conséquence — le filtre porte toujours
sur une seule épreuve. **Deux implémentations, une seule testée** : la suite
tourne sur SQLite, le chemin PostgreSQL ne l'est par aucun test — et sa
**vérification en production reste à faire** (`quickstart.md` §10 de la feature,
reportée sciemment). Si `unaccent` n'est pas résoluble depuis le `search_path`
du rôle applicatif — les extensions vivant conventionnellement dans le schéma
`extensions` sur Supabase —, seule la **recherche par nom** tombera ; la
pagination, la synthèse et les six blocs n'en dépendent pas.
`/athletes?name=` partage désormais le même `name_filter`
(`repositories/athlete_repository.py`) que la recherche gardée, la liste des
participations et le classement d'épreuve : mot à mot, `nom` **ou** `prénom`
par mot, sans casse ni accents (#357). Les quatre sites d'appel ne peuvent
plus diverger — un seul helper, testé une fois.

Côté interface, l'état vit dans l'URL (`page`, `q`, `scope` — ce dernier via
`lib/scope.SCOPE_PARAM`), la pagination est en `<Link>` (ouvrables en nouvel
onglet, utilisables avant hydratation), et la recherche s'applique sur `Entrée`
**sans debounce**, patron de `ResultsFilters`. Tout changement de `q` ou de
`scope` remet à la page 1, sans quoi une recherche à trois résultats atterrit sur
une page vide.

Spec, plan et tâches : `specs/20260803-195212-course-pagination/`.

## Sources multiples d'une épreuve : sources, bascule, re-scrape, fusion (epic #275)

Quatre ressources sous `/admin/courses/{id}/...` (sources #284, bascule #285,
re-scrape à la demande #118, aperçu de fusion #286, fusion #287) : détail,
pièges mesurés et invariants dans
`docs/api/courses-sources-fusion.md`.

## Protéger une ressource (#115)

`api/deps.require_permission(P.X)` fabrique la garde d'**une** route. Elle nomme
un **pouvoir**, jamais un rôle (FR-017), et se pose **route par route** (FR-018) :

```python
@router.get("/admin/pending-providers")
def list_pending_providers(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(P.PENDING_PROVIDERS_READ)),
): ...
```

**Jamais en `dependencies=` de router ni d'application.** `admin.py` monte, sous
le même `/admin/`, le signalement anonyme `POST /admin/pending-providers`, appelé
par le formulaire du site public en `.catch(() => {})` : une garde de préfixe
supprimerait la fonctionnalité sans que rien ne la nomme, invisible en
développement et totale en production. Deux tests de #114 l'interdisent encore.

**401 avant 403, structurellement** : la fabrique compose `current_user`, donc
une requête sans session n'atteint jamais le contrôle de pouvoir. Le corps du 403
ne nomme ni le pouvoir exigé ni ceux portés (FR-019) — le diagnostic passe par le
journal, côté serveur, avec l'identifiant et la ressource visée.

**Les routers délèguent, ils n'écrivent pas** `roles`, `role_permissions` ni
`user_roles` : une route qui le ferait contournerait du même geste la
non-amplification et l'invariant du dernier administrateur. Un méta-test AST le
verrouille (FR-031) — c'est l'invariant qui se perd à la route suivante et ne se
rattrape pas après coup.

`GET /auth/me` rend en plus `permissions`, `roles` et `groups` (#197), **sans
exiger de pouvoir** : elle ne porte que sur soi. C'est la contrepartie de
`GET /admin/permissions`, qui exige `roles:read` — non par secret, les codes
vivant dans un dépôt public, mais parce que son seul usage est de composer un
rôle.

**Les sept ressources de `/admin/groups` (#197) n'ajoutent aucun mécanisme.**
Elles reprennent `require_permission` à l'identique, route par route, et se
classent d'elles-mêmes dans le filet d'inventaire par la règle du préfixe — ni
`test_public_routes_still_open.py` ni `test_permissions_catalogue.py` n'ont eu à
bouger. Un groupe **n'accorde rien** : la garde ne les lit jamais, et
`tests/test_auth/test_groups_grant_nothing.py` l'établit par AST.

## Administration : révocation, gestes correctifs, doublons, feedback, stats

Cinq sujets indépendants, chacun sous `/admin/` ou son pendant public, chacun
gardé par son propre pouvoir (jamais le préfixe, cf. ci-dessus) : révocation
d'urgence des sessions (#169), les huit ressources de `admin_data.py` (#117),
doublons suspects (#288) — détail dans `docs/api/admin-donnees.md` ; retours
utilisateurs (#267) et statistiques détaillées d'une participation (#272) —
détail dans `docs/api/feedback-stats.md`.
