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


def test_save_survives_corrupt_existing_profile(tmp_path):
    """Step 5-A 는 수집 성공 직후다 — 기존 파일이 깨졌다고 여기서 죽으면 안 된다."""
    from domain_profile import DomainProfile
    mgr = DomainProfile(base_dir=str(tmp_path))
    target = tmp_path / "example_com"
    target.mkdir()
    (target / "profile.json").write_text("{not json", encoding="utf-8")
    mgr.save("example.com", {"domain": "example.com", "fetcher_type": "Fetcher"})
    assert mgr.load("example.com")["fetcher_type"] == "Fetcher"


def test_save_and_load_handle_bom(tmp_path):
    """PowerShell 이 기본으로 BOM 을 붙인다 — 손으로 고친 프로필이 읽혀야 한다."""
    from domain_profile import DomainProfile
    mgr = DomainProfile(base_dir=str(tmp_path))
    target = tmp_path / "example_com"
    target.mkdir()
    (target / "profile.json").write_text(
        '{"domain": "example.com", "distribution": "local"}', encoding="utf-8-sig")
    assert mgr.load("example.com")["distribution"] == "local"
    mgr.save("example.com", {"domain": "example.com", "fetcher_type": "Fetcher"})
    assert mgr.load("example.com")["distribution"] == "local"   # sticky 가 BOM 파일에서도 보존


def test_save_survives_ansi_encoded_existing_profile(tmp_path):
    """CLAUDE.md 가 경고하는 대로 Set-Content 는 ANSI 로 쓴다 — 한글 notes 가 그 지뢰다."""
    from domain_profile import DomainProfile
    mgr = DomainProfile(base_dir=str(tmp_path))
    target = tmp_path / "example_com"
    target.mkdir()
    (target / "profile.json").write_bytes(
        '{"domain": "example.com", "notes": "한글 메모"}'.encode("cp949"))
    mgr.save("example.com", {"domain": "example.com", "fetcher_type": "Fetcher"})
    assert mgr.load("example.com")["fetcher_type"] == "Fetcher"


# ── S3: capability SSOT ──
from profile_policy import infer_capability


def test_capability_field_wins():
    assert infer_capability({"capability": "api", "fetcher_type": "Fetcher"}) == "api"


def test_capability_inferred_from_fetcher_type():
    """마이그레이션 호환 — capability 가 없어도 기존 프로필이 그대로 산다."""
    assert infer_capability({"fetcher_type": "Fetcher"}) == "static"
    assert infer_capability({"fetcher_type": "FetcherSession"}) == "api"
    assert infer_capability({"fetcher_type": "DynamicFetcher"}) == "js_render"
    assert infer_capability({"fetcher_type": "playwright_spa_intercept"}) == "session"
    assert infer_capability({"fetcher_type": "chrome_cdp"}) == "session"


def test_capability_unknown_returns_none():
    assert infer_capability({"fetcher_type": "SomeNewThing"}) is None


def test_all_tracked_profiles_declare_capability():
    """마이그레이션이 끝났는지 — 배포되는 프로필은 전부 capability 를 갖는다."""
    from profile_policy import is_distributable, load_all
    missing = [name for name, p in load_all().items()
               if is_distributable(p) and "capability" not in p]
    assert missing == [], f"capability 필드가 없는 배포 프로필: {missing}"
