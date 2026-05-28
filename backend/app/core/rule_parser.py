from dataclasses import dataclass
from enum import StrEnum

from app.schemas.market import Market


class RuleType(StrEnum):
    SIMPLE_BINARY_BARRIER = "simple_binary_barrier"
    FALLBACK_50_50_BEFORE_EVENT = "fallback_50_50_before_event"


@dataclass(frozen=True)
class ParsedRule:
    rule_type: RuleType
    summary: str
    has_fallback_50_50: bool
    has_before_event: bool


def parse_market_rule(market: Market) -> ParsedRule:
    text = f"{market.question}\n{market.description or ''}".lower()
    has_fallback_50_50 = any(
        phrase in text
        for phrase in [
            "resolve to 50-50",
            "resolves 50-50",
            "settle 50-50",
            "settles 50-50",
        ]
    )
    has_before_event = " before " in market.question.lower() or " before " in text

    if has_fallback_50_50 and has_before_event:
        return ParsedRule(
            rule_type=RuleType.FALLBACK_50_50_BEFORE_EVENT,
            summary=(
                "YES if the barrier is hit before the competing event; NO if the competing "
                "event happens first; 50-50 if neither condition resolves by the fallback date."
            ),
            has_fallback_50_50=True,
            has_before_event=True,
        )

    return ParsedRule(
        rule_type=RuleType.SIMPLE_BINARY_BARRIER,
        summary="YES if the barrier is hit by the market deadline; otherwise NO.",
        has_fallback_50_50=False,
        has_before_event=has_before_event,
    )
