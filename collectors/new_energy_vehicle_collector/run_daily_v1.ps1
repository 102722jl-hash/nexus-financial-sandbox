$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$logDir = Join-Path $PSScriptRoot 'logs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$log = Join-Path $logDir "nev-daily-$stamp.log"
$python = (Get-Command python -ErrorAction Stop).Source

try {
  & $python '.\auto_collect_v1.py' '--market-days' '30' *> $log
  if ($LASTEXITCODE -ne 0) { throw "auto_collect_v1 failed: $LASTEXITCODE" }

  $running = & docker inspect -f '{{.State.Running}}' 'coal-network-postgres' 2>$null
  if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL container not found' }
  if ($running.Trim() -ne 'true') {
    & docker start 'coal-network-postgres' *>> $log
    if ($LASTEXITCODE -ne 0) { throw "docker start failed: $LASTEXITCODE" }
  }

  . '.\load_postgres_secrets.ps1'
  & $python '.\sync_postgres_v1.py' *>> $log
  if ($LASTEXITCODE -ne 0) { throw "sync_postgres_v1 failed: $LASTEXITCODE" }
  & $python '.\verify_postgres_v1.py' *>> $log
  if ($LASTEXITCODE -ne 0) { throw "verify_postgres_v1 failed: $LASTEXITCODE" }

  "SUCCESS $(Get-Date -Format o)" | Add-Content -LiteralPath $log -Encoding UTF8
  exit 0
}
catch {
  "FAILED $(Get-Date -Format o) $($_.Exception.Message)" |
    Add-Content -LiteralPath $log -Encoding UTF8
  Write-Error $_
  exit 1
}
