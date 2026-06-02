<#
  scripts/setup.ps1 — Windows 한 방 설치 (venv 생성 + bootstrap 실행)

  실행 (PowerShell 실행 정책 우회 — 이 한 줄이 표준):
    powershell -ExecutionPolicy Bypass -File scripts\setup.ps1

  옵션:
    -CoreOnly      # agent-browser 제외하고 core만 (표준 설치는 full)
    -SkipBrowser   # 브라우저가 이미 있는 환경에서 빠른 재검증
    -Force         # 이미 설치돼 있어도 강제 재설치

  npm / agent-browser 는 PowerShell .ps1 실행정책 문제를 피하려고 bootstrap.py 안에서
  npm.cmd / agent-browser.cmd 로 호출한다.
#>
param(
  [switch]$CoreOnly,
  [switch]$SkipBrowser,
  [switch]$Force
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot   # scripts/ 의 부모 = repo 루트
Set-Location $repo

Write-Host "=== web-crawler 설치 (Windows) ===" -ForegroundColor Cyan

# 1) python 런처 찾기
$py = $null
foreach ($c in @("py", "python")) {
  if (Get-Command $c -ErrorAction SilentlyContinue) { $py = $c; break }
}
if (-not $py) {
  Write-Host "[FAIL] Python을 찾을 수 없음. https://www.python.org/downloads/ 에서 설치 후 다시 실행." -ForegroundColor Red
  exit 2
}

# 2) venv (없으면 생성 — 최초 1회)
if (-not (Test-Path ".venv")) {
  Write-Host "[*] .venv 생성 (최초 1회, 수 초)..." -ForegroundColor Yellow
  if ($py -eq "py") { & py -3 -m venv .venv } else { & python -m venv .venv }
} else {
  Write-Host "[SKIP] .venv 이미 존재" -ForegroundColor DarkGray
}
$venvPy = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
  Write-Host "[FAIL] venv python 없음: $venvPy" -ForegroundColor Red
  exit 2
}

# 3) bootstrap 실행 (deps + browser + agent-browser + preflight)
$bootArgs = @("scripts\bootstrap.py")
if ($CoreOnly)    { $bootArgs += "--core-only" }
if ($SkipBrowser) { $bootArgs += "--skip-browser" }
if ($Force)       { $bootArgs += "--force" }

Write-Host "[*] bootstrap: $venvPy $($bootArgs -join ' ')" -ForegroundColor Cyan
& $venvPy @bootArgs
$code = $LASTEXITCODE

Write-Host ""
if ($code -eq 0) {
  Write-Host "[OK] 설치 완료. 새 PowerShell에서 venv 활성화:  .\.venv\Scripts\Activate.ps1" -ForegroundColor Green
} elseif ($code -eq 1) {
  Write-Host "[INCOMPLETE] core는 준비됨, agent-browser 미완료 → 전체 설치 미완료. 위 '다음에 실행할 명령' 참고." -ForegroundColor Yellow
} else {
  Write-Host "[FAIL] core 설치 미완료 (exit $code). 위 '다음에 실행할 명령'을 실행하세요." -ForegroundColor Red
}
exit $code
