"""프로필 배포 정책 — 우회 레시피가 배포에 섞이지 않는지 검사."""
import pytest

from profile_policy import (distribution, is_distributable, is_unrecognized_tool,
                             ladder_rung, load_all, public_dirs)


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


def test_naver_antibot_reaches_rung_six():
    """네이버 계열 안티봇도 실제 크롬 세션이 필요하다 — 6단으로 분류된다."""
    assert ladder_rung({"antibot_strategy": "naver_antibot"}) == 6
    assert distribution({"antibot_strategy": "naver_antibot"}) == "local"


def test_stealthy_session_reaches_rung_five():
    assert ladder_rung({"antibot_strategy": "stealthy_session"}) == 5


# ── ITEM 1: 저장소 문서가 이미 쓰는 이름들을 사다리가 인식하는가 ──
@pytest.mark.parametrize("value,expected_rung", [
    ("DynamicSession", 3),           # SKILL.md 무한 스크롤 절
    ("PlaywrightFetcher", 3),        # DynamicFetcher 의 옛 이름
    ("playwright_sync_api", 3),      # 절대 규칙 1 예외 문구
    ("Spider", 3),                   # CLAUDE.md 500건+ 권고
])
def test_documented_ladder_a_names_are_recognized(value, expected_rung):
    assert ladder_rung({"fetcher_type": value}) == expected_rung


@pytest.mark.parametrize("value", ["yt-dlp", "RSS", "oEmbed", "Jina"])
def test_phase_zero_routes_are_rung_one_not_unknown(value):
    """Phase 0 공인 우회로는 사다리 A 의 가장 낮은 칸이다 — 0(미상)이 아니라 1이어야 한다.

    0을 썼다면 '모르겠다' 는 뜻이 되어 distribution() 이 default-deny 로 묶어버린다.
    Phase 0 경로는 알려진 값이고 공개해도 되는 사다리 A 이므로 1이 맞다."""
    assert ladder_rung({"fetcher_type": value}) == 1
    assert distribution({"fetcher_type": value}) == "public"


# ── ITEM 4(F2): 사다리 어휘와 capability 매핑이 어긋나면 infer_capability 가 조용히 None 을
# 낸다 — 이 테스트가 있으면 새 사다리 값을 추가하면서 capability 매핑을 빠뜨리는 걸
# 구조적으로 막는다(새 값이 하나라도 매핑을 빠뜨리면 이 테스트가 실패한다). ──
def test_every_ladder_tool_has_a_capability_mapping():
    from profile_policy import LADDER_A_TOOLS, LADDER_B_TOOLS, _FETCHER_TO_CAPABILITY
    missing = (set(LADDER_A_TOOLS) | set(LADDER_B_TOOLS)) - set(_FETCHER_TO_CAPABILITY)
    assert missing == set(), f"capability 매핑이 없는 사다리 도구: {missing}"


# ── is_unrecognized_tool: ladder_rung 이 0 으로 뭉개는 두 경우를 구분한다 ──
@pytest.mark.parametrize("profile", [
    # 한쪽 필드가 인식되는 rung-6 값이어도, 다른 필드가 모르는 값이면 ladder_rung 은 그
    # 신호를 버리고 0 을 낸다(첫 미상에서 즉시 return) — is_unrecognized_tool 은 버려지지
    # 않고 이 조합을 잡아야 한다.
    {"fetcher_type": "chrome_cdp", "antibot_strategy": "some_typo_value"},
    {"fetcher_type": "fetch_via_grid"},
    {"fetcher_type": "StealthyFetcher(solve_cloudflare=True)"},
    {"fetcher_type": "CDP (headed)"},
])
def test_unrecognized_tool_string_is_detected(profile):
    """오타·신종·서술형 문자열은 '정보 없음' 이 아니다 — 판별 불가와는 다르게 잡아야 한다."""
    assert is_unrecognized_tool(profile)


def test_unrecognized_tool_ignores_absent_fields():
    """필드가 아예 없거나 None 이면 '완화' 유지 — 미상(rung 0)일 뿐 unrecognized 는 아니다."""
    assert not is_unrecognized_tool({})
    assert not is_unrecognized_tool({"fetcher_type": None, "antibot_strategy": None})


def test_unrecognized_tool_accepts_known_values():
    assert not is_unrecognized_tool({"fetcher_type": "Fetcher", "antibot_strategy": "none"})
    assert not is_unrecognized_tool({"fetcher_type": "chrome_cdp"})
    assert not is_unrecognized_tool({"antibot_strategy": "authenticated_browser"})


def test_unrecognized_tool_flags_non_string():
    assert is_unrecognized_tool({"fetcher_type": ["chrome_cdp"]})


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


def test_withheld_tool_cannot_be_rescued_by_declaration():
    """'알고서 뺀 것' 은 '모르는 것' 과 다르다 — 선언 한 줄로 풀리면 안 된다."""
    assert distribution({"fetcher_type": "Playwright",
                         "antibot_strategy": "authenticated_browser",
                         "distribution": "public"}) == "local"


def test_unknown_tool_can_still_be_rescued():
    """미상은 여전히 구제 가능하다 — 그게 rung 0 과 WITHHELD 의 차이다."""
    assert distribution({"fetcher_type": "SomeInternalHelper",
                         "distribution": "public"}) == "public"


@pytest.mark.parametrize("bad", [["authenticated_browser"], ["chrome_cdp"], {"t": "cdp"}, 4])
def test_non_string_field_cannot_be_rescued_by_declaration(bad):
    """읽을 수 없는 입력을 선언 한 줄로 배포하게 두면, 비문자열 하드닝이 무의미해진다."""
    assert distribution({"fetcher_type": "Playwright", "antibot_strategy": bad,
                         "distribution": "public"}) == "local"


def test_string_unknown_tool_is_still_rescuable():
    """'읽을 수 없음' 과 '읽었지만 모르는 도구' 는 다르다 — 후자는 여전히 구제 가능하다."""
    assert distribution({"fetcher_type": "SomeInternalHelper",
                         "distribution": "public"}) == "public"


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


def test_ansi_encoded_profile_is_withheld_not_fatal(tmp_path, monkeypatch):
    """읽을 수 없는 인코딩은 public_dirs() 를 무너뜨리지 않고 미상으로 처리돼야 한다."""
    import profile_policy
    (tmp_path / "ansi_com").mkdir()
    (tmp_path / "ansi_com" / "profile.json").write_bytes(
        '{"domain": "a.com", "notes": "한글"}'.encode("cp949"))
    monkeypatch.setattr(profile_policy, "FINGERPRINTS", tmp_path)
    loaded = profile_policy.load_all()
    assert loaded["ansi_com"]["fetcher_type"] == profile_policy.UNREADABLE
    assert profile_policy.public_dirs() == []


def test_empty_profile_is_local():
    """필드가 하나도 없으면 판단 근거가 없다 — default-deny."""
    assert distribution({}) == "local"


# ── 실제 프로필에 대한 회귀 ──
def test_detection_without_response_stays_public():
    """감지 사실과 우회 여부는 다르다 — 무언가 탐지됐어도 평범한 방법으로 끝냈으면 배포한다."""
    assert distribution({"fetcher_type": "FetcherSession", "antibot_strategy": "none"}) == "public"


def test_impersonation_is_a_ladder_b_response():
    """사이트가 평문을 거절해서 지문을 맞춘 것은 탐색이 아니라 돌파다."""
    assert ladder_rung({"fetcher_type": "FetcherSession", "antibot_strategy": "impersonate"}) == 4
    assert distribution({"fetcher_type": "FetcherSession", "antibot_strategy": "impersonate"}) == "local"


def test_session_intercept_stays_public():
    """g2b: SPA 세션 인터셉트는 우회가 아니라 세션 처리다."""
    profiles = load_all()
    assert is_distributable(profiles["g2b_go_kr"])


@pytest.mark.parametrize("name", ["coupang_com", "fin_land_naver_com",
                                  "brand_naver_com", "smartstore_naver_com",
                                  "oliveyoung_co_kr"])
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
        "wanted_co_kr",
        "www_11st_co_kr",
        "www_fss_or_kr",
        "www_gsmarena_com",
        "www_k-startup_go_kr",
        "www_kurly_com",
    ]


# ── .gitignore default-deny ──
import subprocess

from profile_policy import REPO_ROOT, load_all

GITIGNORE = REPO_ROOT / ".gitignore"
BEGIN = "# BEGIN GENERATED: public-profiles"
END = "# END GENERATED: public-profiles"


def _whitelist_block() -> list[str]:
    text = GITIGNORE.read_text(encoding="utf-8")
    body = text[text.index(BEGIN) + len(BEGIN):text.index(END)]
    return [line.strip() for line in body.splitlines() if line.strip().startswith("!")]


def test_whitelist_block_exists():
    assert BEGIN in GITIGNORE.read_text(encoding="utf-8")


def test_whitelist_matches_classifier():
    """생성 블록이 분류기와 어긋나면 sync 를 돌려야 한다."""
    listed = {line.split("/")[1] for line in _whitelist_block()}
    assert listed == set(public_dirs())


def test_no_blanket_profile_whitelist():
    """default-allow 로 되돌아가지 않았는지 — 이 한 줄이 정책 전체를 무력화한다."""
    for line in GITIGNORE.read_text(encoding="utf-8").splitlines():
        assert line.strip() != "!fingerprints/*/profile.json"
        assert line.strip() != "!fingerprints/*/recipe.md"


def test_credential_blocks_come_after_whitelist():
    """last-match-wins — 자격증명 재차단이 whitelist 뒤에 있어야 한다."""
    lines = [l.strip() for l in GITIGNORE.read_text(encoding="utf-8").splitlines()]
    assert lines.index("**/cookies*.json") > lines.index(END)
    assert lines.index("**/auth*.json") > lines.index(END)
    assert lines.index("**/*token*.json") > lines.index(END)
    assert lines.index("**/*secret*") > lines.index(END)


def test_new_bypass_profile_cannot_be_staged(tmp_path):
    """default-deny 실증 — 새 우회 프로필은 인덱스 진입 자체가 막혀야 한다."""
    target = REPO_ROOT / "fingerprints" / "zz_policy_probe_com"
    target.mkdir(parents=True, exist_ok=True)
    probe = target / "profile.json"
    probe.write_text('{"domain": "zz-probe.example", "fetcher_type": "chrome_cdp"}',
                     encoding="utf-8")
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", str(probe.relative_to(REPO_ROOT))],
            cwd=REPO_ROOT, capture_output=True,
        )
        assert result.returncode == 0, "새 우회 프로필이 gitignore 에 막히지 않습니다"
    finally:
        probe.unlink()
        target.rmdir()


def test_no_tracked_profile_is_withheld():
    """git 이 실제로 추적 중인 프로필 중에 미배포 판정이 섞여 있으면 안 된다.

    다른 테스트들은 '분류기가 옳은가', '화이트리스트가 분류기와 맞는가' 를 본다.
    이건 다른 질문이다 — **이 PR 이 지금 실제로 무엇을 배포하려 하는가.**
    .gitignore 는 untracked 파일에만 작용하므로 `git add -f` 로 강제 추가됐거나
    이미 추적 중인 프로필은 막지 못한다. 그 경우를 잡는 것은 이 검사뿐이다.
    """
    import json

    listed = subprocess.run(
        ["git", "ls-files", "fingerprints/*/profile.json"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout.split()

    offenders = []
    for rel in listed:
        path = REPO_ROOT / rel
        if not path.exists():          # 인덱스엔 있고 디스크엔 없는 경우
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (ValueError, OSError):
            offenders.append(f"{rel} (읽을 수 없음)")
            continue
        if not isinstance(data, dict) or not is_distributable(data):
            offenders.append(rel)

    assert offenders == [], (
        f"미배포 판정 프로필이 git 에 추적되고 있습니다: {offenders}. "
        "`git rm --cached <경로>` 로 인덱스에서 빼세요 — 파일은 디스크에 그대로 남습니다."
    )
