$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
python -c "import pandas, psycopg, pymysql, cryptography"
python server.py
