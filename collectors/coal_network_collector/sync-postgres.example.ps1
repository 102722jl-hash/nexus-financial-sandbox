$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:COAL_PG_PASSWORD = Read-Host 'PostgreSQL同步账号密码'
python sync_postgres_v2.py --host 127.0.0.1 --port 5432 --database your_database --user coal_network_writer --password-env COAL_PG_PASSWORD
Remove-Item Env:COAL_PG_PASSWORD
