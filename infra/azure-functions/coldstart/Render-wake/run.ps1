# Lever de la production, 2 h 15 UTC (#1010). Même heure que le cron de secours
# de `render-sleep.yml`, qui repasse plus tard et ne fait alors plus rien.
param($Timer)

try {
    Invoke-RenderSleep -Action resume -Target production
}
catch {
    # Dispatch en échec : la production reste couchée jusqu'au cron de secours. Le
    # moniteur repart tout de suite pour alerter, et l'invocation échoue (#1320).
    Set-BackendMonitor -State start
    throw
}
# Réactivé une fois le backend en ligne, ou au bout de 10 min quoi qu'il arrive :
# un lever raté doit alors se voir, par l'alerte du moniteur (#922).
if (-not (Wait-BackendHealthy -TimeoutSeconds 600)) {
    Write-Warning "Backend toujours injoignable 10 min après le lever."
}
Set-BackendMonitor -State start
