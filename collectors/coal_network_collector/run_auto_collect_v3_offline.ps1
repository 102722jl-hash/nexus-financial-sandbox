$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python auto_collect_v3.py --offline
