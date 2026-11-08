$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:DEBUG = '1'
$env:DEMO_MODE = '1'
if (-not $env:DATABASE_URL -and (Test-Path -LiteralPath '.venv/postgresql/data/PG_VERSION')) {
    . ./scripts/portable-postgres.ps1
}
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create Python environment' }
    & ./.venv/Scripts/python.exe -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Could not install dependencies' }
}
& ./.venv/Scripts/python.exe manage.py migrate
if ($LASTEXITCODE -ne 0) { throw 'Migration failed' }
& ./.venv/Scripts/python.exe manage.py seed_demo
if ($LASTEXITCODE -ne 0) { throw 'Demo seed failed' }
Write-Host 'Shag: http://127.0.0.1:8000/materials/'
& ./.venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000 --noreload
