param([switch]$EdgeTts)
$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '..')
try {
    foreach ($tool in @('ffmpeg', 'ffprobe')) {
        if (!(Get-Command $tool -ErrorAction SilentlyContinue)) {
            throw "$tool must be on PATH."
        }
    }
    if (!(Test-Path '.venv\Scripts\python.exe')) {
        py -3.12 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Virtual environment setup failed.' }
    }
    & .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    if ($EdgeTts) {
        & .\.venv\Scripts\python.exe -m pip install edge-tts
        if ($LASTEXITCODE -ne 0) { throw 'Edge TTS installation failed.' }
    }
} finally {
    Pop-Location
}
