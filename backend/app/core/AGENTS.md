# Observabilité SQL

Deux étages **indépendants**, tous deux éteints ou presque par défaut (#89).

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

`core/tracing.py` — socle OpenTelemetry, `OTEL_ENABLED` à `false` par défaut,
imports paresseux : éteint, aucun paquet OTel n'est chargé. Aucun collecteur
n'est hébergé ; le socle est là pour que le branchement tienne en deux variables
(`OTEL_TRACES_EXPORTER=otlp`, `OTEL_EXPORTER_OTLP_ENDPOINT=…`). **Mais ces deux
variables suffisent aussi à fuiter des données personnelles** : `FastAPIInstrumentor`
pose `http.url` (query string comprise, non masquée) et `net.peer.ip` sur chaque
span HTTP — `name=LEMÉE+Jean` d'une recherche `/api/v1/athletes` part donc en clair
vers le collecteur. Les spans SQL restent paramétrés. Ne pas allumer `OTEL_ENABLED`
avant d'avoir un collecteur maîtrisé ou d'avoir posé un `server_request_hook` qui
réécrit `http.url` sans la query. `OTEL_SERVICE_NAME`
et l'endpoint sont lus par le SDK, mais **`OTEL_TRACES_EXPORTER` est lu par notre
code** — elle n'est interprétée que par le lanceur `opentelemetry-instrument`,
qu'on n'utilise pas. L'exporter `console` écrit sur **stderr** : sur stdout il
casserait `… --json | jq`. La CLI doit appeler `shutdown_cli_tracing()` en fin de
process, faute de quoi le `BatchSpanProcessor` perd les spans du dernier import.
`shutdown_tracing()` ne fait d'ailleurs pas que vider ces spans : elle
**désinstrumente** aussi. Les instrumenteurs OTel sont des singletons par classe
(`BaseInstrumentor`) — sans cet appel symétrique, un second `setup_tracing()` dans
le même process est un no-op **silencieux** (un simple avertissement journalisé,
zéro span produit).

**EXPLAIN et audit d'index restent à faire** : c'est l'analyse à mener *avec* cet
outil, dont le livrable sera un sondage sous `docs/superpowers/specs/`.
Design : `docs/superpowers/specs/2026-07-31-sql-observability-design.md`.

