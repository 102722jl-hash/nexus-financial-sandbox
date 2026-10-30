$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python collector.py seed
python nce_public.py
python database_status.py
