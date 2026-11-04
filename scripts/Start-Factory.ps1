param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '..')
try {
    $python = Join-Path (Get-Location) '.venv\Scripts\python.exe'
    if (!(Test-Path $python)) {
        throw 'Create .venv and install requirements.txt first. See README.md.'
    }
    & npm.cmd --prefix frontend ci
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    & npm.cmd --prefix frontend run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    & $python -m uvicorn factory.app:app --host 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0) { throw "Uvicorn exited with code $LASTEXITCODE" }
} finally {
    Pop-Location
}
