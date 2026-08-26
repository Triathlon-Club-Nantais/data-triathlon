# Observabilité SQL

Un étage, éteint ou presque par défaut (#89).

`core/sql_observability.py` — listeners posés sur l'engine par `database.py`.
Deux niveaux : un **seuil de lenteur** (`SQL_SLOW_QUERY_MS`, défaut 100 ms) qui
sort en WARNING sur le logger `app.sql`, et un **bilan agrégé par unité de
travail** (`SQL_QUERY_STATS`, défaut `false`) — une requête HTTP côté web, une
**épreuve** côté CLI. C'est le second qui rend un N+1 visible (« 1812 requêtes
pour 1810 participants ») ; le premier seul ne le montrerait pas.

Trois règles à ne pas relâcher. Le SQL est journalisé **paramétré**, jamais avec
ses valeurs liées : elles portent des noms d'athlètes et des libellés de club, et
partiraient dans les logs Render (test de non-régression dédié). Le bilan sort en
**plusieurs enregistrements**, jamais en message multi-ligne : le formateur JSON
de `core/logging.py` construit son objet à la main — et le **label** de l'unité
de travail subit le même écrasement d'espaces que le SQL, puisqu'il est lui aussi
construit depuis des données scrapées (`rescrape_service.py` le compose avec
`Course.name`) : un retour à la ligne y casserait le JSON tout autant. Et seuil à
`0` **plus** bilan éteint = aucun listener posé, coût strictement nul.

Le socle OpenTelemetry qui vivait ici (`core/tracing.py`) a été **supprimé** :
`OTEL_ENABLED` était à `false` par défaut, aucun collecteur n'a jamais été
hébergé, et 377 lignes plus 4 dépendances attendaient un futur qui n'est pas
venu. Le jour où un collecteur tourne, `setup_tracing` / `shutdown_tracing` se
réécrivent en ~25 lignes. Deux pièges mesurés à ne pas redécouvrir alors :
`FastAPIInstrumentor` pose `http.url` **query string comprise, non masquée** —
`name=LEMÉE+Jean` d'une recherche `/api/v1/athletes` partirait en clair vers le
collecteur, il faut un `server_request_hook` qui réécrit `http.url` ; et un
`shutdown` symétrique est obligatoire, les instrumenteurs OTel étant des
singletons par classe (`BaseInstrumentor`), sans quoi un second `setup` dans le
même process est un no-op silencieux. Design d'origine :
`docs/superpowers/specs/2026-07-31-sql-observability-design.md`.

**EXPLAIN et audit d'index restent à faire** : c'est l'analyse à mener *avec* cet
outil, dont le livrable sera un sondage sous `docs/superpowers/specs/`.
Design : `docs/superpowers/specs/2026-07-31-sql-observability-design.md`.

# Le catalogue de pouvoirs (`permissions.py`, #115)

**La liste de référence des pouvoirs est ici, et nulle part ailleurs.**
Vingt-deux codes de forme `<domaine>:<geste>` — neuf de #115, trois de #197, un
de #170, cinq de #117, deux de #47, un de #169 et un de #275 —, dataclass gelée,
aucun état, aucun accès base ni réseau :
c'est ce qui autorise `core/` (Principe II), et un test le vérifie sur la
**source** du module.

Le geste nomme l'acte métier quand il en a un (`quality:override`,
`pending_providers:handle`) et retombe sur `read`/`write` sinon. La forme CRUD
n'est pas la norme : `courses:update` décrirait une écriture générique que
personne ne détient et que rien ne vérifie.

`P` est la façade d'appel — `require_permission(P.ROLES_READ)`. Passer par un
membre plutôt que par une chaîne n'est pas du confort :
`require_permission("pending_providres")` refuserait tout le monde, en silence.
`tests/test_permissions_catalogue.py` tient les deux bouts par AST — aucun
pouvoir du catalogue ne garde zéro ressource, aucune garde ne cite un code hors
catalogue. **Ajouter un pouvoir, c'est ajouter un membre à `P` et lui poser une
garde** ; il n'y a pas de migration, et le second test rougit tant que la garde
manque.

# La portée des compteurs (`counter_scope.py`, #95)

**Les prédicats gardent la règle, ce module porte les données.** `club.py` et
`discipline.py` décident toujours *comment* on compare — égalité stricte sur une
forme normalisée pour le club, exclusion pour les disciplines — mais *ce qu'on
compare à quoi* vit en base et s'édite depuis `/admin/portee-compteurs`.

Ce module est un **état de processus** dans `core/`, ce que la doctrine de
`permissions.py` juste au-dessus écarte. La différence est assumée et elle a une
cause précise : `ParticipationOut.is_tcn` est un champ **calculé de DTO**,
évalué sans Session et sans personne pour lui en passer une, et les scrapers
appellent `is_tcn` ligne par ligne à l'intérieur d'un import. Trois formes plus
pures ont été écartées, et il n'est pas utile de les reproposer :

- passer la configuration en **paramètre** aux quatre prédicats — 29 sites
  d'appel, et le champ calculé de DTO n'a personne pour la lui fournir ;
- placer le cache dans `services/` et le faire **lire** par `core/` — inversion
  frontale du sens du flux, que le Principe II interdit ;
- laisser `core/` ouvrir **sa propre Session** — une nouvelle occurrence de
  Session hors `repositories/`, également interdite par le Principe II.

Le registre est donc **poussé depuis le dessus** : `services/counter_scope.
load_from_db` lit la base et appelle `load()`. Toutes les flèches restent vers
le bas. Trois points de remplissage, et trois seulement — le `lifespan` de
`app/main.py`, `cli.load_counter_scope` à l'entrée de `python -m app.cli`, et
chaque écriture d'administration.

**`load()` réassigne, il ne mute jamais en place.** L'import d'épreuve tourne
dans un thread d'arrière-plan (le scrape SSE d'`import_service`) et lit le
registre pendant qu'un administrateur peut écrire : réassigner un nom est
atomique du point de vue de ce thread, muter en place lui exposerait un ensemble
à moitié écrit — quelques lignes mal classées, sans erreur ni trace.
`tests/test_core/test_counter_scope.py` le vérifie en gardant une référence
prise avant un `load()`.

**Les défauts sont les valeurs d'avant la bascule**, et ce n'est pas un repli de
confort : un registre vide rendrait zéro résultat du club, donc tous les
compteurs du club à zéro, sans erreur — un tableau de bord vide qui ressemble à
un tableau de bord. Un remplissage oublié dégrade vers le comportement d'hier.
Le prix est deux sources pour la même valeur, ici et l'amorçage de la migration
`35c74bb2c7b4` ; `tests/test_migrations.py` vérifie qu'elles ne divergent pas.
La suite de tests, qui monte son schéma par `create_all` et n'a donc pas les
lignes amorcées, s'exécute sur ces défauts.

**Ce qui est configurable est l'ensemble des libellés, jamais la
normalisation.** `_normalise_sql` est compilée dans l'index fonctionnel
`ix_participations_club_normalized` : la toucher sans migration de
reconstruction périme cet index en silence (cf. `club.py`). Ajouter un libellé
ne change pas l'expression indexée ; changer la façon de comparer, si.

Conception : `specs/20260826-154613-portee-compteurs-configurable/`.
