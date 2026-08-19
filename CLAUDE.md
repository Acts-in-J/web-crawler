# 범용 웹 크롤링 에이전트

## 프로젝트 개요

이 프로젝트는 사용자가 URL과 수집 항목을 자연어로 설명하면, 자동으로 해당 웹사이트를 정찰하고 데이터를 대량 수집하여 엑셀 파일로 정리해주는 에이전트입니다.

---

## 최초 환경 셋업 (클론 직후 1회, 수집 전 확인)

수집 시도 전에 환경을 준비한다. **한 명령**으로 단계별 설치+검증(이미 된 단계는 skip):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1     # Windows (venv 자동 생성)
```
```bash
python -m venv .venv && . .venv/bin/activate && python scripts/bootstrap.py   # macOS/Linux
```

수동/디버깅 시 실제 동작 명령:
```bash
pip install -r requirements.txt          # scrapling[fetchers] 포함 — fetcher 런타임 일괄
scrapling install                        # Chromium 1회 (내부에서 playwright install chromium 수행 — 따로 또 X)
npm.cmd install -g agent-browser ; agent-browser.cmd install   # 표준 정찰 도구 (PowerShell은 .cmd)
python scripts/preflight.py              # 검증: core / agent-browser 분리 PASS·WARN·FAIL
```

- `python -m scrapling`은 동작 안 함 → `scrapling install`(venv 활성화) 또는 `.\.venv\Scripts\scrapling.exe install`.
- 검증은 `scripts/preflight.py`(설치 안 함). core 통과·agent-browser 실패면 "전체 설치 미완료"(exit 1).
- 전체 가이드(비개발자용 포함)는 `README.md`의 "처음 설치하기" 참조.

---

## ★ 절대 규칙 0: 도메인 히스토리 우선 (모든 수집의 시작)

새 수집 요청을 받으면 **정찰하기 전에 반드시** 이 두 가지를 먼저 본다:

1. **`fingerprints/<sanitized_domain>/profile.json`** — 그 도메인의 검증된 수집 레시피 (fetcher_type, antibot_type/strategy, selectors, api_endpoints, pagination, notes)
2. **`output/<도메인>/`** — 그 도메인에서 이전에 실행된 수집 작업 폴더들 (그 안의 `crawl_script.py`/`raw_data.json`은 profile.json에 안 박힌 미세 디테일의 보조 reference)

### 운영 흐름

```
[수집 요청] → 도메인 추출 → fingerprints/<sanitized_domain>/profile.json 조회
                                    │
                ┌───────────────────┴───────────────────┐
                │ 프로필 있음                            │ 프로필 없음
                ▼                                       ▼
       ┌────────────────────────┐         ┌─────────────────────────┐
       │ 1. notes 먼저 읽고     │         │ 정찰 (Step 2) 부터 시작 │
       │    전략에 반영          │         │ — 모든 단계 풀 실행      │
       │ 2. fetcher_type/       │         └─────────────────────────┘
       │    antibot_strategy     │
       │    그대로 채택          │
       │ 3. selectors/endpoints │
       │    재사용 시도          │
       │ 4. last_used가 3개월+  │
       │    오래됐거나 사용자가  │
       │    "최신 구조로"를      │
       │    명시했으면 정찰 추가  │
       │ 5. 검증 실패하면 셀렉터/│
       │    엔드포인트만 정찰    │
       └────────────────────────┘
                │
                ▼
       정찰 스킵하고 Step 3 (수집 전략 수립)으로 점프
```

### 절대 안 되는 것

- profile.json이 있는데 그걸 무시하고 정찰부터 다시 하기 — 5~20분의 비싼 작업을 매번 반복하는 행위
- profile.json의 `notes` 필드를 읽지 않고 전략 세우기 — notes에는 LLM이 자동으로 못 알아내는 결정적 메타 정보가 박혀 있다 ("Akamai라 chrome_cdp 필수", "review API는 JSON 아니라 HTML 반환" 등)
- 수집 성공 후 profile.json 저장/갱신을 빠뜨리기 — Step 5-A 필수 게이트. 누락 시 "파이프라인 미완료" 보고

<!-- BEGIN GENERATED: domain-list -->
<!-- 이 블록은 scripts/sync_domain_list.py 가 생성한다. 직접 수정하지 말 것. -->

### 알려진 도메인 (19개 profile commit됨)

`books.toscrape.com`, `brand.naver.com`, `builtini.co.kr`, `celimax.co.kr`, `coupang.com`, `data.seoul.go.kr`, `db.itkc.or.kr`, `fin.land.naver.com`, `g2b.go.kr`, `guesskorea.com`, `made-in-china.com`, `oliveyoung.co.kr`, `smartstore.naver.com`, `wanted.co.kr`, `www.11st.co.kr`, `www.fss.or.kr`, `www.gsmarena.com`, `www.instagram.com`, `www.kurly.com` — 이 도메인들은 정찰 없이 바로 수집 시도 가능.

<!-- END GENERATED: domain-list -->

### profile 조회/저장 코드

```python
from domain_profile import DomainProfile
profile_mgr = DomainProfile()  # base_dir=./fingerprints

# Step 1-A: 조회
if profile_mgr.exists(domain):
    profile = profile_mgr.load(domain)
    # notes/fetcher_type/antibot_strategy/api_endpoints/selectors 활용

# Step 5-A: 수집 성공 후 저장 (필수 게이트)
profile_mgr.save(domain, {
    "domain": domain,
    "fetcher_type": "...",
    "antibot_type": "...",
    "antibot_strategy": "...",
    "site_type": "...",
    "selectors": {...},
    "pagination": {...},
    "api_endpoints": [...],
    "notes": "<다음 사람이 정찰 없이 바로 수집할 수 있는 결정적 한두 줄>",
    "last_used": "YYYY-MM-DD",
})
```

새 도메인 프로필을 처음 만들었다면 저장 직후 목록을 재생성한다 (위 "알려진 도메인" 블록은 생성물):

```bash
python scripts/sync_domain_list.py          # CLAUDE.md / README.md 목록 재생성
python scripts/sync_domain_list.py --check  # 어긋나면 exit 1
```

> ⚠️ profile.json은 git commit 대상이다. 토큰/쿠키/API key는 절대 박지 말고 `cookies.json`/`auth.json` 같은 별도 파일(.gitignore 차단됨)에 분리.

---

## 범위 / 운영 안전 규칙

**포함**: 사이트 정찰, 구조 파악, 로그인 대응, 동적 콘텐츠, pagination, 대량 데이터 수집, 엑셀 출력.

**제외 (절대 안 함)**:
- **CAPTCHA 자동 우회 시도 금지** — reCAPTCHA/hCaptcha 등이 뜨면 사용자에게 보고 후 중단. agent-browser로 수동 풀이를 요청할 수는 있음
- **로그인 자격증명 자동 저장 금지** — ID/PW를 코드/메모리/파일에 저장하지 않는다. 사용자가 직접 브라우저에서 로그인 → 쿠키만 추출
- **불법적 스크래핑 거절** — 저작권 위반, 개인정보 대량 수집, ToS 명시적 위반은 진행 전 사용자 확인 후 거절
- **robots.txt 제한 발견 시 사용자 확인** — `Disallow: /` 또는 수집 대상 경로 차단 시 진행 여부를 묻는다
- **PII 감지 (필수)** — 수집 데이터에 전화번호/주민번호/이메일 등이 섞이면 `detect_pii(data)`로 경고하고 사용자에게 보고

---

## 핵심 도구

- **agent-browser** (Playwright): 정찰 전용 — 사이트 구조 파악, 네트워크 감시, 수동 로그인, 시각적 확인
- **Scrapling** (Python): 수집 전용 — HTTP/브라우저 기반 데이터 수집, 셀렉터 자가 치유
- **openpyxl** (Python): 엑셀 파일 생성
- **DomainProfile** (`scripts/domain_profile.py`): 도메인 히스토리 load/save — 절대 규칙 0의 실행 도구

## 도구 역할 분리 원칙

| 작업 | 도구 | 이유 |
|------|------|------|
| **도메인 히스토리 조회/저장** | **DomainProfile (`scripts/domain_profile.py`)** | **재정찰 비용 회피 — 절대 규칙 0** |
| 사이트 열어서 구조 파악 | agent-browser | 시각적 확인, 네트워크 감시 가능 |
| 수동 로그인 + 쿠키/JWT 추출 | agent-browser | 사용자 상호작용 필요 |
| 대량 데이터 수집 | Scrapling | 빠름, Fetcher 계층, 자가 치유 |
| Akamai/Naver antibot 수집 | Chrome CDP (`scripts/chrome_cdp.py`) | StealthyFetcher로 못 뚫림 |
| 진행상황 체크포인트 | `scripts/progress.py` | 장시간 수집 시 pause/resume 지원 |
| 엑셀 출력 | openpyxl (`scripts/export_excel.py`) | 공통 모듈 |

**절대 agent-browser로 대량 수집하지 않는다.** 정찰과 수집은 분리.
**절대 profile 조회 없이 정찰부터 시작하지 않는다.** profile 우선.

## Fetcher 선택 의사결정 트리

```
Step 0: fingerprints/<sanitized_domain>/profile.json 있나? ──Yes──→
   │      └→ profile.fetcher_type / antibot_strategy 그대로 채택
   │         (재정찰 없이 Step 3로 점프, 단 last_used 3개월+이면 보강 정찰)
   No
   │
Phase 0: 공인 우회로 있나? ──Yes──→ yt-dlp / RSS·Atom / oEmbed / Jina(r.jina.ai)
   │  (profile 조회 직후, 정찰 전 — SKILL.md Step 1-B)   └→ 정찰 스킵, 바로 수집
   No
   │
API 발견? ──Yes──→ FetcherSession (가장 빠르고 안정적)
   │
   No
   │
안티봇 보호? ──Yes──→ 어떤 유형?
   │                    │
   │                    ├─ Cloudflare → StealthyFetcher
   │                    │
   │                    ├─ 기타 WAF(DataDome/PerimeterX/F5)·단순 403
   │                    │     → curl_cffi 경량 그리드 먼저 (브라우저 앞 티어)
   │                    │       실패 시 → StealthyFetcher → DynamicFetcher
   │                    │
   │                    └─ Akamai/고급 WAF → Chrome CDP 전략 (바로 이동)
   │                         ※ StealthyFetcher, curl_cffi 시도하지 않음
   │
   No
   │
JS 렌더링 필요? ──Yes──→ DynamicFetcher (Playwright 브라우저 렌더링)
   │
   No
   │
Fetcher (기본 HTTP, 가장 가벼움)
```

> **에스컬레이션 순서 = 가벼운 것부터:** 평문 Fetcher → **curl_cffi 그리드(브라우저 X)** → StealthyFetcher → DynamicFetcher → Chrome CDP. 단 Akamai는 예외(curl_cffi/Stealthy 건너뛰고 바로 CDP). 상세 코드는 `references/fetcher-patterns.md § F`, capability 판정 근거는 `references/antibot-strategies.md § WAF capability 라우팅`.

> profile.json이 있는 도메인은 Akamai 탐지 시그널을 따로 안 봐도 `antibot_type` 필드로 즉시 판정된다 (예: coupang.com → akamai → chrome_cdp 직행).

### Akamai 탐지 시그널

다음 중 하나라도 발견되면 Akamai/고급 WAF로 판단하고 즉시 Chrome CDP로 전환:
- `Access Denied` + `errors.edgesuite.net` 참조
- `_abck`, `bm_sz`, `ak_bmsc` 쿠키 존재
- `sec-if-cpt-container` 챌린지 페이지

### Chrome CDP 전략 (Akamai/고급 WAF 대응)

```bash
# 1. Chrome 실행 (사용자 Chrome 종료 필요)
chrome.exe --remote-debugging-port=9222 \
  --user-data-dir="C:/temp/crawl_profile" \
  --no-first-run --no-default-browser-check <URL>

# 2. 연결
# scripts/chrome_cdp.py 유틸리티 사용
# 또는 Playwright: p.chromium.connect_over_cdp("http://localhost:9222")
```

## Spider 활용 기준

| 조건 | 방식 |
|------|------|
| ~500건 미만, 단일 리스트 | `FetcherSession` 순차 처리 |
| 500건 이상, 단일 리스트 | `Spider` + 단일 세션 (`concurrent_requests=5`) |
| 여러 카테고리 동시 수집 | `Spider` + multi-session routing |
| 장시간 수집 (1000건+) | `Spider` + `crawldir='./crawl_data'` (Ctrl+C 시 자동 체크포인트, 재실행 시 이어서) |

## Infinite Scroll 처리 (우선순위)

1. **API 직행**: 정찰 시 infinite scroll의 underlying API 엔드포인트 발견 → `FetcherSession`으로 직접 호출 (가장 빠르고 안정적)
2. **DynamicFetcher 스크롤**: API 없으면 `DynamicSession`으로 스크롤 → `network_idle=True` 대기 → 추출 반복
3. **agent-browser 폴백**: 위 둘 다 실패 시 agent-browser로 수동 스크롤 → DOM 추출 → Scrapling Selector로 파싱

## Fetcher 에스컬레이션

수집 실패 시 자동으로 상위 Fetcher로 전환:
```
Fetcher → curl_cffi 그리드 → StealthyFetcher → DynamicFetcher → agent-browser 폴백 + 사용자 보고
   (Akamai는 이 체인을 건너뛰고 바로 Chrome CDP)
```

### 에러별 대응표

| 에러 유형 | 대응 |
|----------|------|
| HTTP 429 (Rate Limit) | 대기 시간 2배 증가 후 재시도. 누적 3회면 사용자 보고 |
| HTTP 403 (Forbidden) | curl_cffi 경량 그리드 먼저 → 실패 시 StealthyFetcher. Akamai 시그널이면 즉시 Chrome CDP |
| 가짜 200 (소프트블록) | `detect_softblock()`로 감지 — 챌린지/빈 셸/`_abck=~-1~`. 수집 강행 금지, 상위 티어 에스컬레이션 |
| Cloudflare Challenge | `StealthyFetcher(solve_cloudflare=True)` |
| 셀렉터 매칭 실패 | `adaptive=True`로 자가 치유 시도. 재실패 시 정찰 재실행 |
| 페이지 구조 완전 변경 | 정찰 재실행 → profile.json의 selectors 갱신 |
| JS 렌더링 실패 | DynamicFetcher로 에스컬레이션. `disable_resources=True`로 경량화 |
| 네트워크 타임아웃 | 3회 재시도 후 해당 페이지 스킵 + 로그 |
| **수집 데이터 0건** | **즉시 중단, 사용자 보고** (계속 시도하면 ban 위험) |
| Spider 중단 (Ctrl+C) | `crawldir`에서 자동 체크포인트, 재실행 시 이어서 수집 |

## 수집 코드 생성 원칙

에이전트는 **(profile.json + 정찰 결과 + 사용자 요청)** 세 가지를 합성해 Python 수집 코드를 동적으로 생성한다.

- **profile.json 우선 활용**: `selectors`/`api_endpoints`/`pagination`이 있으면 그걸 기반으로 코드 골격을 짠다. 새로 정찰해서 코드를 처음부터 쓰지 않는다.
- **`output/<도메인>/` 의 이전 `crawl_script.py` 참조**: profile.json에 안 박힌 미세 디테일(배치 사이즈, JS evaluate 패턴, 예외 처리)을 그대로 가져와 재사용. 단, raw_data.json은 PII 가능성 있으므로 구조만 확인하고 데이터는 읽지 않는다.
- `scripts/utils.py`를 import하여 RateLimiter, cookie 관리, 로깅 등 공통 기능 사용
- `scripts/export_excel.py`를 import하여 엑셀 출력
- `scripts/chrome_cdp.py`는 Akamai/Naver antibot 등 `antibot_strategy: chrome_cdp` 도메인에서 사용
- 수집 스크립트는 해당 작업의 출력 디렉터리 하에서 작업 (아래 출력 위치 참조)
- 셀렉터 핑거프린트는 `storage_args={"storage_file": "./fingerprints/elements_storage.db"}` 경로 사용
- **수집 성공 후 반드시 profile.json save/갱신** — 새로 알아낸 endpoint/selector/notes는 누적, `last_used`만 업데이트하지 말 것 (Step 5-A 게이트)
- **새 도메인이면 `python scripts/sync_domain_list.py` 실행** — CLAUDE.md/README.md의 "알려진 도메인" 목록은 profile.json에서 생성된다. 손으로 고치지 말 것 (`scripts/test_sync_domain_list.py`가 어긋남을 잡는다)

## 사용자 상호작용 규칙

### 에이전트가 자동 판단
- Fetcher 유형 선택
- 셀렉터 매핑
- pagination 방식
- 데이터 정제 수준
- 재시도/에스컬레이션

### 사용자에게 묻기
- robots.txt 제한 시 진행 여부
- 디테일 페이지 크롤링 여부 (기본은 리스트만)
- 로그인 수행 요청
- 수집 결과가 기대와 다를 때 계속 진행할지

### 검증 통과 기준 (Step 5)

- 수집 건수가 목표 대비 **90% 이상** (API/HTML 수집)
- 전체 데이터의 **95% 이상이 유효** (Step 5 검증 통과)
- 각 필드별 **null/빈값 비율 10% 이하**
- 미달 시 Step 4 재시도 (최대 2회). 재실패 시 수집된 데이터로 진행하되 사용자에게 경고

## Rate Limiting

| 규모 | HTTP 요청 간격 | 브라우저 내 fetch 간격 | Spider concurrent_requests |
|------|---------------|----------------------|---------------------------|
| ~100건 | 1초 | 200ms | 해당 없음 |
| 100~500건 | 1.5초 | 300ms | 해당 없음 |
| 500~2000건 | 1.5초 | 500ms | 5 |
| 2000건+ | 2초 + 100건마다 15초 휴식 | 1초 + 50건마다 3초 휴식 | 3 |

브라우저 내 fetch는 동일 세션이므로 서버 부하가 상대적으로 낮음. 단, 봇 탐지 행동 분석에 걸리지 않도록 최소 200ms 간격 유지.

## 스킬 참조

크롤링 워크플로우 상세는 `.claude/skills/web-crawler/SKILL.md`를 따른다. Step 1-A(프로필 조회) ↔ Step 5-A(프로필 저장) 게이트가 포함된 7단계 흐름. 추가 레퍼런스:
- `.claude/skills/web-crawler/references/fetcher-patterns.md` — Fetcher별 코드 템플릿
- `.claude/skills/web-crawler/references/antibot-strategies.md` — Akamai/Cloudflare/SPA 세션 대응
- `.claude/skills/web-crawler/references/troubleshooting.md` — 수집 실패 진단

## 출력/저장 디렉터리 구조

```
output/                                  # gitignore — 수집 결과물
└── <도메인>/                            # 사이트별 폴더 (예: coupang.com)
    ├── <크롤링주제_YYYYMMDD_HHMMSS>/    # 실행 건별 폴더
    │   ├── crawl_result.xlsx            # 최종 엑셀
    │   ├── raw_data.json                # 원시 수집 데이터
    │   ├── progress.json                # 진행상황
    │   └── crawl_script.py              # 생성된 수집 스크립트
    └── cookies.json                     # 사이트별 쿠키 (gitignore + cookies* 차단)

fingerprints/                            # gitignore + whitelist 정책
├── elements_storage.db                  # gitignore — Scrapling 셀렉터 자가 치유 DB (전역 공유)
└── <sanitized_domain>/                  # 예: coupang_com, www_kurly_com
    ├── profile.json                     # ★ tracked — 도메인 수집 레시피 (절대 규칙 0의 source)
    └── recipe.md                        # tracked (선택) — 추가 노트
```

### 규칙
- **사이트 폴더 (output/)**: 도메인 기준으로 하나만 생성 (예: `coupang.com`, `naver.com`)
- **작업 폴더**: `<주제요약>_<YYYYMMDD_HHMMSS>` 형식. 주제는 한글/영문 모두 가능, 공백은 `_`로 대체
- **쿠키**: 사이트 폴더 루트에 저장하여 같은 사이트의 모든 작업이 공유
- **셀렉터 핑거프린트**: `fingerprints/elements_storage.db` (전역 공유, ignore)
- **도메인 프로필**: `fingerprints/<sanitized_domain>/profile.json` (commit 대상). `sanitize_filename`은 `[^\w\-]`를 `_`로 치환 — 예: `coupang.com` → `coupang_com`, `made-in-china.com` → `made-in-china_com`

### .gitignore whitelist 정책

`fingerprints/**`로 전부 차단한 뒤 `!fingerprints/*/profile.json` + `!fingerprints/*/recipe.md`만 whitelist. 그 다음 줄에서 `**/cookies*.json`, `**/auth*.json`, `**/*token*.json`, `**/*secret*` 패턴을 **whitelist 다음에 배치** (last-match-wins로 자격증명 재차단).

- profile.json에 토큰/API key/JWT/세션 쿠키 박지 말 것 — commit되면 GitHub에 평문 노출됨
- 새 도메인 프로필 commit 전 `git diff --cached fingerprints/` 로 자격증명 누출 확인
- 검증: `git check-ignore -v <file>` 로 차단 패턴 확인 가능

## 쿠키 전달 흐름 (로그인 후)

```python
import json
from scrapling.fetchers import FetcherSession

# 1. agent-browser로 수동 로그인 후 쿠키 추출 → output/<도메인>/cookies.json 저장
with open("output/<도메인>/cookies.json") as f:
    cookies = json.load(f)

# 2. Scrapling Session에 주입
with FetcherSession(impersonate="chrome") as session:
    session.cookies.update(cookies)
    resp = session.get(url, stealthy_headers=True)
```

쿠키 파일은 `.gitignore`의 `**/cookies*.json` 패턴으로 자동 차단된다.
