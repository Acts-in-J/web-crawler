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
| **Node.js 18 이상** | `node --version` | [nodejs.org](https://nodejs.org/) 에서 설치 (agent-browser용) |

### AI 에이전트에게 셋업 맡기기 (권장)

아래 내용을 **그대로 복사**해서 Claude Code 또는 Codex에게 주세요:

```text
이 레포의 크롤링 환경을 셋업해줘.

1. Python 패키지 설치: `pip install -r requirements.txt` 를 실행해.
   이어서 브라우저 의존성을 받기 위해 `scrapling install` 과
   `playwright install chromium` 도 실행해줘.

2. agent-browser CLI 설치(정찰용): `npm install -g agent-browser` 로
   글로벌 설치하고, `agent-browser install` 로 Chrome을 셋업해줘.
   - PowerShell 실행 정책 오류가 나면 `agent-browser.cmd` 를 사용해.
   - 일반 Chrome이 없어도 중단하지 마. `agent-browser install` 이
     별도 Chrome for Testing을 설치할 수 있어.
   - node/npm·네트워크·권한 문제로 실패하면 원인만 명확히 보고해.

3. 설치 검증: `python scripts/smoke_test.py` 를 실행해서
   Fetcher / StealthyFetcher / DynamicFetcher 가 모두 [PASS] 인지 확인하고,
   CLI 버전·Chrome 경로와 함께 결과를 요약해줘.
```

### 수동 설치

**1단계 — Python 패키지 (수집·엑셀)**

```bash
pip install -r requirements.txt    # scrapling, openpyxl, playwright, pytest
scrapling install                  # Scrapling용 브라우저(Camoufox/Chromium) 다운로드
playwright install chromium        # Playwright용 Chromium 다운로드
```

**2단계 — agent-browser (정찰용)**

```bash
npm install -g agent-browser       # CLI 글로벌 설치
agent-browser install              # Chrome 셋업 (없으면 Chrome for Testing 자동 설치)
```

- Windows PowerShell에서 **실행 정책 오류**가 나면 `agent-browser` 대신 **`agent-browser.cmd`** 를 쓰세요.
- 참고: [github.com/vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser)
- > **Claude Code·Codex 모두 사용합니다.** agent-browser는 독립 CLI라 양쪽 host에서 동일하게 정찰에 씁니다. (사용법은 정찰 전 `agent-browser skills get core --full`로 불러오면 됩니다 — CLI에 내장돼 항상 버전 일치.) 설치가 안 됐거나 브라우저 실행이 막힌 환경이라면 정찰을 Playwright / Scrapling `DynamicFetcher`로 대체합니다.

**3단계 — 설치 확인**

```bash
python scripts/smoke_test.py       # 전부 [PASS]면 수집 환경 정상
pytest scripts/ -q                 # (선택) 단위 테스트 실행
```

### 핵심 도구 요약

| 도구 | 역할 | 설치 |
|------|------|------|
| **Scrapling** | 데이터 수집 (HTTP·브라우저, 셀렉터 자가치유) | `pip install -r requirements.txt` + `scrapling install` |
| **Playwright** | 브라우저 렌더링 (Scrapling 백엔드 / Codex 정찰) | (위 pip에 포함) + `playwright install chromium` |
| **openpyxl** | 엑셀(.xlsx) 출력 | (위 pip에 포함) |
| **agent-browser** | 정찰 — 구조 파악·네트워크 감시 (양 host 공통) | `npm install -g agent-browser` + `agent-browser install` |
| **Chrome / Chrome for Testing** | Akamai 등 고급 안티봇 대응 (CDP) | `agent-browser install` 이 함께 처리 |

---

## 작동 방식 (요약)

에이전트는 다음 7단계로 움직입니다. 자세한 규칙은 `.claude/skills/web-crawler/SKILL.md`에 있습니다.

```
1.  입력 파싱 (URL + 수집 항목 추출)
1-A. 도메인 프로필 조회 ── 있음 + 재사용 OK ──→ 3 으로 점프 (정찰 스킵)
2.  정찰 (사이트 구조·API·페이지네이션 파악)
3.  수집 전략 + Fetcher 선택
4.  수집 스크립트(crawl_script.py) 생성 & 실행
5.  데이터 검증 (건수·빈값·PII 확인)
5-A. 도메인 프로필 저장 (필수 — 다음 수집 가속)
6.  엑셀 생성 & 결과 보고
```

### 수집 방법(Fetcher)은 사이트에 따라 자동 선택

```
API 발견?        → FetcherSession (가장 빠름)
안티봇 보호?      → StealthyFetcher (Cloudflare) / Chrome CDP (Akamai)
JS 렌더링 필요?   → DynamicFetcher (브라우저 렌더링)
그 외            → Fetcher (기본 HTTP)
```

수집이 실패하면 자동으로 상위 방법으로 단계적 전환(에스컬레이션)합니다.

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

현재 12개 도메인 프로필이 포함되어 있습니다: `books.toscrape.com`, `brand.naver.com`, `builtini.co.kr`, `coupang.com`, `data.seoul.go.kr`, `fin.land.naver.com`, `g2b.go.kr`, `made-in-china.com`, `smartstore.naver.com`, `wanted.co.kr`, `www.fss.or.kr`, `www.kurly.com`.

---

## 출력 구조

```
output/                              # gitignore — 수집 결과물
└── <도메인>/
    └── <주제_YYYYMMDD_HHMMSS>/
        ├── crawl_result.xlsx        # 최종 엑셀
        ├── raw_data.json            # 원시 데이터
        └── crawl_script.py          # 생성된 수집 스크립트

fingerprints/                        # gitignore + whitelist
├── elements_storage.db              # ignored — Scrapling 셀렉터 자가치유 DB
└── <sanitized_domain>/
    ├── profile.json                 # ✓ tracked — 도메인 수집 레시피
    ├── recipe.md                    # ✓ tracked (선택) — 추가 노트
    └── cookies.json                 # ignored — 로그인 쿠키
```

## 안전 규칙 (에이전트가 항상 지킴)

- **CAPTCHA 자동 우회 안 함** — 뜨면 사용자에게 보고 후 중단
- **로그인 자격증명 저장 안 함** — 사용자가 직접 로그인 → 쿠키만 추출
- **robots.txt 차단 시 사용자에게 확인**
- **PII(전화번호·주민번호·이메일 등) 감지 시 경고·보고**
- **불법 스크래핑(저작권·개인정보 대량수집·ToS 위반) 거절**

## .gitignore 정책

`fingerprints/**`를 통째로 ignore하되 `profile.json`과 `recipe.md`만 whitelist로 commit. 이어서 `**/cookies*.json`, `**/auth*.json`, `**/*token*.json`, `**/*secret*` 패턴으로 자격증명을 재차단(last-match-wins).

```bash
git check-ignore -v <path>           # 어떤 패턴에 막혔는지 확인
```

## 참고 문서

- `CLAUDE.md` — 메인 에이전트 지시서 (양 host SSOT)
- `AGENTS.md` — Codex 실행 계약 (최초 셋업 포함)
- `.claude/skills/web-crawler/SKILL.md` — 워크플로우 (Step 1-A/5-A 게이트 포함)
- `.claude/skills/web-crawler/references/` — fetcher-patterns / antibot-strategies / troubleshooting
- `blueprint-web-crawler.md` — 시스템 설계서
