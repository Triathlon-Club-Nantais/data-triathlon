# Azure Functions

Une seule Function App aujourd'hui, `coldstart/`, qui porte trois fonctions :
le keep-warm (`Coldstart-curl`) et la veille Render (`Render-sleep`,
`Render-wake`). Son code vivait dans le dépôt séparé
`Triathlon-Club-Nantais/ColdStart-function-curl` (dernier commit `861e116`),
rapatrié ici par #1014 : ce dossier fait désormais foi.

## `coldstart/` : le keep-warm

**Rôle.** Garder le front Vercel et le backend Render éveillés aux heures
d'usage. La Function appelle `/api/cron/keep-warm` sur les deux fronts
(production et preview) ; la route (`frontend/app/api/cron/keep-warm/route.ts`)
ping à son tour `/api/v1/health` du backend. Elle est le seul appelant de cette
route.

**Planning.** `Coldstart-curl/function.json`, timer `0 */10 7-23 * * *` : toutes
les 10 minutes, de 7 h à 23 h **UTC** : une expression CRON de Function s'évalue
en UTC tant que l'App Setting `WEBSITE_TIME_ZONE` n'est pas posée.

**URLs appelées** (`Coldstart-curl/run.ps1`) :

- `https://data.triathlon-club-nantais.com/api/cron/keep-warm` (production) ;
- `https://data-triathlon-tcn-preview.vercel.app/api/cron/keep-warm` (preview).

Requêtes `HEAD`, que Next.js sert par le `GET` de la route. Chaque appel porte
`Authorization: Bearer $env:CRON_SECRET` : sans lui, la route répond 401, et
503 si le secret manque côté Vercel (#1021).

**Articulation avec la veille Render.** Le keep-warm ne réveille qu'un service
**non suspendu** : il évite le sommeil d'inactivité du plan gratuit, pas la
suspension volontaire. Celle-ci est l'affaire des deux fonctions ci-dessous.

## `Render-sleep` et `Render-wake` : la veille de la production (#1010)

Le `schedule` de GitHub Actions démarrait le lever de la production avec 2 à
5 h de retard (#842, #885). Deux timers Azure, qui partent à l'heure,
déclenchent donc `render-sleep.yml` par `workflow_dispatch` (API GitHub,
`POST …/actions/workflows/render-sleep.yml/dispatches`, `ref: main`) :

| Fonction | Timer (UTC) | Entrées du dispatch |
|---|---|---|
| `Render-sleep` | `0 15 23 * * *` | `action: suspend`, `target: production` |
| `Render-wake` | `0 15 2 * * *` | `action: resume`, `target: production` |

La logique reste **dans le workflow** (résolution du service par son nom,
abstention pendant un déploiement, 400 « déjà éveillé ») : le module
`Modules/RenderSleep/RenderSleep.psm1`, chargé d'office par le runtime
PowerShell, ne fait que la demander. `RENDER_API_KEY` ne quitte donc pas GitHub.
La preview garde son coucher horaire par le `schedule` d'Actions, où une heure
de retard ne coûte qu'une heure d'instance.

**Les crons de `render-sleep.yml` restent en secours** (décision du 26/09) tant
que ces fonctions ne sont pas validées en production. Ils passent plus tard, et
ne font alors plus rien. Leur retrait fera l'objet d'une issue de suivi.

**FinOps.** Deux exécutions par jour de plus, dans l'octroi gratuit du plan
Flex Consumption.

**FinOps.** Plan **Flex Consumption** (Linux, France Central, Function App
`coldstart-curl`) : environ 100 exécutions par jour, très en dessous de l'octroi
gratuit mensuel. La facture doit rester proche de
zéro (`docs/infra-azure.md`) ; un plan Premium ou un Always On n'est pas une
option.

### App Settings attendues

| Nom | Rôle |
|---|---|
| `CRON_SECRET` | Même valeur que la variable `CRON_SECRET` des deux projets Vercel (`docs/ci-cd.md`). |
| `GITHUB_DISPATCH_TOKEN` | Jeton *fine-grained* limité au dépôt `data-triathlon`, permission **Actions : read and write** et rien d'autre. Distinct de `GITHUB_BATCH_TOKEN` (Render), pour révoquer l'un sans couper l'autre. Échéance à suivre : un jeton expiré fait échouer `Render-wake`, et seul le cron de secours rallume alors la production. |
| `AzureWebJobsStorage` | Compte de stockage de la Function (posé à la création). |
| `DEPLOYMENT_STORAGE_CONNECTION_STRING` | Conteneur où Flex Consumption dépose le paquet déployé (posé à la création). |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Journaux et *Invocations* (posé à la création). |

En Flex Consumption, le runtime (PowerShell) se règle dans la configuration de
la Function App, pas par `FUNCTIONS_WORKER_RUNTIME`.

Aucune valeur secrète dans ce dépôt : `local.settings.json` est ignoré
(`.gitignore` du dossier).

### Déployer

Procédure réelle à ce jour, manuelle :

1. Ouvrir **ce dossier** (`infra/azure-functions/coldstart/`) dans VS Code, avec
   l'extension *Azure Functions* ; `.vscode/settings.json` fixe
   `deploySubpath: "."`, le runtime `~4` et le langage PowerShell.
2. Panneau *Azure* → la Function App du club → clic droit → *Deploy to Function
   App…*. Le déploiement remplace tout le code de la Function.
3. Contrôler *Monitor → Invocations* au passage suivant, et les logs Vercel de
   `/api/cron/keep-warm` (200 attendus). Pour la veille : un run
   `workflow_dispatch` de `render-sleep.yml` doit apparaître à 23 h 15 et à
   2 h 15 UTC, à la minute.

Changer une App Setting (portail : *Settings → Environment variables*) redémarre
la Function ; aucun redéploiement du code n'est nécessaire.

Un déploiement automatisé par GitHub Actions supposerait une identité Azure
dédiée (cf. #658) : hors de #1014.

### Tester en local

Avec Azure Functions Core Tools v4 et PowerShell 7 :

```bash
cd infra/azure-functions/coldstart
# local.settings.json (ignoré) : {"IsEncrypted": false, "Values": {
#   "FUNCTIONS_WORKER_RUNTIME": "powershell",
#   "AzureWebJobsStorage": "UseDevelopmentStorage=true",
#   "CRON_SECRET": "<secret de test>" }}
azurite --silent &          # émulateur de stockage exigé par le timer
func start
```

Le timer ne se déclenche qu'à l'heure prévue : pour un passage immédiat,
`curl -X POST http://localhost:7071/admin/functions/Coldstart-curl -H "Content-Type: application/json" -d '{}'`.
Attention, le script appelle les URLs **réelles** de production et de preview.
