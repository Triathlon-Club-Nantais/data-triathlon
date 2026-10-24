# Lever de la production, 2 h 15 UTC (#1010). Seul lever planifié depuis le
# retrait des crons de `render-sleep.yml` (#1157).
param($Timer)

try {
    Invoke-RenderSleep -Action resume -Target production
}
catch {
    # Dispatch en échec : aucun cron ne rattrape le lever (#1157), la production
    # reste couchée jusqu'au prochain déploiement ou à un lancement manuel. Le
    # moniteur repart tout de suite pour alerter, et l'invocation échoue (#1320).
    Set-BackendMonitor -State start
    Send-OpsAlert "*Render-wake* (Azure) : lever de la production non déclenché, elle reste couchée jusqu'au prochain déploiement ou à un lancement manuel de render-sleep.yml (action resume, cible production). $_"
    throw
}
# Réactivé une fois le backend en ligne, ou au bout de 10 min quoi qu'il arrive :
# un lever raté doit alors se voir, par l'alerte du moniteur (#922).
if (-not (Wait-BackendHealthy -TimeoutSeconds 600)) {
    Write-Warning "Backend toujours injoignable 10 min après le lever."
}
Set-BackendMonitor -State start
