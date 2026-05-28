from app.schemas.market import Market


def is_viable_market(market: Market) -> bool:
    if not market.active or market.closed:
        return False
    if market.liquidity is not None and market.liquidity < 1_000:
        return False
    if market.volume is not None and market.volume < 10_000:
        return False
    if market.market_probability is not None:
        return 0.05 <= market.market_probability <= 0.95
    return True
