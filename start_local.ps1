$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "No existe .venv. Creándolo..." -ForegroundColor Yellow
    python -m venv .venv
}

& ".\.venv\Scripts\Activate.ps1"
python -m pip install -r requirements.txt
python main.py
