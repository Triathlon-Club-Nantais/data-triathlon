# Lever de la production, 2 h 15 UTC (#1010). Même heure que le cron de secours
# de `render-sleep.yml`, qui repasse plus tard et ne fait alors plus rien.
param($Timer)

Invoke-RenderSleep -Action resume -Target production
