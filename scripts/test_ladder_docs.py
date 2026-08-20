"""사다리 문서 드리프트 — 자동 체인이 사다리 A(1~3단)에서 끝나는지 검사."""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FETCHER_PATTERNS = REPO_ROOT / ".claude/skills/web-crawler/references/fetcher-patterns.md"

LADDER_B_TOOLS = ["StealthyFetcher", "fetch_via_grid", "chrome_cdp", "launch_chrome_cdp"]


def _fetcher_chain_block() -> str:
    """fetcher-patterns.md 의 FETCHER_CHAIN 리터럴 블록만 잘라 반환."""
    text = FETCHER_PATTERNS.read_text(encoding="utf-8")
    start = text.index("FETCHER_CHAIN = [")
    end = text.index("]", start)
    return text[start:end]


def test_chain_starts_with_plain_get():
    """1단은 위장 없는 plain_get 이어야 한다 (S1)."""
    assert "plain_get" in _fetcher_chain_block()


def test_chain_includes_plain_session():
    """2단(숨은 API)은 사다리의 심장이고 자동 체인에 있어야 한다."""
    assert "plain_session" in _fetcher_chain_block()


@pytest.mark.parametrize("tool", LADDER_B_TOOLS)
def test_chain_excludes_ladder_b(tool):
    """사다리 B 는 자동 순차 진입에서 빠진다 — 능력 제거가 아니라 통지 후 진입이다."""
    assert tool not in _fetcher_chain_block(), (
        f"{tool} 이 자동 FETCHER_CHAIN 에 남아 있습니다 — 통지 게이트를 우회하게 됩니다"
    )


def test_bare_fetcher_get_is_not_called_plaintext():
    """G10: Fetcher().get() 을 '평문 HTTP' 라고 부르던 주석이 남아 있으면 안 된다.

    공백 개수에 의존하지 않는다 — 줄이 재정렬되면 문자열이 '사라져서' 통과하는,
    조용히 검사를 멈추는 테스트가 되기 때문이다.
    """
    normalized = " ".join(FETCHER_PATTERNS.read_text(encoding="utf-8").split())
    assert "Fetcher().get(url)), # 평문 HTTP" not in normalized
