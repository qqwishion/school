# Optional developer helper. Expects official EDB binaries in .venv/postgresql/pgsql.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$pgTaskRoot = Join-Path (Get-Location) '.venv/postgresql'
$pgTaskCtl = Join-Path $pgTaskRoot 'pgsql/bin/pg_ctl.exe'
$pgTaskData = Join-Path $pgTaskRoot 'data'
if (-not (Test-Path -LiteralPath $pgTaskCtl)) { throw 'PostgreSQL binaries are missing. See README for the Docker alternative.' }
& $pgTaskCtl -D $pgTaskData status *> $null
if ($LASTEXITCODE -ne 0) {
    $pgTaskProcess = Start-Process -FilePath $pgTaskCtl -ArgumentList @('-D', ('"' + $pgTaskData + '"'), '-l', ('"' + (Join-Path $pgTaskRoot 'server.log') + '"'), '-w', 'start') -WindowStyle Hidden -PassThru
    $pgTaskProcess.WaitForExit()
    if ($pgTaskProcess.ExitCode -ne 0) { throw 'Could not start the local PostgreSQL cluster.' }
}
$env:DATABASE_URL = 'postgresql://postgres@127.0.0.1:55432/shag'
$env:Path = (Join-Path $pgTaskRoot 'pgsql/bin') + ';' + $env:Path
$env:PSYCOPG_IMPL = 'python'
