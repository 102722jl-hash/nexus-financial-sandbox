param(
  [int]$Port = 4186
)

$root = $PSScriptRoot
$localPython = Join-Path $root ".venv-ui\Scripts\python.exe"
$sharedPython = Join-Path $root "..\financial-world-sandbox-v2.19-generated-network\.venv-ui\Scripts\python.exe"

if (Test-Path -LiteralPath $localPython) {
  $python = $localPython
} elseif (Test-Path -LiteralPath $sharedPython) {
  $python = $sharedPython
} else {
  $python = "python"
}

& $python (Join-Path $root "server.py") --port $Port
