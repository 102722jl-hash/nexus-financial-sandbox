$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

python collector.py seed
python -m py_compile collector.py source_adapters.py parsers.py import_snapshots.py
python source_adapters.py --source all
python import_snapshots.py
python database_status.py
