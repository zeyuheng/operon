from enum import StrEnum

from app.schemas.market import Market


class EventModelType(StrEnum):
    FINANCIAL_BARRIER = "financial_barrier"
    PRODUCT_RELEASE = "product_release"
    MACRO_POLICY = "macro_policy"
    ELECTION_POLLING = "election_polling"
    SPORTS_OUTRIGHT = "sports_outright"
    LOGIC_CONSISTENCY = "logic_consistency"
    GENERAL_EVENT = "general_event"


def route_model(market: Market) -> EventModelType:
    text = f"{market.question} {market.category or ''}".lower()
    if any(term in text for term in ["btc", "bitcoin", "eth", "ethereum", "$"]):
        return EventModelType.FINANCIAL_BARRIER
    if any(term in text for term in ["fed", "cpi", "rate", "inflation"]):
        return EventModelType.MACRO_POLICY
    if any(
        term in text
        for term in [
            "election",
            "poll",
            "president",
            "senate",
            "mayor",
            "nomination",
            "nominee",
            "primary",
            "democratic",
            "republican",
            "candidate",
        ]
    ):
        return EventModelType.ELECTION_POLLING
    if any(
        term in text
        for term in [
            "nba",
            "nfl",
            "nhl",
            "mlb",
            "stanley cup",
            "finals",
            "super bowl",
            "world series",
            "championship",
            "win the 2026",
        ]
    ):
        return EventModelType.SPORTS_OUTRIGHT
    if any(term in text for term in ["mutually exclusive", "above", "below", "between"]):
        return EventModelType.LOGIC_CONSISTENCY
    if any(term in text for term in ["openai", "ai", "model", "launch", "release"]):
        return EventModelType.PRODUCT_RELEASE
    return EventModelType.GENERAL_EVENT
