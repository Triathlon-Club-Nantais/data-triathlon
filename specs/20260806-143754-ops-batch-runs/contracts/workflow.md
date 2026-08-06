# Contrat du workflow d'exécution — `.github/workflows/batch.yml`

Le workflow est un composant de production, pas un script d'intégration
continue : il détient la base de production et exécute ce que l'interface lui
demande. Il se relit comme tel.

## Entrées (`workflow_dispatch`)

| Entrée | Type | Contrainte |
| --- | --- | --- |
| `mode` | choix | `rescrape` ou `urls` |
| `provider` | texte | vide, ou un fournisseur du registre |
| `older_than` | texte | vide, ou un entier |
| `limit` | texte | vide, ou un entier |
| `urls` | texte | une URL par ligne (mode `urls` seulement) |
| `dry_run` | booléen | défaut `false` |
| `correlation_id` | texte | identifiant fourni par l'appelant, repris dans `run-name` |

Sept entrées, sous la limite de 25 propriétés de premier niveau. Les valeurs
arrivent déjà validées par l'API (D11) — la validation côté workflow serait un
second inventaire à tenir aligné, et le lancement manuel depuis l'onglet Actions
reste réservé à qui a déjà les droits d'écriture sur le dépôt.

## Règle non négociable — aucune interpolation dans un `run:`

```yaml
# Interdit — la valeur est substituée avant le shell (D3) :
run: uv run python -m app.cli rescrape-db --provider ${{ inputs.provider }}

# Exigé — la valeur transite par l'environnement, et le shell la cite :
env:
  PROVIDER: ${{ inputs.provider }}
run: uv run python -m app.cli rescrape-db ${PROVIDER:+--provider "$PROVIDER"}
```

Toute tâche qui ajoute une entrée respecte cette forme. C'est un critère de
relecture de PR, au même titre que « pas de secret en clair ».

## Concurrence

```yaml
concurrency:
  group: batch
  cancel-in-progress: false
```

Le verrou réel de FR-004. La garde `409` côté API ne le remplace pas : elle donne
un message immédiat, lui empêche deux batches d'écrire en même temps — y compris
quand le second vient de l'onglet Actions ou de la planification.

## Nom d'exécution

```yaml
run-name: "batch · ${{ inputs.mode }} · ${{ inputs.correlation_id }}"
```

C'est l'unique moyen de rattacher une exécution à la demande qui l'a créée : le
dispatch ne rend aucun identifiant.

## Sorties

| Sortie | Destination | Usage |
| --- | --- | --- |
| Rapport texte | `$GITHUB_STEP_SUMMARY` | Lecture humaine sur la page de l'exécution |
| Charge `--json` | artefact `bilan-<correlation_id>.json` | Lecture par l'API (`GET …/report`) |
| Progression et journaux | journal du job (stderr) | Diagnostic |
| Code de sortie | conclusion de l'exécution | Alerte : `1` ⇒ exécution rouge |

La séparation stdout/stderr de la CLI est ce qui rend ces quatre sorties
possibles sans post-traitement : `--json` laisse **uniquement** la ligne JSON sur
stdout, que le workflow redirige vers le fichier d'artefact, pendant que le
rapport texte et la progression partent sur stderr (Principe IV,
`cli/AGENTS.md`). Ne pas « améliorer » cette redirection en capturant les deux
flux ensemble : l'artefact cesserait d'être du JSON valide.

## Planification

```yaml
schedule:
  - cron: "0 3 * * 1"   # cadence à confirmer après mesure (D13)
```

Deux points à ne pas perdre de vue : GitHub **désactive** les workflows planifiés
d'un dépôt inactif depuis 60 jours, et une occurrence planifiée est soumise au
même verrou de concurrence qu'un lancement manuel — elle sera donc ignorée si un
batch tourne, ce qui est le comportement voulu.

## Environnement et secrets

| Nom | Portée | Rôle |
| --- | --- | --- |
| `DATABASE_URL` | environment `batch-production` | Base de production. **Doit viser le pooler Supabase**, joignable en IPv4 (D12). |

L'environnement est dédié plutôt que `production` : ce dernier peut porter une
*required reviewer*, qui laisserait chaque lancement demandé depuis l'interface
en attente d'approbation. Le contrôle d'accès est ici le pouvoir `batch:run`.

## Étapes

1. `actions/checkout@v4` sur `main`
2. `astral-sh/setup-uv` + `uv sync --locked` (mêmes versions que `ci.yml`)
3. exécution de la CLI selon `mode`, sorties comme ci-dessus
4. `actions/upload-artifact` pour le bilan

Aucune étape ne construit ni ne déploie quoi que ce soit : ce workflow lit et
écrit des données, il ne livre pas de code.
