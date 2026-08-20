"""scripts/profile_policy.py — 프로필을 배포해도 되는가에 대한 단일 출처.

판정은 '무엇이 감지됐나(detection)' 가 아니라 '무엇으로 해결했나(response)' 를 본다.
antibot_type 은 신뢰할 수 없다 — 어떤 프로필은 그 값이 null 이면서 실제로는 6단 도구를
쓰고, 어떤 프로필은 WAF 가 감지됐다고 적혀 있으면서 실제로는 2단 API 호출로 끝냈다.

사다리:
    A(자동)  1 정적 HTML · 2 숨은 API · 3 JS 렌더링
    ─────── 이음매: 여기부터 상대가 나를 식별하고 거절한 상황이다 ───────
    B(통지)  4 지문 정렬 · 5 스텔스 브라우저 · 6 실제 크롬

사다리 B 도구로 해결한 프로필은 배포하지 않는다. 능력을 없애는 게 아니라 레시피를
배포에서 빼는 것이다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FINGERPRINTS = REPO_ROOT / "fingerprints"

# _norm() 적용 후의 키 → 사다리 칸
LADDER_A_TOOLS = {
    "fetcher": 1,
    "plainget": 1,
    "static": 1,
    "fetchersession": 2,
    "plainsession": 2,
    "apisession": 2,
    "api": 2,
    "dynamicfetcher": 3,
    "playwright": 3,
    "playwrightspaintercept": 3,
    "playwrightintercept": 3,
    # authenticated_browser 는 의도적으로 넣지 않는다 — 우회는 아니지만 자격증명 수집은
    # ToS 노출이 가장 큰 범주다. rung 0 으로 떨어뜨려 명시 선언 없이는 배포되지 않게 한다.
}

LADDER_B_TOOLS = {
    "curlcffi": 4,
    "curlcffigrid": 4,
    "grid": 4,
    "stealthy": 5,
    "stealthyfetcher": 5,
    "cdp": 6,
    "chromecdp": 6,
}

# '전략 없음' 을 뜻하는 값들 — 미상(unknown)과 구분해야 한다.
# 'none' 은 "안티봇 대응이 필요 없었다" 는 정보이고, 미상은 "모르겠다" 다. 취급이 다르다.
_NEUTRAL = {"", "none", "null", "na"}

# 읽기 실패한 프로필에 넣는 표식 — 어떤 도구 목록에도 없으므로 ladder_rung 이 0(미상)을 낸다
UNREADABLE = "__unreadable__"

# profile.get(field, _MISSING) 에서 '필드 자체가 없음' 과 '필드가 None' 을 구분하기 위한 표식.
_MISSING = object()

_NORM_RE = re.compile(r"[^a-z0-9]")

# 판정에 쓰는 필드. antibot_type 은 의도적으로 뺐다 — 위 docstring 참조.
_FIELDS = ("fetcher_type", "antibot_strategy")


def _norm(value) -> str:
    """대소문자·공백·언더스코어·하이픈을 지운 비교용 키."""
    if not isinstance(value, str):
        return ""
    return _NORM_RE.sub("", value.lower())


def ladder_rung(profile: dict) -> int:
    """프로필이 기록한 해법이 앉은 사다리 칸. 판별 불가면 0.

    0 은 '안전하다' 가 아니라 '모르겠다' 다 — distribution() 이 default-deny 로 받는다.
    아무 필드도 칸을 알려주지 않으면(빈 프로필·읽기 실패) 1 이 아니라 0 이다.
    """
    rungs = []
    for field in _FIELDS:
        raw = profile.get(field, _MISSING)
        if raw is _MISSING or raw is None:
            continue                     # 필드 없음 → 이 필드는 정보를 주지 않는다
        if not isinstance(raw, str):
            return 0                     # 문자열이 아니면 판별 불가 → default-deny
        key = _norm(raw)
        if key in _NEUTRAL:
            continue        # '대응 없음' 은 정보지만 칸을 특정하지는 않는다
        if key in LADDER_B_TOOLS:
            rungs.append(LADDER_B_TOOLS[key])
        elif key in LADDER_A_TOOLS:
            rungs.append(LADDER_A_TOOLS[key])
        else:
            return 0        # 모르는 도구가 하나라도 있으면 판별 불가
    return max(rungs) if rungs else 0


def distribution(profile: dict) -> str:
    """"public" | "local".

    선언은 **조이는 방향으로만 무조건 인정**한다. 푸는 방향은 사다리 A 또는 판별 불가
    (rung <= 3)에 대해서만 허용한다 — 사다리 B 라고 '판정된' 프로필을 한 단어로 뒤집을 수
    있으면, default-deny 정책 전체가 그 단어만큼만 강해진다.
    """
    declared = profile.get("distribution")
    if declared == "local":
        return "local"

    rung = ladder_rung(profile)
    if declared == "public" and rung <= 3:
        return "public"
    return "local" if (rung == 0 or rung >= 4) else "public"


def is_distributable(profile: dict) -> bool:
    return distribution(profile) == "public"


def load_all() -> dict[str, dict]:
    """fingerprints/*/profile.json 전체를 {디렉터리명: dict} 로.

    읽지 못한 프로필은 '내용이 없는 프로필' 이 아니라 '미상' 이다 — 빈 dict 를 넣으면
    ladder_rung 이 1(=정적 HTML)로 읽어 배포 대상이 되어버린다. 명시적으로 미상 표식을 넣는다.
    """
    out = {}
    if not FINGERPRINTS.is_dir():
        return out
    for path in sorted(FINGERPRINTS.glob("*/profile.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            out[path.parent.name] = data if isinstance(data, dict) else {"fetcher_type": UNREADABLE}
        except (json.JSONDecodeError, OSError):
            out[path.parent.name] = {"fetcher_type": UNREADABLE}   # 미상 → default-deny
    return out


def public_dirs() -> list[str]:
    """배포 대상 디렉터리명 정렬 목록."""
    return sorted(name for name, profile in load_all().items() if is_distributable(profile))
