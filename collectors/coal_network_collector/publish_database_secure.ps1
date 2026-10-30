$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
. .\load_postgres_secrets.ps1
try {
  python auto_collect_v2.py
  python sync_postgres_v2.py --database coal_network --user coal_network_writer --password-env COAL_PG_WRITER_PASSWORD
  python grant_postgres_after_sync.py
  python verify_postgres_readonly.py
} finally {
  Remove-Item Env:COAL_PG_ADMIN_PASSWORD -ErrorAction SilentlyContinue
  Remove-Item Env:COAL_PG_WRITER_PASSWORD -ErrorAction SilentlyContinue
  Remove-Item Env:COAL_PG_READONLY_PASSWORD -ErrorAction SilentlyContinue
}
