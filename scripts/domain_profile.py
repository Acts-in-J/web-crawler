"""scripts/domain_profile.py — 도메인별 크롤링 프로필 저장/재사용

프로필 스키마:
{
    "domain": "example.com",
    "capability": "static|js_render|api|session",     # ★ SSOT — 능력 수준
    "distribution": "public|local",                    # 선택 — 없으면 policy 가 자동 판정
    "distribution_reason": "선언 사유",     # distribution 이 있을 때만 의미 있음
    "consent": {"notified_at": "ISO8601", "choice": "proceed"},   # 사다리 B 프로필 필수, sticky
    "fetcher_type": "FetcherSession|Fetcher|StealthyFetcher|DynamicFetcher|chrome_cdp",  # 파생 — 현재 엔진에서의 구현체
    "antibot_type": "none|cloudflare|akamai|other",   # 봇 차단 유형
    "antibot_strategy": "none|stealthy|chrome_cdp",    # 대응 전략
    "selectors": {"필드": "셀렉터"},
    "pagination": {"type": "url_param|next_button|infinite_scroll"},
    "api_endpoints": [{"url": "", "method": "GET", "params": {}, "field_mapping": {}}],
    "notes": "사이트 특이사항 메모",
    "last_used": "2026-03-09",
}
"""
import json
import os
import shutil
from datetime import datetime, timezone

from profile_policy import distribution
from utils import sanitize_filename, setup_logger


# 알려진 안티봇 유형별 추천 전략
ANTIBOT_STRATEGIES = {
    "akamai": "chrome_cdp",
    "cloudflare": "stealthy",
    "none": "none",
}

# 호출자가 새 dict 를 만들어 넘겨도 살아남아야 하는 필드.
# 공통 성격: 전부 "이 프로필을 배포해도 되는가" 를 결정하는 데 관여한다 — 호출자가 생략
# 만으로 그 답을 바꿔서는 안 된다(보존이지 고정은 아니다: 명시적으로 다시 넘기면 그 값이
# 이긴다. 아래 각 필드 참조).
# - distribution/distribution_reason: 배포 여부 선언. 없으면 다음 수집 한 번으로 미배포
#   결정이 조용히 지워진다.
# - capability: 능력 SSOT. fetcher_type 역추론 폴백이 지금은 손실을 감추지만, 그 폴백이
#   깨지는 순간(라이브러리가 클래스 이름을 또 바꾸는 순간) 드러난다 — 폴백이 필요 없어질
#   때가 아니라 필요해질 때 사라지면 안 된다.
# - consent: 이미 내린 통지·선택 기록. 그 도메인에 프로필이 존재한다는 사실 자체가 그
#   사용자가 한 번 통지받고 진행을 골랐다는 뜻이다 — 매 수집마다 다시 묻지 않는다. (프로필이
#   아예 없는 최초 진입에는 상속할 기록이 없으므로 게이트는 그대로 발화한다.)
# - antibot_strategy: distribution() 이 rung 을 매길 때 보는 판정 필드 중 하나다(다른 하나인
#   fetcher_type 은 sticky 가 아니다 — 구현체가 바뀌는 건 자연스러우므로). 예: oliveyoung_co_kr
#   은 fetcher_type 만 보면 사다리 A(FetcherSession) 지만 antibot_strategy: "impersonate" 때문에
#   local 로 분류된다. 이 필드가 생략만으로 사라지면 미배포 결정이 조용히 public 으로 뒤집히고,
#   consent 도 (public 프로필에서는 지워야 하므로) 함께 씻겨나간다.
STICKY_FIELDS = ("distribution", "distribution_reason", "capability", "consent",
                  "antibot_strategy")


class ConsentRequired(Exception):
    """사다리 B(우회) 프로필을 consent 기록 없이 저장하려 할 때.

    통지 게이트의 백스톱이다. 사용자에게 한 번 알리지 않고 조용히 우회한 경우,
    이 예외 때문에 Step 5-A 프로필 저장을 완료할 수 없다.

    consent 는 '근거' 가 아니라 '선택' 을 기록한다 — 무엇을 정당화했는지가 아니라
    통지를 봤고 진행을 골랐다는 사실과 그 시각만 남긴다.

    consent 는 sticky 필드다 — 한 번 기록되면 그 도메인의 다음 저장들이 다시 요구하지
    않는다. 프로필이 이미 있다는 것 자체가 "이 사용자는 이미 통지받고 진행을 골랐다"
    는 근거이기 때문이다. 그 도메인에 프로필이 아직 없는 최초 진입에는 상속할 기록이
    없으므로, 게이트는 정확히 거기서만 발화한다.
    """


class DomainProfile:
    """도메인별 사이트 프로필을 관리."""

    def __init__(self, base_dir: str = "./fingerprints", clock=None):
        self.base_dir = base_dir
        # 손상 파일 백업 접미사에 쓰는 시각 소스. 기본은 실제 UTC now, 테스트는 주입해서 고정.
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def save(self, domain: str, profile: dict):
        profile = dict(profile)   # 호출자의 dict 를 건드리지 않는다
        domain_dir = os.path.join(self.base_dir, sanitize_filename(domain))
        filepath = os.path.join(domain_dir, "profile.json")

        existing = {}
        read_failed = False
        try:
            existing = self.load(domain) or {}
        except (ValueError, OSError):
            # 기존 파일이 깨졌어도 저장은 진행한다 — 수집 성공 후 게이트에서 죽으면 안 된다.
            # 다만 이 저장이 게이트에 막혀 거부되면, 손상된 원본이라도 손대지 않는다 —
            # 거부된 저장이 기존 파일을 지워버리면 "저장 실패" 가 "프로필 소실" 이 되어버린다.
            # 그래서 백업은 지금 하지 않고, 실제로 쓰기로 확정된 뒤로 미룬다.
            read_failed = True

        for field in STICKY_FIELDS:
            if field not in profile and field in existing:
                profile[field] = existing[field]

        if distribution(profile) == "local":
            consent = profile.get("consent")
            if not isinstance(consent, dict) or consent.get("choice") != "proceed":
                raise ConsentRequired(
                    f"{domain}: 이 프로필은 자동 접근 차단을 넘어선 방법을 기록하고 있습니다. "
                    "사용자에게 한 번 통지하고, 그 선택을 consent 블록에 남긴 뒤 저장하세요 — "
                    '예: {"notified_at": "<ISO8601>", "choice": "proceed"}. '
                    "권한 근거를 적을 필요는 없습니다."
                )
        else:
            # public 으로 (재)분류된 프로필에 이전 통지 이력이 남아있으면 안 된다 — consent 는
            # 배포되지 않는 로컬 결정의 기록이지, 배포 whitelist 에 들어갈 값이 아니다.
            # fetcher_type 은 sticky 가 아니므로, 도구가 사다리 A로 내려온 재수집은 이 분기를
            # 그대로 통과해 consent 를 씻어낸다.
            profile.pop("consent", None)

        # 여기까지 왔다면 이 저장은 실제로 진행된다 — 그제야 손상된 기존 파일을 백업한다.
        if read_failed and os.path.exists(filepath):
            backup_path = (
                f"{filepath}.corrupt-{self._clock().strftime('%Y%m%dT%H%M%S.%fZ')}"
            )
            shutil.move(filepath, backup_path)
            setup_logger(__name__).warning(
                "%s: 기존 profile.json을 읽지 못해 백업 후 새로 씁니다 "
                "(distribution 선언이 있었다면 유실 — 백업 파일에서 복구) → %s",
                domain, backup_path,
            )

        os.makedirs(domain_dir, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)

    def load(self, domain: str) -> dict | None:
        filepath = os.path.join(self.base_dir, sanitize_filename(domain), "profile.json")
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r", encoding="utf-8-sig") as f:
            return json.load(f)

    def exists(self, domain: str) -> bool:
        filepath = os.path.join(self.base_dir, sanitize_filename(domain), "profile.json")
        return os.path.exists(filepath)

    def get_antibot_strategy(self, domain: str) -> str:
        """도메인의 안티봇 대응 전략 반환. 프로필 없으면 'none'."""
        profile = self.load(domain)
        if not profile:
            return "none"
        return profile.get("antibot_strategy", "none")

    def is_akamai(self, domain: str) -> bool:
        """해당 도메인이 Akamai 보호 사이트인지 확인."""
        profile = self.load(domain)
        if not profile:
            return False
        return profile.get("antibot_type") == "akamai"

    def capability(self, domain: str) -> str | None:
        """도메인의 능력 수준(static|js_render|api|session). 프로필 없으면 None.

        capability 필드가 SSOT 이고 fetcher_type 은 파생이다. 필드가 없는 옛 프로필은
        fetcher_type 에서 역추론하므로 마이그레이션 없이도 읽힌다.
        """
        from profile_policy import infer_capability
        profile = self.load(domain)
        return infer_capability(profile) if profile else None
