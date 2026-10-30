$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.postgres-secrets.dpapi.json')) { & .\initialize_postgres_secrets.ps1 }
. .\load_postgres_secrets.ps1
try {
  docker compose -f docker-compose.postgres.yml up -d
  $ready = $false
  for ($i = 0; $i -lt 30; $i++) {
    docker exec coal-network-postgres pg_isready -U coal_network_admin -d coal_network *> $null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 2
  }
  if (-not $ready) { throw 'PostgreSQL did not become ready' }
  python setup_postgres_roles.py
  python sync_postgres_v2.py --database coal_network --user coal_network_writer --password-env COAL_PG_WRITER_PASSWORD
  python grant_postgres_after_sync.py
  python verify_postgres_readonly.py
} finally {
  Remove-Item Env:COAL_PG_ADMIN_PASSWORD -ErrorAction SilentlyContinue
  Remove-Item Env:COAL_PG_WRITER_PASSWORD -ErrorAction SilentlyContinue
  Remove-Item Env:COAL_PG_READONLY_PASSWORD -ErrorAction SilentlyContinue
}
