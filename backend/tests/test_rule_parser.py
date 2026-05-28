from app.core.rule_parser import RuleType, parse_market_rule
from app.schemas.market import Market


def test_detects_fallback_50_50_before_event_rule() -> None:
    market = Market(
        id="1",
        question="Will bitcoin hit $1m before GTA VI?",
        description=(
            "This market resolves Yes if BTC hits before GTA VI. "
            "If neither occurs by July 31, 2026, this market will resolve to 50-50."
        ),
    )

    parsed = parse_market_rule(market)

    assert parsed.rule_type == RuleType.FALLBACK_50_50_BEFORE_EVENT
    assert parsed.has_fallback_50_50


def test_simple_barrier_without_fallback() -> None:
    market = Market(id="1", question="Will Bitcoin hit $120k by December?")

    parsed = parse_market_rule(market)

    assert parsed.rule_type == RuleType.SIMPLE_BINARY_BARRIER
