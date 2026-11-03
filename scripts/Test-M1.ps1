param([switch]$Listen)
$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '..')
try {
    $python = '.\.venv\Scripts\python.exe'
    if (!(Test-Path $python)) { throw 'Run Setup-Factory.ps1 -EdgeTts first.' }
    & $python -c "import sys; assert sys.platform == 'win32' and sys.version_info[:2] == (3,12)"
    if ($LASTEXITCODE -ne 0) { throw 'Native Windows and Python 3.12 required.' }
    $env:FACTORY_TTS = 'edge'
    $env:FACTORY_VOICE = 'vi-VN-HoaiMyNeural'
    $root = Join-Path 'workspace' ("M1 tieng Viet " + [guid]::NewGuid())
    foreach ($format in @('short', 'long')) {
        $output = Join-Path $root $format
        # Build the accented component without relying on PowerShell 5 file encoding.
        $output = Join-Path $output ("ti" + [char]0x1EBF + "ng Vi" + [char]0x1EC7 + "t")
        & $python -m factory.smoke $output --format $format
        if ($LASTEXITCODE -ne 0) { throw "Smoke test failed: $format" }
        foreach ($name in @('video.mp4','thumbnail.jpg','subtitles.srt','timeline.json','technical.json','voice-0.wav')) {
            if ((Get-Item (Join-Path $output $name)).Length -le 0) { throw "Empty artifact: $name" }
        }
        if ($Listen) { Invoke-Item (Join-Path $output 'voice-0.wav') }
    }
    & $python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Regression tests failed.' }
} finally {
    Pop-Location
}
