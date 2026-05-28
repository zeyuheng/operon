from app.core.model_router import EventModelType, route_model
from app.schemas.market import Market


def test_routes_financial_barrier_market() -> None:
    market = Market(id="1", question="Will Bitcoin hit $120k before December?")
    assert route_model(market) == EventModelType.FINANCIAL_BARRIER


def test_routes_product_release_market() -> None:
    market = Market(id="2", question="Will OpenAI release a new AI model before July?")
    assert route_model(market) == EventModelType.PRODUCT_RELEASE
