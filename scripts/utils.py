"""scripts/utils.py — 크롤링 에이전트 공통 유틸리티"""
import json
import logging
import os
import re
import time
from urllib.parse import urlparse


class RateLimiter:
    """요청 간 대기를 관리하는 rate limiter."""

    def __init__(self, delay: float = 1.0):
        self.delay = delay
        self._last_request = 0.0

    def wait(self):
        elapsed = time.time() - self._last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request = time.time()

    def backoff(self):
        """HTTP 429 등 rate limit 시 대기 시간 2배 증가."""
        self.delay *= 2


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


def detect_pii(data: list[dict]) -> list[str]:
    """수집 데이터에서 PII(개인식별정보) 패턴을 감지."""
    warnings = []
    sample = data[:50]  # 처음 50건만 검사

    for i, item in enumerate(sample):
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
