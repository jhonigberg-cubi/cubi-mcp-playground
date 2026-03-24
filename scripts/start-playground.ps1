param(
    [string]$Host = "127.0.0.1",
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

Push-Location $Root
try {
    & $Python -m server.playground --host $Host --port $Port
}
finally {
    Pop-Location
}
