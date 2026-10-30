$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python collector.py seed
python daily_job.py
python enrich_financials.py
python build_nodes.py
python database_status.py
