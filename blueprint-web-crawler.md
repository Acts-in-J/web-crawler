# 범용 웹 크롤링 에이전트 시스템 설계서

> 작성일: 2026-03-09
> 최종 갱신: 2026-05-13 (Step 1-A/5-A 도메인 프로필 게이트, fingerprints whitelist 정책 반영)
> 목적: Claude Code 구현 참조용 계획서

---

## 1. 작업 컨텍스트

### 배경 및 목적
사용자가 URL과 수집 항목을 자연어로 설명하면, 자동으로 해당 웹사이트를 정찰하고 데이터를 대량 수집하여 엑셀 파일로 정리해주는 에이전트. 특정 사이트에 국한되지 않고 다양한 형태의 웹사이트(정적/동적, 로그인 필요 여부, SPA 등)에 범용 대응한다.

### 범위
- 포함: 사이트 정찰, 구조 파악, 로그인 대응, 동적 콘텐츠 처리, pagination, 대량 데이터 수집, 엑셀 출력
- 제외: CAPTCHA 수동 풀기 외의 자동 우회, 불법적 스크래핑, 로그인 자격증명 자동 저장

### 입출력 정의

| 항목 | 내용 |
|------|------|
| **입력** | 자연어 명령. 예: "https://example.com/products 에서 상품명, 가격, 리뷰수를 수집해줘" |
| **출력** | 엑셀 파일 (.xlsx), `/output/crawl_<도메인>_<timestamp>.xlsx` |
| **트리거** | 사용자가 크롤링 스킬을 호출하거나 자연어로 수집 요청 |

### 제약조건
- 기술적: agent-browser(Playwright 기반), Scrapling(Python), openpyxl 사용
- 운영: 수백~수천 건 규모. rate limiting 준수 (기본 1~2초 간격)
- 품질: 수집 누락률 5% 이하 목표. 셀렉터 자가 치유로 사이트 구조 변경 대응

### 용어 정의

| 용어 | 정의 |
|------|------|
| 정찰 (Recon) | agent-browser로 사이트를 열어 페이지 구조, 데이터 로딩 방식, API 엔드포인트 등을 파악하는 단계 |
| 셀렉터 핑거프린트 | Scrapling의 `auto_save=True` 기능으로 저장되는 요소 특성 정보. `adaptive=True`로 조회 시 구조 변경에도 자가 치유 |
| 도메인 프로필 | `fingerprints/<도메인>/profile.json`에 저장되는 사이트별 수집 레시피(fetcher_type, antibot 전략, selectors, API 엔드포인트, notes). Step 1-A에서 조회하고 Step 5-A에서 저장/갱신한다. **버전 관리 대상** — gitignore whitelist로 commit됨 |
| Fetcher 계층 | Scrapling의 3단계 Fetcher: `Fetcher`(기본 HTTP) → `StealthyFetcher`(안티봇 우회) → `DynamicFetcher`(브라우저 렌더링) |
| Spider | Scrapling의 대규모 크롤링 프레임워크. 동시 요청, multi-session routing, pause/resume 지원 |

---

## 2. 워크플로우 정의

### 전체 흐름도

```
[사용자 자연어 입력]
       │
       ▼
[Step 1: 입력 파싱] ─── 불명확 → 사용자에게 되묻기
       │
       ▼
[Step 1-A: 도메인 프로필 조회 (fingerprints/<도메인>/profile.json)]
       │
       ├── 프로필 있음 + 재사용 OK ──→ [Step 3로 점프 (정찰 스킵)]
       │
       ├── 없음 또는 신규 정찰 필요
       │
       ▼
[Step 2: 정찰 (agent-browser)]
       │
       ├── 로그인 필요? ──Yes──→ [Step 2-A: 수동 로그인 → 쿠키 추출]
       │                                    │
       ├────────────────────────────────────┘
       │
       ▼
[Step 3: 수집 전략 수립 + Fetcher 선택]
       │
       ├── API 발견 ──→ [Step 4-A: FetcherSession으로 API 호출]
       │                         │
       ├── 정적 HTML ──→ [Step 4-B: Fetcher/Spider로 수집]
       │                         │
       ├── 동적/JS ───→ [Step 4-C: DynamicFetcher로 수집]
       │                         │
       ├── 안티봇 ────→ [Step 4-D: StealthyFetcher로 수집]
       │                         │
       ├─────────────────────────┘
       ▼
[Step 5: 데이터 검증]
       │
       ├── 누락/이상 → 재시도 (최대 2회)
       │
       ▼
[Step 5-A: 도메인 프로필 저장 (필수 게이트)]
       │
       ├── 저장 실패 → "파이프라인 미완료" 보고 + 사유 명시
       │
       ▼
[Step 6: 엑셀 생성]
       │
       ▼
[완료 보고]
```

### LLM 판단 vs 코드 처리 구분

| LLM이 직접 수행 | 스크립트로 처리 |
|----------------|----------------|
| 자연어 입력 파싱 (URL, 항목 추출) | HTTP 요청, HTML 파싱 (Scrapling) |
| 도메인 프로필 재사용 여부 판단 (Step 1-A) | 프로필 load/save (`scripts/domain_profile.py`) |
| 사이트 구조 분석 및 수집 전략 결정 | pagination 순회, 데이터 추출 반복 |
| Fetcher 유형 선택 판단 | 쿠키/세션 관리 (Session 클래스) |
| 셀렉터/API 경로 판단 | 엑셀 파일 생성 (openpyxl) |
| 수집 결과 품질 판단 | rate limiting, 재시도 로직 |
| 프로필 `notes` 작성 (다음 사람에게 결정적 정보 한두 줄) | profile.json 직렬화/디스크 기록 |
| 오류 분석 및 대응 전략 수정 | Spider 기반 대규모 크롤링 |

### 단계별 상세

#### Step 1: 입력 파싱

- **처리 주체**: 에이전트 (LLM 판단)
- **입력**: 사용자 자연어 메시지
- **처리 내용**: URL, 수집 대상 항목명, 특수 조건(로그인, 필터, 정렬 등) 추출. 불명확한 부분이 있으면 사용자에게 되묻기
- **출력**: 구조화된 크롤링 요청 (메모리 내)
  ```json
  {
    "url": "https://example.com/products",
    "fields": ["상품명", "가격", "리뷰수"],
    "options": { "login_required": false, "max_pages": null }
  }
  ```
- **성공 기준**: URL이 유효하고, 수집 항목이 1개 이상 명확히 정의됨
- **검증 방법**: 규칙 기반 (URL 형식 체크, 항목 리스트 비어있지 않음)
- **실패 시 처리**: 사용자에게 되묻기 ("어떤 항목을 수집할지 알려주세요")

#### Step 1-A: 도메인 프로필 조회

- **처리 주체**: 에이전트 + 스크립트 (`scripts/domain_profile.py`)
- **입력**: Step 1에서 추출한 URL의 도메인
- **처리 내용**:
  1. `DomainProfile().load(domain)`으로 `fingerprints/<sanitized_domain>/profile.json` 조회
  2. 프로필이 존재하면 LLM이 재사용 가능 여부 판단:
     - 수집 항목이 기존 `selectors`/`field_mapping`으로 커버되는가
     - `last_used`가 지나치게 오래되지 않았는가 (~3개월 이상이면 정찰 권장)
     - 사용자가 명시적으로 "최신 구조로 다시 정찰"을 요구하지 않았는가
  3. 재사용 결정 시 → Step 2(정찰) 스킵하고 Step 3으로 점프
  4. 신규 정찰 결정 시 → Step 2로 진행
- **출력**: 재사용 가능한 프로필(dict) 또는 `None`
- **성공 기준**: 프로필 로드 성공 또는 부재 확인
- **검증 방법**: 규칙 기반 (스키마 필드 `fetcher_type`, `antibot_strategy` 둘 다 존재해야 재사용 후보)
- **실패 시 처리**: 로드 에러(스키마 깨짐 등) 시 프로필을 무시하고 Step 2로 진행 (silent fallback)
- **참고**: 현재 11개 도메인 프로필이 백필되어 있음 — coupang.com, brand.naver.com, smartstore.naver.com, builtini.co.kr, wanted.co.kr, g2b.go.kr, data.seoul.go.kr, fin.land.naver.com, made-in-china.com, www.kurly.com, books.toscrape.com

#### Step 2: 정찰 (Recon)

- **처리 주체**: agent-browser (Playwright)
- **입력**: 대상 URL
- **처리 내용**:
  1. agent-browser로 사이트 열기
  2. 페이지 스냅샷 촬영 및 DOM 구조 확인
  3. Network 탭에서 XHR/Fetch 요청 감시 → API 엔드포인트 발견
  4. 데이터 로딩 방식 판단 (SSR / CSR / API / infinite scroll / pagination)
  5. 로그인 필요 여부 판단
  6. 안티봇 보호 유무 판단 (Cloudflare, 접근 차단 등)
- **출력**: 정찰 보고서 (메모리 내)
  ```json
  {
    "loading_type": "api | ssr | csr | hybrid",
    "api_endpoints": ["https://example.com/api/products?page=1"],
    "pagination_type": "url_param | next_button | infinite_scroll | none",
    "login_required": false,
    "anti_bot": "none | cloudflare | custom",
    "sample_selectors": { "상품명": "div.product h2", "가격": "span.price" },
    "cookies": null
  }
  ```
- **성공 기준**: 데이터 로딩 방식 식별 완료, 최소 1개 항목의 셀렉터 또는 API 경로 확인
- **검증 방법**: LLM 자기 검증 (스냅샷 기반으로 데이터가 실제로 보이는지 확인)
- **실패 시 처리**: 자동 재시도 1회 (페이지 로딩 타임아웃 증가). 재실패 시 사용자에게 상황 보고

#### Step 2-A: 수동 로그인 및 쿠키 추출

- **처리 주체**: agent-browser + 사용자
- **입력**: 로그인이 필요하다는 정찰 결과
- **처리 내용**:
  1. 사용자에게 "이 사이트는 로그인이 필요합니다. 브라우저에서 로그인해주세요" 안내
  2. agent-browser로 로그인 페이지를 열어 사용자에게 보여줌
  3. 사용자가 수동 로그인 완료 후, agent-browser에서 쿠키 추출
  4. 추출한 쿠키를 `/output/cookies_<도메인>.json`에 저장
- **출력**: 인증 쿠키 (JSON 파일 + Scrapling Session에 전달 가능한 형태)
- **성공 기준**: 로그인 후 페이지에서 인증된 콘텐츠가 보이는 것 확인
- **검증 방법**: 로그인 후 스냅샷에서 로그인 전과 다른 콘텐츠 존재 여부 확인
- **실패 시 처리**: 사용자에게 재로그인 요청 (최대 2회)

#### Step 3: 수집 전략 수립 + Fetcher 선택

- **처리 주체**: 에이전트 (LLM 판단)
- **입력**: 정찰 보고서 + 사용자 요청 항목
- **처리 내용**:
  1. Fetcher 유형 선택 (아래 의사결정 트리 참조)
  2. 각 항목별 셀렉터 또는 API 필드 매핑
  3. pagination 방식에 맞는 순회 전략 결정
  4. 대규모(500건+)이면 Spider 사용 여부 결정
  5. rate limiting 설정
- **Fetcher 선택 의사결정 트리**:
  ```
  API 발견? ──Yes──→ FetcherSession (가장 빠름, 안정적)
     │
     No
     │
  안티봇 보호? ──Yes──→ StealthyFetcher/StealthySession
     │                    (Cloudflare 등 자동 우회)
     No
     │
  JS 렌더링 필요? ──Yes──→ DynamicFetcher/DynamicSession
     │                      (Playwright 기반 브라우저 렌더링)
     No
     │
  Fetcher (기본 HTTP, 가장 가벼움)
  ```
- **대규모 수집 시 Spider 판단**:
  ```
  예상 건수 500건 이상? ──Yes──→ Spider 클래스 사용
     │                           (동시 요청, pause/resume, 콜백)
     No
     │
  Session 클래스로 순차 처리
  ```
- **출력**: 수집 전략 + Python 스크립트 코드
- **성공 기준**: 모든 요청 항목에 대해 추출 경로(셀렉터 or API 필드)가 매핑됨
- **검증 방법**: 규칙 기반 (요청 항목 수 == 매핑된 추출 경로 수)
- **실패 시 처리**: 매핑 불가 항목에 대해 사용자에게 되묻기

#### Step 4-A: API 직접 호출 수집

- **처리 주체**: 스크립트 (`scripts/collect_api.py`)
- **입력**: API 엔드포인트, 파라미터, 인증 쿠키(있으면)
- **처리 내용**:
  1. `FetcherSession`으로 세션 유지하며 API 호출
  2. `impersonate='chrome'`, `stealthy_headers=True` 설정
  3. JSON 응답에서 필요한 필드 추출
  4. pagination 파라미터 변경하며 전체 페이지 순회
  5. rate limiting 적용 (요청 간 대기)
  6. 결과를 리스트로 누적
  ```python
  from scrapling.fetchers import FetcherSession

  with FetcherSession(impersonate='chrome') as session:
      for page in range(1, max_pages + 1):
          resp = session.get(f'{api_url}?page={page}', stealthy_headers=True)
          items = resp.json()['data']
          results.extend(extract_fields(items, field_mapping))
          time.sleep(delay)
  ```
- **출력**: `/output/raw_data.json` (수집된 원시 데이터)
- **성공 기준**: 예상 총 건수 대비 90% 이상 수집
- **검증 방법**: 규칙 기반 (수집 건수 체크, 필수 필드 null 비율 체크)
- **실패 시 처리**: 실패한 페이지 로그 남기고 계속 진행. 실패율 50% 초과 시 중단 후 사용자 보고

#### Step 4-B: 정적 HTML 수집 (Fetcher / Spider)

- **처리 주체**: 스크립트 (`scripts/collect_html.py`)
- **입력**: URL 패턴, 셀렉터 매핑, 인증 쿠키(있으면), pagination 전략
- **처리 내용**:
  1. 첫 페이지에서 `auto_save=True`로 셀렉터 핑거프린트 저장
  2. 이후 페이지에서 `adaptive=True`로 자가 치유 파싱
  3. pagination 순회 (URL 파라미터 or next 버튼 링크 추출)
  4. 500건 이상이면 Spider 사용:
  ```python
  from scrapling.spiders import Spider, Request, Response

  class CrawlSpider(Spider):
      name = "collector"
      start_urls = [target_url]
      concurrent_requests = 5

      async def parse(self, response: Response):
          for item in response.css(item_selector):
              yield {
                  field: item.css(sel, auto_save=True).get()
                  for field, sel in selector_mapping.items()
              }
          next_page = response.css(next_selector)
          if next_page:
              yield response.follow(next_page[0].attrib['href'])

  result = CrawlSpider(crawldir='./crawl_data').start()
  result.items.to_json('output/raw_data.json')
  ```
  5. 500건 미만이면 FetcherSession으로 순차 처리
- **출력**: `/output/raw_data.json`
- **성공 기준**: 예상 총 건수 대비 90% 이상 수집, 각 항목 null 비율 10% 이하
- **검증 방법**: 규칙 기반 (건수, null 비율)
- **실패 시 처리**: 셀렉터 매칭 실패 시 `adaptive=True`로 자가 치유 시도. 재실패 시 에이전트에 돌아가 셀렉터 재분석

#### Step 4-C: 동적/JS 사이트 수집 (DynamicFetcher)

- **처리 주체**: 스크립트 (`scripts/collect_dynamic.py`)
- **입력**: URL 패턴, 셀렉터 매핑, pagination 전략
- **처리 내용**:
  1. `DynamicSession`으로 Playwright 기반 브라우저 렌더링
  2. `network_idle=True`로 JS 로딩 완료 대기
  3. 렌더링된 DOM에서 셀렉터로 데이터 추출
  4. Infinite scroll 처리: 스크롤 → 로딩 대기 → 추출 반복
  ```python
  from scrapling.fetchers import DynamicSession

  with DynamicSession(headless=True) as session:
      page = session.fetch(url, network_idle=True)
      items = page.css(item_selector, auto_save=True)
      # infinite scroll 대응
      while has_more:
          session.scroll_to_bottom()
          page = session.fetch(url, network_idle=True)
          new_items = page.css(item_selector, adaptive=True)
          items.extend(new_items)
  ```
- **출력**: `/output/raw_data.json`
- **성공 기준**: 동일
- **검증 방법**: 동일
- **실패 시 처리**: 렌더링 타임아웃 시 `disable_resources=True`로 경량화 재시도. JS 에러 시 agent-browser로 폴백하여 수동 확인

#### Step 4-D: 안티봇 우회 수집 (StealthyFetcher)

- **처리 주체**: 스크립트 (`scripts/collect_stealth.py`)
- **입력**: URL 패턴, 셀렉터 매핑, 인증 쿠키(있으면)
- **처리 내용**:
  1. `StealthySession`으로 안티봇 우회
  2. Cloudflare 보호 사이트: `solve_cloudflare=True` 설정
  3. 대규모 수집 시 Spider의 multi-session routing 활용:
  ```python
  from scrapling.spiders import Spider, Request, Response
  from scrapling.fetchers import AsyncStealthySession, AsyncFetcherSession

  class StealthSpider(Spider):
      name = "stealth_collector"
      start_urls = [target_url]

      def configure_sessions(self, manager):
          manager.add("stealth", AsyncStealthySession(
              headless=True, solve_cloudflare=True
          ), lazy=True)
          manager.add("fast", AsyncFetcherSession(impersonate="chrome"))

      async def parse(self, response: Response):
          for item in response.css(item_selector):
              yield extract_item(item)
          next_url = response.css(next_selector + '::attr(href)').get()
          if next_url:
              yield Request(next_url, sid="stealth")
  ```
- **출력**: `/output/raw_data.json`
- **성공 기준**: 동일
- **검증 방법**: 동일
- **실패 시 처리**: Cloudflare Enterprise급 보호 시 사용자에게 "이 사이트는 고급 안티봇 보호가 적용되어 자동 수집이 어렵습니다" 보고

#### Step 5: 데이터 검증

- **처리 주체**: 에이전트 (LLM 판단) + 스크립트
- **입력**: `/output/raw_data.json`
- **처리 내용**:
  1. 수집 건수 확인
  2. 각 필드별 null/빈값 비율 체크
  3. 데이터 샘플 (처음 5건, 마지막 5건) LLM이 직접 확인하여 품질 판단
  4. 중복 데이터 제거
  5. 이상치 탐지 (가격이 0원, 이름이 비정상적으로 긴 경우 등)
- **출력**: 검증된 데이터 + 검증 리포트 (콘솔 출력)
- **성공 기준**: 전체 건수의 95% 이상이 유효 데이터
- **검증 방법**: LLM 자기 검증 + 규칙 기반 (null 비율, 중복률)
- **실패 시 처리**: 누락 심각 시 Step 4로 돌아가 재수집 (최대 2회). 재실패 시 수집된 데이터로 진행하되 사용자에게 경고

#### Step 5-A: 도메인 프로필 저장 (필수 게이트)

- **처리 주체**: 에이전트 + 스크립트 (`scripts/domain_profile.py`)
- **입력**: Step 5를 통과한 수집 결과 + 이번 실행에서 확인된 fetcher_type, antibot_type/strategy, selectors, API endpoints, pagination 정보
- **처리 내용**:
  1. `DomainProfile().save(domain, profile)`로 `fingerprints/<sanitized_domain>/profile.json` 저장(신규) 또는 갱신
  2. 기존 프로필이 있으면 이번 실행에서 새로 알아낸 endpoint/selector/notes를 누적/수정 (단순 `last_used` 갱신만으로 끝내지 않음)
  3. `notes` 필드에 다음 사람이 정찰 없이 바로 수집할 수 있는 결정적 한두 줄을 작성:
     - 예: "Akamai라 chrome_cdp 필수, productId/itemId/vendorItemId 3개 필요"
     - 예: "Next.js SPA, `a[href^=\"/goods/\"]`가 안정 셀렉터, ProductCard는 빌드 해시로 자주 변경"
  4. 인증 토큰/쿠키/내부 API key는 profile.json에 박지 않음 — 별도 `cookies_<도메인>.json` (gitignore 차단됨)에 분리
- **출력**: `fingerprints/<도메인>/profile.json` (commit 대상)
- **성공 기준**: 파일 쓰기 성공 + `fetcher_type`/`antibot_strategy`/`notes` 3개 필드 모두 비어있지 않음
- **검증 방법**: 규칙 기반 (저장 직후 load → 필수 필드 존재 확인)
- **실패 시 처리**: 디스크 권한/스키마 누락 등으로 저장 실패 시 **"파이프라인 미완료"**로 보고. 수집 결과(엑셀)는 살아있어도 Step 6 보고에 실패 사실과 사유를 명시
- **누락 시 영향**: 다음 수집 때 정찰부터 다시 해야 하고, 다른 머신/세션에서 노하우가 완전히 사라짐 → 게이트로 강제

#### Step 6: 엑셀 생성

- **처리 주체**: 스크립트 (`scripts/export_excel.py`)
- **입력**: 검증된 데이터
- **처리 내용**:
  1. openpyxl로 워크북 생성
  2. 헤더 행: 사용자가 요청한 항목명 그대로 사용
  3. 데이터 행 채우기
  4. 기본 서식 적용 (헤더 굵게, 열 너비 자동 조정, 필터 설정)
  5. 파일 저장: `/output/crawl_<도메인>_<YYYYMMDD_HHMMSS>.xlsx`
- **출력**: 엑셀 파일
- **성공 기준**: 파일이 정상적으로 열리고, 행 수가 검증된 데이터 건수와 일치
- **검증 방법**: 규칙 기반 (파일 존재, 행 수 일치)
- **실패 시 처리**: openpyxl 에러 시 자동 재시도 1회

### 상태 전이

| 상태 | 전이 조건 | 다음 상태 |
|------|----------|----------|
| 입력 대기 | 사용자가 URL+항목 제공 | 입력 파싱 |
| 입력 파싱 | 파싱 성공 | 프로필 조회 |
| 입력 파싱 | 불명확 | 입력 대기 (되묻기) |
| 프로필 조회 | 프로필 있음 + 재사용 OK | 전략 수립 (정찰 스킵) |
| 프로필 조회 | 프로필 없음 또는 신규 정찰 필요 | 정찰 |
| 정찰 | 로그인 불필요 | 전략 수립 |
| 정찰 | 로그인 필요 | 수동 로그인 |
| 수동 로그인 | 로그인 완료 | 전략 수립 |
| 전략 수립 | Fetcher 유형 결정 | 해당 수집 Step |
| 수집 (4-A/B/C/D) | 수집 완료 | 데이터 검증 |
| 수집 (4-A/B/C/D) | Fetcher 실패 | 상위 Fetcher로 에스컬레이션 |
| 데이터 검증 | 품질 통과 | 프로필 저장 |
| 데이터 검증 | 품질 미달 | 수집 재시도 (최대 2회) |
| 프로필 저장 | 저장 성공 | 엑셀 생성 |
| 프로필 저장 | 저장 실패 | 엑셀 생성 + "파이프라인 미완료" 보고 |
| 엑셀 생성 | 파일 생성 완료 | 완료 보고 |

---

## 3. 구현 스펙

### 폴더 구조

```
/web-crawling-research
  ├── CLAUDE.md                          # 메인 에이전트 지시서
  ├── .gitignore                         # output/, fingerprints/** ignore + profile.json/recipe.md whitelist
  ├── /.claude
  │   └── /skills
  │       └── /web-crawler
  │           ├── SKILL.md               # 크롤링 스킬 정의 (Step 1-A/5-A 게이트 포함)
  │           └── /references
  │               ├── fetcher-patterns.md     # Fetcher별 코드 템플릿
  │               ├── antibot-strategies.md   # Akamai/Cloudflare/SPA 세션 대응
  │               └── troubleshooting.md      # 수집 실패 진단
  ├── /scripts                            # 공유 유틸 (sys.path로 import)
  │   ├── domain_profile.py              # ★ DomainProfile load/save (Step 1-A, 5-A)
  │   ├── chrome_cdp.py                  # Chrome CDP 런처 (Akamai/Naver antibot)
  │   ├── export_excel.py                # openpyxl 엑셀 생성
  │   ├── progress.py                    # 진행상황 체크포인트
  │   ├── utils.py                       # RateLimiter, logger, sanitize_filename
  │   └── <site>_collect_*.py            # 사이트별 수집 스크립트 (런타임에 생성)
  ├── /output                            # 수집 결과물 (gitignore)
  │   └── /<도메인>/<주제_YYYYMMDD_HHMMSS>/
  │       ├── crawl_script.py            # 생성된 수집 스크립트 (런별 보존)
  │       ├── raw_data.json              # 원시 수집 데이터
  │       ├── progress.json              # 진행상황
  │       └── <result>.xlsx              # 최종 엑셀
  ├── /crawl_data                        # Spider pause/resume 체크포인트 (gitignore)
  └── /fingerprints                      # 도메인 프로필 + 셀렉터 핑거프린트
      ├── elements_storage.db            # Scrapling 셀렉터 자가 치유 DB (gitignore)
      └── /<sanitized_domain>/
          ├── profile.json               # ★ 도메인 수집 레시피 (commit 대상, whitelist)
          ├── recipe.md                  # (선택) 추가 노트/마지막 성공 스크립트 발췌 (whitelist)
          └── cookies.json               # (있을 시) 로그인 쿠키 (gitignore)
```

> ★ `fingerprints/<도메인>/profile.json`만 `.gitignore` whitelist로 commit된다. `elements_storage.db`, `cookies*.json`, `auth*.json`, `*token*.json`, `*secret*`은 whitelist를 우회해도 별도 패턴으로 차단된다.

### CLAUDE.md 핵심 섹션 목록

- 프로젝트 개요: 범용 웹 크롤링 에이전트의 목적과 실행 방법
- 워크플로우 요약: 입력 파싱 → 정찰 → 전략 수립 → 수집 → 검증 → 엑셀 참조 안내
- 스킬 호출 규칙: web-crawler 스킬의 트리거 조건과 사용법
- Fetcher 선택 가이드: 상황별 Fetcher 유형 선택 기준 (의사결정 트리)
- 도구 사용 규칙: agent-browser와 Scrapling 각각의 역할 분리 원칙
- 사용자 상호작용 규칙: 언제 되묻고, 언제 알아서 판단하는지 기준
- 에스컬레이션 정책: Fetcher 실패 시 상위 Fetcher로 전환하는 규칙

### 에이전트 구조

**구조 선택**: 단일 에이전트 (CLAUDE.md + 스킬 1개)

**선택 근거**: 워크플로우가 선형적이고, 각 단계가 순차 의존적이므로 서브에이전트 분리의 이점이 없음. 도구 호출(agent-browser, Python 스크립트)은 스킬 내 스크립트로 처리하고, 판단/오케스트레이션은 메인 에이전트가 직접 수행.

#### 메인 에이전트 (CLAUDE.md)
- **역할**: 전체 워크플로우 오케스트레이션, 사용자 대화, 프로필 재사용 판단, 정찰 결과 분석, Fetcher 선택, 수집 전략 결정, 프로필 `notes` 작성
- **담당 단계**: Step 1 (입력 파싱), Step 1-A (프로필 재사용 판단), Step 2 (정찰 지시/분석), Step 3 (전략 수립), Step 5 (검증 판단), Step 5-A (프로필 노트 작성)

### 스킬/스크립트 목록

| 이름 | 유형 | 역할 | 트리거 조건 |
|------|------|------|-----------|
| web-crawler | 스킬 | 크롤링 워크플로우 전체 진행 가이드 (Step 1-A/5-A 게이트 포함) | 사용자가 URL+항목으로 수집 요청 시 |
| `scripts/domain_profile.py` | 스크립트 | `DomainProfile` 클래스 — fingerprints/<도메인>/profile.json load/save/exists/get_antibot_strategy | Step 1-A 조회, Step 5-A 저장 |
| `scripts/chrome_cdp.py` | 스크립트 | `launch_chrome_cdp(port=9222)` + Playwright sync_api 연결 | Akamai(coupang) / naver_antibot(fin.land.naver) 등 chrome_cdp 전략 |
| `scripts/export_excel.py` | 스크립트 | openpyxl로 엑셀 파일 생성 | 데이터 검증 통과 후 |
| `scripts/progress.py` | 스크립트 | 진행상황 체크포인트 (`progress.json`) | 장시간 수집 시 |
| `scripts/utils.py` | 스크립트 | `RateLimiter`, `setup_logger`, `sanitize_filename`, 쿠키 헬퍼 | 다른 스크립트에서 import |
| `output/<도메인>/<주제_TS>/crawl_script.py` | 런타임 산출물 | 사이트별 수집 스크립트 (Step 3에서 생성, FetcherSession/Spider/DynamicFetcher/StealthyFetcher 중 선택) | Step 4에서 실행 |

### 주요 산출물 파일

| 파일 | 형식 | 생성 단계 | 용도 | git tracked |
|------|------|----------|------|-------------|
| `output/<도메인>/<주제_TS>/raw_data.json` | JSON | Step 4 | 수집된 원시 데이터 (검증 전) | ✗ (gitignore) |
| `output/<도메인>/<주제_TS>/crawl_script.py` | Python | Step 3 | 사이트별 생성된 수집 스크립트 (런별 보존) | ✗ (gitignore) |
| `output/<도메인>/<주제_TS>/<result>.xlsx` | XLSX | Step 6 | 최종 산출물 (사용자 전달용) | ✗ (gitignore) |
| `output/<도메인>/cookies.json` | JSON | Step 2-A | 로그인 쿠키 (세션 전달용) | ✗ (gitignore + `**/cookies*.json` 차단) |
| `fingerprints/<sanitized_domain>/profile.json` | JSON | Step 5-A | **도메인 수집 레시피 (재사용 노하우)** | **✓ (whitelist commit)** |
| `fingerprints/<sanitized_domain>/recipe.md` | Markdown | (선택) Step 5-A | 추가 노트/마지막 성공 스크립트 발췌 | ✓ (whitelist commit) |
| `fingerprints/elements_storage.db` | SQLite | Step 4 | Scrapling 셀렉터 핑거프린트 (자가 치유용, 전역 공유) | ✗ (gitignore) |
| `crawl_data/` | 디렉터리 | Step 4 | Spider pause/resume 체크포인트 | ✗ (gitignore) |

---

## 4. 핵심 설계 결정 및 근거

### 도메인 프로필 재사용 전략 (Step 1-A ↔ 5-A)

크롤링은 **첫 정찰이 가장 비싸다** — agent-browser로 사이트 구조를 이해하고 안티봇 유형을 판단하고 셀렉터/API를 식별하는 데 5~20분이 든다. 같은 사이트를 두 번째 수집할 때 이 비용을 반복하지 않으려면 첫 실행 결과를 **버전 관리되는 형태**로 디스크에 박아둬야 한다.

**설계 선택**: `fingerprints/<도메인>/profile.json` 한 파일에 fetcher_type, antibot_type/strategy, selectors, api_endpoints, pagination, notes를 모아 저장. `scripts/domain_profile.py`의 `DomainProfile` 클래스가 load/save 인터페이스 담당.

**게이트 강제 이유**: 시스템이 설계만 되고 운영이 안 됐던 사례가 있었다 (2026-05-13 검토 시점 — coupang.com을 6번 수집했지만 profile.json은 부재). 그래서 Step 5-A를 **선택적 단계가 아니라 필수 게이트**로 박았다. 저장 실패 = 파이프라인 미완료.

**Notes 필드 가치**: selectors/endpoints는 자동 추출 가능하지만, "Akamai라 chrome_cdp 필수", "review API는 JSON이 아니라 HTML 반환", "job_group_id=518이 일반 목록" 같은 **결정적 메타 정보**는 LLM이 정찰 중 깨달은 한두 줄을 적어야 한다. 다음 사람(미래의 나 포함)이 정찰 없이 바로 수집할 수 있는지가 이 필드의 품질로 결정된다.

**Stale 정책**: `last_used`가 3개월 이상 지났거나 사용자가 "최신 구조로 다시" 요구하면 Step 1-A에서 프로필을 무시하고 Step 2로 진행. 그래도 기존 profile은 fallback hint로 활용 (이전에 어떤 fetcher가 통했는지).

### `.gitignore` whitelist 정책

`fingerprints/` 디렉터리는 commit해야 할 것(profile.json — 노하우)과 절대 commit하면 안 되는 것(elements_storage.db — 자동 핑거프린트 + 쿠키류)이 섞여 있다. 통째 ignore하면 노하우가 머신 간에 공유 안 되고, 통째 commit하면 자격증명·바이너리가 새어 나간다.

**해결**: gitignore에서 `fingerprints/**`로 통째 차단한 뒤 `!fingerprints/*/profile.json`과 `!fingerprints/*/recipe.md`만 whitelist. 추가로 whitelist를 우회하더라도 자격증명이 새지 않도록 `**/cookies*.json`, `**/auth*.json`, `**/*token*.json`, `**/*secret*` 패턴을 **whitelist 다음에** 배치 (last-match-wins 규칙으로 차단).

**검증 방법**: `git ls-files --others --exclude-standard fingerprints/` 로 추적 후보를 확인하고 `git check-ignore -v <file>` 로 차단 패턴이 올바른지 확인. 현재 11개 도메인 profile.json만 tracked, elements_storage.db와 cookies는 차단됨.

**profile.json에 토큰 박지 않기**: whitelist commit 대상이므로 API key/JWT/세션 토큰은 profile.json에 직접 적지 않고 별도 `cookies.json`/`auth.json`(차단됨)에 분리. 스킬 가이드(Step 5-A 게이트 규칙 2)에 명시.

### agent-browser vs Scrapling 역할 분리

| 항목 | agent-browser | Scrapling |
|------|--------------|-----------|
| **용도** | 정찰, 수동 로그인, 구조 파악 | 대량 데이터 수집 (모든 유형) |
| **장점** | 실제 브라우저 조작, 시각적 스냅샷, 네트워크 감시 | 빠름, 다단계 Fetcher, 셀렉터 자가 치유, Spider |
| **한계** | 느림, 대량 수집에 부적합 | 시각적 확인 불가, 복잡한 상호작용 제한 |

정찰은 "이해"가 목적이므로 agent-browser의 시각적 확인/네트워크 감시 활용. 수집은 "속도와 안정성"이 목적이므로 Scrapling의 Fetcher 계층 활용.

### Fetcher 에스컬레이션 전략

수집 실패 시 자동으로 상위 Fetcher로 전환:

```
Fetcher (기본) ──실패──→ StealthyFetcher (안티봇)
                              │
                           ──실패──→ DynamicFetcher (브라우저)
                                          │
                                       ──실패──→ agent-browser 폴백 + 사용자 보고
```

### Infinite Scroll 하이브리드 처리

1차 시도: 정찰 시 infinite scroll의 API 엔드포인트 발견 → API 직접 호출 (가장 효율적)
2차 시도: DynamicFetcher로 스크롤 + 렌더링 + 파싱
3차 폴백: agent-browser로 수동 스크롤 → DOM 추출 → Scrapling Selector로 파싱

### Spider 활용 기준

| 조건 | 방식 |
|------|------|
| 500건 미만, 단일 리스트 | Session 클래스로 순차 처리 |
| 500건 이상, 단일 리스트 | Spider + 단일 세션 |
| 여러 카테고리 동시 수집 | Spider + multi-session routing |
| 장시간 수집 (1000건+) | Spider + `crawldir` (pause/resume 지원) |

### Rate Limiting 전략

| 수집 규모 | 요청 간격 | Spider concurrent_requests |
|----------|----------|---------------------------|
| ~100건 | 1초 | 해당 없음 (Session) |
| 100~500건 | 1.5초 | 해당 없음 (Session) |
| 500~2000건 | 1.5초 | 5 |
| 2000건 이상 | 2초 + 100건마다 15초 휴식 | 3 |

사이트의 robots.txt와 응답 시간을 참고하여 에이전트가 동적으로 조정.

### 에러 복구 전략

| 에러 유형 | 대응 |
|----------|------|
| HTTP 429 (Rate Limit) | 대기 시간 2배 증가 후 재시도 |
| HTTP 403 (Forbidden) | StealthyFetcher로 에스컬레이션 |
| Cloudflare Challenge | `StealthyFetcher(solve_cloudflare=True)` |
| 셀렉터 매칭 실패 | `adaptive=True`로 자가 치유 시도 |
| 페이지 구조 완전 변경 | 에이전트에 돌아가 정찰 재실행 |
| JS 렌더링 실패 | DynamicFetcher로 에스컬레이션 |
| 네트워크 타임아웃 | 3회 재시도 후 해당 페이지 스킵 + 로그 |
| 수집 데이터 0건 | 즉시 중단, 사용자에게 보고 |
| Spider 중단 (Ctrl+C) | `crawldir`에서 자동 체크포인트, 재실행 시 이어서 수집 |

### 쿠키 전달 흐름

```
agent-browser (수동 로그인)
       │
       ▼
  쿠키 추출 → /output/cookies_<도메인>.json 저장
       │
       ▼
  Scrapling Session에 쿠키 주입
  ┌─────────────────────────────────────────┐
  │ with FetcherSession() as session:       │
  │     session.cookies.update(loaded_cookies) │
  │     resp = session.get(url)             │
  └─────────────────────────────────────────┘
```
