<#
  scripts/setup.ps1 - Windows one-shot setup (create venv + run bootstrap)

  Run (execution-policy bypass is the standard form):
    powershell -ExecutionPolicy Bypass -File scripts\setup.ps1

  Options:
    -CoreOnly      # core only, skip agent-browser (standard install is full)
    -SkipBrowser   # skip browser install (env that already has Chromium)
    -Force         # reinstall even if already present

  npm / agent-browser are invoked from bootstrap.py as npm.cmd / agent-browser.cmd
  to avoid PowerShell .ps1 execution-policy errors.

  NOTE: messages here are ASCII on purpose. Windows PowerShell 5.1 reads a BOM-less
  UTF-8 .ps1 as ANSI(cp949) and would garble non-ASCII text. Detailed Korean guidance
  lives in bootstrap.py / preflight.py (Python renders Unicode correctly in a console).
#>
param(
  [switch]$CoreOnly,
  [switch]$SkipBrowser,
  [switch]$Force
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot   # parent of scripts/ = repo root
Set-Location $repo

Write-Host "=== web-crawler setup (Windows) ===" -ForegroundColor Cyan

# 1) find a python launcher
$py = $null
foreach ($c in @("py", "python")) {
  if (Get-Command $c -ErrorAction SilentlyContinue) { $py = $c; break }
}
if (-not $py) {
  Write-Host "[FAIL] Python not found. Install from https://www.python.org/downloads/ and re-run." -ForegroundColor Red
  exit 2
}

# 2) venv (create if missing - first time only)
if (-not (Test-Path ".venv")) {
  Write-Host "[*] creating .venv (first time, a few seconds)..." -ForegroundColor Yellow
  if ($py -eq "py") { & py -3 -m venv .venv } else { & python -m venv .venv }
} else {
  Write-Host "[SKIP] .venv already exists" -ForegroundColor DarkGray
}
$venvPy = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
  Write-Host "[FAIL] venv python missing: $venvPy" -ForegroundColor Red
  exit 2
}

# 3) run bootstrap (deps + browser + agent-browser + preflight)
$bootArgs = @("scripts\bootstrap.py")
if ($CoreOnly)    { $bootArgs += "--core-only" }
if ($SkipBrowser) { $bootArgs += "--skip-browser" }
if ($Force)       { $bootArgs += "--force" }

Write-Host "[*] bootstrap: $venvPy $($bootArgs -join ' ')" -ForegroundColor Cyan
& $venvPy @bootArgs
$code = $LASTEXITCODE

Write-Host ""
if ($code -eq 0) {
  Write-Host "[OK] setup complete. Activate venv in a new PowerShell:  .\.venv\Scripts\Activate.ps1" -ForegroundColor Green
} elseif ($code -eq 1) {
  Write-Host "[INCOMPLETE] core ready, agent-browser unfinished -> install not complete. See 'next commands' above." -ForegroundColor Yellow
} else {
  Write-Host "[FAIL] core setup incomplete (exit $code). Run the 'next commands' shown above." -ForegroundColor Red
}
exit $code
