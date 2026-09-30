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
    $body = @{ ref = 'main'; inputs = @{ action = $Action; target = $Target } } | ConvertTo-Json

    # 204 sans corps en cas de succès. Une erreur (jeton expiré, 404) lève, et
    # l'invocation apparaît en échec dans *Monitor → Invocations*.
    Invoke-RestMethod -Method Post -Headers $headers -Body $body -ContentType 'application/json' `
        -MaximumRetryCount 3 -RetryIntervalSec 10 -ConnectionTimeoutSeconds 30 `
        -Uri 'https://api.github.com/repos/Triathlon-Club-Nantais/data-triathlon/actions/workflows/render-sleep.yml/dispatches'

    Write-Host "render-sleep.yml déclenché : $Action $Target"
}

Export-ModuleMember -Function Invoke-RenderSleep
