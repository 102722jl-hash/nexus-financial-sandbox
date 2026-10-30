$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python -m py_compile collector.py source_adapters.py
python source_adapters.py --source all
