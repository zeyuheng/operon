from app.core.model_router import EventModelType, route_model
from app.schemas.market import Market


def test_routes_financial_barrier_market() -> None:
    market = Market(id="1", question="Will Bitcoin hit $120k before December?")
    assert route_model(market) == EventModelType.FINANCIAL_BARRIER


def test_routes_product_release_market() -> None:
    market = Market(id="2", question="Will OpenAI release a new AI model before July?")
    assert route_model(market) == EventModelType.PRODUCT_RELEASE


def test_routes_nomination_market_to_election() -> None:
    market = Market(
        id="3",
        question="Will Gavin Newsom win the 2028 Democratic presidential nomination?",
    )
    assert route_model(market) == EventModelType.ELECTION_POLLING


def test_routes_sports_outright_market() -> None:
    market = Market(id="4", question="Will the Knicks win the 2026 NBA Finals?")
    assert route_model(market) == EventModelType.SPORTS_OUTRIGHT


def test_routes_airdrop_project_with_eth_name_away_from_financial_barrier() -> None:
    market = Market(id="5", question="Will MegaETH perform an airdrop by June 30?")
    assert route_model(market) == EventModelType.PRODUCT_RELEASE


def test_routes_crypto_price_barrier_only_with_explicit_price_language() -> None:
    market = Market(id="6", question="Will ETH hit $3,000 by June 30?")
    assert route_model(market) == EventModelType.FINANCIAL_BARRIER
