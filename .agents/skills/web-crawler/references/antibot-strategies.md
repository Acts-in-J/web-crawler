# 안티봇 대응 전략 레퍼런스

사이트의 봇 차단 메커니즘별 대응 전략을 정리한 문서.
SKILL.md Step 3에서 안티봇이 감지되면 이 문서를 참조한다.

## 목차

1. [Akamai/고급 WAF → Chrome CDP](#akamai고급-waf--chrome-cdp)
2. [SPA 세션 보호 → Playwright 인터셉트](#spa-세션-보호--playwright-인터셉트)
3. [Cloudflare → StealthyFetcher](#cloudflare--stealthyfetcher)
4. [Fetcher 에스컬레이션 자동화](#fetcher-에스컬레이션-자동화)

---

## Akamai/고급 WAF → Chrome CDP

### 감지 시그널

다음 중 **하나라도** 발견되면 Akamai로 판단하고 즉시 Chrome CDP 전략으로 전환:
- `Access Denied` 페이지 + `errors.edgesuite.net` 참조
- `_abck`, `bm_sz`, `ak_bmsc` 쿠키 존재
- `sec-if-cpt-container` 챌린지 페이지
- 알려진 Akamai 사이트: coupang.com 등

### 핵심 원칙

- **일반 FETCHER_CHAIN을 사용하지 않는다** (StealthyFetcher, DynamicFetcher 시도하지 않음)
- **즉시 Chrome CDP로 전환한다**
- headless Chrome은 Akamai에 탐지됨 → **headed Chrome** 필수 (macOS/Windows)

### Chrome CDP 수집 코드 패턴

```python
# Akamai 사이트 전용 — FETCHER_CHAIN 사용 금지
import sys, os, json, time
sys.path.insert(0, './scripts')
from utils import RateLimiter, setup_logger
from export_excel import export_to_excel
from chrome_cdp import CDPSession

logger = setup_logger("akamai_crawler")
limiter = RateLimiter(delay=1.5)
results = []
consecutive_errors = 0

with CDPSession(url="<TARGET_URL>") as session:
    for page_num in range(1, max_pages + 1):
        try:
            limiter.wait()
            data = session.evaluate(f"""
                async () => {{
                    const resp = await fetch('<API_URL>?page={page_num}');
                    return await resp.json();
                }}
            """)
            # ... 데이터 파싱 ...
            consecutive_errors = 0
        except Exception as e:
            consecutive_errors += 1
            logger.warning(f"Page {page_num} error: {e}")
            if consecutive_errors >= 5:
                logger.error("5회 연속 실패, 중단")
                break
            continue

        # 100건마다 중간 저장
        if len(results) % 100 == 0 and results:
            with open(raw_data_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
```

### JS 일괄 수집 규모별 패턴

| 규모 | 방식 | 이유 |
|------|------|------|
| ~200건 | JS 일괄 실행 | 빠르고 간단 |
| 200~2000건 | JS 일괄 + 배치 분할 | 메모리 안전 |
| 2000건+ | Python 루프 + 체크포인트 | 중간 저장, 재시도 필수 |

```python
# 배치 분할 패턴 (200~2000건)
BATCH_SIZE = 50
all_data = []

for batch_start in range(1, TOTAL_PAGES + 1, BATCH_SIZE):
    batch_end = min(batch_start + BATCH_SIZE - 1, TOTAL_PAGES)
    batch = page.evaluate(f"""
        async () => {{
            const data = [];
            for (let p = {batch_start}; p <= {batch_end}; p++) {{
                const resp = await fetch(`/api/endpoint?page=${{p}}&size=10`);
                const json = await resp.json();
                data.push(...json.data);
                await new Promise(r => setTimeout(r, 300));
            }}
            return data;
        }}
    """)
    all_data.extend(batch)
    # 중간 저장
    with open(raw_data_path, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
```

### Chrome CDP 사용 불가 시

StealthyFetcher → DynamicFetcher 순서로 폴백하되, 사용자에게 경고:
"Akamai 보호 사이트이므로 Chrome CDP가 필요합니다"

---

## SPA 세션 보호 → Playwright 인터셉트

### 감지 시그널

다음 조건이 모두 충족되면 SPA 세션 보호 사이트로 판단:
- 브라우저에서 정상적으로 데이터가 표시됨 (검색, 조회 가능)
- 동일한 API를 HTTP 클라이언트로 직접 호출하면 **403** 반환
- 에러 메시지 예: "접근 권한이 존재하지 않습니다" (ErrorCode -801)
- WebSquare, SAP UI5, Oracle ADF 등 엔터프라이즈 SPA 프레임워크 사용
- URL이 변하지 않는 SPA 네비게이션

### 왜 API 직접 호출이 안 되는가

이런 사이트들은 서버 측에서 SPA의 네비게이션 상태를 추적한다:
1. 메인 페이지 로드 → 서버 세션 생성
2. SPA 내 메뉴 클릭 → 서버가 현재 화면 상태를 기록
3. API 호출 시 서버가 "이 세션이 해당 화면에 있는가" 검증
4. 직접 API 호출은 이 상태 없이 오므로 403 거부

### 해결 전략: Playwright + 응답 인터셉트

SPA를 정상적으로 로드하고 UI를 조작하되, 데이터는 XHR 응답을 인터셉트하여 수집한다.

```python
"""SPA 세션 보호 사이트 수집 패턴 (g2b.go.kr 등)"""
import json, time
from playwright.sync_api import sync_playwright

all_items = []
collected_ids = set()

def on_response(response):
    """백그라운드 XHR 응답 리스너."""
    try:
        if "<API_PATH_KEYWORD>" in response.url and response.status == 200:
            data = response.json()
            items = data.get("result", [])
            for item in items:
                item_id = item.get("<ID_FIELD>", "")
                if item_id and item_id not in collected_ids:
                    collected_ids.add(item_id)
                    all_items.append(item)
            if items:
                print(f"[캡쳐] +{len(items)}건 (누적 {len(all_items)}건)")
    except Exception:
        pass

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(locale="ko-KR")
    page = ctx.new_page()

    # 응답 인터셉터 등록
    page.on("response", on_response)

    # 1. 메인 페이지 로드
    page.goto("https://<DOMAIN>/", wait_until="networkidle", timeout=60000)

    # 2. SPA 내비게이션 (메뉴 클릭)
    page.locator('a:has-text("<MENU_1>")').first.click()
    page.wait_for_timeout(2000)
    page.locator('a:has-text("<MENU_2>")').first.click()
    page.wait_for_timeout(3000)
    page.wait_for_load_state("networkidle")

    # 3. 검색/조회 트리거 (UI 버튼 클릭)
    page.evaluate("""() => {
        document.querySelectorAll('button').forEach(btn => {
            if (btn.textContent.trim() === '<SEARCH_TEXT>') btn.click();
        });
    }""")
    page.wait_for_timeout(8000)

    # 4. 필요 시 페이지 사이즈 변경 + 적용
    page.evaluate("""() => {
        const sels = document.querySelectorAll('select');
        for (const sel of sels) {
            const opt = Array.from(sel.options).find(o => o.value === '100');
            if (opt) { sel.value = opt.value; sel.dispatchEvent(new Event('change', {bubbles:true})); }
        }
    }""")
    page.wait_for_timeout(500)
    page.evaluate("""() => {
        document.querySelectorAll('button').forEach(b => {
            if (b.textContent.trim() === '적용') b.click();
        });
    }""")
    page.wait_for_timeout(8000)

    browser.close()

# all_items에 인터셉트된 데이터가 축적됨
```

### 핵심 포인트

1. **`page.on("response")`는 백그라운드 리스너** — expect_response와 달리 타이밍에 덜 민감
2. **UI 조작으로 API를 트리거** — fetch()로 직접 호출하면 403
3. **중복 제거** — 같은 데이터가 여러 번 인터셉트될 수 있으므로 ID 기반 중복 체크 필수
4. **`page.evaluate()`로 검색/적용 버튼 클릭** — Playwright의 locator보다 WebSquare 같은 프레임워크에서 안정적

---

## Cloudflare → StealthyFetcher

### 감지 시그널
- `cf_clearance` 쿠키
- Cloudflare 챌린지 페이지 (5초 대기 화면)

### 수집 패턴

```python
from scrapling.fetchers import StealthyFetcher

fetcher = StealthyFetcher()

# Cloudflare 보호 사이트
page = fetcher.fetch("<URL>", headless=True, solve_cloudflare=True)
```

---

## Fetcher 에스컬레이션 자동화

범용 에스컬레이션 함수. 어떤 Fetcher를 사용해야 할지 불확실할 때 사용.

```python
from scrapling.fetchers import Fetcher, StealthyFetcher, DynamicFetcher
from utils import setup_logger

logger = setup_logger("escalation")

FETCHER_CHAIN = [
    ("Fetcher", lambda url: Fetcher().get(url)),
    ("StealthyFetcher", lambda url: StealthyFetcher().fetch(url, headless=True)),
    ("DynamicFetcher", lambda url: DynamicFetcher().fetch(url, network_idle=True)),
]

def fetch_with_escalation(url: str):
    for name, fetch_fn in FETCHER_CHAIN:
        try:
            page = fetch_fn(url)
            if page.status == 200 and page.css("body"):
                logger.info(f"[{name}] Success")
                return page, name
            elif page.status == 403:
                logger.warning(f"[{name}] 403 Forbidden, escalating")
                continue
        except Exception as e:
            logger.warning(f"[{name}] Error: {e}, escalating")
            continue
    return None, None
```
