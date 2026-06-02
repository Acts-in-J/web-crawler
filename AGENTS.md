# AGENTS.md — web-crawling-research (Codex / Claude Code dual-host)

이 레포는 URL과 수집 항목을 받아 사이트를 정찰·대량수집하고 엑셀로 내보내는 범용 웹 크롤링 에이전트다. **`CLAUDE.md`와 `.codex/skills/web-crawler/SKILL.md`가 *어떻게*에 대한 SSOT다.** 이 파일은 Codex용 **실행 계약**이다 — Claude Code는 Skill 런타임으로 같은 규율을 자동 적용받지만, Codex는 Skill 런타임이 없으므로 이 파일이 대신 강제한다.

## 최초 환경 셋업 (클론 직후 1회)

수집을 시도하기 전에 환경이 준비됐는지 확인한다. 미설치면 아래를 실행:

```bash
pip install -r requirements.txt    # scrapling, openpyxl, playwright, pytest
scrapling install                  # Scrapling용 브라우저(Camoufox/Chromium)
playwright install chromium        # 정찰/렌더링용 Chromium
npm install -g agent-browser && agent-browser install   # 정찰 CLI (양 host 공통; PowerShell 정책 오류 시 agent-browser.cmd)
python scripts/smoke_test.py       # 검증: Fetcher/StealthyFetcher/DynamicFetcher 전부 [PASS]면 정상
```

`agent-browser`는 독립 CLI라 Codex에서도 동일하게 쓴다. 설치/실행이 막힌 제한된 환경이면 정찰을 Playwright/`DynamicFetcher`로 대체. 전체 셋업 가이드는 `README.md`의 "처음 설치하기" 참조.

## 스킬 소스 (생성 미러)

- **`.claude/skills/`가 정본. `.codex/skills/`는 생성 미러**다 — 텍스트 안의 `.claude/skills` 경로만 `.codex/skills`로 치환된 것 외엔 byte-identical.
- **`.codex/skills/`를 직접 수정하지 말 것.** `.claude/skills/`를 고친 뒤 `python scripts/sync_codex_mirror.py`를 실행해 미러를 재생성한다. (어긋남 확인: `python scripts/sync_codex_mirror.py --check`)

## 크롤링 요청을 받으면 — 필수 절차

사용자가 "크롤링/스크래핑/수집/~를 모아줘/입찰공고 수집" 등을 요청하면:

1. **즉흥 처리 금지.** `.codex/skills/web-crawler/SKILL.md`를 단계대로 실행한다. 절차를 요약하고 임의로 구현하지 않는다. **폴백 재구현 금지** — `requests`/`urllib`/`httpx`/`BeautifulSoup`로 직접 수집하거나 인라인으로 긁지 않는다. 수집은 항상 생성한 `crawl_script.py` 안의 **Scrapling 또는 Playwright**로만 한다.

2. **절대 규칙 0 — 도메인 히스토리 우선.** 정찰하기 전에 반드시 `fingerprints/<sanitized_domain>/profile.json`과 `output/<도메인>/`을 먼저 본다. 프로필이 있으면 `notes`/`fetcher_type`/`antibot_strategy`를 그대로 채택하고 정찰을 건너뛰어 Step 3으로 점프한다. profile.json이 있는데 무시하고 정찰부터 다시 하는 것은 금지(5~20분 비싼 작업 반복). 알려진 도메인 목록은 `CLAUDE.md` 참조 (coupang.com, g2b.go.kr, wanted.co.kr, www.kurly.com 등).

3. **프로필 게이트.** Step 1-A(프로필 있으면 load) ↔ Step 5-A(수집 성공 직후 save/갱신, `notes` 필드 필수). Step 5-A를 빠뜨리면 수집 결과가 살아있어도 **"파이프라인 미완료"**로 보고한다.

## 정찰 도구 — 양 host 공통

- 정찰(Step 2)의 **1순위 도구는 `agent-browser`**다. 이것은 vercel-labs의 독립 CLI(`npm install -g agent-browser`)이므로 **Claude Code·Codex 모두에서 동일하게 쓴다** — Claude 전용이 아니다. 셋업돼 있으면 Codex도 그대로 사용한다. 사용법은 양 host 모두 정찰 시작 전 `agent-browser skills get core --full`로 로드한다 — CLI에 내장돼 항상 버전 일치(파일 복사 불필요).
- agent-browser를 못 쓰는 환경(미설치, 또는 브라우저 실행이 막힌 제한된 Codex 클라우드 샌드박스)에서는 **Scrapling `DynamicFetcher`** 또는 **Playwright `sync_api` 스크립트**(`page.on("response")`로 XHR/API 캡처)로 정찰을 대체한다. 둘 다 Python 의존성에 포함돼 항상 가능. (SKILL.md 규칙 1 예외와 동일한 Playwright 사용.)
- **수집·프로필·엑셀·CDP는 양 host 완전 동일**: 수집(Scrapling), 도메인 프로필(`scripts/domain_profile.py`), 엑셀(`scripts/export_excel.py`), Akamai/고급 WAF 대응(`scripts/chrome_cdp.py`), 진행 체크포인트(`scripts/progress.py`).

## 안전 — 하드룰 (위반 금지)

- **CAPTCHA 자동 우회 금지** — reCAPTCHA/hCaptcha 등이 뜨면 사용자에게 보고 후 중단한다.
- **로그인 자격증명 저장 금지** — ID/PW를 코드·메모리·파일에 저장하지 않는다. 사용자가 직접 로그인 → 쿠키만 추출(`output/<도메인>/cookies.json`, `.gitignore`가 차단).
- **robots.txt 제한** 발견 시(`Disallow: /` 또는 대상 경로 차단) 진행 여부를 사용자에게 묻는다.
- **PII 감지 필수** — 수집 데이터에 전화번호/주민번호/이메일 등이 섞이면 `detect_pii(data)`로 경고하고 보고한다.
- **불법 스크래핑 거절** — 저작권 위반·개인정보 대량 수집·ToS 명시 위반은 진행 전 사용자 확인 후 거절한다.
- **수집 0건이면 즉시 중단·보고** — 계속 시도하면 ban 위험.

## 빠른 참조

| 무엇 | 경로 |
|------|------|
| 워크플로우 7단계 | `.codex/skills/web-crawler/SKILL.md` |
| Fetcher 코드 템플릿 | `.codex/skills/web-crawler/references/fetcher-patterns.md` |
| 안티봇(Akamai/Cloudflare/SPA 세션) | `.codex/skills/web-crawler/references/antibot-strategies.md` |
| 수집 실패 진단 | `.codex/skills/web-crawler/references/troubleshooting.md` |
| 프로젝트 규칙·도구 분리 SSOT | `CLAUDE.md` |
