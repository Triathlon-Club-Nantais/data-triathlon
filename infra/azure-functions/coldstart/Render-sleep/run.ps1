# Coucher de la production, 23 h 15 UTC (#1010). Même heure que le cron de secours
# de `render-sleep.yml`.
param($Timer)

# Pause d'abord : le coucher ne doit déclencher aucune alerte (#922).
Set-BackendMonitor -State pause
Invoke-RenderSleep -Action suspend -Target production
