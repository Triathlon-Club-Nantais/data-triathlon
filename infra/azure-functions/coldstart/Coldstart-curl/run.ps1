# Input bindings are passed in via param block.
param($Timer)

# Get the current universal time in the default string format
$currentUTCtime = (Get-Date).ToUniversalTime()

# The 'IsPastDue' porperty is 'true' when the current function invocation is later than scheduled.
if ($Timer.IsPastDue) {
    Write-Host "PowerShell timer is running late!"
}

# Write an information log with the current time.
Write-Host "PowerShell timer trigger function ran! TIME: $currentUTCtime"

# Invoke-RestMethod -Method Head -ConnectionTimeoutSeconds 1 -Uri "https://data-triathlon-gamma.vercel.app/dashboard"
# La route keep-warm exige `Authorization: Bearer <CRON_SECRET>` (#1021) : même
# valeur que la variable CRON_SECRET des deux projets Vercel, posée ici en App Setting.
$headers = @{ Authorization = "Bearer $env:CRON_SECRET" }
Invoke-RestMethod -Method Head -ConnectionTimeoutSeconds 1 -Headers $headers -Uri "https://data.triathlon-club-nantais.com/api/cron/keep-warm"
Invoke-RestMethod -Method Head -ConnectionTimeoutSeconds 1 -Headers $headers -Uri "https://data-triathlon-tcn-preview.vercel.app/api/cron/keep-warm"