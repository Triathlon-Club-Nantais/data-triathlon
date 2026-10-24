# Coucher de la production, 23 h 15 UTC (#1010).
param($Timer)

# Pause d'abord : le coucher ne doit déclencher aucune alerte (#922).
Set-BackendMonitor -State pause
try {
    Invoke-RenderSleep -Action suspend -Target production
}
catch {
    # Dispatch en échec : la production reste allumée jusqu'au coucher de la nuit
    # suivante et doit rester surveillée. L'alerte Slack signale la panne (#1320).
    Set-BackendMonitor -State start
    Send-OpsAlert "*Render-sleep* (Azure) : coucher de la production non déclenché. $_"
    throw
}
