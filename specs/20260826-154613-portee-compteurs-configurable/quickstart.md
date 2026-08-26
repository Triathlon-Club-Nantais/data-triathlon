# Quickstart — vérifier la portée des compteurs configurable

Feature : [spec.md](./spec.md) · Contrat : [contracts/admin-counter-scope.md](./contracts/admin-counter-scope.md)

Comment prouver que la feature marche, du plus rapide au plus complet. Tout se lance depuis le worktree ; aucun accès réseau n'est requis.

## Prérequis

```bash
cd backend && uv sync
uv run alembic upgrade head        # pose counter_scope_entries et l'amorce
```

Le front a besoin d'un backend qui tourne :

```bash
# terminal 1
cd backend && uv run python scripts/dev_server.py
# terminal 2
cd frontend && npm run dev
```

## 1. La non-régression, d'abord (SC-003)

C'est la vérification qui compte le plus, et elle se fait **sans rien configurer** : avant toute modification, l'application doit rendre exactement ce qu'elle rendait.

```bash
cd backend && uv run pytest -m "not integration"
```

Attendu : vert, **sans qu'une seule assertion de la suite existante ait été modifiée**. Les tests créent leur schéma par `Base.metadata.create_all` (`tests/conftest.py`), donc sans les lignes d'amorçage : ils s'exécutent sur les défauts du registre, qui sont les valeurs d'aujourd'hui. Si un test existant a dû changer, c'est que le comportement a bougé — et il ne devait pas.

Avec RTK : `rtk uv run pytest -m "not integration"`.

## 2. L'amorçage correspond aux défauts du code

```bash
cd backend && uv run pytest tests/test_migrations.py -k counter_scope -n 0
```

Applique les migrations sur une base vierge et compare les douze lignes obtenues aux défauts de `core/counter_scope.py`. C'est le garde-fou contre la divergence entre les littéraux de la migration et ceux du code (research.md §3).

## 3. Le contrat Python ↔ SQL, sur une configuration modifiée (FR-005, SC-005)

```bash
cd backend && uv run pytest tests/test_repositories/test_club_filter.py -n 0
```

Le test existant éprouvait l'accord entre `is_tcn` et `tcn_clause` sur le corpus de production (`tests/club_corpus.py`). Il l'éprouve désormais aussi après un `counter_scope.load(...)` qui ajoute et retire un libellé : c'est la garantie que le registre alimente bien les deux implémentations, et non une seule.

## 4. Le geste complet, en API

Il faut une session avec le pouvoir `counter_scope:manage` :

```bash
cd backend && uv run python -m app.cli grant-role <votre-email> <role-portant-le-pouvoir>
```

Puis, connecté. `scripts/dev_server.py` prend un port éphémère et le publie (`docs/dev-multi-worktree.md`) — remplacer `8001` ci-dessous par celui qu'il annonce :

```bash
# état courant
curl -s localhost:8001/api/v1/admin/counter-scope | jq

# ajouter une orthographe de club (US1)
curl -s -X POST localhost:8001/api/v1/admin/counter-scope/club-labels \
  -H 'content-type: application/json' \
  -d '{"value":"TRIATHLON  CLUB NANTAIS 44"}' | jq
# attendu : 201, value == "triathlon club nantais 44" (normalisée)

# le doublon est refusé (FR-009)
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  localhost:8001/api/v1/admin/counter-scope/club-labels \
  -H 'content-type: application/json' -d '{"value":"tcn"}'
# attendu : 409

# vider la liste des libellés est refusé (FR-010)
# retirer les entrées une à une jusqu'à la dernière → attendu : 409 sur la dernière
```

## 5. L'effet sur les compteurs, sans redémarrage (FR-008, SC-002)

Le point le plus facile à croire acquis à tort. Avec le backend **toujours en cours d'exécution** :

1. Repérer une épreuve dont un résultat porte un libellé de club non reconnu — `uv run python -m app.cli club-labels` liste les libellés observés et leur verdict.
2. Ajouter ce libellé par l'API (§4).
3. Sans rien redémarrer, recharger `GET /api/v1/participations?course_id=<id>` : la ligne porte maintenant `"is_tcn": true`.
4. Recharger `GET /api/v1/stats/...` avec `scope=club` : le compteur a augmenté d'autant.

Si le badge bouge mais pas le compteur (ou l'inverse), le registre n'alimente qu'un seul des deux prédicats — c'est exactement ce que le §3 est censé attraper.

Même vérification pour les disciplines (US2) : exclure `swimrun`, puis constater qu'un résultat de swimrun sort des compteurs avec `federal_only=true` et y reste avec le défaut neutre.

## 6. L'écran (US1, US3)

`http://localhost:3000/admin/portee-compteurs`, connecté avec le pouvoir.

À vérifier à l'œil :

- Les deux listes s'affichent, chacune avec sa phrase d'explication (FR-015) : exclusion pour les disciplines, libellés reconnus pour le club.
- Chaque entrée porte son auteur et sa date ; les entrées d'amorçage affichent « Configuration initiale » (FR-016).
- Une discipline hors nomenclature porte un badge d'avertissement (FR-011).
- Le retrait demande confirmation et rappelle l'effet sur les compteurs (FR-017).
- Sans le pouvoir : l'entrée de navigation ne s'affiche pas, et l'accès direct à l'URL est refusé (FR-012).

```bash
cd frontend && npm test && npm run lint && npm run build
```

## 7. La trace (FR-013)

`http://localhost:3000/admin/journal` — les gestes des §4 et §6 y figurent, en `counter_scope.entry_add` et `counter_scope.entry_remove`, avec leur auteur.

## 8. Le coût de lecture (FR-006, SC-004)

Le registre est lu en mémoire : la feature ne doit ajouter **aucune** requête base. La grandeur à comparer est le **nombre de requêtes**, pas le chrono — c'est la seule reproductible, et c'est elle qui régresserait si un chemin se remettait à lire la base par participation.

```bash
cd backend && SQL_QUERY_STATS=true uv run python scripts/dev_server.py
```

Charger le classement d'une épreuve de plusieurs milliers de résultats, relever le bilan agrégé sorti par le logger `app.sql` (`core/sql_observability.py`, #89), et comparer au même relevé fait sur `main` avant la bascule.

Attendu : comptes identiques. Les deux chiffres se consignent dans la description de la PR.

## Ce que ce quickstart ne couvre pas

- **La propagation entre processus** : hors périmètre, l'API tourne en un seul processus (research.md §5).
