$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python auto_collect_v2.py
python sync_postgres_v2.py --host 127.0.0.1 --port 5432 --database coal_network --schema coal_network --user coal_network_writer --password-env COAL_PG_WRITER_PASSWORD
python grant_postgres_after_sync.py
python verify_postgres_readonly.py
