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
Dix-neuf codes de forme `<domaine>:<geste>` — neuf de #115, trois de #197, un de
#170, cinq de #117 et un de #169 —, dataclass gelée, aucun état, aucun accès base
ni réseau :
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
