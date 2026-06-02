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
