$ErrorActionPreference = 'Stop'
$path = Join-Path $PSScriptRoot '.postgres-secrets.dpapi.json'
if (Test-Path -LiteralPath $path) { throw "Secrets already exist: $path" }
function New-Password {
  $bytes = New-Object byte[] 32
  [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  [Convert]::ToBase64String($bytes)
}
function Protect-Text([string]$value) {
  ConvertTo-SecureString $value -AsPlainText -Force | ConvertFrom-SecureString
}
$payload = [ordered]@{
  writer = Protect-Text (New-Password)
  readonly = Protect-Text (New-Password)
  createdAt = [DateTimeOffset]::UtcNow.ToString('o')
}
$payload | ConvertTo-Json | Set-Content -LiteralPath $path -Encoding UTF8
$acl = Get-Acl -LiteralPath $path
$acl.SetAccessRuleProtection($true, $false)
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
  $identity, 'FullControl', 'Allow'
)
$acl.SetAccessRule($rule)
Set-Acl -LiteralPath $path -AclObject $acl
Write-Output "Encrypted NEV PostgreSQL credentials created for $env:USERNAME"
