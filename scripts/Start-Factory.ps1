param([ValidateRange(1024,65535)][int]$Port = 8000)
$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '..')
try {
    $python = Join-Path (Get-Location) '.venv\Scripts\python.exe'
    if (!(Test-Path $python)) {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            & py -3.12 -m venv .venv
        } elseif (Get-Command python -ErrorAction SilentlyContinue) {
            & python -m venv .venv
        } else {
            throw 'Install Python 3.12 and enable the Python launcher, then run this script again.'
        }
        if ($LASTEXITCODE -ne 0 -or !(Test-Path $python)) {
            throw 'Could not create .venv. Install Python 3.12 (py -3.12), then retry. Existing data was preserved.'
        }
    }
    & $python -m ensurepip --upgrade
    if ($LASTEXITCODE -ne 0) { throw 'Could not prepare pip inside .venv.' }
    & $python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed. Check your network and retry.' }
    & $python -c 'import fastapi, uvicorn, httpx, dotenv'
    if ($LASTEXITCODE -ne 0) { throw 'Backend imports failed inside .venv.' }
    if (!(Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'Install Node.js LTS, reopen PowerShell and retry.' }
    & npm.cmd --prefix frontend ci
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    & npm.cmd --prefix frontend run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    Write-Host "AI Review Studio: http://127.0.0.1:$Port (keep this window open)"
    & $python -m uvicorn factory.app:app --host 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0) { throw "Uvicorn exited with code $LASTEXITCODE" }
} finally {
    Pop-Location
}
