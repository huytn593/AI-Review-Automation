param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '..')
try {
    $python = Join-Path (Get-Location) '.venv\Scripts\python.exe'
    if (!(Test-Path $python)) {
        throw 'Create .venv and install requirements.txt first. See README.md.'
    }
    & $python -m uvicorn factory.app:app --host 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0) { throw "Uvicorn exited with code $LASTEXITCODE" }
} finally {
    Pop-Location
}
