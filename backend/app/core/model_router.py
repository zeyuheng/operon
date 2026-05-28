from enum import StrEnum

from app.schemas.market import Market


class EventModelType(StrEnum):
    FINANCIAL_BARRIER = "financial_barrier"
    PRODUCT_RELEASE = "product_release"
    MACRO_POLICY = "macro_policy"
    GENERAL_EVENT = "general_event"


def route_model(market: Market) -> EventModelType:
    text = f"{market.question} {market.category or ''}".lower()
    if any(term in text for term in ["btc", "bitcoin", "eth", "ethereum", "$"]):
        return EventModelType.FINANCIAL_BARRIER
    if any(term in text for term in ["fed", "cpi", "rate", "inflation"]):
        return EventModelType.MACRO_POLICY
    if any(term in text for term in ["openai", "ai", "model", "launch", "release"]):
        return EventModelType.PRODUCT_RELEASE
    return EventModelType.GENERAL_EVENT
