# Azure Functions

Une seule Function App aujourd'hui, `coldstart/`, qui porte quatre fonctions :
le keep-warm (`Coldstart-curl`) et la veille Render (`Render-sleep`,
`Render-wake`, `Render-sleep-preview`). Son code vivait dans le dépôt séparé
`Triathlon-Club-Nantais/ColdStart-function-curl` (dernier commit `861e116`),
rapatrié ici par #1014 : ce dossier fait désormais foi.

## `coldstart/` : le keep-warm

**Rôle.** Garder le front Vercel et le backend Render de production éveillés aux
heures d'usage. La Function appelle `/api/cron/keep-warm` sur le front de
production ; la route (`frontend/app/api/cron/keep-warm/route.ts`) ping à son
tour `/api/v1/health` du backend. Elle est le seul appelant de cette route.

**Planning.** `Coldstart-curl/function.json`, timer `0 */10 7-22 * * *` : toutes
les 10 minutes, de 7 h à 22 h 50 **UTC**, avant le coucher de 23 h 15 (une
heure 23 ne produisait que des 502). Une expression CRON de Function s'évalue
en UTC tant que l'App Setting `WEBSITE_TIME_ZONE` n'est pas posée.

**URL appelée** (`Coldstart-curl/run.ps1`) :
`https://data.triathlon-club-nantais.com/api/cron/keep-warm`. La preview ne
l'est plus (#1333) : suspendue chaque heure, un ping ne la réveille pas, et
98 % de ses appels échouaient (audit #1315).

Requête `HEAD`, que Next.js sert par le `GET` de la route, avec
`Authorization: Bearer $env:CRON_SECRET` : sans lui, la route répond 401, et
503 si le secret manque côté Vercel (#1021). `-TimeoutSec 15` borne toute la
requête au-dessus des 10 s que la route accorde au backend ; un échec fait
échouer l'invocation (#1333).

**Articulation avec la veille Render.** Le keep-warm ne réveille qu'un service
**non suspendu** : il évite le sommeil d'inactivité du plan gratuit, pas la
suspension volontaire. Celle-ci est l'affaire des trois fonctions ci-dessous.

**FinOps.** Plan **Flex Consumption** (Linux, France Central, Function App
`coldstart-curl`) : 96 exécutions par jour, très en dessous de l'octroi
gratuit mensuel. La facture doit rester proche de
zéro (`docs/infra-azure.md`) ; un plan Premium ou un Always On n'est pas une
option.

## `Render-sleep`, `Render-wake` et `Render-sleep-preview` : la veille Render (#1010, #1319)

Le `schedule` de GitHub Actions démarrait le lever de la production avec 2 à
5 h de retard (#842, #885). Deux timers Azure, qui partent à l'heure,
déclenchent donc `render-sleep.yml` par `workflow_dispatch` (API GitHub,
`POST …/actions/workflows/render-sleep.yml/dispatches`, `ref: main`) :

| Fonction | Timer (UTC) | Entrées du dispatch |
|---|---|---|
| `Render-sleep` | `0 15 23 * * *` | `action: suspend`, `target: production`, `alert: true` |
| `Render-wake` | `0 15 2 * * *` | `action: resume`, `target: production`, `alert: true` |
| `Render-sleep-preview` | `0 45 * * * *` | `action: suspend`, `target: preview`, `alert: true` |

`alert` fait ouvrir l'issue `ops` sur un échec (`notify-failure.yml`, #922) :
personne ne suit ces runs, contrairement à un lancement manuel.

Les deux fonctions pilotent aussi le **moniteur UptimeRobot du backend** (#922),
dont la fenêtre de maintenance est payante : `Render-sleep` le met en pause
avant de coucher la production, `Render-wake` le réactive dès que
`/api/v1/health` répond, ou au bout de 10 min (un lever raté doit alors alerter).
Un dispatch en échec (jeton expiré) réactive aussi le moniteur, dans les deux
fonctions, poste une alerte Slack d'ops et fait échouer l'invocation. Avant #1320, l'erreur HTTP n'arrêtait
que l'appel : l'invocation finissait en *Succeeded* après avoir journalisé
« déclenché », et la panne du jeton est passée inaperçue trois nuits.
`host.json` porte donc un `functionTimeout` de 15 min. Sans les App Settings
UptimeRobot, ce pilotage est simplement sauté.

La logique reste **dans le workflow** (résolution du service par son nom,
abstention pendant un déploiement, 400 « déjà éveillé ») : le module
`Modules/RenderSleep/RenderSleep.psm1`, chargé d'office par le runtime
PowerShell, ne fait que la demander. `RENDER_API_KEY` ne quitte donc pas GitHub.
La preview est couchée chaque heure par `Render-sleep-preview` (#1319) : le cron
horaire d'Actions sautait des heures entières (environ 7 passages sur 24 le
10/10), laissant la preview éveillée 4 à 5 h après un déploiement. Ses gardes
(déploiement en vol, délai de grâce) restent dans le workflow. Pas d'alerte
Slack côté Azure pour elle : un jeton en panne alerte déjà par la veille de la
production, et un échec du workflow passe par `notify-failure.yml`, limité à un
message par 12 h.

**Ces fonctions sont le seul déclencheur planifié de `render-sleep.yml`** :
ses crons d'Actions, gardés en secours depuis le 26/09, ont été retirés par
#1157 après onze nuits consécutives sans échec (13/10 au 24/10/2026). Un lever
manqué n'a plus de cron derrière lui : il se rattrape par le `resume` de
`deploy.yml` ou un `workflow_dispatch` manuel, et l'échec du dispatch alerte
le canal Slack d'ops (#1320).

**FinOps.** 26 exécutions par jour de plus (24 pour la preview, quelques
secondes chacune), dans l'octroi gratuit du plan Flex Consumption. Côté GitHub,
autant de runs courts, gratuits sur un dépôt public.

### App Settings attendues

| Nom | Rôle |
|---|---|
| `CRON_SECRET` | Même valeur que la variable `CRON_SECRET` du projet Vercel de production (`docs/ci-cd.md`). |
| `GITHUB_DISPATCH_TOKEN` | Jeton *fine-grained* limité au dépôt `data-triathlon`, permission **Actions : read and write** et rien d'autre. Distinct de `GITHUB_BATCH_TOKEN` (Render), pour révoquer l'un sans couper l'autre. Échéance à suivre : un jeton expiré fait échouer `Render-wake`, et la production reste éteinte jusqu'à un déploiement ou un `workflow_dispatch` manuel. |
| `SLACK_OPS_WEBHOOK_URL` | Même valeur que le secret de dépôt `SLACK_OPS_WEBHOOK_URL` (`notify-failure.yml`). Poste dans le canal d'ops quand `Render-sleep` ou `Render-wake` ne parvient pas à déclencher le workflow (#1320). Absente : pas d'alerte, seulement un warning. |
| `UPTIMEROBOT_API_KEY` | Clé d'API principale du compte UptimeRobot (`it.triathlonclubnantais@gmail.com`), pour la pause du moniteur backend. |
| `UPTIMEROBOT_BACKEND_MONITOR_ID` | Identifiant du moniteur « Backend production (Render) » : `804143914`. |
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
   2 h 15 UTC, à la minute, et un `suspend · preview` à chaque minute 45.

Sans VS Code, la CLI fait le même déploiement (utilisé le 11/10/2026) : zipper le
contenu de ce dossier **à la racine de l'archive** (`host.json` en tête), sans ce
qu'exclut `.funcignore`, puis
`az functionapp deployment source config-zip -g TCN_data_Front -n coldstart-curl --src coldstart.zip`.
`az functionapp function list -g TCN_data_Front -n coldstart-curl` confirme les
fonctions chargées et leurs plannings.

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
Attention, le script appelle l'URL **réelle** de production.
