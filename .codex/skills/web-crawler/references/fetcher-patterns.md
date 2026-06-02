# 수집 코드 패턴 레퍼런스

이 문서는 crawl_script.py 생성 시 참조하는 코드 템플릿 모음이다.
SKILL.md Step 3에서 결정된 전략에 맞는 패턴을 선택하여 사용한다.

## 목차

1. [공통 필수 패턴](#공통-필수-패턴) — 모든 수집 코드에 적용
2. [A: API 직접 수집 (FetcherSession)](#a-api-직접-수집)
3. [B-1: 정적 HTML 수집 (Fetcher)](#b-1-정적-html-수집)
4. [B-2: 동적/JS 사이트 수집 (DynamicFetcher)](#b-2-동적js-사이트-수집)
5. [Infinite Scroll 패턴 (DynamicSession)](#infinite-scroll-패턴)
6. [대규모 수집 (Spider)](#대규모-수집-spider)
7. [Resume (이어서 수집)](#resume-이어서-수집)
8. [데이터 정제](#스마트-데이터-정제)

> 안티봇 관련 패턴(Akamai Chrome CDP, SPA 세션 인터셉트, Cloudflare)은
> `antibot-strategies.md`에 별도 정리되어 있다.

---

## 공통 필수 패턴

모든 수집 코드에 반드시 포함할 요소:

### FETCHER_CHAIN 에스컬레이션

연속 실패 시 상위 Fetcher로 자동 전환한다. Akamai/SPA 세션 사이트에서는 이 체인을 사용하지 않는다.

```python
from scrapling.fetchers import Fetcher, StealthyFetcher, DynamicFetcher

# ⚠ Akamai 사이트 → antibot-strategies.md의 Chrome CDP 패턴 사용
# ⚠ SPA 세션 사이트 → antibot-strategies.md의 Playwright 인터셉트 패턴 사용
FETCHER_CHAIN = [
    ("Fetcher", lambda: Fetcher()),
    ("StealthyFetcher", lambda: StealthyFetcher()),
    ("DynamicFetcher", lambda: DynamicFetcher()),
]

results = []
consecutive_errors = 0
current_fetcher_idx = 0

for page_num in range(1, max_pages + 1):
    try:
        limiter.wait()
        fetcher = FETCHER_CHAIN[current_fetcher_idx][1]()
        page = fetcher.get(url) if current_fetcher_idx == 0 else fetcher.fetch(url)

        if page.status != 200:
            raise Exception(f"Status {page.status}")

        # ... 데이터 파싱 ...
        consecutive_errors = 0

    except Exception as e:
        consecutive_errors += 1
        logger.warning(f"Page {page_num} error: {e}")

        if consecutive_errors >= 2 and current_fetcher_idx < len(FETCHER_CHAIN) - 1:
            current_fetcher_idx += 1
            logger.info(f"Escalating to {FETCHER_CHAIN[current_fetcher_idx][0]}")
            consecutive_errors = 0
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
- except 블록에서 반드시 `continue` — 절대 `break`로 중단하지 않는다
- 연속 5회 실패 시에만 최종 중단

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
