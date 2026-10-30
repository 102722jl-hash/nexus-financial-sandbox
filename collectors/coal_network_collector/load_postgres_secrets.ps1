function Unprotect-Text([string]$cipher) {
  $secure = ConvertTo-SecureString $cipher
  $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  try { [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
  finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}
$secretPath = Join-Path $PSScriptRoot '.postgres-secrets.dpapi.json'
if (-not (Test-Path -LiteralPath $secretPath)) { throw "Run initialize_postgres_secrets.ps1 first" }
$secrets = Get-Content -LiteralPath $secretPath -Raw | ConvertFrom-Json
$env:COAL_PG_ADMIN_PASSWORD = Unprotect-Text $secrets.admin
$env:COAL_PG_WRITER_PASSWORD = Unprotect-Text $secrets.writer
$env:COAL_PG_READONLY_PASSWORD = Unprotect-Text $secrets.readonly
