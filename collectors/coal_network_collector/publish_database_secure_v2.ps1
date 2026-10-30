$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
. .\load_postgres_secrets.ps1
try {
  python auto_collect_v2.py
  if ($LASTEXITCODE -ne 0) { throw 'Local collection failed' }
  python sync_postgres_v3.py
  if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL sync failed' }
  python grant_postgres_after_sync.py
  if ($LASTEXITCODE -ne 0) { throw 'Read-only grant refresh failed' }
  python verify_postgres_readonly.py
  if ($LASTEXITCODE -ne 0) { throw 'Read-only verification failed' }
} finally {
  Remove-Item Env:COAL_PG_ADMIN_PASSWORD -ErrorAction SilentlyContinue
  Remove-Item Env:COAL_PG_WRITER_PASSWORD -ErrorAction SilentlyContinue
  Remove-Item Env:COAL_PG_READONLY_PASSWORD -ErrorAction SilentlyContinue
}
