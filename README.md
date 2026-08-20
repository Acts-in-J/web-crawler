# 범용 웹 크롤링 에이전트

여러 웹사이트에서 원하는 정보를 **자동으로 모아 엑셀로 정리**해 주는 AI 에이전트입니다. 코딩을 몰라도, *"이 사이트에서 이런 걸 모아줘"* 라고 말하면 에이전트가 알아서 사이트를 살펴보고(정찰), 데이터를 수집하고, 엑셀 파일로 만들어 줍니다.

> 직접 프로그램을 짜는 게 아닙니다. **Claude Code나 Codex 같은 AI 코딩 에이전트**에게 자연어로 부탁하면, 이 레포에 담긴 도구·규칙·과거 수집 노하우를 따라 에이전트가 대신 수집해 줍니다.

## 시작하기 전에 — 어디까지 수집해도 되나

크롤링은 "되는 것/안 되는 것" 의 이분법이 아닙니다. **논란이 없는 영역부터** 보여드립니다.

### 1. 녹색 지대 — 여기부터 시작하세요

1. **공식 API·공개 데이터 포털** — `data.go.kr`, 서울 열린데이터광장, 공공누리.
   제공자가 명시적으로 허용한 것이라 엄밀히는 크롤링도 아닙니다.
2. **명시적 라이선스가 붙은 데이터** — CC 라이선스, 공공누리 유형표시. 조건만 지키면 됩니다.
3. **내가 소유한 사이트 / 서면 허가를 받은 사이트**
4. **연습용 사이트** — `books.toscrape.com`, `quotes.toscrape.com`
5. **위 넷에 해당하지 않아도, 아래 여섯 조건을 지키면 검색엔진 크롤러가 매일 하는 일과 기술적으로 다르지 않습니다.**

### 2. 여섯 조건 체크리스트

```
① 접근   기술적 우회 없음  AND  약관·robots 가 금지하지 않음
② 부담   사람 한 명 수준 이하 (초당 1건 이하 · 총량 상한 · 429 뜨면 중단)
③ 성격   개인정보 아님
④ 분량   저작물 본문이 아니고, DB 전체의 "상당한 부분" 이 아님 — 필요한 만큼만
⑤ 이용   내 영업에서 원 서비스를 대체하거나 경쟁하지 않음
⑥ 흔적   숨지 않음 — User-Agent 에 신원·연락처, 로그 보관
```

> ① 을 확인하는 법 — 에이전트에게 "이 사이트 robots.txt 와 약관 확인해줘" 라고 하면 대신 확인합니다.

**여섯을 다 지키면 녹색, 하나가 빠지면 노랑, ① 의 앞쪽(기술적 우회)이 빠지면 빨강입니다.**
우회를 따로 빼는 이유는 **거기서 형사 층이 가장 먼저, 가장 확실하게 켜지기** 때문입니다.
약관만 금지하고 우회는 없는 경우는 원칙적으로 계약 문제입니다 — 빨강이 아니라 짙은 노랑입니다.
다만 ② 부담(업무방해)·③ 개인정보·④ 분량(저작권법 §136)에도 각각 형사 조항이 있으니
노랑을 "민사만" 으로 읽지 마세요.

④ 가 가장 자주 빠뜨리는 축입니다. 저작권법 §93② 은 **소량이라도 반복적·체계적으로 복제해
원 DB 의 통상적 이용과 충돌하거나 DB제작자의 이익을 부당하게 해치면 "상당한 부분의 복제" 로
본다**고 정합니다 — 두 갈래 중 **하나만** 해당해도 됩니다. 하루 10건씩 매일 긁는 것은 "10건"
이 아닙니다 — **같은 사이트라도 10건과 전부는 질적으로 다른 행위**입니다.

⑥ 은 법적 요건이 아니지만 실무에서 결정적입니다. 숨지 않는 것이 "고의·악의 없음" 의 가장 좋은
증거이고, 대부분의 사이트는 자기를 밝히는 봇을 그냥 둡니다.

### 3. 자주 하는 오해

**Q. 공개된 페이지니까 마음껏 긁어도 되나요?**
A. "공개" 는 **기술적 장벽**이 없다는 뜻이지 **약관이 허용**한다는 뜻이 아닙니다.
미국 hiQ 사건에서 법원은 공개 프로필 수집에 해킹법(CFAA)은 적용되지 않는다고 보면서도
**이용약관 위반은 별개로 인정**했고, hiQ 는 50만 달러로 마무리했습니다.
기술적으로 열려 있다는 것과 계약상 허용된다는 것은 다른 층입니다.

**Q. 개인정보만 아니면 되나요?**
A. 아닙니다. 사실 정보라도 **체계적으로 모아둔 집합에는 별도 권리**가 붙습니다.
경쟁사가 잡코리아의 채용공고를 긁어간 사건에서, 법원은 **DB제작자 권리 침해**를 인정해
4.5억 원 배상을 명했습니다.
보호받은 것은 개별 공고의 창작성이 아니라 **모아둔 투자**입니다.

**Q. 팔지 않고 회사 내부 분석용으로만 쓰면 괜찮나요?** ← **가장 흔한 오해**
A. **네 축 중 하나만 낮아집니다.** 접근(침입·우회)·부담(업무방해)·개인정보는 그대로입니다.
형사 층은 접근·부담뿐 아니라 개인정보에도 걸쳐 있어서 "내부용이니 형사는 괜찮다" 는
성립하지 않습니다. 함정이 셋 더 있습니다:

- **저작권법의 "사적이용"(§30) 은 회사 내부를 포함하지 않습니다.** 조문은 *"영리를 목적으로
  하지 아니하고"* 와 *"개인적으로 이용하거나 가정 및 이에 준하는 한정된 범위 안에서"* 를
  **둘 다** 요구합니다. 뒤쪽은 "개인적 이용" 이나 "가정에 준하는 한정된 범위" 중 **하나만**
  충족하면 되는 선택지지만, 회사 내부의 조직적 복제는 앞 요건과 뒤 선택지 **양쪽 모두에서
  걸립니다** — 통설과 실무는 **기업 내부의 조직적 복제를 여기서 배제**합니다. "회사 내부" 는
  "사적" 의 확장이 아니라 정반대입니다.
- **부정경쟁방지법은 "영리" 가 아니라 "자신의 영업을 위하여" 를 봅니다.** 경쟁사 가격을 긁어
  내부 가격 결정에 쓰면, 팔지 않았어도 명백히 영업을 위한 것입니다.
- **개인정보보호법은 영리 여부를 묻지 않습니다.**

실제로 낮아지는 것은 **배상액 산정**과 **발각 가능성**이지 위법성 자체가 아닙니다.

### 4. 이 도구가 하는 일

robots.txt 는 법적 구속력이 없지만 표지판입니다. 무시했다는 사실은 "알고도 했다" 의 정황이 됩니다.

이 도구는 차단된 사이트에 대해 **우회를 시도할 수 있는 능력을 제공하지만, 그 도메인에서 처음
그 지점에 닿을 때 한 번 확인을 구합니다.** 진행 여부의 판단과 그 결과에 대한 책임은 사용자에게
있습니다.

**막히면 여기로 돌아오세요.** 여섯 중 무엇이 빠졌는지 짚고, 채울 수 있으면 채우고,
못 채우면 녹색 지대의 대안(공식 API·공개 데이터 포털)을 먼저 찾습니다.

> *작성자는 변호사가 아니며 위 내용은 법률 자문이 아닙니다. 상업적 이용 전 전문가 확인을 권합니다.*
> 자세한 이용 범위는 [`ACCEPTABLE_USE.md`](ACCEPTABLE_USE.md) 를 참고하세요.

## 이런 걸 할 수 있어요

- 🛒 쇼핑몰 상품 목록·가격·리뷰
- 📋 정부·공공 입찰공고·공시 (나라장터, 금융감독원, 서울 열린데이터광장 등 공공데이터)
- 💼 채용공고
- 🏢 부동산·기업정보 등 목록형 데이터
- 📚 연습용 사이트 (`books.toscrape.com` 등) — 처음 써 볼 때 여기부터

결과는 항상 깔끔한 **엑셀(.xlsx)** 파일로 나옵니다.

> 어떤 사이트에서 수집할지는 사용자가 정합니다. 시작 전에 위 [여섯 조건](#2-여섯-조건-체크리스트)을 확인하세요.

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

> 💡 **가장 쉬운 방법** — 아래 [AI 에이전트에게 셋업 맡기기](#ai-에이전트에게-셋업-맡기기)의 프롬프트를 복사해 에이전트에게 주면 알아서 다 설치합니다. 직접 하고 싶으면 그 아래 [수동 설치](#수동-설치-단계별)를 따라 하세요.

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
| **Chrome / Chrome for Testing** | 브라우저 세션이 필요한 사이트 대응 (CDP) | `agent-browser install` 이 함께 처리 |

> **왜 정찰에만 Node 런타임(agent-browser)이 필요한가.** Playwright 는 Scrapling 으로 이미 깔려오지만,
> agent-browser 는 AI 에이전트가 몰기 좋은 형태(snapshot/ref)로 설계돼 있어 같은 정찰을 훨씬 적은
> 토큰으로 끝냅니다. 두 번째 런타임을 설치하는 비용을 주고 그 편의를 산 것이고, **의식적인 선택**입니다.
> 수집에는 쓰지 않습니다 — 정찰과 수집은 분리돼 있습니다.

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

### 수집 방법(Fetcher)은 사이트에 따라 선택 — 어디까지가 자동인가

```
[자동]  API 발견?       → plain_session (숨은 API — 가장 빠름)
        JS 렌더링 필요? → DynamicFetcher (브라우저 렌더링)
        그 외           → plain_get (기본 HTTP, 위장 없음)
   │
   │ 위 셋이 다 막히면 = 사이트가 자동 접근을 거절하고 있다는 뜻
   ▼
■ 여기서 한 번 물어봅니다 ■  [진행 / 중단]
   │
   ▼
[확인 후]  그 외 WAF·단순 403 : curl_cffi 경량 그리드 (브라우저 X)
           Cloudflare        : StealthyFetcher
           Akamai/고급 WAF   : Chrome CDP (앞 단계 건너뜀)
```

수집이 실패하면 **가벼운 것부터** 자동으로 단계적 전환합니다 — `plain_get → plain_session → DynamicFetcher`. 여기까지는 사이트가 나를 막은 게 아니라 **데이터가 있는 위치가 다를 뿐**이라 자동으로 진행합니다.

**그 위부터는 자동으로 넘어가지 않습니다.** 사이트가 자동 접근을 차단하고 있다면(봇 탐지·WAF·CAPTCHA), 에이전트가 **한 번 알리고 진행 여부를 묻습니다.** '진행' 을 고르면 그대로 진행하며 — 근거를 제출받거나 검증하지 않습니다 — 그 선택은 도메인 프로필에 기록됩니다. 같은 사이트를 다시 수집할 때는 묻지 않습니다.

판단의 주체를 도구에서 사용자로 옮기는 것이 이 확인 절차의 목적입니다.

---

## 도메인 프로필 (재수집 가속)

같은 사이트를 다시 수집할 때 정찰을 건너뛸 수 있도록, 수집에 성공하면 `fingerprints/<도메인>/profile.json`에 "수집 레시피"를 저장합니다. 다음번엔 이 레시피만 보고 바로 수집에 들어갑니다.

```json
{
  "domain": "example.com",
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
- **`notes` 비우지 않기.** "이 사이트는 브라우저 세션이 필요 — chrome_cdp", "review API는 HTML 반환" 같은 결정적 메타 정보.
- **자격증명 박지 않기.** 배포되는 profile.json은 commit 대상이므로 API key/토큰/쿠키는 별도 파일로 분리.
- **확인을 거친 프로필은 그 선택을 함께 기록한다.** 자동 접근 차단을 넘어선 방법으로 수집했다면 `consent` 블록(알린 시각과 사용자의 선택)이 함께 저장됩니다. 무엇을 정당화했는지가 아니라 **알렸고 사용자가 골랐다는 사실**만 남습니다.

> **이미 `fingerprints/` 를 갖고 있다가 이 버전으로 올린 경우.** 확인 절차를 넘어선 방법(예: `chrome_cdp`, `stealthy`)이 적힌 기존 프로필에 `consent` 기록이 없으면, 다음 저장에서 `ConsentRequired` 로 한 번 멈춥니다. **버그가 아니라 설계된 동작입니다** — 예전에는 그런 프로필이 조용히 배포 대상으로 분류됐고, 이제는 사용자에게 한 번 알린 사실이 있어야 저장이 끝납니다. 알리고 '진행' 을 고른 뒤 그 시각과 선택을 `consent` 에 적으면 이어서 진행되고, 그 도메인은 다음부터 다시 묻지 않습니다.

<!-- BEGIN GENERATED: domain-list -->
<!-- 이 블록은 scripts/sync_domain_list.py 가 생성한다. 직접 수정하지 말 것. -->

현재 14개 도메인 프로필이 포함되어 있습니다: `books.toscrape.com`, `builtini.co.kr`, `celimax.co.kr`, `data.seoul.go.kr`, `db.itkc.or.kr`, `g2b.go.kr`, `guesskorea.com`, `made-in-china.com`, `wanted.co.kr`, `www.11st.co.kr`, `www.fss.or.kr`, `www.gsmarena.com`, `www.k-startup.go.kr`, `www.kurly.com`.

<!-- END GENERATED: domain-list -->

---

## 레포 구조

**이 레포 하나가 전부입니다.** 별도의 내부 저장소는 없습니다. 커밋되는 것은 코드와 수집 레시피뿐이고, **실제로 수집한 데이터는 어떤 경로로도 커밋되지 않습니다.**

| 경로 | 상태 | 내용 |
|------|------|------|
| `scripts/` · `.claude/` · `.codex/` | ✓ tracked | 공통 모듈, 에이전트 지시서·스킬 |
| `fingerprints/<도메인>/profile.json` | 배포 판정 통과분만 tracked | 도메인 수집 레시피 (자격증명 제외). 판정은 `scripts/profile_policy.py` |
| `output/` | 로컬 전용 | 수집 결과물 — 제3자 콘텐츠·PII 가능 |
| `autoresearch-web-crawler/` | 로컬 전용 | 스킬 평가 실험 run 데이터 |
| `docs/` | 로컬 전용 | 내부 기획·설계 노트 |
| `fingerprints/elements_storage.db` | 로컬 전용 | Scrapling 셀렉터 자가치유 DB |
| `**/cookies*.json` · `**/*auth*.json` | 로컬 전용 | 로그인 쿠키·토큰 |

### 출력 디렉터리

```
output/                              # gitignore — 수집 결과물
└── <도메인>/                        # 예: example.com
    ├── <주제_YYYYMMDD_HHMMSS>/      # 실행 건별 폴더
    │   ├── crawl_result.xlsx        # 최종 엑셀
    │   ├── raw_data.json            # 원시 데이터
    │   ├── progress.json            # 진행 상황 (중단 시 이어서 수집)
    │   └── crawl_script.py          # 생성된 수집 스크립트
    └── cookies.json                 # ignored — 로그인 쿠키 (같은 사이트의 모든 작업이 공유)

fingerprints/                        # gitignore + 배포 화이트리스트 (default-deny)
├── elements_storage.db              # ignored — Scrapling 셀렉터 자가치유 DB (전역 공유)
└── <sanitized_domain>/              # 예: example_com, www_example_co_kr
    ├── profile.json                 # 배포 판정 통과분만 tracked — 도메인 수집 레시피
    └── recipe.md                    # 배포 판정 통과분만 tracked (선택) — 추가 노트
```

## 안전 규칙 (에이전트가 항상 지킴)

- **자동 접근 차단을 만나면 한 번 확인** — CAPTCHA·WAF·봇 탐지를 만나면 자동으로 넘어가지 않고 사용자에게 알리고 묻습니다. *능력이 없어서가 아니라, 판단의 주체가 사용자이기 때문입니다.* '진행' 을 고르면 그대로 진행합니다
- **CAPTCHA 자동 풀이는 하지 않음** — 위 확인과 별개입니다. *프로그램으로 CAPTCHA 를 푸는 것은 보호조치의 직접적 무력화입니다.* 사용자가 직접 풀고 이어가는 것은 가능합니다
- **로그인 자격증명 저장 안 함** — 사용자가 직접 로그인하고 쿠키만 추출합니다. *자격증명이 파일이나 로그에 남지 않게 하기 위해서입니다*
- **robots.txt 를 실제로 확인** — 정찰 전에 `check_robots()` 로 읽고, 차단이면 사용자에게 묻습니다. *robots.txt 는 법적 구속력이 없지만, 무시했다는 사실은 "알고도 했다" 의 정황이 됩니다*
- **요청 간격** — 기본 1~2초 간격, 지연 하한 0.5초, 연속 rate limit 응답 3회면 중단합니다. **총 요청 상한은 기본값이 없습니다 — `max_requests` 로 직접 설정하세요.** *부담은 접근과 별개 축이고 여기에도 형사 층(업무방해)이 있습니다*
- **PII 감지 시 경고·보고** — 값 패턴(이메일·전화)과 컬럼명(작성자·닉네임 등) 양쪽을 봅니다. *개인정보보호법은 영리 여부를 묻지 않습니다*
- **명백히 위법한 요청은 거절** — 저작권 침해 목적의 본문 복제, 개인정보 대량수집, 명시적으로 금지된 재배포 등. *약관이 크롤링을 금지한다는 사실만으로는 여기 해당하지 않습니다 — 그건 위 ① 의 계약 층이고, 확인 절차로 갑니다.*
- **수집한 데이터의 이용 범위는 사용자 책임** — 이 도구는 수집을 돕지, 수집 이후의 재배포·경쟁 서비스·학습데이터 이용에 대해 판단하지 않습니다. *"어떻게 들어갔나" 와 "가져다 뭘 했나" 는 다른 질문이고 다른 법이 답합니다*

> **'거절' 과 '확인' 은 다른 층위입니다.** 거절은 **요청 자체를** 받지 않는 것이고, 확인은 수집
> 도중 기술적 차단을 만났을 때 **알리고 사용자가 고르는** 것입니다. 확인 절차는 거절하지
> 않습니다 — '진행' 을 뒤집는 근거로 쓰이지 않습니다.

## .gitignore 정책

단일 public 레포이므로, 수집한 데이터가 실수로 공개되지 않도록 세 겹으로 막습니다.

1. **수집 결과물 통째 차단** — `output/`, `crawl_data/`, `autoresearch-web-crawler/`, `docs/`. 스크랩한 제3자 콘텐츠(리뷰 본문·작성자명 등)가 레포에 들어가지 않습니다.
2. **fingerprints 배포 화이트리스트 (default-deny)** — `fingerprints/**` 를 통째로 ignore 하고, **배포 대상으로 판정된 프로필만** 명시적으로 whitelist 합니다. 이 목록은 `scripts/profile_policy.py` 의 판정 결과로 `scripts/sync_domain_list.py` 가 생성합니다. 자동 접근 차단을 넘어선 방법을 기록한 프로필은 **로컬에 남되 배포되지 않습니다** — 능력은 그대로고 레시피만 빠집니다.
3. **자격증명 재차단** — `**/cookies*.json`, `**/*auth*.json`, `**/*token*.json`, `**/*secret*` 를 whitelist **뒤에** 배치해 last-match-wins로 다시 막습니다.

```bash
git check-ignore -v <path>           # 어떤 패턴에 막혔는지 확인
git diff --cached --name-only        # commit 직전 무엇이 올라가는지 확인
```

## 참고 문서

- `ACCEPTABLE_USE.md` — 이용 범위·사용자 책임·기여자 규칙
- `CLAUDE.md` — 메인 에이전트 지시서 (양 host SSOT)
- `AGENTS.md` — Codex 실행 계약 (최초 셋업 포함)
- `.claude/skills/web-crawler/SKILL.md` — 워크플로우 (Step 1-A/5-A 게이트 포함)
- `.claude/skills/web-crawler/references/` — fetcher-patterns / antibot-strategies / troubleshooting
