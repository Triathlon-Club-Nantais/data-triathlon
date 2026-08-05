# Modèle normalisé

- **Athlete** — `UNIQUE(nom, prenom, birth_date)`.
- **Course** — `UNIQUE(name, event_date, event_type, is_relay)`
  (`uq_course_identity`) : le relais est un **heat distinct** du solo, sans quoi
  les deux fusionnaient dans la même ligne. Quatre colonnes, pas trois — la
  vérité est dans `backend/app/models/course.py`. `source_url` = clé de cache TTL.
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
