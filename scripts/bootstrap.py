"""scripts/bootstrap.py — 신규 환경 설치 (단계별, 이미 설치된 건 skip)

단계: (1) Python deps → (2) Browser deps(Chromium) → (3) agent-browser → (4) preflight 검증.
각 단계는 이미 충족되면 건너뛴다. 실패하면 '다음에 실행할 정확한 명령'을 보여준다.

가능하면 venv 안의 python으로 실행한다. Windows는 scripts/setup.ps1 이 venv를 만들고
이 스크립트를 venv python으로 호출한다.

사용법:
    python scripts/bootstrap.py                # full(표준): deps + browser + agent-browser + preflight
    python scripts/bootstrap.py --core-only    # agent-browser 제외 (표준 설치는 full)
    python scripts/bootstrap.py --skip-browser # 브라우저가 이미 있는 환경에서 빠른 재검증
    python scripts/bootstrap.py --force        # 이미 있어도 강제 재설치
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

IS_WIN = os.name == "nt"
REPO = Path(__file__).resolve().parents[1]
PY = sys.executable


def log(msg=""):
    print(msg, flush=True)


def stage(title):
    log(f"\n=== {title} ===")


def _cmd(name):
    if IS_WIN:
        return shutil.which(name + ".cmd") or shutil.which(name)
    return shutil.which(name)


def run(cmd):
    log("  $ " + " ".join(str(c) for c in cmd))
    return subprocess.run(cmd)


# ---------------- 상태 점검 ----------------
def py_deps_ready():
    try:
        import scrapling.fetchers  # noqa: F401
        import openpyxl  # noqa: F401
        import playwright  # noqa: F401
        import curl_cffi  # noqa: F401
        import patchright  # noqa: F401
        import browserforge  # noqa: F401
        import msgspec  # noqa: F401
        return True
    except Exception:
        return False


def scrapling_exe():
    d = Path(PY).parent
    cand = d / ("scrapling.exe" if IS_WIN else "scrapling")
    if cand.exists():
        return str(cand)
    return _cmd("scrapling")


def browsers_ready():
    # 1) scrapling 센티넬
    try:
        import scrapling
        if (Path(scrapling.__file__).parent / ".scrapling_dependencies_installed").exists():
            return True
    except Exception:
        pass
    # 2) ms-playwright 에 chromium 빌드 존재
    cands = []
    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        cands.append(Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"]))
    home = Path(os.path.expanduser("~"))
    cands += [home / "AppData/Local/ms-playwright", home / ".cache/ms-playwright",
              home / "Library/Caches/ms-playwright"]
    for c in cands:
        try:
            if c.exists() and any(x.name.startswith("chromium") for x in c.iterdir()):
                return True
        except Exception:
            pass
    return False


def agent_browser_ready():
    p = _cmd("agent-browser")
    if not p:
        return False
    try:
        return subprocess.run([p, "--version"], capture_output=True, text=True, timeout=30).returncode == 0
    except Exception:
        return False


# ---------------- 단계 ----------------
def do_python_deps(force):
    stage("1/4 Python deps")
    if not force and py_deps_ready():
        log("  [SKIP] 이미 설치됨 (scrapling[fetchers] 등 import 확인)")
        return True, None
    log("  최초 1회는 수 분 걸릴 수 있음 (scrapling[fetchers]: playwright/patchright/curl_cffi 등 다운로드).")
    req = REPO / "requirements.txt"
    r = run([PY, "-m", "pip", "install", "-r", str(req)])
    if r.returncode != 0:
        return False, f'{PY} -m pip install -r "{req}"'
    return True, None


def do_browser_deps(skip, force):
    stage("2/4 Browser deps (Chromium)")
    if skip:
        log("  [SKIP] --skip-browser")
        return True, None
    if not force and browsers_ready():
        log("  [SKIP] Chromium 이미 있음 (ms-playwright 또는 scrapling 센티넬 감지)")
        return True, None
    log("  최초 1회만 오래 걸림 (Chromium 다운로드 ~150MB). 이미 받은 경우 빠르게 끝남.")
    log("  참고: scrapling install 이 내부적으로 playwright install chromium 을 수행 — 따로 또 안 해도 됨.")
    exe = scrapling_exe()
    if exe:
        r = run([exe, "install"])
        nxt = f'"{exe}" install'
    else:
        # 폴백: scrapling install 이 하는 일과 동일 (python -m scrapling 은 동작 안 하므로 playwright 직접 호출)
        r = run([PY, "-m", "playwright", "install", "chromium"])
        nxt = f"{PY} -m playwright install chromium"
    if r.returncode != 0:
        return False, nxt
    return True, None


def do_agent_browser(core_only, force):
    stage("3/4 agent-browser (표준 정찰 도구)")
    if core_only:
        log("  [SKIP] --core-only (단, 표준 설치는 agent-browser 포함 full)")
        return True, None
    if not force and agent_browser_ready():
        log("  [SKIP] agent-browser 이미 설치됨")
        return True, None
    npm = _cmd("npm")
    npm_fix = "npm.cmd install -g agent-browser" if IS_WIN else "npm install -g agent-browser"
    if not npm:
        return False, npm_fix + "  (먼저 Node.js: https://nodejs.org/)"
    log("  CLI 글로벌 설치 + Chrome 셋업 (최초 1회, Chrome for Testing 다운로드 가능).")
    if run([npm, "install", "-g", "agent-browser"]).returncode != 0:
        return False, npm_fix
    ab = _cmd("agent-browser")
    ab_fix = "agent-browser.cmd install" if IS_WIN else "agent-browser install"
    if not ab:
        return False, ab_fix
    if run([ab, "install"]).returncode != 0:
        return False, ab_fix
    return True, None


def do_preflight(core_only):
    stage("4/4 Preflight 검증")
    cmd = [PY, str(REPO / "scripts" / "preflight.py")]
    if core_only:
        cmd.append("--core-only")
    return run(cmd).returncode


def main():
    ap = argparse.ArgumentParser(description="신규 환경 설치 (단계별, skip 지원)")
    ap.add_argument("--core-only", action="store_true", help="agent-browser 제외 (표준은 full)")
    ap.add_argument("--skip-browser", action="store_true", help="브라우저 설치 생략(이미 있는 환경)")
    ap.add_argument("--force", action="store_true", help="이미 있어도 강제 재설치")
    args = ap.parse_args()

    log("=== web-crawler 설치 부트스트랩 ===")
    if sys.prefix == sys.base_prefix:
        log("  [WARN] venv 밖에서 실행 중. Windows는 'scripts\\setup.ps1' 권장(venv 자동 생성).")
    log(f"  python: {PY}")

    results, times, nexts = {}, {}, []
    for key, fn in [
        ("Python deps", lambda: do_python_deps(args.force)),
        ("Browser deps", lambda: do_browser_deps(args.skip_browser, args.force)),
        ("agent-browser", lambda: do_agent_browser(args.core_only, args.force)),
    ]:
        t0 = time.time()
        ok, nxt = fn()
        times[key] = time.time() - t0
        results[key] = ok
        if not ok:
            log(f"  [FAIL] {key}")
            if nxt:
                nexts.append((key, nxt))

    pf = do_preflight(args.core_only)

    stage("설치 요약")
    for key in ["Python deps", "Browser deps", "agent-browser"]:
        log(f"  [{'OK' if results[key] else 'FAIL'}] {key}  ({times[key]:.1f}s)")
    log(f"  preflight exit = {pf}  (0=전체통과 / 1=core통과·agent-browser미완료 / 2=core실패)")

    if nexts:
        log("\n다음에 실행할 명령:")
        for key, nxt in nexts:
            log(f"  - {key}: {nxt}")

    if pf == 0 and all(results.values()):
        log("\n[OK] 설치 완료 — 수집 환경 준비됨.")
        return 0
    if pf == 2 or not results["Python deps"] or not results["Browser deps"]:
        log("\n[FAIL] core 설치 미완료. 위 명령 실행 후 'python scripts/preflight.py' 로 재검증.")
        return 2
    log("\n[INCOMPLETE] core는 준비됐으나 agent-browser 미완료 → 전체 설치 미완료(표준 정찰 도구).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
