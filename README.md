# 범용 웹 크롤링 에이전트

URL과 수집 항목을 자연어로 설명하면 자동으로 사이트를 정찰하고 데이터를 수집하여 엑셀로 출력하는 에이전트.

## 핵심 도구

| 도구 | 역할 |
|------|------|
| **agent-browser** | 정찰 전용 — 사이트 구조 파악, 네트워크 감시, 수동 로그인 |
| **Scrapling** | 수집 전용 — HTTP/브라우저 기반 데이터 수집, 셀렉터 자가 치유 |
| **openpyxl** | 엑셀 파일 생성 |

## 워크플로우

```
1.  입력 파싱 (URL + 수집 항목 추출)
1-A. 도메인 프로필 조회 ── 있음 + 재사용 OK ──→ 3 로 점프 (정찰 스킵)
2.  정찰 (agent-browser)
3.  수집 전략 + Fetcher 선택
4.  crawl_script.py 생성 & 실행
5.  데이터 검증
5-A. 도메인 프로필 저장 (필수 게이트 — 누락 시 파이프라인 미완료)
6.  엑셀 생성
```

## Fetcher 선택

```
API 발견? → FetcherSession (HTTP)
안티봇? → StealthyFetcher / Chrome CDP (Akamai/Naver)
JS 렌더링? → DynamicFetcher (Playwright)
기본 → Fetcher (HTTP)
```

수집 실패 시 자동 에스컬레이션: `Fetcher → StealthyFetcher → DynamicFetcher → agent-browser`

## 도메인 프로필 (재수집 가속)

같은 사이트를 다시 수집할 때 정찰을 스킵할 수 있도록, 수집 성공 시 `fingerprints/<도메인>/profile.json`에 레시피를 저장한다.

```json
{
  "domain": "wanted.co.kr",
  "fetcher_type": "FetcherSession",
  "antibot_type": "none",
  "antibot_strategy": "none",
  "site_type": "api",
  "selectors": {},
  "pagination": { "type": "offset", "param": "offset", "limit": 20 },
  "api_endpoints": [{ "url": "...", "method": "GET", "params": {...}, "field_mapping": {...} }],
  "notes": "다음 사람이 정찰 없이 바로 수집할 수 있는 결정적 한두 줄",
  "last_used": "2026-03-25"
}
```

- **저장은 필수.** Step 5-A 게이트에서 강제 — 빠뜨리면 다른 머신/세션에서 노하우가 사라진다
- **`notes` 비우지 않기.** "Akamai라 chrome_cdp 필수", "review API는 HTML 반환" 같은 결정적 메타 정보 한두 줄
- **자격증명 박지 않기.** profile.json은 commit 대상이므로 API key/토큰/쿠키는 별도 파일로 분리

현재 11개 도메인 프로필이 commit되어 있다: `books.toscrape.com`, `brand.naver.com`, `builtini.co.kr`, `coupang.com`, `data.seoul.go.kr`, `fin.land.naver.com`, `g2b.go.kr`, `made-in-china.com`, `smartstore.naver.com`, `wanted.co.kr`, `www.kurly.com`.

## 출력 구조

```
output/                              # gitignore — 수집 결과물
└── <도메인>/
    └── <주제_YYYYMMDD_HHMMSS>/
        ├── crawl_result.xlsx        # 최종 엑셀
        ├── raw_data.json            # 원시 데이터
        └── crawl_script.py          # 생성된 수집 스크립트

fingerprints/                        # gitignore + whitelist
├── elements_storage.db              # ignored — Scrapling 셀렉터 자가 치유 DB
└── <sanitized_domain>/
    ├── profile.json                 # ✓ tracked — 도메인 수집 레시피
    ├── recipe.md                    # ✓ tracked (선택) — 추가 노트
    └── cookies.json                 # ignored — 로그인 쿠키
```

## .gitignore 정책

`fingerprints/**`를 통째로 ignore하되, `profile.json`과 `recipe.md`만 whitelist로 commit. 그 다음 줄에서 `**/cookies*.json`, `**/auth*.json`, `**/*token*.json`, `**/*secret*` 패턴으로 자격증명 류를 재차단 (last-match-wins).

검증:
```bash
git ls-files --others --exclude-standard fingerprints/   # 추적 후보 확인
git check-ignore -v <path>                                # 차단 패턴 확인
```

## 참고 문서

- `CLAUDE.md` — 메인 에이전트 지시서
- `.claude/skills/web-crawler/SKILL.md` — 워크플로우 (Step 1-A/5-A 게이트 포함)
- `.claude/skills/web-crawler/references/` — fetcher-patterns / antibot-strategies / troubleshooting
- `blueprint-web-crawler.md` — 시스템 설계서
