# Modèle normalisé

- **Athlete** — `UNIQUE(last_name_key, first_name_key, homonym_rank)` (#907) :
  les deux clés sont écrites par l'écouteur `_store_identity_keys` à chaque
  insertion ou mise à jour ORM, jamais par l'appelant ; un `UPDATE` de masse
  sur `nom`/`prenom` les laisserait périmées. Rang 0 = fiche principale, la
  seule que l'import résout. Un rang ≥ 1 naît à l'import quand un dossard neuf
  tomberait sur une fiche qui porte déjà un autre dossard de la même épreuve
  individuelle (`athlete_repository.create_homonym`, rang suivant, #967) ; une clé vide (`?`, `-`) vaut NULL et ne désigne
  personne. `birth_date` n'entre pas dans l'identité (#900). La création par
  l'import est idempotente sous concurrence : `athlete_repository.create_batch`
  insère en `ON CONFLICT DO NOTHING` puis relit les identités qu'une autre
  transaction a créées (#981), et la résolution prend `FOR KEY SHARE` sur les
  fiches trouvées, qu'une fusion ne peut donc pas supprimer sous un import.
  `club` porte le club
  **actuel** : il suit la dernière épreuve **courue**, pas la dernière importée
  (#965). Un import ne le réécrit que si son épreuve est au moins aussi récente
  que la plus récente participation datée avec club déjà connue (validée, hors
  relais composé, #1153)
  (`athlete_repository.club_is_current`, même règle dans `resolve` et dans la
  résolution par lot d'`import_service`). Sauf correction humaine : `club_locked` (#439),
  posé par `admin_actions.update_athlete` quand le club écrit diffère de celui en
  base, dit à `athlete_repository.resolve` de ne plus le réécrire. Sans lui, une
  course d'il y a trois ans annonçant le club de l'époque ramènerait la
  correction à chaque réimport. Le club **de l'époque** d'un résultat, lui, vit
  sur `Participation.club` et ne bouge jamais.
  **Trois tables pointent vers `athletes.id` hors des résultats sans
  `ondelete`** : `volunteer_actions`, `season_validations` et
  `users.athlete_id` (la liaison des équipiers mise à part, ci-dessous ; les
  variantes et paires écartées, en cascade, plus bas). Une
  fiche sans résultat mais référencée par l'une d'elles n'est **pas
  orpheline** : la purge d'orphelins (`delete_orphans_among`) comme la purge
  totale (`delete_unreferenced`, #994) la conservent via
  `referenced_outside_results` (#901), sans quoi PostgreSQL lève
  une `ForeignKeyViolation` que SQLite, FK inertes, ne montre pas. Les tests
  qui l'éprouvent passent par la fixture `db_session_fk`
  (`PRAGMA foreign_keys=ON`).
- **AthleteAlias** (#908) — une graphie absorbée par une fusion admin,
  `UNIQUE(last_name_key, first_name_key)`, `athlete_id` en `ON DELETE CASCADE`.
  L'import la résout comme l'identité de sa fiche, après l'identité directe et
  avant le repli. Une fusion repointe les variantes de la fiche absorbée et y
  ajoute la sienne. **Une fusion déplace neuf références** : `participations`,
  `participation_teammates`, `volunteer_actions`, `season_validations`
  (dédoublonnées par saison), `users.athlete_id`, `challenge_results`,
  `athlete_aliases`, `ignored_athlete_pairs` et `athlete_known_clubs` (sans
  compter `club_members`, repointé aussi) ; une nouvelle table qui pointe vers `athletes.id`
  doit rejoindre `athlete_merge.merge_athletes`.
- **IgnoredAthletePair** (#908) — une paire de fiches qu'un admin a déclarées
  deux personnes depuis la revue d'identité, `UNIQUE(athlete_id_low,
  athlete_id_high)` (paire normalisée), les deux ids en `ON DELETE CASCADE`. La
  revue ne la propose plus, la reprise (`reconcile-athletes`) ne la fusionne
  jamais. **Le jugement suit la personne** : une fusion le reporte sur la fiche
  conservée (`ignored_athlete_pair_repository.repoint`), et la reprise l'étend
  à tout ce qu'une fiche aura absorbé dans son plan. Sans ce report, la cascade
  effaçait la paire avec la fiche absorbée et rouvrait le cas.
- **AthleteKnownClub** (#1209) : un club qu'un admin a confirmé pour une fiche
  (`club_key` canonique), `UNIQUE(athlete_id, club_key)`, `athlete_id` en
  `ON DELETE CASCADE`. Lu par la revue `multi_club` et par l'import. Une paire
  posée par l'import n'a pas d'auteur : `ignored_athlete_pairs.ignored_by_user_id`
  est nullable.
- **IgnoredIdentityCase** (#1252) : un cas de revue à une seule fiche
  (`same_course_bibs`) qu'un admin a écarté, `UNIQUE(athlete_id, reason)`,
  `athlete_id` en `ON DELETE CASCADE`. `fingerprint` retient les épreuves en
  conflit jugées : une épreuve de plus rouvre le cas. Une fusion **ne le
  reporte pas**, elle l'efface (`athlete_merge`) : la fiche conservée réunit
  d'autres épreuves que celles jugées.
- **Les quatre seules tables en `ON DELETE CASCADE` vers `athletes.id`** sont
  `athlete_aliases`, `athlete_known_clubs`, `ignored_athlete_pairs` et
  `ignored_identity_cases` : la suppression d'une fiche
  (purge d'orphelins, opposition, fusion) les emporte en PostgreSQL, mais
  **pas en SQLite**, où `database.py` n'émet aucun `PRAGMA foreign_keys=ON`.
  Les tests qui en dépendent passent par `db_session_fk`.
- **Challenge** (#1008) — un classement qui cumule les résultats d'un athlète
  sur plusieurs épreuves du même jour (Klikego « START CHALLENGE (XS - M - L) »).
  Trois tables : `challenges` (`UNIQUE(name, event_date)`), `challenge_courses`
  (les N épreuves liées, cascade des deux côtés) et `challenge_results`
  (`UNIQUE(challenge_id, bib_number)`, `athlete_id` en `RESTRICT`). **Une ligne
  Challenge n'est pas une `Participation`** : elle n'entre dans aucun compteur,
  `federal_only`, validation de saison, stat ni classement, par construction.
  Elle ne crée jamais de fiche : l'import l'apparie aux athlètes déjà présents
  sur les épreuves du même jour, et écarte une ligne sans appariement unique
  (une personne opposée, déjà anonymisée, ne revient donc pas par là). Elle
  désigne pourtant la fiche : `referenced_outside_results` la compte, la
  fusion la déplace, l'opposition l'anonymise, les purges totales la vident.
  Design : `docs/superpowers/specs/2026-10-02-challenge-rankings-design.md`.
- **Course** — `UNIQUE(name, event_date, event_type, is_relay)`
  (`uq_course_identity`) : le relais est un **heat distinct** du solo, sans quoi
  les deux fusionnaient dans la même ligne. Quatre colonnes, pas trois — la
  vérité est dans `backend/app/models/course.py`. `source_url` et `provider`
  n'en font **plus** partie (#279) : deux `hybrid_property` lisant la source
  active, cf. plus bas. `source_url` reste la clé du cache TTL.
- **CourseSource** — `UNIQUE(course_id, url)`, **jamais** `UNIQUE(url)` (cf. plus bas).
- **Participation** — `UNIQUE(course_id, bib_number)` → plus de doublons à l'import.
  `counts_for_tcn` porte le verdict du club (#1206) ; un écouteur n'en pose que
  la condition du libellé, le reste vient de `tcn_count_repository`.
  `source_identity_key` retient la clé (`<nom>|<prénom>`, #907) de la ligne
  source qui a produit le résultat, indépendamment de sa fiche : l'import
  apparie par elle les lignes sans dossard, et ne change un résultat de fiche
  que si elle change, c'est-à-dire si le chronométreur a corrigé le nom (#896).
  Une fiche renommée, datée ou fusionnée par un admin garde donc ses résultats.
  `athlete_locked`, posé par `reassign_participation`, fige la fiche choisie :
  l'import ne met plus à jour que les valeurs. Un résultat saisi à la main n'a
  pas de clé source, celle de sa fiche en tient lieu.
- **ParticipationTeammate** (#894) — les équipiers d'un relais attribué, table
  `participation_teammates`, PK `(participation_id, athlete_id)`, ordonnée par
  `position`. Le résultat reste **une** ligne `participations` : classement,
  compteurs de l'épreuve et podiums du club le comptent une fois, sans
  dédoublonnage. Invariants : liaison vide = résultat classique ; non vide =
  2 à 8 équipiers, dont `athlete_id` (le porteur, premier de la liste). Trois
  pièges :
  - **Toute lecture « par athlète » passe par la liaison** :
    `participation_repository.carried_by` (fiche, `exists_for_athlete_on_course`,
    comptes) et `athlete_repository.credits` (roster, rang, composition, et
    `only_on_course`). Un équipier n'est référencé que par la liaison :
    `delete_orphans_among` l'épargne explicitement.
  - **L'import ne touche jamais un relais attribué** : `_Persister` le met à
    jour en valeurs sans résoudre l'identité de l'équipe (avec dossard), et
    l'apparie par `team_name` normalisé (`_team_key`, sans dossard) — sinon le
    rescrape recréait la fiche d'équipe et défaisait l'attribution.
    `set_teammates` pose `team_name` depuis la fiche d'origine pour cela.
  - **Un podium de relais n'est pas un podium individuel** (spec FR-011) :
    exclu des podiums du roster et des tuiles de la fiche athlète, compté une
    fois pour le club.
  - **Tout `DELETE` de masse sur `participations` efface d'abord la liaison**
    (`participation_repository.delete_teammates`) : son `ON DELETE CASCADE`
    est inerte en SQLite (aucun `PRAGMA foreign_keys=ON`), et un id réutilisé
    hériterait d'équipiers fantômes. Même raison, le `RESTRICT` vers
    `athletes.id` n'est vérifiable qu'en PostgreSQL : aucun test ne le couvre.

  Deux limites assumées (revue de #894) : la **bascule de source** d'une
  épreuve (`delete_for_course` puis réimport) perd les compositions posées,
  les équipiers devenant orphelins ; et `credits()` est un `UNION ALL` avec un
  `NOT EXISTS` corrélé sur toute la table, recalculé par roster, composition,
  recherche et totaux — à mesurer (`EXPLAIN`) sur la base PostgreSQL si ces
  écrans ralentissent.
- **AthleteOpposition** (#334) : l'empreinte (`core/identity.identity_hash`)
  du nom et du prénom normalisés d'une personne qui s'est opposée à la
  publication de ses résultats, ses dates et son auteur. **Aucun nom ni lien
  vers `athletes`** : la fiche disparaît à l'application. `_Persister` charge
  les empreintes une fois par import et rend anonyme (« Anonyme
  {épreuve}-{dossard} ») toute ligne qui correspond. La clé ignore la date de
  naissance, que les imports n'ont jamais, donc les homonymes sont couverts.
  **Un relais qui nomme la personne arrive anonyme en entier**, jamais découpé :
  son libellé (`team_name`, ligne brute, fiche d'équipe d'un découpage refusé)
  la nommerait, et un découpage refusé recréerait ce libellé en fiche.
- **AbsorbedCourse** (#983) — l'identité publiée (URL, nom, date, type, relais)
  d'une épreuve supprimée par une fusion, et sa cible. Une ligne scrapée qui la
  porte est **ignorée** (`mapping.is_absorbed`, `_Persister.add`) : sans quoi le
  rescrape d'une URL partagée par des épreuves sœurs recréait l'absorbée, et la
  rediriger vers la cible y écrasait temps et rangs. Suit sa cible :
  `Course.absorbed` en `delete-orphan`, et une seconde fusion qui absorbe la
  cible la repointe (`absorbed_course_repository.repoint`, par la relation et
  avant le `delete`, comme `move_to`). `course_repository.delete_all` la vide
  avant `courses`.
- **IgnoredCourseDuplicate** (#754) — `UNIQUE(course_id_low, course_id_high)`,
  la paire normalisée (le plus petit id en premier). **Seule table à référencer
  `courses.id` sans cascade ORM ni `ondelete`** : contrairement à `CourseSource`
  (`Course.sources`, `delete-orphan`), rien sur `Course` ne la connaît.
  `course_repository.delete`/`.delete_all` appellent explicitement
  `ignored_course_duplicate_repository.delete_for_course`/`.delete_all` avant de
  supprimer une épreuve — un futur point de suppression de `Course` (nouveau
  chemin de fusion, purge…) doit faire de même, sous peine de
  `ForeignKeyViolation` en PostgreSQL, invisible en SQLite (`database.py`
  n'émet aucun `PRAGMA foreign_keys=ON`).
- **`Course.format_label`** (#270) — précision libre du format quand il n'entre
  dans aucune taille normalisée (« Autre » du formulaire de saisie manuelle). Le
  format normalisé, lui, reste encodé **dans** `event_type` (`triathlon-m`) —
  cette colonne ne le duplique jamais, elle ne porte que ce que la taxonomie
  fermée ne peut pas exprimer.
- **`Participation.team_name`**, **`.evidence_url`**, **`.is_pending_validation`**
  (#270) — respectivement le nom d'équipe d'un résultat collectif, le lien de
  vérification saisi par le déclarant (jamais une `CourseSource` — un lien
  posé en source active scraperait la page collée par un membre avec
  `provider="manuel"`), et l'état de validation d'un résultat déclaré.
  `is_pending_validation` est une **dimension distincte** de `status` : un
  abandon déclaré reste un abandon une fois validé. Exclusion des agrégats
  publics : `app/core/validation.py` (`validated_clause`, sur le
  patron de `club.py`/`discipline.py`), appliquée à 9 fonctions réparties sur
  trois repositories (`participation_repository.py` : liste, épreuves,
  stats, classement, synthèse, saisons distinctes ; `course_repository.py` :
  catalogue en portée club ; `athlete_repository.py` : activité par saison,
  recherche de la palette ⌘K — détail dans `app/api/AGENTS.md`) et
  délibérément absente de `list_for_athlete`, qui doit montrer
  une participation pendante (FR-019) ; la page épreuve la lit à part (#1273).
  **Piège mesuré** : `server_default="false"` (chaîne) sur SQLite se relit
  `True` via l'ORM — une chaîne non vide est vraie en Python. `is_relay`
  ci-dessous en porte le même défaut, non corrigé (hors périmètre de #270) ;
  `is_pending_validation` utilise `server_default=false()` (l'expression
  SQLAlchemy, pas la chaîne), qui rend `DEFAULT 0` et relit correctement.
- **splits** en **JSON** (remplace les colonnes figées swim/t1/bike/t2/run) →
  couvre tous les sports (duathlon course1/course2, swimrun…). Temps = strings.
  Les scrapers rangent les segments dans 5 slots positionnels triathlon
  (`swim/t1/bike/t2/run` de `ScrapedResult`) ; `services/mapping.build_splits`
  ré-étiquette ces slots selon `event_type` via le gabarit
  `SPLIT_KEYS_BY_SPORT` (ex. duathlon → `course1`/`course2`) et omet les slots
  **vides**. Elle écarte aussi, sur les deux chemins, tout segment qui n'est pas
  une durée strictement positive (`00:00:00`, durée négative, « FRA ») ou qui
  dépasse le total, et vide les splits d'une ligne dont tous les segments (au
  moins deux) valent le total (#971). Limite : « vide n'écrase pas », donc un
  rescrape ne nettoie pas une ligne dont **tous** les segments sont écartés. Un slot sans discipline lisible pour le sport n'est pas absent du
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
  épreuve déjà connue ne prend pas la main, la première scrapée la garde. C'est
  vrai de `add`, la primitive ; `attach` (#283, le point d'entrée de l'import) la
  pose **active quand l'épreuve n'en a aucune** — même règle lue dans l'autre
  état, une épreuve sans source n'a personne à qui laisser la main. Rattacher en
  passive une épreuve sans active produirait une source orpheline : jamais
  scrapée (#282), jamais affichée (#279), à activer à la main faute d'alternative.
- **Pas d'`ondelete`**, comme partout : la cascade est portée par
  `Course.sources` (`delete-orphan`). Supprimer une épreuve emporte ses sources ;
  en absorber une (#287) suppose de repointer `source.course` **avant** le delete,
  comme `services/reclassify` le fait pour les participations.

### La table est la seule vérité (#279)

`Course.source_url` et `Course.provider` **ne sont plus des colonnes** : ce sont
deux `hybrid_property` qui lisent la source active **dans la collection déjà en
mémoire** (`_from_active_source`), sans requête ni `@expression` SQL.

**#306, tranché** : l'`@expression` (sous-requête scalaire corrélée) a été
**supprimée**, pas gardée. Ses quatre anciens consommateurs —
`get_latest_by_source_url`, `list_by_source_url`, `list_by_source_urls` et
`iter_all(provider=…)` — joignaient déjà `course_sources` depuis #281/#282,
plus rapide qu'une corrélée évaluée une fois par ligne de `courses`. #288
(détection de doublons) et #289 (rapprochement automatique), les deux
candidats que la question laissait ouverte, sont arrivés depuis sans en créer
de nouveau : `list_identities_with_counts` (#288) et
`course_reconciliation.find_reconcilable_course` (#289) lisent tous les deux
`CourseSource.provider`/`.url` directement, jamais `Course.provider` en
requête. Zéro appelant restant confirmé sur tout le dépôt (grep, pas
supposition) : la garder aurait contredit « pas d'indirection spéculative ».
**Un futur `filter(Course.provider == …)` lève désormais** — c'est l'effet
voulu, pas une régression : la bonne écriture est la jointure sur
`course_sources`, comme les quatre fonctions ci-dessus. La moitié **Python**,
elle, n'a jamais été en cause : `CourseBrief` et le rescrape la lisent sur
chaque épreuve, à l'instance — c'est la seule forme qui reste.

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

## Licenciés du club par saison (#1202)

`club_members` (`id`, `season`, `licence_id`, `nom`, `prenom`, `gender`,
`last_name_key`, `first_name_key`, `athlete_id`, `link_status`, `source`,
`created_at`) liste les licenciés du club, lus sur la page FFTri ou importés d'un
fichier. Seul point de passage : `club_member_repository`.

- **`season` suit `core/season`** (année de début) : la licence FFTri « 2027 »,
  publiée dès septembre 2026, couvre la saison 2026.
- **Deux unicités.** `(season, licence_id)` ; et, pour les lignes sans numéro
  (fichier) non rattachées ou ambiguës, `(season, last_name_key, first_name_key)`
  par un index partiel. Une ligne rattachée sans numéro est identifiée par sa
  fiche, hors de l'index (le service d'import dédoublonne). Deux homonymes avec
  numéros distincts coexistent.
- **`link_status`** : `auto` et `manual` (rattaché, `LINKED`), `unlinked`,
  `ambiguous` (plusieurs fiches pour la clé, un humain tranche). `source` :
  `fftri` ou `file`.
- **`athlete_id` est en `SET NULL`**, donc une fusion de fiches doit appeler
  `club_member_repository.repoint` avant de supprimer la fiche absorbée.
- **Conservation.** Les saisons plus anciennes que `current_season() - 1`
  passent par `purge_before` : lignes non rattachées supprimées ; lignes
  rattachées réduites à `(season, athlete_id, link_status, source)` (une seule par
  fiche et saison ; celles dont la fiche a disparu sont supprimées), numéro de
  licence effacé, nom et prénom remplacés par ceux de la fiche. Les résultats
  passés continuent ainsi de compter sans second exemplaire de la donnée.
