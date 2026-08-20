"""scripts/test_domain_profile.py — DomainProfile 단위 테스트"""
import json
import os
import time
from domain_profile import DomainProfile


def test_save_and_load_profile(tmp_path):
    profile = DomainProfile(str(tmp_path))
    data = {
        "domain": "example.com",
        "fetcher_type": "Fetcher",
        "selectors": {"title": "h2::text", "price": ".price::text"},
        "pagination": {"type": "url_param", "param": "page"},
    }
    profile.save("example.com", data)
    loaded = profile.load("example.com")
    assert loaded["fetcher_type"] == "Fetcher"
    assert loaded["selectors"]["title"] == "h2::text"


def test_load_nonexistent(tmp_path):
    profile = DomainProfile(str(tmp_path))
    assert profile.load("nonexistent.com") is None


def test_profile_exists(tmp_path):
    profile = DomainProfile(str(tmp_path))
    profile.save("example.com", {"domain": "example.com"})
    assert profile.exists("example.com") is True
    assert profile.exists("other.com") is False


def test_distribution_declaration_survives_resave(tmp_path):
    """Step 5-A 는 매번 새 dict 를 넘긴다 — 선언이 거기서 지워지면 안 된다."""
    from domain_profile import DomainProfile
    mgr = DomainProfile(base_dir=str(tmp_path))
    mgr.save("example.com", {"domain": "example.com", "fetcher_type": "Playwright",
                             "distribution": "local", "distribution_reason": "robots"})
    mgr.save("example.com", {"domain": "example.com", "fetcher_type": "Playwright"})
    reloaded = mgr.load("example.com")
    assert reloaded["distribution"] == "local"
    assert reloaded["distribution_reason"] == "robots"


def test_caller_can_still_change_distribution(tmp_path):
    """보존이지 고정이 아니다 — 명시적으로 넘기면 그 값이 이긴다."""
    from domain_profile import DomainProfile
    mgr = DomainProfile(base_dir=str(tmp_path))
    mgr.save("example.com", {"domain": "example.com", "fetcher_type": "Fetcher",
                             "distribution": "local", "distribution_reason": "x"})
    mgr.save("example.com", {"domain": "example.com", "fetcher_type": "Fetcher",
                             "distribution": "public", "distribution_reason": "y"})
    assert mgr.load("example.com")["distribution"] == "public"
