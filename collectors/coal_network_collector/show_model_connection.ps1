$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
. .\load_postgres_secrets.ps1
try {
  [pscustomobject]@{
    DatabaseType = 'PostgreSQL'
    Host = '127.0.0.1'
    Port = 5432
    Database = 'coal_network'
    Schema = 'coal_network'
    User = 'coal_network_readonly'
    Password = $env:COAL_PG_READONLY_PASSWORD
    SSL = 'prefer'
  } | Format-List
} finally {
  Remove-Item Env:COAL_PG_ADMIN_PASSWORD -ErrorAction SilentlyContinue
  Remove-Item Env:COAL_PG_WRITER_PASSWORD -ErrorAction SilentlyContinue
  Remove-Item Env:COAL_PG_READONLY_PASSWORD -ErrorAction SilentlyContinue
}
