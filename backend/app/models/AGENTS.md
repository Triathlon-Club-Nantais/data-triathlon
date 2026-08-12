# Modèle normalisé

- **Athlete** — `UNIQUE(nom, prenom, birth_date)`.
- **Course** — `UNIQUE(name, event_date, event_type, is_relay)`
  (`uq_course_identity`) : le relais est un **heat distinct** du solo, sans quoi
  les deux fusionnaient dans la même ligne. Quatre colonnes, pas trois — la
  vérité est dans `backend/app/models/course.py`. `source_url` et `provider`
  n'en font **plus** partie (#279) : deux `hybrid_property` lisant la source
  active, cf. plus bas. `source_url` reste la clé du cache TTL.
- **CourseSource** — `UNIQUE(course_id, url)`, **jamais** `UNIQUE(url)` (cf. plus bas).
- **Participation** — `UNIQUE(course_id, bib_number)` → plus de doublons à l'import.
- **splits** en **JSON** (remplace les colonnes figées swim/t1/bike/t2/run) →
  couvre tous les sports (duathlon course1/course2, swimrun…). Temps = strings.
  Les scrapers rangent les segments dans 5 slots positionnels triathlon
  (`swim/t1/bike/t2/run` de `ScrapedResult`) ; `services/mapping.build_splits`
  ré-étiquette ces slots selon `event_type` via le gabarit
  `_SPLIT_KEYS_BY_SPORT` (ex. duathlon → `course1`/`course2`) et omet les slots
  **vides**. Un slot sans discipline lisible pour le sport n'est pas absent du
  gabarit pour autant : il porte une clé positionnelle (`segment1` en bike & run,
  `segment2` en swimrun). L'omettre du gabarit jetait sans bruit le temps qui s'y
  trouvait, le filtre du gabarit ne distinguant pas « pas de clé » de « pas de
  valeur ». *Limite levée pour les scrapers qui renseignent `segments`*
  (RaceResult) : la liste ordonnée de segments étiquetés prime sur les 5 slots
  et n'a pas de plafond côté code. **Ce déplafonnement n'est pas mesuré** : sur
  le panel RaceResult, le maximum observé est de 5 segments, et les swimruns
  sondés n'ont **aucune liste publiée portant une colonne de split** — ils
  sortent donc à 0 segment, non par troncature. Ne pas en déduire qu'un swimrun
  multi-legs « garde toutes ses étapes » : rien ne l'établit à ce jour. Panel et
  chiffres : `docs/superpowers/specs/2026-07-19-raceresult-api-sondage.md`. Les
  scrapers qui remplissent encore les 5 slots restent plafonnés à 5 segments.

## Sources d'une épreuve (#278) — une table, deux contraintes

`course_sources` (`id`, `course_id`, `url`, `provider`, `is_active`,
`created_at`, `created_by_user_id`, `last_scraped_at`) donne à une épreuve **N
sources dont une seule active**. Les participations restent portées par la
`Course`, jamais par la source : le classement affiché ne mélange pas deux
chronométreurs.

- **`UNIQUE(course_id, url)`, et surtout pas `UNIQUE(url)`.** Une URL porte
  légitimement N épreuves — heats Klikego, multi-catégories Wiclax, multi-listes
  RaceResult, multi-épreuves Chronoplace, cf.
  `course_repository.list_by_source_url`. Ce n'est pas une hypothèse : sur la base
  de dev, **5 URLs portent plusieurs épreuves, la plus chargée en porte 13** — un
  unique global aurait fait échouer la migration de reprise elle-même.
- **`Index` partiel unique `UNIQUE(course_id) WHERE is_active`** : l'unicité de la
  source active est tenue par la **base**, pas par une lecture préalable que deux
  exploitants simultanés franchiraient tous deux. Il porte `sqlite_where=` **et**
  `postgresql_where=` — même piège qu'`uq_role_global_slug` : n'en donner qu'un
  produit un index *complet* sur l'autre moteur, et la deuxième source d'une
  épreuve devient irreprésentable.
- **Une source naît passive** (`is_active=False`) : une URL soumise pour une
  épreuve déjà connue ne prend pas la main, la première scrapée la garde.
- **Pas d'`ondelete`**, comme partout : la cascade est portée par
  `Course.sources` (`delete-orphan`). Supprimer une épreuve emporte ses sources ;
  en absorber une (#287) suppose de repointer `source.course` **avant** le delete,
  comme `services/reclassify` le fait pour les participations.

### La table est la seule vérité (#279)

`Course.source_url` et `Course.provider` **ne sont plus des colonnes** : ce sont
deux `hybrid_property` qui lisent la source active, sur le patron de
`Course.is_reliable` (plus bas) — la propriété Python **plus** son `@expression`.
L'`@expression` est une sous-requête scalaire corrélée repliée sur `""` par
`coalesce` — sans ce repli, le SQL rendrait `NULL` là où le contrat public promet
une chaîne. Vérifiée exécutée sur SQLite **et** PostgreSQL (`WHERE`, `IN`,
`ORDER BY`, projection) : la suite de tests, elle, ne voit que SQLite
(`tests/conftest.py` code le moteur en dur).

**Elle n'a plus d'appelant depuis #281 et #282.** Ses quatre consommateurs —
`get_latest_by_source_url`, `list_by_source_url`, `list_by_source_urls` et
`iter_all(provider=…)` — joignent désormais `course_sources` : une corrélée
s'évalue une fois par ligne de `courses`, une jointure ramène `courses` par sa
clé primaire. Seuls les tests de `test_course_derived_source` l'exercent encore.
**Le sort de l'`@expression` est #306, à trancher avant #293** : la garder sans
appelant contredit « pas d'indirection spéculative » ; la supprimer ferait lever
tout futur `filter(Course.provider == …)`, ce qui est peut-être l'effet voulu —
la bonne écriture est maintenant la jointure. La question ne se referme qu'une
fois les lots 2 à 4 livrés, #288 et #289 étant les deux candidats plausibles à
lui rendre un appelant. La moitié **Python**, elle, n'est pas en cause :
`CourseBrief` et le rescrape la lisent sur chaque épreuve.

- **Aucun `@setter`, et c'est délibéré** : plus aucun appelant n'écrit ces deux
  champs. Ce n'est pas une convention à surveiller par grep — l'affectation lève.
  Le point d'écriture unique est `course_repository.get_or_create`, dont la
  **signature ne bouge pas** (les 14 scrapers et `services/mapping` appellent
  comme avant) : ses kwargs `source_url`/`provider` deviennent la source active
  de l'épreuve neuve, passée `is_active=True` **explicitement** puisque la
  colonne vaut `False` par défaut.
- **`selectinload(Course.sources)` sur tout chemin qui rend des entités et lit
  ces champs** — les trois recherches par URL, `iter_all` (`rescrape-db` les lit
  sur *chaque* épreuve) et `list_all` (le catalogue sérialise `CourseBrief`). Pas
  sur `_filtered`, que `count_all` partage et qui ne charge rien.
- **Jointure pour filtrer, `selectinload` pour charger** (#281, #282), et les deux
  sont nécessaires sur les mêmes requêtes : la jointure est filtrée sur la seule
  source active, elle ne peut donc pas peupler `course.sources` — un
  `contains_eager` y mettrait une collection tronquée à une ligne, et
  `list_for_course` (#284) rendrait une source unique sur une épreuve qui en a
  trois. Aucun `DISTINCT` n'est nécessaire : l'index partiel
  `UNIQUE(course_id) WHERE is_active` ne laisse au plus **une** ligne joignable
  par épreuve.
- **Filtrer sur `is_active` est une règle, pas une optimisation** : une source
  passive n'alimente aucun affichage, ne porte pas de cache TTL (#281) et n'est
  jamais scrapée (#282). Une requête qui l'oublie rend le classement d'un autre
  chronométreur sous l'URL qu'on vient de coller.
- **Un `provider` sans URL n'est plus représentable** : le provider est un champ
  de la **source**, et `CourseSource.url` est `NOT NULL`. `POST /participations`
  sans `source_url` donne donc une épreuve à provider vide. La décision ne date
  pas d'ici — la reprise de #278 n'avait donné aucune source aux épreuves à
  `source_url` vide. Portée mesurée sur la base de dev le 12/08/2026 : **0
  épreuve sur 95**. Épinglé par
  `test_course_derived_source.test_a_provider_without_a_url_is_not_representable`,
  à revérifier sur preview avant #293.
- **La remontée de `b3c4d5e6f7a8` rend les colonnes *et leur contenu***, relu
  depuis la source active. Les passives, elles, n'ont pas d'endroit dans l'ancien
  schéma : c'est la limite assumée, et la raison pour laquelle `course_sources`
  n'est **pas** supprimée par cette remontée.

## RBAC (#115) — quatre tables, deux colonnes

- **Organisation** — le club. Une ligne (`tcn`). Elle existe pour rendre
  `user_roles.organisation_id` **non nul**, ce qui supprime le piège des deux
  index d'unicité qu'imposerait une colonne nullable. Ne portera jamais de donnée
  sportive : `Course` est unique par `(name, event_date, event_type, is_relay)`,
  deux clubs important la même épreuve obtiennent la **même** ligne.
- **Role** — `UNIQUE(organisation_id, slug)` **et** un `Index` partiel unique sur
  `slug` `WHERE organisation_id IS NULL`. Les deux, parce que SQLite comme
  PostgreSQL tiennent deux `NULL` pour distincts : la contrainte seule laisse
  passer deux rôles globaux `admin`. L'index porte `sqlite_where=` **et**
  `postgresql_where=` — n'en donner qu'un produit un index *complet* sur l'autre
  moteur, ce qui interdirait silencieusement un même slug dans deux
  organisations. Et il vit dans `__table_args__`, pas seulement dans la
  migration : `conftest.py` construit le schéma par `create_all`.
- **RolePermission** — `permission_code` est une **chaîne sans clé étrangère**,
  sur le patron de `Course.event_type`. La liste de référence des codes vit dans
  `core/permissions.py` ; une table `permissions` serait un second inventaire, et
  son sync effacerait des attributions en production le jour où un module ne
  serait pas importé au démarrage.
- **UserRole** — `UNIQUE(user_id, role_id, organisation_id)` : c'est **elle** qui
  rend l'attribution idempotente sous concurrence, pas une lecture préalable, que
  deux exploitants simultanés franchiraient tous deux. `role_id` et non `role`,
  d'où un renommage gratuit. Pas d'`ondelete`, cascade ORM depuis `User.roles` —
  même raison qu'en #114.
- **`users` ne porte toujours aucune colonne de rôle**, et un test le vérifie sur
  le schéma appliqué.

**`Course.is_reliable` est une `hybrid_property`**, plus une colonne :
`coalesce(reliability_override, is_reliable_computed)`, avec son `@expression`
— sans lui elle serait illisible dans un `WHERE`. `is_reliable_computed` est
écrite par l'import à chaque passage, `reliability_override` par le porteur de
`quality:override`. Les deux chemins d'écriture **ne se croisent pas**, et c'est
la forme qui l'assure, pas une garde. Lever l'avis humain (`NULL`) fait
réapparaître le **dernier** verdict calculé, pas celui qui valait au moment de la
décision. Le contrat public ne bouge pas : `from_attributes=True` lit une
propriété comme une colonne.

## Liste d'autorisation (#170) — une table, trois invariants

`allowed_emails` (`id`, `email` **UNIQUE**, `created_at`, `created_by_user_id`,
`role_id`) dit qui a le droit d'ouvrir une session. Elle remplace `AUTH_ALLOWED_EMAILS`,
dont la lecture par un `Settings` en `lru_cache` faisait de l'ajout d'un
contributeur un redéploiement.

- **L'adresse est rangée normalisée** — minuscules, espaces retirés — par
  `allowed_email_repository`, seul point de passage de la table. C'est ce qui
  rend le `UNIQUE` suffisant et évite un index fonctionnel `lower(email)` côté
  PostgreSQL.
- **Elle autorise, elle n'identifie pas.** Aucune colonne ne désigne le
  titulaire et aucune ne le désignera : une identité externe inconnue crée
  **toujours** un nouvel utilisateur (#114, FR-003), et apparier sur l'adresse
  rouvrirait la prise de contrôle par pré-inscription. `created_by_user_id` nomme
  celui qui **accorde**, jamais celui qui reçoit — d'où le champ d'API
  `created_by_name`, un nom d'affichage et non un identifiant. **`role_id` ne
  fait pas exception, et il a fallu une correction pour que ce soit vrai** :
  laissé posé après usage, il armait *chaque* identité suivante portant
  l'adresse — l'appariement par adresse, sur le chemin qui accorde du pouvoir.
  Il est **consommé** à l'application (`provisioning`), donc il ne dit jamais
  « cette adresse est administratrice », seulement « le prochain compte à naître
  ici commencera avec ceci ».
- **Elle n'est pas rattachée à une organisation.** Elle répond « cette adresse
  peut-elle ouvrir une session ? », pas « dans quel club ? » — c'est le rôle qui
  porte l'organisation. Une liste par club supposerait de savoir à quel club
  rattacher quelqu'un *avant* qu'il existe.

**Pas d'`ondelete`**, comme les trois tables de #114 : supprimer l'utilisateur
qui a inscrit une adresse ne doit jamais retirer l'adresse — ce serait une
révocation d'accès par effet de bord.
