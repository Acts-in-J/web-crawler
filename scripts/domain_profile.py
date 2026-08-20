"""scripts/domain_profile.py — 도메인별 크롤링 프로필 저장/재사용

프로필 스키마:
{
    "domain": "example.com",
    "distribution": "public|local",       # 배포 가능 여부 선언 (scripts/profile_policy.py 참조)
    "distribution_reason": "선언 사유",     # distribution 이 있을 때만 의미 있음
    "fetcher_type": "FetcherSession|Fetcher|StealthyFetcher|DynamicFetcher|chrome_cdp",
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
from utils import sanitize_filename


# 알려진 안티봇 유형별 추천 전략
ANTIBOT_STRATEGIES = {
    "akamai": "chrome_cdp",
    "cloudflare": "stealthy",
    "none": "none",
}

# 호출자가 새 dict 를 만들어 넘겨도 살아남아야 하는 필드.
# 배포 여부 선언이 여기 없으면, 다음 수집 한 번으로 미배포 결정이 조용히 지워진다.
STICKY_FIELDS = ("distribution", "distribution_reason")


class DomainProfile:
    """도메인별 사이트 프로필을 관리."""

    def __init__(self, base_dir: str = "./fingerprints"):
        self.base_dir = base_dir

    def save(self, domain: str, profile: dict):
        profile = dict(profile)   # 호출자의 dict 를 건드리지 않는다
        try:
            existing = self.load(domain) or {}
        except (json.JSONDecodeError, OSError):
            existing = {}       # 기존 파일이 깨졌어도 저장은 진행한다 — 수집 성공 후 게이트에서 죽으면 안 된다
        for field in STICKY_FIELDS:
            if field not in profile and field in existing:
                profile[field] = existing[field]

        domain_dir = os.path.join(self.base_dir, sanitize_filename(domain))
        os.makedirs(domain_dir, exist_ok=True)
        filepath = os.path.join(domain_dir, "profile.json")
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
