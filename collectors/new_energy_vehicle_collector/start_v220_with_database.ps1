param(
  [int]$Port = 4186,
  [string]$DatabaseContainer = "coal-network-postgres",
  [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$browserRoot = Join-Path (Split-Path -Parent $root) "financial-world-sandbox-v2.20-composite-network"
$logDir = Join-Path $root "logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$logPath = Join-Path $logDir "start-v220-with-database.log"

function Write-StartupLog([string]$Message) {
  $line = "$(Get-Date -Format o) $Message"
  Add-Content -LiteralPath $logPath -Value $line -Encoding UTF8
  Write-Host $line
}

function Test-Http([int]$TargetPort) {
  try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$TargetPort/" -TimeoutSec 2
    return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500)
  } catch {
    return $false
  }
}

function Ensure-DockerEngine($DockerCommand) {
  $desktop = Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\Docker Desktop.exe"
  $engineReady = $false
  try {
    & $DockerCommand.Source info 2>$null | Out-Null
    $engineReady = ($LASTEXITCODE -eq 0)
  } catch {
    $engineReady = $false
  }
  if ($engineReady) {
    return
  }
  if (Test-Path -LiteralPath $desktop) {
    Write-StartupLog "Docker engine is unavailable; starting Docker Desktop"
    Start-Process -FilePath $desktop -WindowStyle Minimized
  } else {
    throw "Docker engine is unavailable and Docker Desktop was not found: $desktop"
  }
  for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Seconds 1
    & $DockerCommand.Source info 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
      return
    }
  }
  throw "Docker engine did not become ready within 90 seconds"
}

try {
  if (-not (Test-Path -LiteralPath $browserRoot)) {
    throw "V2.20 browser directory not found: $browserRoot"
  }

  $dockerPath = Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\resources\bin\docker.exe"
  if (Test-Path -LiteralPath $dockerPath) {
    $docker = Get-Command $dockerPath
  } else {
    $docker = Get-Command docker -ErrorAction Stop
  }
  Ensure-DockerEngine $docker
  $containerExists = & $docker.Source inspect $DatabaseContainer 2>$null
  if ($LASTEXITCODE -ne 0 -or -not $containerExists) {
    throw "PostgreSQL container not found: $DatabaseContainer"
  }

  $running = (& $docker.Source inspect -f "{{.State.Running}}" $DatabaseContainer 2>$null).Trim()
  if ($running -ne "true") {
    Write-StartupLog "Starting PostgreSQL container: $DatabaseContainer"
    & $docker.Source start $DatabaseContainer 2>&1 | ForEach-Object {
      Add-Content -LiteralPath $logPath -Value $_ -Encoding UTF8
    }
    if ($LASTEXITCODE -ne 0) {
      throw "PostgreSQL container failed to start: $DatabaseContainer"
    }
  } else {
    Write-StartupLog "PostgreSQL container already running: $DatabaseContainer"
  }

  $ready = $false
  for ($i = 0; $i -lt 30; $i++) {
    $probe = & $docker.Source exec $DatabaseContainer pg_isready -U coal_network_admin -d coal_network 2>$null
    if ($LASTEXITCODE -eq 0) {
      $ready = $true
      break
    }
    Start-Sleep -Seconds 1
  }
  if (-not $ready) {
    throw "PostgreSQL did not become ready within 30 seconds"
  }
  Write-StartupLog "PostgreSQL is ready: local databases remain isolated"

  if (-not (Test-Http $Port)) {
    $startScript = Join-Path $browserRoot "start-v220.ps1"
    Write-StartupLog "Starting V2.20 browser service on port $Port"
    $arguments = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $startScript, "-Port", $Port)
    Start-Process -FilePath "powershell.exe" -ArgumentList $arguments -WorkingDirectory $browserRoot -WindowStyle Minimized
  } else {
    Write-StartupLog "V2.20 browser service already running on port $Port"
  }

  $browserReady = $false
  for ($i = 0; $i -lt 30; $i++) {
    if (Test-Http $Port) {
      $browserReady = $true
      break
    }
    Start-Sleep -Seconds 1
  }
  if (-not $browserReady) {
    throw "V2.20 browser did not become ready within 30 seconds"
  }

  $url = "http://127.0.0.1:$Port"
  Write-StartupLog "V2.20 browser is ready: $url"
  if (-not $NoBrowser) {
    Start-Process $url
  }
  exit 0
} catch {
  $err = $_.Exception.Message
  Write-StartupLog "STARTUP_FAILED: $err"
  Add-Type -AssemblyName PresentationFramework
  $message = "V2.20 browser or PostgreSQL startup failed." + [Environment]::NewLine + [Environment]::NewLine +
    $err + [Environment]::NewLine + [Environment]::NewLine + "Log: " + $logPath
  [System.Windows.MessageBox]::Show($message, "NEXUS V2.20 startup failed", "OK", "Error") | Out-Null
  exit 1
}
