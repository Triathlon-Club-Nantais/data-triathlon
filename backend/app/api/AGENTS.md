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
  « Inclure les autres disciplines » — et, depuis #502, `GET /athletes/{id}`,
  qui reçoit `seasons`/`federal_only` de la bande « Ma saison » du tableau de
  bord. Un défaut à `true` amputerait silencieusement tout futur appelant.

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
`core/discipline.federal_clause`. Appliqué à neuf fonctions, réparties sur
trois repositories :

| Fonction | Fichier | Alimente |
| --- | --- | --- |
| `_apply_filters` | `participation_repository.py` | `list_participations`, et via `_grouped_events_query` : `events_with_counts`/`events_page` |
| `stats_totals`/`stats_by_type`/`stats_by_month_rows`/`stats_recent_rows`/`stats_rank_rows` | `participation_repository.py` | tableau de bord, page club, podiums (calculés côté front sur ces données) — remplacent `for_stats`, supprimée (#580) |
| `list_page_for_course` | `participation_repository.py` | classement paginé d'une épreuve |
| `summary_rows_for_course` | `participation_repository.py` | synthèse d'épreuve |
| `finishers_count_by_group` | `participation_repository.py` | `course_finishers` de la fiche athlète |
| `distinct_seasons` | `participation_repository.py` | `stats_service.list_seasons` → sélecteur de saisons |
| `_filtered` (branche `club_only`) | `course_repository.py` | `GET /courses?scope=club` et `GET /courses/count?scope=club` |
| `list_with_season_participation_count` | `athlete_repository.py` | `GET /athletes/season-activity` — page coureurs (#274, #382) |
| `search_by_relevance` | `athlete_repository.py` | `GET /athletes/search` — `participation_count` de la palette ⌘K (#484) |

**`search_by_relevance` joint `Participation` en `outerjoin`** (un athlète à
zéro résultat doit rester trouvable) : `validated_clause` y vit dans la
**condition du join**, jamais dans un `.filter()` après coup — un `.filter()`
post-jointure dégraderait l'`outerjoin` en jointure interne de fait et ferait
disparaître de la palette un athlète dont l'unique résultat est en attente,
au lieu de l'y garder à 0 résultat validé (#562).

**Délibérément absente** de six autres fonctions de `participation_repository.py` :
`list_for_athlete` (la surface voulue par FR-019 — la filtrer viderait la
feature de son objet), `list_for_course` (chemin d'import, pas d'affichage),
`count_for_athlete` (purge des fiches orphelines, #117),
`count_for_course`/`delete_for_course` (gestes d'administration),
`count_bibs_absent_from` (aperçu de fusion, #286) et `existing_bibs_for_course`
(dédoublonnage d'import). Verrouillé par un test **comportemental** (une
participation pendante + une validée, assertion par fonction publique) dans
`tests/test_repositories/test_pending_exclusion.py` — pas par lecture AST :
`_apply_filters` est un helper partagé par trois fonctions publiques, qu'un
lecteur d'appels statique attribuerait mal, et la règle traverse trois
fichiers différents.

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

### Ce que la page épreuve a ajouté (#486)

Six champs et deux paramètres, tous **additifs**, tous à défaut neutre.

- **`club` et `category` sur `GET /courses/{id}`** filtrent le classement en
  **égalité exacte**, et se cumulent entre eux, avec `q` et avec `scope`. L'exactitude
  n'est pas un détail d'implémentation : les valeurs viennent de `/summary`, qui les
  tire d'un `Counter` sur ces colonnes — ce sont littéralement les chaînes stockées.
  Un `ilike` ferait « BLAIN TRIATHLON » ramasser « BLAIN TRIATHLON JEUNES », et le
  compteur de la carte cesserait de coïncider avec le total du classement, défaut que
  #485 vient de corriger. **`club` n'est pas `scope=club`** : le second porte la
  sémantique TCN arbitrée par `core/club.py` (dépositaire unique, #76), le premier un
  club quelconque. Leur croisement peut être vide par construction, et c'est l'écran
  qui l'explique — pas l'API qui l'interdit. Une valeur inconnue rend une sélection
  vide, jamais un 404 : l'épreuve existe.
- **`clubs_total` sur `/summary`** compte les clubs **distincts**, dénominateur du
  « et N autres clubs ». Attention au faux ami : `categories_total`, son voisin, compte
  des **participants**. Les deux disent ce que la carte omet, dans deux unités
  différentes.
- **`split_gap_ratio` (par participation), `split_gap_median` et `split_gap_rows`
  (par synthèse)** publient l'écart entre le temps total et la somme des inters. Ce
  sont des **mesures, jamais des verdicts** : les seuils d'affichage vivent côté écran,
  ce qui permettra de les régler après re-sondage sans toucher au contrat. La règle
  elle-même vit dans `app/core/split_gap.py` et **nulle part ailleurs** — le front en a
  besoin par ligne, la synthèse pour la médiane, et deux implémentations divergeraient
  comme les trois listes du critère club de #76. Son **gabarit de segments dérive de
  `services/mapping._SPLIT_KEYS_BY_SPORT`**, la table qui pose les clés de `splits` : en
  tenir une copie, c'est garantir la divergence, et le premier jet de ce module l'a
  démontré — sa copie valait `bike/run` pour un bike-run là où le gabarit réel pose
  `segment1/bike/run`, d'où un tiers du parcours ignoré et un écart fabriqué. Le point de
  vérité des seuils est
  `docs/superpowers/specs/2026-08-25-ecart-inters-total-sondage.md`, rejouable par
  `scripts/sondage_ecart_inters.py`.
- **`is_reliable` et `quality_issues` sur `EventOut`** — miroir de `CourseBrief`, pour
  que `/resultats` marque ce qu'elle liste sans un second appel. `quality_issues` est
  une colonne **JSON** : elle est sélectionnée mais **jamais** ajoutée au `GROUP BY`,
  PostgreSQL n'ayant pas d'opérateur d'égalité sur ce type — la requête passerait en
  SQLite et échouerait en production. Le `GROUP BY Course.id` suffit par dépendance
  fonctionnelle. Ce chemin n'est **pas** couvert par les tests, qui tournent sur
  SQLite : à vérifier au premier déploiement.

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

## Plafonds de débit par IP (#395, #398)

Six routes publiques sont plafonnées par IP, **route par route** comme les
gardes de pouvoir — `api/deps.scrape_rate_limit` sur `POST /scrape/event` et
`POST /scrape/event/stream`, `api/deps.authorize_rate_limit` sur
`GET /auth/{provider}/authorize`, `api/deps.public_write_rate_limit` sur
`POST /admin/pending-providers` et `POST /participations`, et
`api/deps.site_access_rate_limit` sur `POST /site-access/session` (#509).
Quatre choses à ne pas défaire :

- **Un seul seau par geste, pas par route.** Les deux routes de scraping
  déclenchent le même travail (jusqu'à ~26 requêtes sortantes, puis des
  centaines de lignes écrites) ; les deux écritures publiques se suivent dans
  la même séquence (import échoué → signalement du fournisseur → saisie
  manuelle). Dans les deux cas, des compteurs distincts ne feraient qu'offrir
  un plafond à contourner par alternance. **Le corollaire est la réciproque, et
  il a coûté un seau** : `POST /site-access/session` a partagé `public_write`
  jusqu'à la revue de #513, alors qu'elle n'est dans le geste d'aucune des deux
  écritures — un membre qui saisissait sa saison ne pouvait plus ouvrir de
  session, et un club derrière une seule IP NAT épuisait les 30 tentatives
  collectivement. Elle a son seau `site_access`, plus large (60/h) pour la
  raison inverse de tous les autres : c'est le **premier** geste de chaque
  visiteur, partagé entre adhérents, et une saisie au clavier se trompe. Ce
  qu'il ferme reste le déni de service par `hashlib.scrypt` (~16 Mo, 50-100 ms
  de CPU par tentative, bonne ou mauvaise), pas la force brute — le secret est
  généré à 144 bits.
- **Le compteur est en mémoire du process**, contrairement à celui de
  `POST /feedback` qui compte des lignes en base : il n'y a ici aucune table où
  compter, et en créer une ferait écrire la requête que le plafond empêche.
  Exact tant que l'API tourne en un seul process — le cas sur Render.
- **La clé est `request.client.host`**, donc la première entrée de
  `X-Forwarded-For` depuis #393. Sans ce préalable, tout plafond par IP se
  contourne avec un en-tête forgé — c'est pourquoi #395 en dépendait.
- **Le compteur survit d'un test à l'autre** : la fixture autouse
  `_compteurs_de_debit_vierges` de `tests/conftest.py` le remet à zéro, sinon
  l'ordre d'exécution déciderait quel test prend un 429.

**Depuis #509**, les cinq premières restent anonymes **côté RBAC** — aucune
session, aucun pouvoir — mais exigent désormais le mot de passe partagé du
site comme le reste de l'API (`require_site_access`, posé à l'inclusion dans
`v1/router.py`) : un visiteur qui ne l'a jamais entré ne les atteint plus du
tout, plafond ou pas. La sixième, `POST /site-access/session`, est par
construction hors de cette garde — c'est elle qui la satisfait. Son plafond est
donc le seul qui borne encore un vrai anonyme, et le seul à ne pas pouvoir
compter sur la garde en amont.

Le SSE prend `optional_user` et journalise son appelant : il ne le faisait pas,
et un import lancé depuis là ne laissait aucune trace de qui l'avait demandé.

**Ce que le plafond des écritures publiques borne, et ce qu'il ne borne pas**
(A04-3, #398) : `POST /admin/pending-providers` et `POST /participations`
écrivent en base sans session, et ce qui les encadrait ne bornait que ce qu'un
anonyme **publie** — le `provider_hint` déduit pour l'une, la quarantaine
`is_pending_validation` pour l'autre. La base grossissait quand même, et la
fiche d'un athlète réel restait polluable. **Aucune des deux ne se ferme** :
le signalement anonyme (#267) et la saisie sans compte (#270) sont des choix
délibérés que `tests/test_auth/test_public_routes_still_open.py` nomme. C'est
aussi pourquoi `PendingProviderCreate.url` est un `HttpUrl` et non un `str` :
sans forme imposée, la colonne `TEXT` en face accepte n'importe quelle taille.
Le signalement suivant toujours un import échoué, l'URL est déjà passée par
`ScrapeRequest` — la contrainte ne coûte rien à l'appelant légitime.

**`POST /participations` ignore `source_url` et force `provider="manuel"`,
côté serveur (#565).** Avant ce correctif, un appelant sans session choisissait
l'URL et le fournisseur de la **source active** posée sur l'épreuve qu'il
crée (`course_repository.get_or_create`, D3 de #278 — « la première source
d'une épreuve neuve prend la main sans arbitrage »), avec deux effets :
l'épreuve fabriquée entrait dans la file de re-scrape (`rescrape-db
--provider klikego`) et changeait la clé de cache d'un import ultérieur de
la même URL ; et — mesuré, pas seulement théorique — un `provider` ∈
`{klikego, breizhchrono}` et une `source_url` partageant `platform_event_id`
+ `heat_slug` avec une épreuve déjà en base **détournait cette épreuve
existante** via la règle R de `services/course_reconciliation`, qui
s'applique **avant** l'identité stricte (nom/date/type) et ne les compare
jamais. `ParticipationCreate.source_url` fait partie du contrat `/api/v1`
publié : le Principe IV interdit de le modifier silencieusement, donc le
champ reste **accepté** en entrée pour ne pas casser un appelant existant,
mais `api/v1/participations._to_scraped` le remplace toujours par `""` et
force `provider="manuel"` — sur le même patron que `is_pending_validation`
juste en dessous. `provider`, lui, a été **retiré** du schéma d'entrée : le
seul appelant (`ManualResultForm.tsx`) l'envoyait déjà en dur à `"manuel"`,
sans autre usage légitime côté client. Forcer `provider="manuel"` ferme
aussi le détournement d'épreuve existante en même temps que l'injection de
source : `find_reconcilable_course` n'agit que pour `provider` ∈
`{klikego, breizhchrono}`, jamais `"manuel"`. `evidence_url` reste le champ
prévu pour le lien de vérification d'une saisie manuelle — il n'a jamais
créé de `CourseSource` (#279, testé par
`test_evidence_url_ne_cree_aucune_source_de_scraping`).

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
Anonyme ici veut dire **sans RBAC** ; depuis #509, `POST /admin/pending-
providers` comme `POST /participations` restent derrière le mot de passe
partagé du site (`require_site_access`), au même titre que le reste de l'API
hors des cinq exceptions nommées de `v1/router.py`.

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
d'urgence des sessions (#169), les dix ressources de `admin_data.py` (#117),
doublons suspects (#288) — détail dans `docs/api/admin-donnees.md` ; retours
utilisateurs (#267) et statistiques détaillées d'une participation (#272) —
détail dans `docs/api/feedback-stats.md`.

## Page bénévoles : une seconde garde, hors du socle SSO (#271)

`benevoles.py` porte neuf ressources gardées par `require_benevole_access`
(`api/deps.py`) — **pas** `require_permission`. Mot de passe partagé (5-6
bénévoles). Décision produit et alternatives rejetées : `specs/20260815-
114258-page-validation-benevoles/research.md` §D1.

**Le mot de passe est géré depuis le back-office, plus une variable
d'environnement** (`specs/20260815-173645-admin-mdp-benevoles/`) : trois
routes sous `admin_benevole_access.py`, gardées par le pouvoir dédié
`benevole_access:manage` (`GET`/`PUT /admin/benevoles/access`,
`POST /admin/benevoles/access/generate`), lisent et écrivent la table
`benevole_access_config` — une seule ligne à tout instant, absence = accès
non configuré (fail-closed). Stocké **haché et salé** (`hashlib.scrypt`,
jamais en clair, jamais récupérable), avec un `session_secret` distinct qui
sert de clé au cookie signé HMAC-SHA256 : ce n'est plus le mot de passe lui-
même qui signe le cookie (research.md §D2 de cette dernière feature), ce qui
permet de préserver la propriété d'#271 — changer le mot de passe invalide
tous les cookies d'un coup (seule révocation retenue, aucune identité
individuelle à révoquer) — sans jamais avoir besoin de relire le mot de passe
en clair. `services/benevole_access.replace_password` est le seul point
d'écriture des trois champs secrets, toujours ensemble.

Deux d'entre elles délèguent à `admin_actions.update_course`/
`.reassign_participation` (déjà livrées pour `/admin/*`) sous le `user_id`
d'un **compte système** (« Bénévoles (accès partagé) », seedé par migration,
jamais par le code applicatif) — `AdminActionLog.user_id` est une FK `NOT
NULL`, et il n'y a pas d'identité individuelle à y mettre. **Quatre sont une
logique neuve** (#437) : `validate_participation`
(`is_pending_validation → false`), `reject_participation`/
`unreject_participation` (bascule `is_rejected`, jamais `is_pending_validation`
— cf. `app/models/participation.py`), et `update_participation_fields`
(dossard/place/club/catégorie, conflit de dossard détecté par lecture
préalable). Les deux routes restantes, `GET /benevoles/queue` et
`GET /benevoles/rejected`, lisent directement le repository sans passer par
`admin_actions` ; ni l'une ni l'autre ne filtre par club ou par portée : les
bénévoles valident les saisies de tous les clubs, pas seulement du leur.

**La neuvième est `GET /benevoles/athletes`** (revue de #513) — recherche
d'athlètes par nom, rendue en `AthleteBrief`, plafonnée à 20 résultats. C'est le
jumeau volontaire de `GET /athletes` : la réattribution d'une participation
(`ParticipationPanel`) a besoin de chercher un athlète, mais la page bénévoles
est une route sœur du groupe gardé côté front et un bénévole n'a que le mot de
passe **bénévoles**, jamais celui du site. Exempter `athletes` de
`require_site_access` aurait rouvert toute la recherche d'athlètes à l'anonyme ;
une route sous `/benevoles/` la garde derrière la garde que le bénévole possède
déjà. Elle rend `AthleteBrief`, donc sans `birth_date`.

**Le renommage, la réattribution, la validation, le rejet et la correction de
champs sont scopés au résultat en attente actionnable** (relevé en revue de
code, #437) : déléguer tel quel à `admin_actions` donnerait au mot de passe
partagé le pouvoir de réécrire
**n'importe quelle** épreuve ou participation en base, validée ou rejetée —
un pouvoir d'administration de fait, sans le contrôle individuel du SSO.
`rename_course` vérifie donc `participation_repository.has_pending_for_course`
avant de déléguer ; `reassign`, `validate`, `reject` et `update_fields`
relisent la participation ciblée pour confirmer `is_actionable_pending`
(`core/validation.py` — en attente **et** non rejetée, #437) — les cinq 404
sinon. `unreject` porte la garde inverse et n'en a pas besoin d'autre :
l'entrée doit au contraire être `is_rejected`, sans quoi il n'y a rien à
annuler.

`POST /benevoles/session` reste **non gardée** — c'est elle qui pose la garde
des neuf autres — et `test_public_routes_still_open.py` classe les neuf
routes gardées dans `ROUTES_BENEVOLES_FERMEES`, pas dans le préfixe `/admin/`
(ce mécanisme n'a rien à voir avec le SSO/RBAC). Y **ajouter** toute nouvelle
route de ce router : le test range par défaut dans « publique », donc un oubli
se lit comme une régression d'ouverture, pas comme une absence de couverture.

## Mot de passe d'accès au site : deux routeurs jumeaux (#509)

`site_access.py` (`POST`/`DELETE /site-access/session`, `GET` pour la
vérification) et `admin_site_access.py` (`GET`/`PUT /admin/site-access`,
`POST /admin/site-access/generate`) reprennent, secret par secret, le même
duo que `benevoles.py`/`admin_benevole_access.py` — même patron de mot de
passe haché+salé (`hashlib.scrypt`) et de cookie signé HMAC, gardé par le
pouvoir dédié `site_access:manage`. Deux différences assumées, pas un
doublon à fusionner : ce mot de passe ferme **tout** le site (posé en
`dependencies=` à l'inclusion de chaque sous-router dans `v1/router.py`,
plutôt qu'une garde route par route) et non la seule page bénévoles, et
`POST /site-access/session` porte `site_access_rate_limit` — cette route est
désormais la seule porte publique non authentifiée du site, et son
`hashlib.scrypt` à chaque tentative en fait un levier de déni de service sans
ce plafond (revue finale, § « Plafond de débit » de
`docs/superpowers/specs/2026-08-20-mot-de-passe-site-design.md` ; le seau est
devenu **dédié** en revue de #513, cf. § « Plafonds de débit par IP »).

**Six routers sont exemptés de la garde**, et la liste
`_EXEMPTES_DE_LA_GARDE_SITE` de `v1/router.py` en est la description unique :
`health` (sonde Render), `site_access` (elle pose la garde), `auth` +
`admin_site_access` (le chemin qui installe le tout premier mot de passe sur un
déploiement neuf), `benevoles` (le bénévole n'a que **son** mot de passe, cf. la
section ci-dessus) et `feedback` (revue de #513 — `FeedbackButton` vit dans le
layout racine du front, donc il se rend aussi sur `/acces` et `/benevoles`, où
aucun cookie de site n'existe ; son unique route est déjà bornée par honeypot et
par un plafond compté en base, et `admin_feedback` reste gardé, lui). Les
inventaires dérivés de cette liste — `tests/test_auth/test_site_access_gate.py`,
son `ROUTES_EXEMPTEES_PREFIXES` — se mettent à jour du même geste.

La longueur maximale du mot de passe est **une seule constante partagée**,
`schemas/site_access.MAX_PASSWORD_LENGTH`, que `site_access_config.py` importe :
les deux bouts doivent s'accorder, sans quoi l'administration accepte un mot de
passe que la connexion refuse en 422 — un accès configuré et inutilisable
(relevé en revue de #513).

