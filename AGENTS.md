# AGENTS.md — web-crawler (Codex / Claude Code dual-host)

이 레포는 URL과 수집 항목을 받아 사이트를 정찰·대량수집하고 엑셀로 내보내는 범용 웹 크롤링 에이전트다. **`CLAUDE.md`와 `.codex/skills/web-crawler/SKILL.md`가 *어떻게*에 대한 SSOT다.** 이 파일은 Codex용 **실행 계약**이다 — Claude Code는 Skill 런타임으로 같은 규율을 자동 적용받지만, Codex는 Skill 런타임이 없으므로 이 파일이 대신 강제한다.

## 최초 환경 셋업 (클론 직후 1회)

수집 전에 환경을 준비한다. **한 명령**으로 단계별 설치+검증을 하고, 이미 된 단계는 skip한다:

```powershell
# Windows (PowerShell) — 실행 정책 우회가 표준
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```
```bash
# macOS / Linux
python -m venv .venv && . .venv/bin/activate && python scripts/bootstrap.py
```

단계: ① Python deps → ② 브라우저(Chromium) → ③ agent-browser(표준 정찰 도구) → ④ preflight 검증.
실패하면 "다음에 실행할 정확한 명령"이 출력된다. 모드: 기본 full(표준) / `--core-only`(agent-browser 제외) / `--skip-browser` / `-VerbosePip`(pip 상세 로그).

**`py` 런처 깨짐 자동 처리**: `setup.ps1`은 `py -3`/`python`/`python3`를 실제 실행해 3.10+를 확인하고 성공하는 쪽으로 venv를 만든다. `py -3`가 `No installed Python found!`로 실패하면 자동으로 `python`으로 fallback한다. 그래도 venv가 안 생기면 직접: `python -m venv .venv` → `.\.venv\Scripts\python.exe scripts\bootstrap.py`.

**수동/디버깅 시 실제 동작하는 명령 (Windows)**:
```powershell
python --version ; py -3 --version       # 어느 쪽이 동작하는지 먼저 확인 (py 깨졌으면 python 사용)
python -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt --progress-bar off    # 멈춘 듯하면 끝에 -v 추가
scrapling install                        # Chromium 1회 설치 (내부에서 playwright install chromium 수행 — 따로 또 X)
npm.cmd install -g agent-browser ; agent-browser.cmd install   # PowerShell은 .cmd 사용
python scripts\preflight.py              # 검증: core / agent-browser 분리 PASS·WARN·FAIL
```
- `python -m scrapling`은 동작 안 함 → `scrapling install`(venv 활성화) 또는 `.\.venv\Scripts\scrapling.exe install`.
- pip이 진행 없이 멈춘 듯하면 정상(대용량 휠 다운로드). 진행 확인: `.\.venv\Scripts\python.exe -m pip install -r requirements.txt --progress-bar off -v`.
- 검증은 `scripts/preflight.py`가 담당: **core(Python/Scrapling/Playwright)**와 **agent-browser**를 분리 보고. core 통과·agent-browser 실패면 "전체 설치 미완료"(종료코드 1). 전체 가이드는 `README.md` "처음 설치하기".

## 스킬 소스 (생성 미러)

- **`.claude/skills/`가 정본. `.codex/skills/`는 생성 미러**다 — 텍스트 안의 `.claude/skills` 경로만 `.codex/skills`로 치환된 것 외엔 byte-identical.
- **`.codex/skills/`를 직접 수정하지 말 것.** `.claude/skills/`를 고친 뒤 `python scripts/sync_codex_mirror.py`를 실행해 미러를 재생성한다. (어긋남 확인: `python scripts/sync_codex_mirror.py --check`)
- **문서의 "알려진 도메인" 목록도 생성물**이다 — `fingerprints/*/profile.json`이 SSOT. 새 프로필을 추가했으면 `python scripts/sync_domain_list.py`로 CLAUDE.md/README.md를 재생성한다. (어긋남 확인: `python scripts/sync_domain_list.py --check` / 테스트: `scripts/test_sync_domain_list.py`)

## 크롤링 요청을 받으면 — 필수 절차

사용자가 "크롤링/스크래핑/수집/~를 모아줘/입찰공고 수집" 등을 요청하면:

1. **즉흥 처리 금지.** `.codex/skills/web-crawler/SKILL.md`를 단계대로 실행한다. 절차를 요약하고 임의로 구현하지 않는다. **폴백 재구현 금지** — `requests`/`urllib`/`httpx`/`BeautifulSoup`로 직접 수집하거나 인라인으로 긁지 않는다. 수집은 항상 생성한 `crawl_script.py` 안의 **Scrapling 또는 Playwright**로만 한다.

2. **절대 규칙 0 — 도메인 히스토리 우선.** 정찰하기 전에 반드시 `fingerprints/<sanitized_domain>/profile.json`과 `output/<도메인>/`을 먼저 본다. 프로필이 있으면 `notes`/`fetcher_type`/`antibot_strategy`를 그대로 채택하고 정찰을 건너뛰어 Step 3으로 점프한다. profile.json이 있는데 무시하고 정찰부터 다시 하는 것은 금지(5~20분 비싼 작업 반복). 알려진 도메인 목록은 `CLAUDE.md` 참조 (coupang.com, g2b.go.kr, wanted.co.kr, www.kurly.com 등).

3. **프로필 게이트.** Step 1-A(프로필 있으면 load) ↔ Step 5-A(수집 성공 직후 save/갱신, `notes` 필드 필수). Step 5-A를 빠뜨리면 수집 결과가 살아있어도 **"파이프라인 미완료"**로 보고한다.

## 정찰 도구 — agent-browser가 표준 (양 host 공통)

- 정찰(Step 2)의 **표준·기본 도구는 `agent-browser`**다. 선택 기능이 아니다 — 워크플로상 정찰 단계에서는 **단순 정적 사이트를 긁더라도 agent-browser를 먼저 사용**한다. vercel-labs의 독립 CLI(`npm install -g agent-browser`)라 **Claude Code·Codex 모두 동일하게** 쓴다(Claude 전용 아님). 사용법은 양 host 모두 정찰 시작 전 `agent-browser skills get core --full`로 로드 — CLI 내장, 항상 버전 일치(파일 복사 불필요).
- **대체(degraded fallback)** — agent-browser CLI 설치가 안 됐거나 브라우저 실행이 막힌 제한된 샌드박스에서만: **Scrapling `DynamicFetcher`** 또는 **Playwright `sync_api`**(`page.on("response")`로 XHR/API 캡처). 둘 다 Python 의존성에 포함돼 항상 가능. (SKILL.md 규칙 1 예외와 동일.) 이 경우에도 가능하면 `agent-browser.cmd install`로 표준 경로 복구를 먼저 시도한다.
- **수집·프로필·엑셀·CDP는 양 host 완전 동일**: 수집(Scrapling), 도메인 프로필(`scripts/domain_profile.py`), 엑셀(`scripts/export_excel.py`), Akamai/고급 WAF 대응(`scripts/chrome_cdp.py`), 진행 체크포인트(`scripts/progress.py`).

## 안전 — 하드룰 (위반 금지)

- **CAPTCHA 자동 우회 금지** — reCAPTCHA/hCaptcha 등이 뜨면 사용자에게 보고 후 중단한다.
- **로그인 자격증명 저장 금지** — ID/PW를 코드·메모리·파일에 저장하지 않는다. 사용자가 직접 로그인 → 쿠키만 추출(`output/<도메인>/cookies.json`, `.gitignore`가 차단).
- **robots.txt 제한** 발견 시(`Disallow: /` 또는 대상 경로 차단) 진행 여부를 사용자에게 묻는다.
- **PII 감지 필수** — 수집 데이터에 전화번호/주민번호/이메일 등이 섞이면 `detect_pii(data)`로 경고하고 보고한다.
- **불법 스크래핑 거절** — 저작권 위반·개인정보 대량 수집·ToS 명시 위반은 진행 전 사용자 확인 후 거절한다.
- **수집 0건이면 즉시 중단·보고** — 계속 시도하면 ban 위험.

## 빠른 참조

| 무엇 | 경로 |
|------|------|
| 워크플로우 7단계 | `.codex/skills/web-crawler/SKILL.md` |
| Fetcher 코드 템플릿 | `.codex/skills/web-crawler/references/fetcher-patterns.md` |
| 안티봇(Akamai/Cloudflare/SPA 세션) | `.codex/skills/web-crawler/references/antibot-strategies.md` |
| 수집 실패 진단 | `.codex/skills/web-crawler/references/troubleshooting.md` |
| 프로젝트 규칙·도구 분리 SSOT | `CLAUDE.md` |
