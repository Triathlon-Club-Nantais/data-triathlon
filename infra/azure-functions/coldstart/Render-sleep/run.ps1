# Coucher de la production, 23 h 15 UTC (#1010). Même heure que le cron de secours
# de `render-sleep.yml`.
param($Timer)

# Pause d'abord : le coucher ne doit déclencher aucune alerte (#922).
Set-BackendMonitor -State pause
try {
    Invoke-RenderSleep -Action suspend -Target production
}
catch {
    # Dispatch en échec : la production reste allumée jusqu'au cron de secours et
    # doit rester surveillée. L'alerte de la nuit qui suit signale la panne (#1320).
    Set-BackendMonitor -State start
    Send-OpsAlert "*Render-sleep* (Azure) : coucher de la production non déclenché. $_"
    throw
}
