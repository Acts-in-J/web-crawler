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


# ── distribution ──
def test_ladder_a_is_public():
    assert distribution({"fetcher_type": "FetcherSession"}) == "public"


def test_ladder_b_is_local():
    assert distribution({"fetcher_type": "chrome_cdp"}) == "local"


def test_unknown_is_local_by_default_deny():
    assert distribution({"fetcher_type": "SomeNewBypassTool"}) == "local"


def test_explicit_declaration_wins_over_rule():
    """우회가 아닌 다른 이유(robots·ToS·계약)로 빼는 경우를 위한 탈출구."""
    assert distribution({"fetcher_type": "Fetcher", "distribution": "local"}) == "local"
    assert distribution({"fetcher_type": "chrome_cdp", "distribution": "public"}) == "public"


def test_invalid_declaration_falls_back_to_rule():
    assert distribution({"fetcher_type": "chrome_cdp", "distribution": "maybe"}) == "local"


def test_unreadable_profile_is_local():
    """읽지 못한 프로필은 '내용 없음' 이 아니라 '미상' 이다 — 배포하지 않는다."""
    from profile_policy import UNREADABLE
    assert distribution({"fetcher_type": UNREADABLE}) == "local"


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
    assert len(public_dirs()) == 15
