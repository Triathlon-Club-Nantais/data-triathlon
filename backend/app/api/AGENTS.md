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

## Sources d'une épreuve : `GET /courses/{id}/sources` (#284)

**Publique**, lecture seule, et ce n'est pas un oubli de garde : la décision D4
de #275 rend la liste visible de tous — quel chronométreur alimente le classement
affiché est une information de lecture. Ce qui reste fermé, c'est l'écriture
(soumettre une URL, basculer l'active) et le **nom du soumetteur** :
`CourseSourceOut` ne porte que `id`, `url`, `provider`, `is_active`,
`last_scraped_at`, jamais `created_by`. L'ordre — active en tête, puis les
passives par `created_at` — appartient à `course_source_repository.list_for_course`
et n'est pas cosmétique : sans lui, la source affichée sauterait d'un
rechargement à l'autre. Une épreuve inconnue est un **404**
(`NotFoundError("Course introuvable")`, comme les deux routes voisines), une
épreuve sans source une **liste vide** — confondre les deux ferait lire un
identifiant inventé comme « aucune source ».

## Basculer la source active : `PATCH /admin/courses/{id}/sources/{source_id}` (#285)

Le seul geste d'administration qui **scrape** — d'où son module à part,
`admin_course_sources.py`, sa dépendance à `Settings` et sa durée en secondes.
Garde `courses:sources`, et non `courses:write` : le pouvoir voisin est borné aux
quatre champs d'identité, où corriger un libellé ne détruit rien ; ici le
classement affiché est remplacé **en entier** (décision D2 de #275, un upsert par
dossard laisserait survivre les lignes de l'ancienne source, donc exactement le
mélange de deux chronométreurs que l'epic existe pour supprimer). Rend la liste
des sources dans la forme et l'ordre de `GET /courses/{id}/sources`, pour que
l'écran se réaffiche sans second appel.

Cinq choses à ne pas défaire :

- **L'ordre des quatre étapes est le contrat** : scraper, valider, détruire,
  réimporter. Rien de destructeur n'est écrit avant qu'on tienne un classement
  utilisable — c'est ce qui rend impossible l'accident propre à cette route, une
  épreuve vidée par un geste qui échoue ensuite à la remplir. Ce n'est pas un
  choix de style : `import_event` **commite** en interne, et un `begin_nested()`
  autour ne le contient pas (mesuré sur SQLAlchemy 2.0.51 — le `commit` clôt la
  transaction *externe*). Aucun rollback n'était donc disponible ; n'avoir rien
  écrit est plus solide de toute façon.
- **Le cache TTL est neutralisé des deux côtés.** `is_fresh` court-circuiterait
  le scrape, mais `force=True` ne suffit pas : la sonde par manche à l'intérieur
  de `_scrape_all` juge chaque sous-épreuve fraîche indépendamment, et l'épreuve
  qu'on bascule est par définition la plus fraîche de la base. D'où
  `import_service.scrape_for_replacement`, qui passe `use_cache_probe=False` —
  sans quoi une épreuve fan-out perdrait toutes ses manches.
- **Un scrape qui publie une autre épreuve est refusé** (422), pas importé.
  `mapping.get_or_create_course` apparie sur `(nom, date, type, relais)` à
  l'égalité stricte : un libellé différent chez le second chronométreur créerait
  une **nouvelle** épreuve et laisserait celle qu'on vient de vider à zéro
  résultat, sans qu'aucune exception ne passe. Zéro résultat est refusé pour la
  même raison — banal sur le chemin d'import ordinaire (succès à zéro compteur),
  ici un classement effacé.
- **`is_active: false` est refusé** (400). L'index partiel autorise zéro active,
  et une épreuve sans active n'est plus scrapée (#282) ni affichée avec sa source
  (#279) : le seul moyen de changer d'active est d'en désigner une autre.
- **Bloquant, et sans progression.** #275 tranche que la bascule et le re-scrape
  à la demande « doivent partager le même mécanisme, pas en inventer deux » : le
  SSE d'administration appartient donc à #118, et aucun critère d'acceptation de
  #285 ne porte sur la progression.

La purge des fiches coureur devenues vides relève ses candidats **avant** la
suppression et ne tranche qu'**après** le réimport — même primitive et même piège
que `DELETE /admin/courses/{id}`.

## Aperçu d'impact avant fusion : `GET /admin/courses/{id}/merge-impact` (#286)

`?absorbed_id={id}`, gardé par **`courses:sources`** — le pouvoir qui *arbitre*,
pas un pouvoir de lecture : même raison que `deletion-impact` sous
`courses:delete`, qui peut trancher peut mesurer. `courses:write` ne conviendrait
pas, sa description est bornée aux quatre champs d'identité. Le module est
`admin_course_merge.py`, distinct d'`admin_data.py` : la fusion appartient à
l'epic #275, pas aux quatre gestes correctifs de #117, et #287 (la fusion) s'y
ajoutera.

Quatre points à ne pas défaire :

- **Deux épreuves qui diffèrent sur `name`, `event_date` et `event_type` sont le
  cas nominal**, pas une erreur : deux chronométreurs ne nomment ni ne classent
  la même épreuve de la même façon. Les deux côtés sortent tels quels.
- **Le rapprochement se fait par dossard** (`uq_participation_bib`), et un
  dossard absent ou vide **n'a pas d'équivalent** — rien ne permet de le
  rapprocher, et le compter comme sauvé annoncerait des résultats qui
  disparaîtraient. `NOT EXISTS` corrélé et non `NOT IN` : un seul partant sans
  dossard côté cible rendrait un `NOT IN` toujours faux, donc l'aperçu
  annoncerait « aucune perte ».
- **`tcn_participations_without_match` est le chiffre qui décide** ; il sort de
  la même agrégation que le total, en une requête à deux colonnes. Le nombre de
  requêtes est constant (10 mesurées), et un test de
  `tests/test_services/test_course_merge.py` le vérifie en comparant deux
  tailles de jeu — rapprocher les classements en Python coûterait 1811 lignes
  sur la plus chargée des épreuves.
- **`same_source_url` regarde *toutes* les sources de la cible, l'active comme
  les passives** : `UNIQUE(course_id, url)` ignore `is_active`, donc une URL déjà
  connue de la cible ne peut pas y être repointée — la fusion n'ajoute alors
  aucune source, elle supprime un doublon (cas Mesquer, ids 38 et 50 en base de
  dev). `athletes_orphaned` vient de `athlete_repository.only_on_course`, la
  **même** fonction que la purge de #117 : l'annonce et l'acte de #287 ne peuvent
  pas diverger à base constante.

Fusionner une épreuve avec elle-même est un **400** (message français) : le geste
n'a rien à absorber, et #287 supprimerait la cible qu'on croit garder.

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

`POST /admin/sessions/revoke` (`sessions:revoke`), corps facultatif, rend
`{"sessions": N, "accounts": M}` — deux chiffres qui ne comptent
que ce qui était **vivant** (non expiré, compte actif), alors que la suppression,
elle, emporte tout. L'écart est délibéré : supprimer une ligne morte est de
l'hygiène gratuite, l'annoncer comme « fermée » serait un mensonge, et faute
d'ordonnanceur une base réelle en est pleine. Trois points :

- **Une ressource, deux portées**, et la seconde n'est pas un doublon du
  retrait d'adresse. Corps absent → tout ; `{"email": …}` → les comptes portant
  cette adresse, **tous** (`users.email` n'est pas unique, FR-003 — en épargner
  un sous incident serait l'erreur coûteuse). Retirer une adresse (#170) ferme
  par la jointure mais **n'efface aucune ligne**, donc une réinscription dans la
  fenêtre de TTL ressuscite les jetons ; ici les lignes partent et le compte
  reste actif. Une adresse inconnue est un **succès sans effet** : l'écran ne
  propose que des adresses de sa propre liste, il n'y a pas de faute de frappe
  possible, là où la CLI la refuse.
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

## Doublons suspects (#288)

`admin_course_duplicates.py` — une seule ressource,
`GET /admin/courses/duplicates`, gardée par `courses:sources` : la liste est la
porte d'entrée de la fusion (#289) et de l'arbitrage entre chronométreurs
(#285), pas une correction d'identité. Ni pagination ni filtre.

Le router est mince à l'extrême ; **tout le jugement est dans
`services/course_duplicates.py`**, et c'est là qu'il faut lire avant de toucher
au réglage : les **deux seuils** y sont documentés côte à côte — celui de #277,
qui rapproche **automatiquement** à l'import, et celui d'ici, délibérément plus
large parce qu'un humain relit. Les motifs sont un ensemble **fermé** de trois,
chacun rattaché à un cas de terrain mesuré ; les élargir se tranche en
re-sondant, pas en ajoutant une tolérance
(`docs/superpowers/specs/2026-08-12-sources-multiples-epreuve-sondage.md`).
