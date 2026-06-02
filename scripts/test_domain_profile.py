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
