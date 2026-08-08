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
`/athletes?name=` garde son comportement d'origine (casse seule) ; l'unifier est
un autre sujet.

Côté interface, l'état vit dans l'URL (`page`, `q`, `scope` — ce dernier via
`lib/scope.SCOPE_PARAM`), la pagination est en `<Link>` (ouvrables en nouvel
onglet, utilisables avant hydratation), et la recherche s'applique sur `Entrée`
**sans debounce**, patron de `ResultsFilters`. Tout changement de `q` ou de
`scope` remet à la page 1, sans quoi une recherche à trois résultats atterrit sur
une page vide.

Spec, plan et tâches : `specs/20260803-195212-course-pagination/`.

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

## Révocation d'urgence des sessions (#169)

Deux ressources, un seul pouvoir, `sessions:revoke` :
`POST /admin/sessions/revoke` (toutes) et
`POST /admin/users/{user_id}/sessions/revoke` (un compte). Toutes deux rendent
`{"sessions": N, "accounts": M}` — deux chiffres qui ne comptent
que ce qui était **vivant** (non expiré, compte actif), alors que la suppression,
elle, emporte tout. L'écart est délibéré : supprimer une ligne morte est de
l'hygiène gratuite, l'annoncer comme « fermée » serait un mensonge, et faute
d'ordonnanceur une base réelle en est pleine. Trois points :

- **Deux ressources, même pouvoir**, et la seconde n'est pas un doublon du
  retrait d'adresse. `POST /admin/users/{user_id}/sessions/revoke` cible **un
  compte** : retirer une adresse (#170) ferme par la jointure mais **n'efface
  aucune ligne**, donc une réinscription dans la fenêtre de TTL ressuscite les
  jetons ; ici les lignes partent et le compte reste actif. Elle cible un
  **identifiant**, jamais une adresse — `users.email` n'est pas unique (FR-003),
  et l'écran qui l'appelle liste des comptes : frapper par adresse y toucherait
  des homonymes que rien n'aurait nommés. La CLI, elle, prend l'adresse faute
  d'écran pour choisir. Un identifiant inconnu est un **succès sans effet**,
  même parti pris que le retrait d'une adresse et d'un rôle.
- **Elle ferme la session de l'appelant**, et ce n'est pas un effet de bord à
  corriger : sous fuite, son jeton est suspect comme les autres. L'écran
  l'annonce avant le geste et renvoie vers `/login`.
- **Idempotente** : « 0 session fermée » est un succès. Distinguer un geste utile
  d'un geste dans le vide appartient au compte rendu, pas au code de statut.

Le jumeau hors ligne est `python -m app.cli revoke-sessions`, et la redondance
est le but — voir `app/cli/AGENTS.md`.

## Administration des données (#117)

`admin_data.py` porte six ressources : quatre gestes correctifs et deux lectures
réservées. Elles vivent sous `/admin/`, et **chacune porte sa garde** — jamais le
préfixe, pour la raison rappelée ci-dessus.

| Ressource | Pouvoir |
| --- | --- |
| `GET /admin/courses/{id}/deletion-impact` | `courses:delete` |
| `DELETE /admin/courses/{id}` | `courses:delete` |
| `PATCH /admin/courses/{id}` | `courses:write` |
| `GET /admin/athletes` (recherche) et `GET /admin/athletes/{id}` | `athletes:read` |
| `PATCH /admin/athletes/{id}` | `athletes:write` |
| `POST /admin/participations/{id}/reassign` | `participations:reassign` |

Quatre points à ne pas défaire :

- **L'ampleur annoncée est l'ampleur réelle.** Supprimer une épreuve emporte ses
  résultats *et* les fiches coureur qui n'ont couru qu'elle. `deletion-impact` et
  la purge appellent la **même** fonction (`athlete_repository.only_on_course`) :
  c'est ce qui rend l'égalité structurelle plutôt que surveillée. Un test la
  vérifie sur une même épreuve.
- **La cascade est ORM, pas DB.** `Course.participations` porte
  `cascade="all, delete-orphan"` ; aucun `ondelete` n'a été ajouté, et c'est
  délibéré — `database.py` n'émet pas `PRAGMA foreign_keys=ON`, la contrainte
  serait inerte en SQLite (dev et tests) et active en PostgreSQL.
- **`birth_date` ne sort que par `athletes:read`.** C'est la seule donnée
  personnelle fermée du site, et l'unique raison d'être de ce pouvoir. Ajouter le
  champ à `AthleteBrief` (lecture publique) le viderait de son objet ; un test de
  `test_athletes_api.py` l'interdit.
- **Le journal ne consigne que ce qui a changé.** Rattacher un résultat au
  coureur qui le porte déjà réussit sans écrire d'entrée : une demande sans effet
  n'est pas un geste. Un refus, lui, n'écrit rien **et** ne modifie rien — le
  service `flush`, la route `commit`.

Spec, plan et tâches : `specs/20260806-180938-admin-crud-actions/`.
