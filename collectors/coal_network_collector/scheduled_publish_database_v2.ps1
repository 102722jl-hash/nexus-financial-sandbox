$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = (Get-Command python -ErrorAction Stop).Source
$docker = 'C:\Users\LL\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe'
$dockerDesktop = 'C:\Users\LL\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe'
$logDir = Join-Path $PSScriptRoot 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$log = Join-Path $logDir ("postgres-publish-$stamp.log")
$statusPath = Join-Path $PSScriptRoot 'scheduled_run_status.json'
function Write-Stage([string]$message) {
  $line = "{0} {1}" -f ([DateTimeOffset]::Now.ToString('o')), $message
  Add-Content -LiteralPath $log -Value $line -Encoding UTF8
}
function Docker-Ready {
  $previous = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  & $docker info *> $null
  $code = $LASTEXITCODE
  $ErrorActionPreference = $previous
  return ($code -eq 0)
}
$result = [ordered]@{ startedAt = [DateTimeOffset]::Now.ToString('o'); status = 'RUNNING'; stage = 'START'; log = $log }
$result | ConvertTo-Json | Set-Content -LiteralPath $statusPath -Encoding UTF8
try {
  Write-Stage 'START'
  if (-not (Docker-Ready)) {
    Write-Stage 'STARTING_DOCKER_DESKTOP'
    Start-Process -FilePath $dockerDesktop -WindowStyle Hidden
    $ready = $false
    for ($i = 0; $i -lt 40; $i++) {
      if (Docker-Ready) { $ready = $true; break }
      Start-Sleep -Seconds 3
    }
    if (-not $ready) { throw 'DOCKER_ENGINE_NOT_READY' }
  }
  Write-Stage 'DOCKER_READY'
  & $docker start coal-network-postgres *> $null
  if ($LASTEXITCODE -ne 0) { throw 'POSTGRES_CONTAINER_START_FAILED' }
  Write-Stage 'POSTGRES_CONTAINER_READY'
  . .\load_postgres_secrets.ps1
  Write-Stage 'ONLINE_COLLECTION_START'
  & $python auto_collect_v4.py *> (Join-Path $logDir "collector-$stamp.log")
  if ($LASTEXITCODE -ne 0) { throw 'ONLINE_COLLECTION_FAILED' }
  Write-Stage 'ONLINE_COLLECTION_DONE'
  & $python validate_v3.py >> $log
  if ($LASTEXITCODE -ne 0) { throw 'DATABASE_VALIDATION_FAILED' }
  Write-Stage 'DATABASE_VALIDATION_DONE'
  & $python sync_postgres_v4.py *> (Join-Path $logDir "postgres-sync-$stamp.log")
  if ($LASTEXITCODE -ne 0) { throw 'POSTGRES_SYNC_FAILED' }
  Write-Stage 'POSTGRES_SYNC_DONE'
  & $python grant_postgres_after_sync.py >> $log
  if ($LASTEXITCODE -ne 0) { throw 'READONLY_GRANT_FAILED' }
  & $python verify_postgres_readonly.py *> (Join-Path $logDir "postgres-verify-$stamp.log")
  if ($LASTEXITCODE -ne 0) { throw 'POSTGRES_VERIFY_FAILED' }
  Write-Stage 'SUCCESS'
  $result.status = 'SUCCESS'; $result.stage = 'COMPLETE'; $result.finishedAt = [DateTimeOffset]::Now.ToString('o')
} catch {
  Write-Stage ("FAILED " + $_.Exception.Message)
  $result.status = 'FAILED'; $result.stage = 'ERROR'; $result.error = $_.Exception.Message; $result.finishedAt = [DateTimeOffset]::Now.ToString('o')
  $result | ConvertTo-Json | Set-Content -LiteralPath $statusPath -Encoding UTF8
  exit 1
} finally {
  Remove-Item Env:COAL_PG_ADMIN_PASSWORD -ErrorAction SilentlyContinue
  Remove-Item Env:COAL_PG_WRITER_PASSWORD -ErrorAction SilentlyContinue
  Remove-Item Env:COAL_PG_READONLY_PASSWORD -ErrorAction SilentlyContinue
}
$result | ConvertTo-Json | Set-Content -LiteralPath $statusPath -Encoding UTF8
exit 0
