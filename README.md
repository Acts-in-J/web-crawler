# 범용 웹 크롤링 에이전트

여러 웹사이트에서 원하는 정보를 **자동으로 모아 엑셀로 정리**해 주는 AI 에이전트입니다. 코딩을 몰라도, *"이 사이트에서 이런 걸 모아줘"* 라고 말하면 에이전트가 알아서 사이트를 살펴보고(정찰), 데이터를 수집하고, 엑셀 파일로 만들어 줍니다.

> 직접 프로그램을 짜는 게 아닙니다. **Claude Code나 Codex 같은 AI 코딩 에이전트**에게 자연어로 부탁하면, 이 레포에 담긴 도구·규칙·과거 수집 노하우를 따라 에이전트가 대신 수집해 줍니다.

## 이런 걸 할 수 있어요

- 🛒 쇼핑몰 상품 목록·가격·리뷰 (쿠팡, 컬리, 스마트스토어, 네이버 브랜드스토어 등)
- 📋 정부·공공 입찰공고·공시 (나라장터 g2b, 금융감독원, 서울 열린데이터광장 등)
- 💼 채용공고 (원티드 등)
- 🏢 부동산·기업정보 등 목록형 데이터

결과는 항상 깔끔한 **엑셀(.xlsx)** 파일로 나옵니다.

## 사용법 (설치 후)

설치가 끝났다면, AI 에이전트에게 이렇게 부탁하면 됩니다:

> "https://www.example.com 에서 상품명, 가격, 평점을 100개 모아서 엑셀로 정리해줘"

그러면 에이전트가 알아서:

1. 사이트 구조를 살펴보고 (정찰)
2. 가장 적합한 수집 방법을 고르고
3. 수집 스크립트를 만들어 실행하고
4. 엑셀 파일로 저장한 뒤 결과를 보고합니다.

**URL**과 **무엇을 모을지** 두 가지만 알려주면 됩니다.

---

## 처음 설치하기 (최초 1회)

> 💡 **가장 쉬운 방법** — 아래 [AI 에이전트에게 셋업 맡기기](#ai-에이전트에게-셋업-맡기기-권장)의 프롬프트를 복사해 에이전트에게 주면 알아서 다 설치합니다. 직접 하고 싶으면 그 아래 [수동 설치](#수동-설치)를 따라 하세요.

### 미리 필요한 것

| 필요 | 확인 명령 | 없으면 |
|------|-----------|--------|
| **Python 3.10 이상** | `python --version` | [python.org](https://www.python.org/downloads/) 에서 설치 |
| **Node.js 18 이상** | PowerShell: `npm.cmd --version` | [nodejs.org](https://nodejs.org/) 에서 설치 (agent-browser용) |

> Windows PowerShell에서는 `npm` / `agent-browser` 가 `.ps1` 실행 정책 때문에 막힐 수 있습니다. 그럴 땐 **`npm.cmd` / `agent-browser.cmd`** 를 쓰세요(아래 스크립트는 자동 처리).

### 한 방 설치 (권장)

신규 사용자는 한 명령이면 됩니다. **단계별로 진행하며, 이미 설치된 단계는 자동으로 건너뜁니다.** 실패하면 "다음에 실행할 정확한 명령"을 보여줍니다.

```powershell
# Windows (PowerShell) — 실행 정책 우회가 표준
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```

```bash
# macOS / Linux
python -m venv .venv && . .venv/bin/activate && python scripts/bootstrap.py
```

> **`py` 런처가 깨져 있어도 자동 처리됩니다.** 일부 Windows에서는 `py -3`가 `No installed Python found!`로 실패합니다. `setup.ps1`은 `py -3`/`python`/`python3`를 **실제로 실행해 3.10+ 여부를 확인**하고, 성공하는 쪽으로 `.venv`를 만듭니다 — `py -3`가 실패하면 자동으로 `python`으로 fallback합니다.
> pip 설치가 한동안 조용해 멈춘 듯 보이면 정상입니다(대용량 휠 다운로드). 진행 로그를 보려면 `-VerbosePip`(예: `... -File scripts\setup.ps1 -VerbosePip`).

진행 단계: **① Python deps → ② 브라우저(Chromium) → ③ agent-browser → ④ preflight 검증.** 처음 한 번만 오래 걸리고(브라우저·패키지 다운로드), 이후엔 skip되어 빠릅니다.

설치 모드:

| 모드 | 명령 | 용도 |
|------|------|------|
| **full (표준)** | `setup.ps1` / `bootstrap.py` | Python + 브라우저 + **agent-browser** + 검증 전체 |
| `--core-only` | `... -CoreOnly` / `... --core-only` | agent-browser 제외하고 core만 (단, **표준은 full**) |
| `--skip-browser` | `... -SkipBrowser` / `... --skip-browser` | 브라우저가 이미 있는 환경의 빠른 재검증 |

### AI 에이전트에게 셋업 맡기기

아래를 **그대로 복사**해 Claude Code 또는 Codex에게 주세요:

```text
이 레포의 크롤링 환경을 셋업해줘.

1. Windows면 `powershell -ExecutionPolicy Bypass -File scripts\setup.ps1` 를,
   macOS/Linux면 venv 만들고 `python scripts/bootstrap.py` 를 실행해.
   - 단계별(Python deps → 브라우저 → agent-browser → preflight)로 진행되고
     이미 된 단계는 skip돼. 어느 단계에서 막혔는지 보고해줘.
   - venv가 안 만들어지면 `py -3 --version` 과 `python --version` 을 확인해.
     `py -3`가 실패하면(`No installed Python found!`) `python -m venv .venv` 로 직접 만들고
     이어서 `.\.venv\Scripts\python.exe scripts\bootstrap.py` 를 실행해.
   - PowerShell에서 npm/agent-browser 실행 정책 오류가 나면 npm.cmd / agent-browser.cmd 를 써.
   - 브라우저는 `scrapling install` 하나로 끝나(내부에서 playwright install chromium 수행).
     playwright install 을 또 돌리지 마.
   - pip이 오래 멈춘 듯 보이면 `--verbose-pip`(setup.ps1은 `-VerbosePip`)로 진행 로그를 봐.

2. 끝나면 `python scripts/preflight.py` 결과(PASS/WARN/FAIL)를 요약해줘.
   core(Python/Scrapling/Playwright)와 agent-browser를 구분해서, 막힌 단계와
   '다음에 실행할 명령'을 알려줘. agent-browser가 실패하면 "전체 설치 미완료"로 보고해.
```

### 수동 설치 (단계별)

Windows PowerShell 기준 — 실제 동작하는 명령입니다.

```powershell
# 0) venv (최초 1회).  활성화가 막히면 새 세션을: powershell -ExecutionPolicy Bypass
py -3 -m venv .venv               # 실패하면(No installed Python found!) → python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 1) Python 패키지 (scrapling[fetchers] + openpyxl + pytest)
pip install -r requirements.txt

# 2) 브라우저(Chromium) — 이거 하나면 됨
scrapling install                 # 또는:  .\.venv\Scripts\scrapling.exe install

# 3) agent-browser (표준 정찰 도구) — PowerShell은 .cmd
npm.cmd install -g agent-browser
agent-browser.cmd install         # 없으면 Chrome for Testing 자동 설치

# 4) 검증 (단계별 PASS/WARN/FAIL — 설치는 안 함)
python scripts\preflight.py
```

**꼭 알아둘 점**
- `python -m scrapling` 은 **동작하지 않습니다**(`__main__` 없음). venv 활성화 후 `scrapling install`, 또는 `.\.venv\Scripts\scrapling.exe install` 을 쓰세요.
- `scrapling install` 이 내부적으로 `playwright install chromium` 을 수행합니다. **`playwright install` 을 따로 또 돌리지 마세요**(같은 다운로드 반복 → 시간 낭비). 이미 받았으면 즉시 끝납니다.
- PowerShell에서 `npm` / `agent-browser` 가 실행 정책 오류면 **`npm.cmd` / `agent-browser.cmd`**.
- 검증만 다시 하려면 `python scripts\preflight.py` (core만: `--core-only`).

### 문제가 생기면 (Windows 디버깅)

```powershell
# 1) 어떤 python 이 동작하는지 확인 (py 런처가 깨졌을 수 있음)
python --version       # 동작하면 이걸로 venv 생성
py -3 --version        # 'No installed Python found!' 면 py 런처가 깨진 것

# 2) py 가 안 되면 python 으로 직접 venv 생성 후 bootstrap
python -m venv .venv
.\.venv\Scripts\python.exe scripts\bootstrap.py

# 3) pip 이 진행 없이 멈춘 듯 보일 때 — 진행 로그를 보며 직접 설치
.\.venv\Scripts\python.exe -m pip install -r requirements.txt --progress-bar off -v

# 4) 최종 검증
.\.venv\Scripts\python.exe scripts\preflight.py
.\.venv\Scripts\python.exe -m pytest -q
```

> macOS / Linux는 위 명령에서 `py -3 -m venv` → `python3 -m venv`, 활성화 `. .venv/bin/activate`, `npm.cmd`→`npm`, `agent-browser.cmd`→`agent-browser` 로 바꾸면 동일합니다.

### 핵심 도구 요약

| 도구 | 역할 | 설치 |
|------|------|------|
| **Scrapling** (`[fetchers]`) | 데이터 수집 (HTTP·브라우저, 셀렉터 자가치유). fetcher 런타임(curl_cffi/playwright/patchright 등)이 함께 들어옴 | `pip install -r requirements.txt` |
| **Chromium** | 브라우저 렌더링(DynamicFetcher/StealthyFetcher) | `scrapling install` (playwright Chromium 1회 다운로드) |
| **openpyxl** | 엑셀(.xlsx) 출력 | (requirements.txt에 포함) |
| **agent-browser** | **표준 정찰 도구** — 구조 파악·네트워크 감시 (양 host 공통) | `npm.cmd install -g agent-browser` + `agent-browser.cmd install` |
| **Chrome / Chrome for Testing** | Akamai 등 고급 안티봇 대응 (CDP) | `agent-browser install` 이 함께 처리 |

---

## 작동 방식 (요약)

에이전트는 다음 흐름으로 움직입니다. 자세한 규칙은 `.claude/skills/web-crawler/SKILL.md`에 있습니다.

```
1.  입력 파싱 (URL + 수집 항목 추출)
1-A. 도메인 프로필 조회 ── 있음 + 재사용 OK ──→ 3 으로 점프 (정찰 스킵)
1-B. 공인 우회로 확인 (공개 API·RSS·oEmbed 등) ── 있음 ──→ 4 로 점프 (정찰 스킵)
2.  정찰 (사이트 구조·API·페이지네이션 파악)
2-A. 인증 처리 (로그인 필요 시 — 사용자가 직접 로그인, 쿠키만 추출)
3.  수집 전략 + Fetcher 선택
4.  수집 스크립트(crawl_script.py) 생성 & 실행
5.  데이터 검증 (소프트블록 → 건수·빈값·PII 순)
5-A. 도메인 프로필 저장 (필수 — 다음 수집 가속)
6.  엑셀 생성 & 결과 보고
```

> **소프트블록**이란 차단인데 겉으로는 성공(HTTP 200)처럼 보이는 응답입니다. 빈 껍데기 페이지를 정상 데이터로 착각하고 계속 긁으면 차단이 굳어지므로, 다른 검증보다 **먼저** 확인합니다.

### 수집 방법(Fetcher)은 사이트에 따라 자동 선택

```
API 발견?        → FetcherSession (가장 빠름)
안티봇 보호?      → Cloudflare        : StealthyFetcher
                  그 외 WAF·단순 403 : curl_cffi 경량 그리드 → 실패 시 브라우저
                  Akamai/고급 WAF    : Chrome CDP (앞 단계 건너뜀)
JS 렌더링 필요?   → DynamicFetcher (브라우저 렌더링)
그 외            → Fetcher (기본 HTTP)
```

수집이 실패하면 **가벼운 것부터** 자동으로 단계적 전환(에스컬레이션)합니다 — `Fetcher → curl_cffi 그리드 → StealthyFetcher → DynamicFetcher → Chrome CDP`. 브라우저를 띄우기 전에 저비용 방법을 먼저 시도하는 구조입니다. 단 Akamai는 앞 단계가 통하지 않으므로 곧장 Chrome CDP로 갑니다.

---

## 도메인 프로필 (재수집 가속)

같은 사이트를 다시 수집할 때 정찰을 건너뛸 수 있도록, 수집에 성공하면 `fingerprints/<도메인>/profile.json`에 "수집 레시피"를 저장합니다. 다음번엔 이 레시피만 보고 바로 수집에 들어갑니다.

```json
{
  "domain": "wanted.co.kr",
  "fetcher_type": "FetcherSession",
  "antibot_type": "none",
  "antibot_strategy": "none",
  "site_type": "api",
  "selectors": {},
  "pagination": { "type": "offset", "param": "offset", "limit": 20 },
  "api_endpoints": [{ "url": "...", "method": "GET", "params": {}, "field_mapping": {} }],
  "notes": "다음 사람이 정찰 없이 바로 수집할 수 있는 결정적 한두 줄",
  "last_used": "2026-03-25"
}
```

- **저장은 필수.** Step 5-A 게이트 — 빠뜨리면 다른 머신/세션에서 노하우가 사라진다.
- **`notes` 비우지 않기.** "Akamai라 chrome_cdp 필수", "review API는 HTML 반환" 같은 결정적 메타 정보.
- **자격증명 박지 않기.** profile.json은 commit 대상이므로 API key/토큰/쿠키는 별도 파일로 분리.

<!-- BEGIN GENERATED: domain-list -->
<!-- 이 블록은 scripts/sync_domain_list.py 가 생성한다. 직접 수정하지 말 것. -->

현재 20개 도메인 프로필이 포함되어 있습니다: `books.toscrape.com`, `brand.naver.com`, `builtini.co.kr`, `celimax.co.kr`, `coupang.com`, `data.seoul.go.kr`, `db.itkc.or.kr`, `fin.land.naver.com`, `g2b.go.kr`, `guesskorea.com`, `made-in-china.com`, `oliveyoung.co.kr`, `smartstore.naver.com`, `wanted.co.kr`, `www.11st.co.kr`, `www.fss.or.kr`, `www.gsmarena.com`, `www.instagram.com`, `www.k-startup.go.kr`, `www.kurly.com`.

<!-- END GENERATED: domain-list -->

---

## 레포 구조

**이 레포 하나가 전부입니다.** 별도의 내부 저장소는 없습니다. 커밋되는 것은 코드와 수집 레시피뿐이고, **실제로 수집한 데이터는 어떤 경로로도 커밋되지 않습니다.**

| 경로 | 상태 | 내용 |
|------|------|------|
| `scripts/` · `.claude/` · `.codex/` | ✓ tracked | 공통 모듈, 에이전트 지시서·스킬 |
| `fingerprints/<도메인>/profile.json` | ✓ tracked | 도메인 수집 레시피 (자격증명 제외) |
| `output/` | 로컬 전용 | 수집 결과물 — 제3자 콘텐츠·PII 가능 |
| `autoresearch-web-crawler/` | 로컬 전용 | 스킬 평가 실험 run 데이터 |
| `docs/` | 로컬 전용 | 내부 기획·설계 노트 |
| `fingerprints/elements_storage.db` | 로컬 전용 | Scrapling 셀렉터 자가치유 DB |
| `**/cookies*.json` · `**/auth*.json` | 로컬 전용 | 로그인 쿠키·토큰 |

### 출력 디렉터리

```
output/                              # gitignore — 수집 결과물
└── <도메인>/                        # 예: coupang.com
    ├── <주제_YYYYMMDD_HHMMSS>/      # 실행 건별 폴더
    │   ├── crawl_result.xlsx        # 최종 엑셀
    │   ├── raw_data.json            # 원시 데이터
    │   ├── progress.json            # 진행 상황 (중단 시 이어서 수집)
    │   └── crawl_script.py          # 생성된 수집 스크립트
    └── cookies.json                 # ignored — 로그인 쿠키 (같은 사이트의 모든 작업이 공유)

fingerprints/                        # gitignore + whitelist
├── elements_storage.db              # ignored — Scrapling 셀렉터 자가치유 DB (전역 공유)
└── <sanitized_domain>/              # 예: coupang_com, www_kurly_com
    ├── profile.json                 # ✓ tracked — 도메인 수집 레시피
    └── recipe.md                    # ✓ tracked (선택) — 추가 노트
```

## 안전 규칙 (에이전트가 항상 지킴)

- **CAPTCHA 자동 우회 안 함** — 뜨면 사용자에게 보고 후 중단
- **로그인 자격증명 저장 안 함** — 사용자가 직접 로그인 → 쿠키만 추출
- **robots.txt 차단 시 사용자에게 확인**
- **PII(전화번호·주민번호·이메일 등) 감지 시 경고·보고**
- **불법 스크래핑(저작권·개인정보 대량수집·ToS 위반) 거절**

## .gitignore 정책

단일 public 레포이므로, 수집한 데이터가 실수로 공개되지 않도록 세 겹으로 막습니다.

1. **수집 결과물 통째 차단** — `output/`, `crawl_data/`, `autoresearch-web-crawler/`, `docs/`. 스크랩한 제3자 콘텐츠(리뷰 본문·작성자명 등)가 레포에 들어가지 않습니다.
2. **fingerprints whitelist** — `fingerprints/**`를 통째로 ignore하되 `profile.json`과 `recipe.md`만 whitelist로 commit.
3. **자격증명 재차단** — `**/cookies*.json`, `**/auth*.json`, `**/*token*.json`, `**/*secret*` 를 whitelist **뒤에** 배치해 last-match-wins로 다시 막습니다.

```bash
git check-ignore -v <path>           # 어떤 패턴에 막혔는지 확인
git diff --cached --name-only        # commit 직전 무엇이 올라가는지 확인
```

## 참고 문서

- `CLAUDE.md` — 메인 에이전트 지시서 (양 host SSOT)
- `AGENTS.md` — Codex 실행 계약 (최초 셋업 포함)
- `.claude/skills/web-crawler/SKILL.md` — 워크플로우 (Step 1-A/5-A 게이트 포함)
- `.claude/skills/web-crawler/references/` — fetcher-patterns / antibot-strategies / troubleshooting
