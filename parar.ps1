$ErrorActionPreference = "Stop"
$logsDeKids = Join-Path $PSScriptRoot ".logs"
foreach ($serviceDeKids in @("api", "telas")) {
    $recordPathDeKids = Join-Path $logsDeKids "$serviceDeKids.json"
    if (Test-Path -LiteralPath $recordPathDeKids) {
        $recordDeKids = Get-Content -LiteralPath $recordPathDeKids | ConvertFrom-Json
        $processDeKids = Get-Process -Id $recordDeKids.id -ErrorAction SilentlyContinue
        if ($processDeKids -and $processDeKids.StartTime.ToUniversalTime().ToString("o") -eq $recordDeKids.started) {
            Stop-Process -Id $processDeKids.Id
        }
        Remove-Item -LiteralPath $recordPathDeKids
    }
}
Write-Output "Serviços DeKids encerrados."
