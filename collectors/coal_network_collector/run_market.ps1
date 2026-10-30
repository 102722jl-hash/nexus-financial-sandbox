$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python akshare_market.py
python complete_contract.py
python build_nodes.py
python manifest.py
