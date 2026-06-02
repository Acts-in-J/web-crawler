---
name: web-crawler
description: URL과 수집 항목을 받아 사이트를 정찰하고 데이터를 수집하여 엑셀로 출력하는 범용 웹 크롤링 에이전트. 사용자가 URL과 함께 데이터 수집/크롤링/스크래핑을 요청하거나, 웹사이트에서 정보를 추출하고 싶다고 할 때 반드시 이 스킬을 사용한다. "이 사이트에서 ~를 모아줘", "~를 크롤링해줘", "입찰공고를 수집해줘" 등의 요청에도 트리거된다.
---

# 웹 크롤링 워크플로우

## 절대 규칙

1. **수집에는 Scrapling 또는 Playwright만 사용한다.** `requests`, `urllib`, `httpx`, `BeautifulSoup`로 직접 수집하지 않는다.
2. **agent-browser는 정찰 전용이다.** agent-browser에서 `page.evaluate()`로 데이터를 추출하거나 DOM을 파싱하여 수집하는 것은 금지. agent-browser는 구조 파악, 스크린샷, 네트워크 감시에만 사용한다.
3. **반드시 crawl_script.py를 생성하고 실행한다.** 스크립트 없이 인라인으로 수집하지 않는다.
4. **정찰과 수집의 역할을 분리한다.** 정찰(agent-browser) → 수집(crawl_script.py 내 Scrapling/Playwright) → 출력(openpyxl).

> **규칙 1 예외 — Playwright 직접 사용이 허용되는 경우:**
> SPA 세션 보호 사이트(WebSquare, 내부 API 403 등)에서는 crawl_script.py 안에서 Playwright를 직접 사용하여 SPA를 로드하고, `page.on("response")`로 XHR 응답을 인터셉트하여 데이터를 수집할 수 있다. 이 경우에도 agent-browser가 아닌 Playwright sync_api를 사용한다.

## 워크플로우 개요

```
Step 1: 입력 파싱 → Step 1-A: 도메인 프로필 확인
    ↓
Step 2: 정찰 (agent-browser) → Step 2-A: 인증 처리 (필요 시)
    ↓
Step 3: 사이트 분류 & 수집 전략 결정 ← 핵심 의사결정
    ↓
Step 4: 수집 코드 생성 & 실행
    ↓
Step 5: 데이터 검증
    ↓
Step 5-A: 도메인 프로필 저장 (필수 게이트, 누락 시 파이프라인 미완료)
    ↓
Step 6: 엑셀 출력 & 보고
```

---

## Step 1: 입력 파싱

사용자 메시지에서 추출:
- **URL**: 수집 대상 주소
- **수집 항목**: 데이터 필드 목록
- **특수 조건**: 로그인, 필터, 정렬, 건수 제한 등

불명확하면 되묻기. 최소 요건: URL 1개 + 수집 항목 1개.

### Step 1-A: 도메인 프로필 확인

재수집 시 기존 프로필이 있으면 정찰을 스킵할 수 있다.

```python
from domain_profile import DomainProfile
profile_mgr = DomainProfile()
if profile_mgr.exists(domain):
    profile = profile_mgr.load(domain)
    # "이전 설정을 재사용할까요?" → Yes면 Step 3으로
```

수집 성공 후 프로필 저장:
```python
profile_mgr.save(domain, {
    "domain": domain,
    "fetcher_type": "<SELECTED_FETCHER>",
    "site_type": "<static|csr|api|spa_session|akamai>",
    "selectors": {<MAPPING>},
    "pagination": {<CONFIG>},
    "api_endpoints": [<LIST>],
    "notes": "<특이사항>",
})
```

---

## Step 2: 정찰 (agent-browser)

### 정찰 규칙
- agent-browser 접근 **최대 2회** 시도
- 2회 실패 시 Chrome CDP 전략으로 전환
- 같은 도메인에 **5분 내 3회 이상 접근하지 않음**

### 정찰 항목
1. 스냅샷 + DOM 구조 확인
2. 데이터 로딩 방식 판단 (SSR / CSR / API / SPA 세션 보호 / infinite scroll)
3. CSS 셀렉터 식별
4. pagination 방식 (URL 파라미터 / next 버튼 / infinite scroll / scroll 페이지네이션)
5. 총 데이터 건수 추정

### 네트워크 감시 (필수)

agent-browser에서 네트워크 요청을 캡처하여 API를 식별한다.

**API 식별 2단계:**
1. **URL 패턴 휴리스틱**: `/api/`, `/graphql/`, `/v1/` 포함, `application/json` 응답, 광고/분석 제외
2. **LLM 응답 분석**: 후보 API의 JSON 응답에서 사용자 요청 항목과 매칭되는 필드 식별

**SPA 세션 보호 감지 (중요):**

정찰 중 다음을 확인하면 "SPA 세션 보호 사이트"로 분류:
- 브라우저에서는 검색/조회가 되지만 API 직접 호출 시 403/401 반환
- WebSquare, SAP UI5, Oracle ADF 등 엔터프라이즈 SPA 프레임워크 사용
- URL이 변하지 않는 SPA 내비게이션 (메뉴 클릭해도 URL 동일)
- XHR 요청에 서버 측 세션 토큰이 자동 포함됨

### Step 2-A: 인증 처리

로그인이 필요한 경우:
1. 사용자에게 안내 → agent-browser로 로그인 페이지 열기
2. 수동 로그인 완료 대기
3. 쿠키/JWT 추출 → `save_cookies()` 또는 `save_auth_token()`으로 저장

---

## Step 3: 사이트 분류 & 수집 전략 결정

정찰 결과에 따라 사이트를 분류하고, 적합한 수집 전략을 선택한다. 이것이 전체 워크플로우에서 가장 중요한 결정이다.

### 사이트 분류 의사결정 트리

```
정찰에서 API 발견?
├── Yes → API 직접 호출 가능?
│   ├── Yes → (A) API 직접 수집 (FetcherSession)
│   └── No (403/세션 필요) → (E) SPA 세션 인터셉트 (Playwright)
│
└── No → 안티봇 보호?
    ├── Akamai 감지 → (D) Chrome CDP 전략
    ├── Cloudflare 감지 → (C) StealthyFetcher
    └── 없음 → JS 렌더링 필요?
        ├── Yes → (B-2) DynamicFetcher
        └── No → (B-1) Fetcher (기본 HTTP)
```

### 각 전략의 코드 패턴

> 📖 각 전략의 상세 코드 템플릿은 `references/fetcher-patterns.md`를 참조한다.

| 전략 | Fetcher | 적용 사이트 예시 | 참조 섹션 |
|------|---------|-----------------|----------|
| **(A) API 직접** | FetcherSession | wanted.co.kr, 공개 API 사이트 | fetcher-patterns.md § API 수집 |
| **(B-1) 정적 HTML** | Fetcher | books.toscrape.com, 정적 게시판 | fetcher-patterns.md § 정적 HTML |
| **(B-2) JS 렌더링** | DynamicFetcher | kurly.com (Next.js CSR) | fetcher-patterns.md § 동적 사이트 |
| **(C) Cloudflare** | StealthyFetcher | CF 보호 사이트 | antibot-strategies.md § Cloudflare |
| **(D) Akamai/WAF** | Chrome CDP | coupang.com | antibot-strategies.md § Akamai |
| **(E) SPA 세션** | Playwright 인터셉트 | g2b.go.kr (WebSquare) | antibot-strategies.md § SPA 세션 |

### 안티봇 감지 시그널

> 📖 상세 감지 로직과 대응 전략은 `references/antibot-strategies.md`를 참조한다.

**Akamai**: `_abck`/`bm_sz`/`ak_bmsc` 쿠키, `Access Denied` + `errors.edgesuite.net`, 알려진 사이트 (coupang.com)
**Cloudflare**: `cf_clearance` 쿠키, Cloudflare 챌린지 페이지
**SPA 세션 보호**: 브라우저에서는 정상 작동하나 API 직접 호출 시 403 (ErrorCode -801 등)

### Step 3.5: API 필드 매핑 검증

API 사용 시, 코드 생성 전에 샘플 5건으로 필드 매핑을 검증한다:
1. API 1페이지 호출 → JSON 구조 확인
2. 사용자 요청 필드 ↔ API 필드 매핑표 작성
3. null/빈값 비율, 병합 필요 여부 확인

---

## Step 4: 수집 코드 생성 & 실행

Step 3에서 결정한 전략에 맞는 코드 패턴을 `references/fetcher-patterns.md`에서 참조하여 crawl_script.py를 생성한다.

### 모든 수집 코드의 필수 요소

1. **try/except + continue** — 한 페이지 실패가 전체를 중단시키지 않도록
2. **consecutive_errors 추적** — 연속 5회 실패 시에만 최종 중단
3. **RateLimiter** — `scripts/utils.py`의 RateLimiter 사용
4. **부분 데이터 저장** — 100건마다 raw_data.json에 중간 저장
5. **FETCHER_CHAIN 에스컬레이션** — 연속 2회 실패 시 상위 Fetcher로 전환 (Akamai/SPA 세션 제외)

> **except 블록에서 반드시 `continue`** — 절대 `break`로 중단하지 않는다.

### 출력 디렉토리 구조

```
output/<도메인>/<주제_YYYYMMDD_HHMMSS>/
├── crawl_script.py    # 생성된 수집 스크립트
├── raw_data.json      # 원시 데이터
├── crawl_result.xlsx   # 엑셀 결과
└── progress.json       # 진행 상황
```

### 셀렉터 자가 치유

```python
# 첫 수집: 핑거프린트 저장
items = page.css("<SELECTOR>", auto_save=True,
    storage_args={"storage_file": "./fingerprints/elements_storage.db"})

# 이후: 자가 치유
items = page.css("<SELECTOR>", adaptive=True, auto_save=True,
    storage_args={"storage_file": "./fingerprints/elements_storage.db"})
```

---

## Step 5: 데이터 검증

1. 수집 건수 확인 (목표 대비 %)
2. 각 필드별 null/빈값 비율 체크
3. 샘플 확인 (처음 5건 + 마지막 5건)
4. 중복 제거
5. PII 감지: `detect_pii(data)` 실행
6. robots.txt 제한 발견 시 사용자에게 경고

95% 이상 유효 데이터면 통과. 미달 시 Step 4 재시도 (최대 2회).

> 📖 수집 실패 시 원인 진단은 `references/troubleshooting.md`를 참조한다.

---

## Step 5-A: 도메인 프로필 저장 (필수 게이트)

검증을 통과한 직후, **반드시** `fingerprints/<도메인>/profile.json`을 저장하거나 갱신한다. 이걸 빼먹으면 다음 수집 시 정찰부터 다시 해야 하고, 다른 머신/세션에서는 노하우가 완전히 사라진다.

```python
from domain_profile import DomainProfile
from datetime import date

profile_mgr = DomainProfile()  # base_dir=./fingerprints
profile_mgr.save(domain, {
    "domain": domain,
    "fetcher_type": "<FetcherSession|StealthyFetcher|DynamicFetcher|chrome_cdp|API_SESSION>",
    "antibot_type": "<none|cloudflare|akamai|naver_antibot|other>",
    "antibot_strategy": "<none|stealthy|chrome_cdp>",
    "site_type": "<static|csr|api|spa_session|akamai>",
    "selectors": {<필드: 셀렉터>},
    "pagination": {<config — type/param/limit 등>},
    "api_endpoints": [{<url, method, params, field_mapping>}],
    "notes": "<재수집 시 결정적인 한두 줄: 인증 필요 여부, 페이지네이션 트릭, 봇 차단 회피 포인트>",
    "last_used": str(date.today()),
})
```

### 게이트 규칙

1. **`notes` 필드는 비워두지 않는다.** 다음 사람(미래의 나 포함)이 정찰 안 하고도 바로 수집할 수 있는 한두 줄의 결정적 정보를 적는다 — "API key는 OK, job_group_id=518이 일반 목록", "Akamai 보호라 Chrome CDP 필수", "review API는 POST에 originProductNo 필요" 같은 형식.
2. **인증 토큰/쿠키/내부 API key는 profile.json에 박지 않는다.** `.gitignore`가 `cookies*.json`/`auth*.json`/`*token*.json`/`*secret*`은 차단하지만 profile.json은 commit 대상이므로 평문 자격증명이 새지 않게 분리한다.
3. **fetcher_type / antibot_strategy 둘은 무조건 채운다.** 다음 실행에서 Step 1-A가 이 두 값만 보고 fetcher chain을 건너뛰므로, 빈 값이면 게이트 기능을 못 한다.
4. **이미 profile이 있으면 `last_used`만 갱신하지 말고**, 이번 수집에서 새로 알아낸 게 있으면 `notes`와 endpoint/selector를 누적/수정한다.

저장이 끝나면 Step 6으로 진행. profile.json 저장 실패 시 수집 결과는 살아있어도 **"파이프라인 미완료"**로 보고하고 사용자에게 원인을 알린다 (디스크 권한, 스키마 누락 등).

---

## Step 6: 엑셀 출력 & 보고

```python
from export_excel import export_to_excel
export_to_excel(data, filepath)
```

### 완료 보고 항목
- 엑셀 파일 경로
- 수집 건수 / 목표 건수 (%)
- 각 필드별 채움률
- 누락/에러 건수
- 소요 시간
- 사용된 Fetcher 유형
- **`fingerprints/<도메인>/profile.json` 저장 여부 (신규 / 갱신 / 실패)** — 실패면 사유 명시

---

## 레퍼런스 가이드

| 파일 | 내용 | 언제 참조 |
|------|------|----------|
| `references/fetcher-patterns.md` | 모든 수집 패턴의 코드 템플릿 | Step 4에서 crawl_script.py 생성 시 |
| `references/antibot-strategies.md` | Akamai, SPA 세션, Cloudflare 대응 전략 | Step 3에서 안티봇 감지 시 |
| `references/troubleshooting.md` | 실패 사례와 해결책 | 수집 실패 시 원인 진단 |
