"""scripts/utils.py — 크롤링 에이전트 공통 유틸리티"""
import json
import logging
import os
import re
import time
from urllib.parse import urlparse


class BudgetExceeded(Exception):
    """수집 부담 상한을 넘었다. 계속 두드리지 말고 멈춘다.

    부담은 접근과 별개 축이고 여기에도 형사 층이 있다(업무방해). 429 가 반복된다는 것은
    상대가 거절하고 있다는 뜻이지 더 기다리면 될 문제가 아니다.
    """


class RateLimiter:
    """요청 간 대기 + 총량·연속실패 상한.

    delay 하한이 있는 이유: 0 을 넣어 사실상 무제한으로 두드리는 것을 막는다.
    """

    MIN_DELAY = 0.5

    def __init__(self, delay: float = 1.0, min_delay: float = MIN_DELAY,
                 max_requests: int | None = None, max_consecutive_errors: int = 3):
        self.min_delay = max(min_delay, 0.0)
        self.delay = max(delay, self.min_delay)
        self.max_requests = max_requests
        self.max_consecutive_errors = max_consecutive_errors
        self.request_count = 0
        self.consecutive_errors = 0
        self._last_request = 0.0

    def wait(self):
        if self.max_requests is not None and self.request_count >= self.max_requests:
            raise BudgetExceeded(
                f"총 요청 상한({self.max_requests}건)에 도달했습니다. "
                "필요한 만큼만 가져오는 것이 부담 축의 핵심입니다 — "
                "정말 더 필요하면 max_requests 를 명시적으로 올리세요"
            )
        elapsed = time.time() - self._last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request = time.time()
        self.request_count += 1

    def backoff(self):
        """HTTP 429/503 등에서 대기 2배. 연속 한도를 넘으면 하드 중단."""
        self.consecutive_errors += 1
        if self.consecutive_errors >= self.max_consecutive_errors:
            raise BudgetExceeded(
                f"연속 {self.consecutive_errors}회 rate limit 응답을 받았습니다. "
                "상대가 거절하고 있는 것이지 더 기다리면 될 문제가 아닙니다 — 중단합니다"
            )
        self.delay *= 2

    def reset_errors(self):
        """요청이 성공했을 때 연속 카운터를 리셋한다."""
        self.consecutive_errors = 0


def validate_url(url: str) -> bool:
    """URL이 유효한 http/https 형식인지 확인."""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def sanitize_filename(name: str) -> str:
    """파일명에 사용할 수 없는 문자를 _로 치환."""
    return re.sub(r'[^\w\-]', '_', name)


def save_cookies(cookies: dict, filepath: str):
    """쿠키를 JSON 파일로 저장."""
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)


def load_cookies(filepath: str, max_age_hours: int = 24) -> dict | None:
    """쿠키 파일 로드. 24시간 초과 시 만료로 None 반환."""
    if not os.path.exists(filepath):
        return None
    age_hours = (time.time() - os.path.getmtime(filepath)) / 3600
    if age_hours > max_age_hours:
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_auth_token(token: str, filepath: str, token_type: str = "bearer"):
    """인증 토큰을 JSON 파일로 저장."""
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({"type": token_type, "token": token}, f)


def load_auth_token(filepath: str, max_age_hours: int = 24) -> dict | None:
    """토큰 파일 로드. 24시간 초과 시 만료로 None 반환."""
    if not os.path.exists(filepath):
        return None
    age_hours = (time.time() - os.path.getmtime(filepath)) / 3600
    if age_hours > max_age_hours:
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


_EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
_PHONE_PATTERN = re.compile(r'(\d{2,4}[-.\s]?\d{3,4}[-.\s]?\d{4})')

# 개인을 가리키는 컬럼명. 값이 아니라 '스키마' 를 보는 게 이 경우 더 정확하다 —
# "홍길동" 이라는 값만 봐서는 사람 이름인지 상품명인지 알 수 없지만, 컬럼명이 '작성자' 면 확실하다.
_PII_COLUMN_HINTS = (
    "작성자", "이름", "성명", "닉네임", "별명", "아이디", "회원", "구매자", "리뷰어",
    "author", "writer", "nickname", "username", "user_name", "userid", "user_id",
    "reviewer", "member", "buyer", "customer", "profile",
)


def detect_pii(data: list[dict]) -> list[str]:
    """수집 데이터에서 PII(개인식별정보)를 감지 — 값 패턴과 컬럼명 양쪽을 본다."""
    warnings = []
    if not data:
        return warnings

    # 1) 스키마 — 데이터셋당 한 번. 컬럼명이 개인을 가리키는지.
    columns = {key for item in data[:50] if isinstance(item, dict) for key in item}
    for column in sorted(columns):
        lowered = str(column).lower()
        for hint in _PII_COLUMN_HINTS:
            if hint in lowered:
                warnings.append(
                    f"개인식별 컬럼 감지: '{column}' — 개인정보보호법은 영리 여부를 묻지 않는다. "
                    "수집·보관 근거를 확인하고, 필요 없으면 이 필드를 빼는 것을 권한다"
                )
                break

    # 2) 값 — 처음 50건에서 이메일·전화 패턴
    for i, item in enumerate(data[:50]):
        if not isinstance(item, dict):
            continue
        for field, value in item.items():
            if not isinstance(value, str):
                continue
            if _EMAIL_PATTERN.search(value):
                warnings.append(f"이메일 패턴 감지: 필드 '{field}' (row {i+1})")
            if _PHONE_PATTERN.search(value):
                warnings.append(f"전화번호 패턴 감지: 필드 '{field}' (row {i+1})")

    return warnings


# ── 소프트블록(가짜 200) 탐지 — insane-search R2 4단계 검증 차용 ──
# WAF는 HTTP 200으로 챌린지/빈 셸을 돌려주는 경우가 많다. status 200 = 성공이 아니라
# "검증 시작"이다. 아래 마커/크기/쿠키 센서를 AND로 보고 수집 직전에 걸러낸다.
_SOFTBLOCK_MARKERS = (
    "sec-if-cpt-container",      # Akamai 챌린지 컨테이너
    "access denied",            # Akamai/edgesuite 거부
    "errors.edgesuite.net",
    "reference #",              # Akamai/edgesuite 에러 페이지
    "pardon our interruption",  # PerimeterX
    "captcha-delivery.com",     # DataDome
    "just a moment...",         # Cloudflare 챌린지
    "cf-browser-verification",
    "attention required",       # Cloudflare 1020
    "verifying you are human",
    "enable javascript and cookies to continue",
)


def detect_softblock(text, status: int = 200, cookies: dict | None = None,
                     selector_hit: bool | None = None, min_size: int = 3000) -> dict:
    """가짜 200(소프트블록) 판별. HTTP 200이라도 본문이 WAF 챌린지면 잡아낸다.

    insane-search의 4단계 AND 검증 차용:
      1) 챌린지 마커 부재  2) 응답 크기 정상  3) 쿠키 센서 정상(_abck=...~-1~ 거부)
      4) success selector 매칭(제공 시 strong, 미제공 시 weak)

    반환: {"blocked": bool, "verdict": str, "signals": [..]}
      verdict ∈ strong_ok | weak_ok | challenge | blocked
    selector_hit 단독 미스만으로는 차단 판정하지 않는다(셀렉터 오타/자가치유와 충돌 방지).
    실제 차단 판정은 마커/크기/쿠키 센서 시그널이 있을 때만.
    """
    text = text or ""
    low = text.lower()

    # HTTP 레벨 차단 (즉시 종료)
    if status in (401, 402, 403):
        return {"blocked": True, "verdict": "blocked", "signals": [f"HTTP {status}"]}

    signals = []
    # 1) 챌린지 마커
    for marker in _SOFTBLOCK_MARKERS:
        if marker in low:
            signals.append(f"challenge marker: {marker}")
    # 2) 응답 크기 (지나치게 작으면 챌린지/빈 셸 의심)
    if len(text) < min_size:
        signals.append(f"response too small: {len(text)}B < {min_size}B")
    # 3) 쿠키 센서 — Akamai _abck 가 '...~-1~' 면 아직 미통과(차단) 상태
    if cookies:
        abck = cookies.get("_abck", "")
        if "~-1~" in abck:
            signals.append("akamai _abck sensor unsolved (~-1~)")

    if signals:
        return {"blocked": True, "verdict": "challenge", "signals": signals}

    # 4) 마커/크기/쿠키 정상 → selector 매칭 여부로 strong/weak 구분
    verdict = "strong_ok" if selector_hit else "weak_ok"
    return {"blocked": False, "verdict": verdict, "signals": []}


def setup_logger(name: str, level=logging.INFO) -> logging.Logger:
    """콘솔 출력용 로거 생성."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
        )
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


# ── 사다리 1·2단 — 위장 없는 표준 호출 ────────────────────────────────────
# Scrapling 기본값은 impersonate="chrome" + stealthy_headers=True 라, 아무것도 안 하면
# 1단이 이미 TLS 지문을 위장하고 가짜 Google referer 까지 붙인다(헤더 16개).
# 안티봇이 없는 사이트에는 위장할 이유가 없다. 두 인자를 함께 끄면 헤더가 4개로 떨어진다.
#
# ⚠ 반드시 '둘 다' 꺼야 한다. 하나만 끄면 헤더는 랜덤 브라우저인데 TLS 지문은 평범한 curl 인
#   불일치 상태가 되어 일관된 위장보다 오히려 더 잘 탐지된다. 부분 적용은 개선이 아니라 악화다.
#
# Fetcher.configure() 는 파서 전용이라 이 기본값을 전역으로 못 바꾼다
# (ValueError: Unknown parser argument: "impersonate"). 그래서 래퍼를 쓴다.
PLAIN_KWARGS = {"impersonate": None, "stealthy_headers": False}


def _apply_plain_kwargs(kw: dict) -> dict:
    """두 인자를 함께 적용한다. 한쪽만 덮으려는 호출은 거부한다.

    부분 적용은 개선이 아니라 악화다 — 헤더는 브라우저라고 말하는데 TLS 지문은 그렇지 않은
    불일치 상태가 되어 일관된 위장보다 더 잘 탐지된다. 그래서 '둘 다' 이거나 '둘 다 아니거나' 만 허용한다.
    """
    overridden = [key for key in PLAIN_KWARGS if key in kw]
    if len(overridden) == 1:
        missing = next(key for key in PLAIN_KWARGS if key not in kw)
        raise ValueError(
            f"{overridden[0]} 만 지정했습니다. {missing} 도 함께 지정하세요 — "
            "한쪽만 바꾸면 불일치 지문이 되어 오히려 더 잘 탐지됩니다"
        )
    for key, value in PLAIN_KWARGS.items():
        kw.setdefault(key, value)
    return kw


def plain_get(url: str, **kw):
    """사다리 1단. 위장 없는 평문 HTTP — 안티봇이 없는 사이트에 쓴다."""
    kw = _apply_plain_kwargs(kw)
    from scrapling.fetchers import Fetcher  # lazy — utils 는 scrapling 을 물지 않는다
    return Fetcher.get(url, **kw)


def plain_session(**kw):
    """사다리 2단. 위장 없는 세션 — 숨은 API 를 직접 호출할 때 쓴다."""
    kw = _apply_plain_kwargs(kw)
    from scrapling.fetchers import FetcherSession  # lazy
    return FetcherSession(**kw)


# ── robots.txt — 표지판이지 잠금장치가 아니지만, 무시했다는 사실은 정황이 된다 ──
def _fetch_robots(url: str, timeout: int = 10):
    """robots.txt 를 가져와 (본문, status) 반환. 테스트에서 monkeypatch 한다."""
    from urllib.request import Request, urlopen
    req = Request(url, headers={"User-Agent": "web-crawler-agent"})
    with urlopen(req, timeout=timeout) as resp:      # noqa: S310 (http/https만 들어온다)
        return resp.read().decode("utf-8", errors="replace"), resp.status


def check_robots(url: str, user_agent: str = "*") -> dict:
    """robots.txt 를 실제로 읽어 이 URL 수집이 허용되는지 판정.

    반환: {"allowed": bool, "crawl_delay": float|None, "robots_url": str, "error": str|None}

    robots.txt 는 법적 구속력이 없지만, 무시했다는 사실은 "알고도 했다" 의 정황이 된다.
    가져오지 못한 것(error)과 허용된 것(allowed)은 다르다 — 호출자가 구분할 수 있게 둘 다 준다.
    """
    from protego import Protego

    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    result = {"allowed": True, "crawl_delay": None, "robots_url": robots_url, "error": None}

    try:
        body, status = _fetch_robots(robots_url)
    except Exception as exc:
        result["error"] = f"robots.txt 를 가져오지 못했습니다: {exc}"
        return result

    if status == 404 or not body.strip():
        return result       # 제한 없음

    try:
        parser = Protego.parse(body)
    except Exception as exc:
        result["error"] = f"robots.txt 파싱 실패: {exc}"
        return result

    result["allowed"] = parser.can_fetch(url, user_agent)
    delay = parser.crawl_delay(user_agent)
    result["crawl_delay"] = float(delay) if delay is not None else None
    return result
