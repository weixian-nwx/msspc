# Creates an isolated virtual environment and installs all dependencies.
# Run from the project root:  .\setup.ps1
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not (Test-Path ".\.venv")) {
    Write-Host "Creating virtual environment (.venv)..." -ForegroundColor Cyan
    python -m venv .venv
}

Write-Host "Upgrading pip..." -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m pip install --upgrade pip

Write-Host "Installing dependencies..." -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host "`nSetup complete. Launch the app with:  .\run.ps1" -ForegroundColor Green
