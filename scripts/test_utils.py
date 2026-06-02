"""scripts/test_utils.py"""
import json
import os
import time
import pytest
from unittest.mock import patch
from utils import (
    RateLimiter,
    load_cookies,
    save_cookies,
    load_auth_token,
    save_auth_token,
    setup_logger,
    validate_url,
    sanitize_filename,
)


def test_rate_limiter_enforces_delay():
    limiter = RateLimiter(delay=0.1)
    start = time.time()
    limiter.wait()
    limiter.wait()
    elapsed = time.time() - start
    assert elapsed >= 0.1


def test_rate_limiter_backoff_on_429():
    limiter = RateLimiter(delay=0.1)
    limiter.backoff()
    assert limiter.delay == 0.2  # doubled


def test_validate_url_valid():
    assert validate_url("https://example.com/products") is True
    assert validate_url("http://example.com") is True


def test_validate_url_invalid():
    assert validate_url("not-a-url") is False
    assert validate_url("") is False
    assert validate_url("ftp://example.com") is False


def test_sanitize_filename():
    assert sanitize_filename("example.com") == "example_com"
    assert sanitize_filename("a/b:c*d") == "a_b_c_d"


def test_save_and_load_cookies(tmp_path):
    cookies = {"session": "abc123", "token": "xyz"}
    filepath = tmp_path / "cookies.json"
    save_cookies(cookies, str(filepath))
    loaded = load_cookies(str(filepath))
    assert loaded == cookies


def test_load_cookies_expired(tmp_path):
    cookies = {"session": "abc123"}
    filepath = tmp_path / "cookies.json"
    save_cookies(cookies, str(filepath))
    # Simulate 25 hours old
    old_time = time.time() - (25 * 3600)
    os.utime(str(filepath), (old_time, old_time))
    loaded = load_cookies(str(filepath))
    assert loaded is None  # expired (24h policy)


def test_save_and_load_auth_token(tmp_path):
    token = "eyJhbGciOiJIUzI1NiJ9.test_payload.signature"
    filepath = tmp_path / "token.json"
    save_auth_token(token, str(filepath), token_type="bearer")
    loaded = load_auth_token(str(filepath))
    assert loaded == {"type": "bearer", "token": token}


def test_load_auth_token_expired(tmp_path):
    filepath = tmp_path / "token.json"
    save_auth_token("expired_token", str(filepath))
    old_time = time.time() - (25 * 3600)
    os.utime(str(filepath), (old_time, old_time))
    loaded = load_auth_token(str(filepath))
    assert loaded is None


def test_setup_logger():
    logger = setup_logger("test_crawler")
    assert logger.name == "test_crawler"


def test_detect_pii_email():
    from utils import detect_pii
    data = [{"name": "홍길동", "contact": "hong@email.com"}]
    warnings = detect_pii(data)
    assert len(warnings) > 0
    assert "이메일" in warnings[0]


def test_detect_pii_phone():
    from utils import detect_pii
    data = [{"name": "홍길동", "phone": "010-1234-5678"}]
    warnings = detect_pii(data)
    assert len(warnings) > 0


def test_detect_pii_clean():
    from utils import detect_pii
    data = [{"name": "상품A", "price": "10000"}]
    warnings = detect_pii(data)
    assert len(warnings) == 0
