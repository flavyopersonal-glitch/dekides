$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$pythonDeKids = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonDeKids)) { throw "Instale o ambiente Python venv e as dependências primeiro." }
$logsDeKids = Join-Path $PSScriptRoot ".logs"
New-Item -ItemType Directory -Path $logsDeKids -Force | Out-Null
$env:DEKIDS_ENV_FILE = ".env"
$env:DEKIDS_API_URL = "http://127.0.0.1:8000"
$env:PYTHONIOENCODING = "utf-8"
foreach ($serviceDeKids in @(
    @{name="api"; port=8000; arguments=@("-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000")},
    @{name="telas"; port=8501; arguments=@("-m","streamlit","run","frontend/Home.py","--server.address=127.0.0.1","--server.port=8501","--server.headless=true","--browser.gatherUsageStats=false")}
)) {
    if (Get-NetTCPConnection -LocalPort $serviceDeKids.port -State Listen -ErrorAction SilentlyContinue) {
        Write-Output "Porta $($serviceDeKids.port) já está em uso; esse serviço não foi iniciado novamente."
        continue
    }
    $processDeKids = Start-Process -FilePath $pythonDeKids -ArgumentList $serviceDeKids.arguments -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logsDeKids "$($serviceDeKids.name).out.log") -RedirectStandardError (Join-Path $logsDeKids "$($serviceDeKids.name).err.log")
    @{id=$processDeKids.Id; started=$processDeKids.StartTime.ToUniversalTime().ToString("o")} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logsDeKids "$($serviceDeKids.name).json")
}
Write-Output "DeKids: http://localhost:8501"
