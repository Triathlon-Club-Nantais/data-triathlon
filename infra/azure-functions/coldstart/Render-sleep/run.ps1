# Coucher de la production, 23 h 15 UTC (#1010). Même heure que le cron de secours
# de `render-sleep.yml`.
param($Timer)

Invoke-RenderSleep -Action suspend -Target production
