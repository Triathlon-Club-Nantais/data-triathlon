# Validation — pagination et recherche du classement

Scénarios exécutables prouvant la feature de bout en bout. Détail des formes de
réponse : `contracts/courses-api.md`. Détail des champs : `data-model.md`.

## Prérequis

```bash
cd backend && uv sync
uv run alembic upgrade head          # applique la migration unaccent
uv run python scripts/reset_db.py    # base SQLite de dev, vide + migrée + seed
```

Deux serveurs, dans deux terminaux (le port est publié dans
`.dev-backend.json`, cf. `AGENTS.md` §Dev multi-worktree) :

```bash
cd backend  && uv run python scripts/dev_server.py
cd frontend && npm run dev
```

Il faut au moins une épreuve conséquente en base. À défaut du seed :

```bash
cd backend && uv run python -m app.cli rescrape-db --url <url-d-une-grosse-epreuve>
```

## 1. La suite de tests

```bash
cd backend  && uv run pytest -m "not integration" && uv run ruff check .
cd frontend && npm test && npm run lint && npm run build
```

Attendu : tout au vert. C'est SC-006.

## 2. La tranche par défaut (FR-001, FR-005)

```bash
PORT=$(python3 -c "import json;print(json.load(open('../.dev-backend.json'))['port'])")
curl -s "http://127.0.0.1:$PORT/api/v1/courses/1" | jq '{n: (.participations|length), total, page, page_size}'
```

Attendu : `n` vaut 20 (ou le nombre de participations si l'épreuve en a moins),
`total` le nombre réel, `page` 1, `page_size` 20.

## 3. L'échappatoire `all` (FR-006, SC-007)

```bash
curl -s "http://127.0.0.1:$PORT/api/v1/courses/1?page_size=all" \
  | jq '{n: (.participations|length), total, page_size}'
```

Attendu : `n == total`, `page_size` à `null`.

## 4. L'ordre est le même, page après page (FR-008 à FR-011, SC-003)

Le test qui compte : concaténer toutes les tranches doit redonner, ligne pour
ligne, ce que rend `all`.

```bash
TOTAL=$(curl -s "http://127.0.0.1:$PORT/api/v1/courses/1" | jq .total)
curl -s "http://127.0.0.1:$PORT/api/v1/courses/1?page_size=all" | jq -c '[.participations[].id]' > /tmp/tout.json
for p in $(seq 1 $(( (TOTAL + 19) / 20 ))); do
  curl -s "http://127.0.0.1:$PORT/api/v1/courses/1?page=$p" | jq -c '.participations[].id'
done | jq -s -c . > /tmp/pages.json
diff /tmp/tout.json /tmp/pages.json && echo "ORDRE IDENTIQUE"
```

Attendu : `ORDRE IDENTIQUE`. Aucun doublon, aucun trou.

## 5. Les bornes (FR-004, FR-007)

```bash
curl -s "http://127.0.0.1:$PORT/api/v1/courses/1?page=99999" | jq '{n:(.participations|length), total}'
curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:$PORT/api/v1/courses/1?page_size=0"
curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:$PORT/api/v1/courses/1?page_size=tout"
curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:$PORT/api/v1/courses/1?page_size=9999"
```

Attendu : `n` à 0 avec `total` exact ; puis `422`, `422`, `422`.

## 6. La recherche, accents compris (FR-012 à FR-016)

Prendre un athlète de l'épreuve dont le nom porte un accent, puis :

```bash
curl -s "http://127.0.0.1:$PORT/api/v1/courses/1?q=lemee" | jq '.total, [.participations[].athlete.nom]'
curl -s "http://127.0.0.1:$PORT/api/v1/courses/1?q=LEMÉE" | jq '.total'
curl -s "http://127.0.0.1:$PORT/api/v1/courses/1?q=%20%20" | jq '.total'
```

Attendu : les deux premières commandes rendent le **même** `total`, non nul.
La troisième (deux espaces) rend le total de l'épreuve entière — une recherche
blanche n'est pas une recherche.

## 7. La synthèse ne bouge pas (FR-018, SC-002)

```bash
curl -s "http://127.0.0.1:$PORT/api/v1/courses/1/summary" | jq > /tmp/s1.json
curl -s "http://127.0.0.1:$PORT/api/v1/courses/1/summary" | jq > /tmp/s2.json
diff /tmp/s1.json /tmp/s2.json && echo "STABLE"
jq '.total == (.finishers + .non_finishers + .unknown)' /tmp/s1.json
```

Attendu : `STABLE`, puis `true` — l'invariant de ventilation.

Vérifier ensuite **à l'œil**, sur `/courses/1` dans le navigateur, que les six
blocs affichent les mêmes valeurs qu'avant la branche. Comparer avec la
production (`https://data-triathlon-gamma.vercel.app/courses/25`) est le
contrôle le plus direct de SC-002.

## 8. L'écran (FR-023 à FR-030)

Sur `http://127.0.0.1:3000/courses/1` :

1. le tableau montre 20 lignes ; les contrôles de pagination sont en pied ;
2. cliquer « Suivant » : l'adresse porte `?page=2`, le bouton « retour » du
   navigateur ramène à la page 1 ;
3. ouvrir un lien de pagination en nouvel onglet (clic milieu) : il fonctionne ;
4. saisir un nom, valider par `Entrée` : l'adresse porte `?q=…`, la page est
   revenue à 1, les six blocs du haut n'ont pas bougé ;
5. basculer « Triathlon Club Nantais » : l'adresse porte `?scope=club`, la page
   est revenue à 1 ;
6. les colonnes de temps intermédiaires sont **les mêmes** en page 1 et en
   page 5 ;
7. ouvrir une épreuve de moins de 20 participations : aucun contrôle de
   pagination.

## 9. La charge transportée (SC-001)

Onglet Réseau du navigateur, rechargement de `/courses/25` : le document rendu
par le serveur ne doit plus contenir les 2500 participations. Comparer sa taille
à celle d'avant la branche.

## 10. PostgreSQL — vérification manuelle obligatoire

Les tests tournent sur SQLite ; le chemin `unaccent` de production n'est couvert
par aucun d'eux (cf. `research.md`, R2). **Avant de clore la branche**, sur la
base Supabase :

```sql
SELECT extname, nspname FROM pg_extension e
  JOIN pg_namespace n ON n.oid = e.extnamespace WHERE extname = 'unaccent';
SELECT unaccent('LEMÉE');   -- doit rendre 'LEMEE'
```

Si l'extension est installée dans le schéma `extensions` (convention Supabase),
vérifier qu'il figure bien dans le `search_path` du rôle applicatif. Sans cela,
la recherche rendra une erreur en production alors qu'elle passe en
développement.
