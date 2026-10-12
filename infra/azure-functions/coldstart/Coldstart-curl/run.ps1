param($Timer)

if ($Timer.IsPastDue) {
    Write-Host "PowerShell timer is running late!"
}

# Une erreur HTTP n'arrêtait que l'appel : l'invocation restait verte même en échec
# (audit #1315). `Stop` la rend visible dans *Monitor → Invocations* (#1333).
$ErrorActionPreference = 'Stop'

# La route keep-warm exige `Authorization: Bearer <CRON_SECRET>` (#1021) : même
# valeur que la variable CRON_SECRET du projet Vercel de production.
# `-TimeoutSec 15` borne toute la requête : la route attend jusqu'à 10 s la réponse
# de /api/v1/health. L'ancien `-ConnectionTimeoutSeconds 1` coupait 43 % des appels.
# La preview n'est plus appelée : suspendue chaque heure, un ping ne la réveille pas.
$headers = @{ Authorization = "Bearer $env:CRON_SECRET" }
Invoke-RestMethod -Method Head -TimeoutSec 15 -Headers $headers -Uri "https://data.triathlon-club-nantais.com/api/cron/keep-warm"
