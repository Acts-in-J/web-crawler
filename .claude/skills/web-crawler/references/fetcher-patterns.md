# 수집 코드 패턴 레퍼런스

이 문서는 crawl_script.py 생성 시 참조하는 코드 템플릿 모음이다.
SKILL.md Step 3에서 결정된 전략에 맞는 패턴을 선택하여 사용한다.

## 목차

1. [공통 필수 패턴](#공통-필수-패턴) — 모든 수집 코드에 적용
2. [A: API 직접 수집 (FetcherSession)](#a-api-직접-수집)
3. [B-1: 정적 HTML 수집 (Fetcher)](#b-1-정적-html-수집)
4. [B-2: 동적/JS 사이트 수집 (DynamicFetcher)](#b-2-동적js-사이트-수집)
5. [F: curl_cffi 경량 그리드 (브라우저 전 돌파)](#f-curl_cffi-경량-그리드)
6. [Infinite Scroll 패턴 (DynamicSession)](#infinite-scroll-패턴)
7. [대규모 수집 (Spider)](#대규모-수집-spider)
8. [Resume (이어서 수집)](#resume-이어서-수집)
9. [데이터 정제](#스마트-데이터-정제)

> 안티봇 관련 패턴(Akamai Chrome CDP, SPA 세션 인터셉트, Cloudflare)은
> `antibot-strategies.md`에 별도 정리되어 있다.

---

## 공통 필수 패턴

모든 수집 코드에 반드시 포함할 요소:

### FETCHER_CHAIN 에스컬레이션 (사다리 A 전용)

연속 실패 시 상위 티어로 자동 전환한다. **이 체인은 사다리 A(1~3단)에서 끝난다.**

사다리 1~3단에서 사이트는 나를 막은 적이 없다 — 데이터가 있는 **위치**가 다를 뿐이다. 4단부터가 처음으로 "상대가 나를 식별하고 거절한" 상황이고, 거기부터는 **자동으로 넘어가지 않고 사용자에게 한 번 통지한다** (SKILL.md Step 3 "이음매 통지 게이트").

우회 능력은 전부 그대로 있다. 자동 순차 진입에서 빠진 것뿐이다.

```python
from scrapling.fetchers import DynamicFetcher
from utils import plain_get, plain_session

ITEM_SELECTOR = "<ITEM_SELECTOR>"

def _session_tier(url):
    """2단 — 세션·쿠키를 유지한 채 재시도. 숨은 API 호출에도 이 세션을 쓴다."""
    with plain_session() as session:
        return session.get(url)

# 각 티어는 url을 받아 page(.css 가능) 또는 None을 반환하는 callable
FETCHER_CHAIN = [
    ("plain_get",      plain_get),                                            # 1단 정적 HTML (위장 없음)
    ("plain_session",  _session_tier),                                        # 2단 숨은 API·세션 유지
    ("DynamicFetcher", lambda url: DynamicFetcher().fetch(url, network_idle=True)),  # 3단 JS 렌더링
]

results = []
consecutive_errors = 0
current_fetcher_idx = 0

for page_num in range(1, max_pages + 1):
    try:
        limiter.wait()
        page = FETCHER_CHAIN[current_fetcher_idx][1](url)

        if page is None or (getattr(page, "status", 200) != 200):
            raise Exception("blocked or non-200")
        if not page.css(ITEM_SELECTOR):          # 소프트블록(가짜 200) 방어
            raise Exception("soft-block: 핵심 셀렉터 미매칭")

        # ... 데이터 파싱 ...
        consecutive_errors = 0

    except Exception as e:
        consecutive_errors += 1
        logger.warning(f"Page {page_num} error: {e}")

        if consecutive_errors >= 2 and current_fetcher_idx < len(FETCHER_CHAIN) - 1:
            current_fetcher_idx += 1
            logger.info(f"Escalating to {FETCHER_CHAIN[current_fetcher_idx][0]}")
            consecutive_errors = 0
        elif consecutive_errors >= 2:
            # 사다리 A 를 다 썼다. 다음은 사다리 B — 자동으로 넘어가지 않는다.
            logger.error("사다리 A 소진 — 사다리 B 진입은 사용자 통지가 필요하다 (SKILL.md Step 3)")
            break
        elif consecutive_errors >= 5:
            logger.error("5회 연속 실패, 중단")
            break
        continue

    # 100건마다 중간 저장
    if len(results) % 100 == 0 and results:
        with open(raw_data_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
```

**핵심 규칙:**
- except 블록에서 반드시 `continue` — 페이지 하나의 실패로 전체를 중단하지 않는다
- **체인은 3단에서 끝난다.** 사다리 A 를 소진하면 루프를 빠져나와 사용자에게 통지한다
- **`plain_get`/`plain_session` 을 쓴다** — 맨 `Fetcher().get(url)` 은 기본값이 `impersonate="chrome"` + `stealthy_headers=True` 라 **평문이 아니다**. 헤더 16개에 가짜 `Referer: https://www.google.com/` 까지 붙는다
- **두 인자를 함께 끈다.** 하나만 끄면 불일치 지문이 되어 오히려 더 잘 탐지된다
- **Akamai 는 이 체인 자체를 쓰지 않는다** — 통지 후 바로 Chrome CDP (antibot-strategies.md § WAF capability 라우팅)

### 소프트블록 사전 검증 (첫 페이지 — 대량 루프 진입 전 필수)

`status == 200`이라도 본문이 WAF 챌린지면 그대로 파싱하면 안 된다. 첫 페이지에서 한 번 건다.

```python
from utils import detect_softblock

first = fetcher.get(start_url)  # 또는 .fetch(...)
v = detect_softblock(first.html_content, status=first.status,
                     selector_hit=bool(first.css("<ITEM_SELECTOR>")))
if v["blocked"]:
    logger.error(f"소프트블록 — {v['verdict']}: {v['signals']}")
    raise SystemExit("수집 중단: 상위 Fetcher로 에스컬레이션 필요 (antibot-strategies.md)")
```

### 부분 데이터 저장

```python
# Session 기반: 100건마다 중간 저장
if len(results) % 100 == 0 and results:
    with open(raw_data_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

# Spider 기반: crawldir 자동 체크포인트
CollectSpider(crawldir="./crawl_data").start()
```

---

## A: API 직접 수집

API를 발견했으면 반드시 FetcherSession을 사용한다. 기본 Fetcher로 API를 호출하지 않는다.

```python
import json, sys
sys.path.insert(0, './scripts')
from utils import RateLimiter, setup_logger
from scrapling.fetchers import FetcherSession

logger = setup_logger("api_crawler")
limiter = RateLimiter(delay=1.0)
results = []

with FetcherSession(impersonate='chrome') as session:
    page_num = 1
    while True:
        limiter.wait()
        url = f"<API_URL>?page={page_num}&limit=<LIMIT>"
        logger.info(f"API call page {page_num}: {url}")

        resp = session.get(url, stealthy_headers=True)
        if resp.status != 200:
            logger.warning(f"Status {resp.status}, stopping")
            break

        data = resp.json()
        items = <EXTRACT_PATH>  # e.g., data['results']
        if not items:
            break

        for item in items:
            results.append({
                "<FIELD1>": item.get("<JSON_KEY1>"),
                "<FIELD2>": item.get("<JSON_KEY2>"),
            })

        logger.info(f"Collected {len(results)} items")

        if len(items) < <LIMIT>:
            break
        page_num += 1

with open("./output/raw_data.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
```

---

## B-1: 정적 HTML 수집

```python
import json, sys
sys.path.insert(0, './scripts')
from utils import RateLimiter, setup_logger
from scrapling.fetchers import Fetcher

logger = setup_logger("crawler")
limiter = RateLimiter(delay=1.0)
results = []
fetcher = Fetcher()

page_num = 1
while True:
    limiter.wait()
    url = f"<BASE_URL>?page={page_num}"
    page = fetcher.get(url)
    if page.status != 200:
        break

    items = page.css("<ITEM_SELECTOR>")
    if not items:
        break

    for item in items:
        results.append({
            "<FIELD1>": item.css("<SELECTOR1>::text").get("").strip(),
            "<FIELD2>": item.css("<SELECTOR2>::text").get("").strip(),
        })

    next_link = page.css("<NEXT_SELECTOR>::attr(href)").get()
    if not next_link:
        break
    page_num += 1

with open("./output/raw_data.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
```

---

## B-2: 동적/JS 사이트 수집

CSR(Next.js, React 등) 사이트에서 JS 렌더링이 필요한 경우.

```python
from scrapling.fetchers import DynamicFetcher

logger = setup_logger("dynamic_crawler")
limiter = RateLimiter(delay=1.5)
results = []
fetcher = DynamicFetcher()

page_num = 1
while True:
    limiter.wait()
    url = f"<BASE_URL>?page={page_num}"
    page = fetcher.fetch(url, network_idle=True)
    if page.status != 200:
        break

    items = page.css("<ITEM_SELECTOR>")
    if not items:
        break

    for item in items:
        results.append({
            "<FIELD1>": item.css("<SELECTOR1>::text").get("").strip(),
            "<FIELD2>": item.css("<SELECTOR2>::text").get("").strip(),
        })

    next_link = page.css("<NEXT_SELECTOR>::attr(href)").get()
    if not next_link:
        break
    page_num += 1
```

### DynamicFetcher + page_action

SPA에서 클릭/스크롤 등 추가 조작이 필요할 때:

```python
def custom_action(page):
    """페이지 로드 후 추가 조작."""
    page.wait_for_timeout(3000)
    # 탭/버튼 클릭
    page.locator('button:has-text("더보기")').click()
    page.wait_for_timeout(2000)

page = fetcher.fetch(url, network_idle=True, page_action=custom_action)
```

---

## F: curl_cffi 경량 그리드

브라우저를 띄우기 전, TLS 지문 위조 HTTP 요청을 **격자로 완전탐색**해 저비용으로 뚫는다. (insane-search Phase 1 차용) DataDome/PerimeterX/단순 403에 효과적. **Akamai는 제외** — `antibot-strategies.md § WAF capability 라우팅` 참조.

`curl_cffi`는 `scrapling[fetchers]`에 포함돼 별도 설치 불필요. 매 응답을 `detect_softblock()`로 검증한다 — 200이어도 통과로 치지 않는다.

```python
import sys
sys.path.insert(0, './scripts')
from curl_cffi import requests as cffi
from utils import detect_softblock, setup_logger
from urllib.parse import urlparse

logger = setup_logger("cffi_grid")

IMPERSONATE   = ["safari17_0", "chrome131", "chrome120", "firefox133", "safari_ios"]
def _url_transforms(url):
    p = urlparse(url)
    host = p.netloc
    yield url                                            # 원본
    if host.startswith("www."):
        bare = host[4:]
        yield url.replace(host, "m." + bare, 1)          # 모바일 서브도메인
        yield url.replace(host, bare, 1)                 # www 제거
    elif host.count(".") == 1:                           # www 없는 표준 도메인(example.com)
        yield url.replace(host, "m." + host, 1)          # 모바일 변형만 추가
def _referers(url):
    p = urlparse(url)
    return [f"{p.scheme}://{p.netloc}/", "https://www.google.com/", None]

def fetch_via_grid(url, item_selector=None, timeout=25):
    """그리드 완전탐색. 첫 strong/weak_ok 응답을 반환. 전부 실패 시 (None, trace)."""
    trace = []
    for imp in IMPERSONATE:
        for u in _url_transforms(url):
            for ref in _referers(url):
                headers = {"Referer": ref} if ref else {}
                try:
                    r = cffi.get(u, impersonate=imp, headers=headers,
                                 timeout=timeout, allow_redirects=True)
                except Exception as e:
                    trace.append({"imp": imp, "url": u, "ref": ref, "err": str(e)})
                    continue
                hit = None
                if item_selector:
                    from scrapling import Selector
                    hit = bool(Selector(r.text).css(item_selector))
                # ⚠ dict(r.cookies)는 무관 도메인에 동명 쿠키 있으면 CookieConflict로 터짐
                #   (리다이렉트/외부 referer 시) → get_dict()로 안전 평탄화
                v = detect_softblock(r.text, status=r.status_code,
                                     cookies=r.cookies.get_dict(), selector_hit=hit)
                trace.append({"imp": imp, "url": u, "ref": ref,
                              "status": r.status_code, "verdict": v["verdict"]})
                if not v["blocked"]:
                    logger.info(f"그리드 돌파: {imp} / {u} / ref={ref} → {v['verdict']}")
                    return r, trace
    logger.warning(f"그리드 소진, 미돌파 ({len(trace)}회 시도) → 브라우저 단계로 에스컬레이션")
    return None, trace
```

돌파 성공 시 `r.text`를 Scrapling Selector로 파싱해 평소처럼 수집. 실패하면 StealthyFetcher → DynamicFetcher로 올린다.

> 그리드도 안 뚫리고 브라우저까지 가기 전 본문만 빠르게 보려면 **Jina Reader 폴백**(`antibot-strategies.md § Jina Reader 폴백`)을 쓴다. 정찰·단발 본문 확인용이며 대량 수집엔 부적합.

---

## Infinite Scroll 패턴

```python
from scrapling.fetchers import DynamicSession

with DynamicSession(headless=True) as session:
    page = session.fetch("<URL>", network_idle=True)
    all_items = []
    prev_count = 0

    for scroll in range(50):
        items = page.css("<ITEM_SELECTOR>")
        if len(items) == prev_count:
            break
        prev_count = len(items)

        all_items = []
        for item in items:
            all_items.append({...})

        session.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        import time; time.sleep(2)
        page = session.fetch("<URL>", network_idle=True)
```

---

## 대규모 수집 (Spider)

500건 이상 예상 시 Spider 클래스 사용.

```python
from scrapling.spiders import Spider, Request, Response
from scrapling.fetchers import AsyncFetcherSession

class CollectSpider(Spider):
    name = "collector"
    start_urls = ["<START_URL>"]
    concurrent_requests = 5

    def configure_sessions(self, manager):
        manager.add("default", AsyncFetcherSession(impersonate="chrome"))

    async def parse(self, response: Response):
        for item in response.css("<ITEM_SELECTOR>"):
            yield {
                "<FIELD1>": item.css("<SELECTOR1>::text").get("").strip(),
            }
        next_page = response.css("<NEXT_SELECTOR>::attr(href)").get()
        if next_page:
            yield response.follow(next_page)

result = CollectSpider(crawldir="./crawl_data").start()
result.items.to_json("./output/raw_data.json")
```

---

## Resume (이어서 수집)

```python
import os, json

if os.path.exists("./output/raw_data.json"):
    with open("./output/raw_data.json") as f:
        results = json.load(f)
    start_page = (len(results) // items_per_page) + 1
    logger.info(f"Resuming from page {start_page} ({len(results)} existing)")
else:
    results = []
    start_page = 1
```

---

## 스마트 데이터 정제

LLM이 처음 10건 샘플을 분석하여 정제 함수를 동적 생성한다.

```python
import re

def clean_price(val):
    """₩15,000 → 15000"""
    if not val: return None
    cleaned = re.sub(r'[^\d.]', '', val.replace(',', ''))
    try: return float(cleaned)
    except ValueError: return val

def clean_url(val, base="https://example.com"):
    """상대 URL → 절대 URL"""
    if val and val.startswith('/'):
        return base + val
    return val

for item in data:
    item["가격"] = clean_price(item.get("가격"))
    item["링크"] = clean_url(item.get("링크"))
```
