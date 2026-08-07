# Contrat du workflow d'exécution — `.github/workflows/batch.yml`

Le workflow est un composant de production, pas un script d'intégration
continue : il détient la base de production et exécute ce que l'interface lui
demande. Il se relit comme tel.

## Entrées (`workflow_dispatch`)

| Entrée | Type | Contrainte |
| --- | --- | --- |
| `target` | choix | `preview` ou `production` — **défaut `preview`** |
| `mode` | choix | `rescrape` ou `urls` |
| `provider` | texte | vide, ou un fournisseur du registre |
| `older_than` | texte | vide, ou un entier |
| `limit` | texte | vide, ou un entier |
| `urls` | texte | une URL par ligne (mode `urls` seulement) |
| `dry_run` | booléen | défaut `false` |
| `correlation_id` | texte | identifiant fourni par l'appelant, repris dans `run-name` |

Huit entrées, sous la limite de 25 propriétés de premier niveau. Les valeurs
arrivent déjà validées par l'API (D11) — la validation côté workflow serait un
second inventaire à tenir aligné, et le lancement manuel depuis l'onglet Actions
reste réservé à qui a déjà les droits d'écriture sur le dépôt.

**`target` n'est pas un choix offert dans l'écran.** L'API l'envoie depuis son
propre réglage `GITHUB_BATCH_TARGET` : l'administration de la preview écrit dans
la base de preview, celle de la production dans la sienne. Un champ dans le
formulaire permettrait à l'une d'écrire chez l'autre. Le choix n'existe que pour
un lancement manuel depuis l'onglet Actions, où il est explicite.

**Son défaut est `preview`, et son repli est `production`** — les deux ne se
contredisent pas, ils couvrent deux situations :

- un lancement **manuel** porte toujours une valeur : le défaut `preview` évite
  qu'une inattention écrive chez les adhérents ;
- une exécution **planifiée** ne porte aucune entrée. `inputs.target` y est vide,
  d'où le `|| 'production'` dans `environment` et `concurrency`. Sans lui, le
  cron nocturne hériterait de `preview` et ne rafraîchirait jamais la base
  réelle — une panne qu'on ne découvre qu'en cherchant pourquoi les résultats
  datent.

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
  group: batch-${{ inputs.target || 'production' }}
  cancel-in-progress: false
```

Le verrou réel de FR-004. La garde `409` côté API ne le remplace pas : elle donne
un message immédiat, lui empêche deux batches d'écrire en même temps — y compris
quand le second vient de l'onglet Actions ou de la planification.

Le groupe **porte la cible** : preview et production sont deux bases distinctes,
et faire attendre l'une pendant que l'autre travaille n'aurait aucun sens.

## Nom d'exécution

```yaml
run-name: "batch · ${{ inputs.mode }} · ${{ inputs.correlation_id }}"
```

C'est l'unique moyen de rattacher une exécution à la demande qui l'a créée : le
dispatch ne rend aucun identifiant.

## Sorties

| Sortie | Destination | Usage |
| --- | --- | --- |
| Rapport texte, **200 derniers Ko** | `$GITHUB_STEP_SUMMARY` | Lecture humaine sur la page de l'exécution |
| Rapport texte entier | artefact `rapport-<correlation_id>` | Diagnostic humain |
| Charge `--json` | artefact `bilan-<correlation_id>.json` | Lecture par l'API (`GET …/report`) |
| Progression et journaux | journal du job (stderr) | Diagnostic |
| Code de sortie | conclusion de l'exécution | Alerte : `1` ⇒ exécution rouge |

Le résumé est **borné** : au-delà de 1 Mo, la plateforme le refuse en entier —
il ne tronque pas, il perd tout. Le journal de scraping d'une seule épreuve
suffit à l'atteindre (run 31202351491, 1029 Ko). Le rapport entier reste donc
lisible dans son propre artefact. Il est **séparé** du bilan : le lecteur du
bilan tient de ce contrat que le zip ne porte qu'une entrée, et qu'elle est le
JSON.

La séparation stdout/stderr de la CLI est ce qui rend ces sorties
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
| `DATABASE_URL` | environment `batch-preview` | Base de preview |
| `DATABASE_URL` | environment `batch-production` | Base de production |

Dans les deux cas, la valeur **doit viser le pooler Supabase**, joignable en IPv4
(D12). C'est l'environment, et lui seul, qui décide de la base écrite : rien dans
le script ne la nomme.

Environments **dédiés** plutôt que `Preview` / `Production` — deux raisons
constatées sur le dépôt : ces derniers ne portent aucune `DATABASE_URL` (l'URL
vit côté Render), et `Production` porte une *required reviewer* active qui
laisserait chaque lancement demandé depuis l'interface en attente d'approbation
humaine. Le contrôle d'accès est ici le pouvoir `batch:run`.

## Étapes

1. `actions/checkout@v4` sur `main`
2. `astral-sh/setup-uv` + `uv sync --locked` (mêmes versions que `ci.yml`)
3. exécution de la CLI selon `mode`, sorties comme ci-dessus
4. `actions/upload-artifact` pour le bilan

Aucune étape ne construit ni ne déploie quoi que ce soit : ce workflow lit et
écrit des données, il ne livre pas de code.
