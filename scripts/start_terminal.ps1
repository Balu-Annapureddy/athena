# Start Athena historical terminal on Windows (local-only)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python is not on PATH. Install Python 3.12 and retry."
}
if ([string]::IsNullOrWhiteSpace($env:UPSTOX_ACCESS_TOKEN)) {
    Write-Host "UPSTOX_ACCESS_TOKEN is missing in this PowerShell session."
    Write-Host "Set it locally before launching. Never commit or share the token."
    exit 1
}
Write-Host "Athena historical terminal: http://127.0.0.1:8765"
Write-Host "Local-only. No broker orders. Press Ctrl+C to stop."
python scripts/run_market_terminal.py
exit $LASTEXITCODE
