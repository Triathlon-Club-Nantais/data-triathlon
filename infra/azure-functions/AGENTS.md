# Azure Functions

Une seule Function aujourd'hui, `coldstart/`. Son code vivait dans le dépôt
séparé `Triathlon-Club-Nantais/ColdStart-function-curl` (dernier commit
`861e116`), rapatrié ici par #1014 : ce dossier fait désormais foi.

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

**Articulation avec la veille Render.** `render-sleep.yml` suspend et reprend les
services Render par le `schedule` de GitHub Actions, peu fiable (#885). Le
keep-warm ne réveille qu'un service **non suspendu** : il évite le sommeil
d'inactivité du plan gratuit, pas la suspension volontaire. Déplacer la veille
et le réveil sur l'ordonnanceur Azure est #1010, à écrire **dans ce dossier**.

**FinOps.** Plan Consumption : environ 100 exécutions par jour, très en dessous
du million d'exécutions gratuites par mois. La facture doit rester proche de
zéro (`docs/infra-azure.md`) ; un plan Premium ou un Always On n'est pas une
option.

### App Settings attendues

| Nom | Rôle |
|---|---|
| `CRON_SECRET` | Même valeur que la variable `CRON_SECRET` des deux projets Vercel (`docs/ci-cd.md`). |
| `FUNCTIONS_WORKER_RUNTIME` | `powershell` (posé à la création). |
| `AzureWebJobsStorage` | Compte de stockage de la Function (posé à la création). |

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
   `/api/cron/keep-warm` (200 attendus).

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
