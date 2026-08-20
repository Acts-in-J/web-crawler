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


# ── S1: 사다리 1·2단 위장 끄기 ──

from utils import PLAIN_KWARGS, plain_get, plain_session


def test_plain_kwargs_has_both_arguments():
    """부분 적용은 악화다 — 두 인자가 항상 함께 있어야 한다."""
    assert PLAIN_KWARGS == {"impersonate": None, "stealthy_headers": False}


def test_plain_get_passes_both_arguments(monkeypatch):
    captured = {}

    class _FakeFetcher:
        @staticmethod
        def get(url, **kw):
            captured["url"] = url
            captured["kw"] = kw
            return "response"

    monkeypatch.setattr("scrapling.fetchers.Fetcher", _FakeFetcher)

    assert plain_get("https://example.com") == "response"
    assert captured["url"] == "https://example.com"
    assert captured["kw"]["impersonate"] is None
    assert captured["kw"]["stealthy_headers"] is False


def test_plain_get_allows_explicit_override(monkeypatch):
    """호출자가 명시적으로 덮을 수는 있다 — 단 둘을 함께 덮어야 한다."""
    captured = {}

    class _FakeFetcher:
        @staticmethod
        def get(url, **kw):
            captured.update(kw)
            return "response"

    monkeypatch.setattr("scrapling.fetchers.Fetcher", _FakeFetcher)

    plain_get("https://example.com", impersonate="chrome", stealthy_headers=True)
    assert captured["impersonate"] == "chrome"
    assert captured["stealthy_headers"] is True


def test_plain_session_passes_both_arguments(monkeypatch):
    captured = {}

    class _FakeSession:
        def __init__(self, **kw):
            captured.update(kw)

    monkeypatch.setattr("scrapling.fetchers.FetcherSession", _FakeSession)

    plain_session()
    assert captured["impersonate"] is None
    assert captured["stealthy_headers"] is False


def test_plain_helpers_do_not_import_scrapling_at_module_level():
    """utils 는 scrapling 을 물지 않는다 — import 는 함수 안에서 lazy 하게.

    AST 의 최상위 노드만 본다. 문자열 검색은 두 방향으로 틀린다 —
    파일 뒤쪽에 덧붙은 코드를 놓치고, 메서드 안의 정당한 lazy import 를 오탐한다.
    """
    import ast
    from pathlib import Path

    import utils

    tree = ast.parse(Path(utils.__file__).read_text(encoding="utf-8"))
    for node in tree.body:              # 최상위만 — 함수/클래스 내부는 보지 않는다
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        offenders = [n for n in names if n.startswith("scrapling")]
        assert not offenders, f"utils 모듈 최상단에서 scrapling 을 import 하고 있습니다: {offenders}"


def test_plain_get_rejects_partial_override():
    """한쪽만 끄거나 켜는 것은 악화다 — 조용히 허용하지 않는다."""
    with pytest.raises(ValueError, match="impersonate"):
        plain_get("https://example.com", stealthy_headers=True)
    with pytest.raises(ValueError, match="stealthy_headers"):
        plain_get("https://example.com", impersonate="chrome")


def test_plain_session_rejects_partial_override():
    with pytest.raises(ValueError, match="stealthy_headers"):
        plain_session(impersonate="chrome")
