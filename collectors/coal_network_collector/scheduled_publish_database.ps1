$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$logDir = Join-Path $PSScriptRoot 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("postgres-publish-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
Start-Transcript -LiteralPath $log | Out-Null
try {
  docker info *> $null
  if ($LASTEXITCODE -ne 0) {
    Start-Process -FilePath 'C:\Users\LL\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe'
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
      docker info *> $null
      if ($LASTEXITCODE -eq 0) { $ready = $true; break }
      Start-Sleep -Seconds 3
    }
    if (-not $ready) { throw 'Docker engine did not become ready' }
  }
  docker start coal-network-postgres *> $null
  & .\publish_database_secure_v3.ps1
} finally {
  Stop-Transcript | Out-Null
}
