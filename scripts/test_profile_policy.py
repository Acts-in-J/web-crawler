"""프로필 배포 정책 — 우회 레시피가 배포에 섞이지 않는지 검사."""
import pytest

from profile_policy import distribution, is_distributable, ladder_rung, load_all, public_dirs


# ── 정규화: 같은 것을 두 표기로 쓰고 있다 (chrome_cdp / CDP) ──
@pytest.mark.parametrize("value", ["chrome_cdp", "CDP", "Chrome CDP", "chromeCDP", "cdp"])
def test_cdp_spellings_all_reach_rung_six(value):
    assert ladder_rung({"fetcher_type": value}) == 6


def test_ladder_a_tools():
    assert ladder_rung({"fetcher_type": "Fetcher"}) == 1
    assert ladder_rung({"fetcher_type": "FetcherSession"}) == 2
    assert ladder_rung({"fetcher_type": "API_SESSION"}) == 2
    assert ladder_rung({"fetcher_type": "DynamicFetcher"}) == 3


def test_ladder_b_tools():
    assert ladder_rung({"antibot_strategy": "stealthy"}) == 5
    assert ladder_rung({"fetcher_type": "StealthyFetcher"}) == 5


def test_unknown_tool_is_rung_zero():
    """모르는 도구는 판별 불가(0) — distribution 이 default-deny 로 받는다."""
    assert ladder_rung({"fetcher_type": "SomeNewBypassTool"}) == 0


def test_neutral_values_are_ignored():
    """none/null/빈값은 '전략 없음' 이지 미상이 아니다."""
    assert ladder_rung({"fetcher_type": "Fetcher", "antibot_strategy": "none"}) == 1
    assert ladder_rung({"fetcher_type": "Fetcher", "antibot_strategy": None}) == 1


def test_max_rung_wins():
    assert ladder_rung({"fetcher_type": "Fetcher", "antibot_strategy": "chrome_cdp"}) == 6


@pytest.mark.parametrize("bad", [["chrome_cdp"], {"tool": "chrome_cdp"}, 6, True])
def test_non_string_field_is_not_published(bad):
    """문자열이 아닌 값은 '대응 없음' 이 아니라 '판별 불가' 다 — 배포하지 않는다."""
    assert ladder_rung({"fetcher_type": "Fetcher", "antibot_strategy": bad}) == 0
    assert distribution({"fetcher_type": "Fetcher", "antibot_strategy": bad}) == "local"


def test_authenticated_browser_is_not_auto_published():
    """로그인 기반 수집은 우회가 아니지만 자동 배포 대상도 아니다."""
    assert distribution({"fetcher_type": "Playwright",
                         "antibot_strategy": "authenticated_browser"}) == "local"


# ── distribution ──
def test_ladder_a_is_public():
    assert distribution({"fetcher_type": "FetcherSession"}) == "public"


def test_ladder_b_is_local():
    assert distribution({"fetcher_type": "chrome_cdp"}) == "local"


def test_unknown_is_local_by_default_deny():
    assert distribution({"fetcher_type": "SomeNewBypassTool"}) == "local"


def test_local_declaration_always_wins():
    """조이는 방향은 무조건 인정된다."""
    assert distribution({"fetcher_type": "Fetcher", "distribution": "local"}) == "local"


def test_public_declaration_cannot_overturn_ladder_b():
    """푸는 방향으로는 사다리 B 판정을 뒤집지 못한다."""
    assert distribution({"fetcher_type": "chrome_cdp", "distribution": "public"}) == "local"


def test_public_declaration_can_rescue_unknown_tool():
    """rung 0(미상) 오판은 선언으로 구제할 수 있다 — 이게 푸는 방향의 정당한 용도다."""
    assert distribution({"fetcher_type": "SomeInternalHelper", "distribution": "public"}) == "public"


def test_invalid_declaration_falls_back_to_rule():
    assert distribution({"fetcher_type": "chrome_cdp", "distribution": "maybe"}) == "local"


def test_corrupt_profile_is_withheld(tmp_path, monkeypatch):
    """읽기 실패는 '내용 없음' 이 아니라 '미상' 이다 — load_all 이 실제로 그렇게 만드는가."""
    import profile_policy
    (tmp_path / "broken_com").mkdir()
    (tmp_path / "broken_com" / "profile.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "notobject_com").mkdir()
    (tmp_path / "notobject_com" / "profile.json").write_text("[1, 2]", encoding="utf-8")
    monkeypatch.setattr(profile_policy, "FINGERPRINTS", tmp_path)
    loaded = profile_policy.load_all()
    assert loaded["broken_com"]["fetcher_type"] == profile_policy.UNREADABLE
    assert not profile_policy.is_distributable(loaded["broken_com"])
    assert not profile_policy.is_distributable(loaded["notobject_com"])
    assert profile_policy.public_dirs() == []


def test_empty_profile_is_local():
    """필드가 하나도 없으면 판단 근거가 없다 — default-deny."""
    assert distribution({}) == "local"


# ── 실제 프로필에 대한 회귀 ──
def test_detection_without_bypass_stays_public():
    """oliveyoung: cloudflare 가 감지됐으나 평범한 API 호출로 끝냈다. 우회한 게 아니다."""
    profiles = load_all()
    assert is_distributable(profiles["oliveyoung_co_kr"])


def test_session_intercept_stays_public():
    """g2b: SPA 세션 인터셉트는 우회가 아니라 세션 처리다."""
    profiles = load_all()
    assert is_distributable(profiles["g2b_go_kr"])


@pytest.mark.parametrize("name", ["coupang_com", "fin_land_naver_com",
                                  "brand_naver_com", "smartstore_naver_com"])
def test_ladder_b_profiles_are_not_distributable(name):
    profiles = load_all()
    assert not is_distributable(profiles[name])


def test_expected_public_count():
    assert public_dirs() == [
        "books_toscrape_com",
        "builtini_co_kr",
        "celimax_co_kr",
        "data_seoul_go_kr",
        "db_itkc_or_kr",
        "g2b_go_kr",
        "guesskorea_com",
        "made-in-china_com",
        "oliveyoung_co_kr",
        "wanted_co_kr",
        "www_11st_co_kr",
        "www_fss_or_kr",
        "www_gsmarena_com",
        "www_k-startup_go_kr",
        "www_kurly_com",
    ]
