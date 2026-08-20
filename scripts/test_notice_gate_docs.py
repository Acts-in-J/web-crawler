"""통지 게이트 문서 드리프트 — 산문 지시가 조용히 사라지지 않도록.

protego 가 requirements 에 있으면서 어디서도 import 되지 않은 채 몇 달을 보낸 전례가 있다.
문서에만 적힌 규칙은 반드시 흐트러진다.
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".claude/skills/web-crawler/SKILL.md"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
ANTIBOT = REPO_ROOT / ".claude/skills/web-crawler/references/antibot-strategies.md"
README = REPO_ROOT / "README.md"

GATE_DOCS = [SKILL, CLAUDE_MD, ANTIBOT]


@pytest.mark.parametrize("path", GATE_DOCS, ids=lambda p: p.name)
def test_notice_gate_present(path):
    """이음매 통지가 세 지시 문서에 전부 살아 있어야 한다."""
    text = path.read_text(encoding="utf-8")
    assert "통지" in text, f"{path.name} 에서 통지 게이트 서술이 사라졌습니다"


def test_skill_offers_an_explicit_choice():
    """통지는 알림이 아니라 선택지다 — 사용자가 고를 수 있어야 한다."""
    assert "[진행 / 중단]" in SKILL.read_text(encoding="utf-8")


def test_skill_does_not_demand_justification():
    """원칙 ④ — 근거를 제출받거나 검증하지 않는다."""
    text = SKILL.read_text(encoding="utf-8")
    assert "근거를 묻지도 검증하지도 않는다" in text


@pytest.mark.parametrize("path", GATE_DOCS + [README], ids=lambda p: p.name)
def test_docs_do_not_overclaim_a_ban(path):
    """문서가 실제 동작보다 강하게 말하면 안 된다 — 통지지 금지가 아니다."""
    text = path.read_text(encoding="utf-8")
    for phrase in ("우회하지 않는다", "우회 금지", "우회를 하지 않습니다"):
        assert phrase not in text, (
            f"{path.name} 에 '{phrase}' 가 있습니다. 이 도구는 우회 능력을 유지하며 "
            "사용자가 진행을 고르면 그대로 진행합니다 — 문서가 동작보다 강하게 말하면 안 됩니다"
        )


def test_captcha_rule_is_layered_with_waf():
    """G2 — CAPTCHA 와 WAF 가 같은 층위여야 한다. 자동 풀이 금지는 별개로 유지."""
    text = CLAUDE_MD.read_text(encoding="utf-8")
    assert "CAPTCHA 자동 풀이 금지" in text
    assert "CAPTCHA·WAF·봇 탐지는 법적으로 같은 보호조치" in text
