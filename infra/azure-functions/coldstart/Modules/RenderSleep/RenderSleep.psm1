# Déclenche `render-sleep.yml` par `workflow_dispatch` (#1010).
#
# Le `schedule` de GitHub Actions démarrait le lever de la production avec 2 à
# 5 h de retard (#842, #885). Le timer Azure, lui, part à l'heure : il ne fait
# que demander le run, et toute la logique (résolution du service par son nom,
# abstention pendant un déploiement, 400 « déjà éveillé ») reste dans le
# workflow, sans être recopiée ici. `RENDER_API_KEY` ne quitte pas GitHub.

function Invoke-RenderSleep {
    param(
        [Parameter(Mandatory)] [ValidateSet('suspend', 'resume')] [string] $Action,
        [Parameter(Mandatory)] [ValidateSet('preview', 'production', 'both')] [string] $Target
    )

    if (-not $env:GITHUB_DISPATCH_TOKEN) {
        throw "App Setting GITHUB_DISPATCH_TOKEN absente : render-sleep.yml n'est pas déclenché."
    }

    $headers = @{
        Authorization          = "Bearer $env:GITHUB_DISPATCH_TOKEN"
        Accept                 = 'application/vnd.github+json'
        'X-GitHub-Api-Version' = '2022-11-28'
    }
    # `alert` : personne ne suit ce run, un échec doit ouvrir l'issue `ops` (#922).
    $body = @{ ref = 'main'; inputs = @{ action = $Action; target = $Target; alert = 'true' } } | ConvertTo-Json

    # 204 sans corps en cas de succès. Une erreur (jeton expiré, 404) lève, et
    # l'invocation apparaît en échec dans *Monitor → Invocations*.
    Invoke-RestMethod -Method Post -Headers $headers -Body $body -ContentType 'application/json' `
        -MaximumRetryCount 3 -RetryIntervalSec 10 -ConnectionTimeoutSeconds 30 `
        -Uri 'https://api.github.com/repos/Triathlon-Club-Nantais/data-triathlon/actions/workflows/render-sleep.yml/dispatches'

    Write-Host "render-sleep.yml déclenché : $Action $Target"
}

# Moniteur UptimeRobot du backend de production (#922) : en pause pendant la veille
# volontaire, sans quoi chaque nuit enverrait deux alertes. La fenêtre de
# maintenance programmée d'UptimeRobot est payante ; la piloter d'ici est gratuit.
# App Settings absents : rien n'est fait, la veille Render n'en dépend pas.
function Set-BackendMonitor {
    param([Parameter(Mandatory)] [ValidateSet('pause', 'start')] [string] $State)

    if (-not $env:UPTIMEROBOT_API_KEY -or -not $env:UPTIMEROBOT_BACKEND_MONITOR_ID) {
        Write-Warning "UPTIMEROBOT_API_KEY ou UPTIMEROBOT_BACKEND_MONITOR_ID absent : moniteur non piloté."
        return
    }
    try {
        Invoke-RestMethod -Method Post -ContentType 'application/json' -Body '{}' `
            -Headers @{ Authorization = "Bearer $env:UPTIMEROBOT_API_KEY" } `
            -MaximumRetryCount 3 -RetryIntervalSec 10 -ConnectionTimeoutSeconds 30 `
            -Uri "https://api.uptimerobot.com/v3/monitors/$($env:UPTIMEROBOT_BACKEND_MONITOR_ID)/$State" | Out-Null
        Write-Host "Moniteur UptimeRobot du backend : $State"
    }
    catch {
        # Un moniteur mal piloté donne au pire une fausse alerte : jamais une raison
        # de ne pas coucher ou lever la production.
        Write-Warning "Moniteur UptimeRobot non piloté ($State) : $_"
    }
}

# Attend que le backend de production réponde, avant de réactiver son moniteur.
# Le lever par Render prend une à deux minutes après le dispatch.
function Wait-BackendHealthy {
    param([int] $TimeoutSeconds = 600)

    $limite = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $limite) {
        try {
            $reponse = Invoke-WebRequest -Uri 'https://data-triathlon-vq6u.onrender.com/api/v1/health' `
                -ConnectionTimeoutSeconds 20 -SkipHttpErrorCheck
            if ($reponse.StatusCode -eq 200) { return $true }
        }
        catch { }
        Start-Sleep -Seconds 20
    }
    return $false
}

Export-ModuleMember -Function Invoke-RenderSleep, Set-BackendMonitor, Wait-BackendHealthy
