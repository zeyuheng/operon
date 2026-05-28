from app.core.financial_barrier_model import (
    estimate_annualized_volatility,
    parse_financial_barrier,
    simulate_barrier_hit_probability,
)
from app.schemas.market import Market


def test_parse_bitcoin_million_barrier() -> None:
    spec = parse_financial_barrier(Market(id="1", question="Will bitcoin hit $1m?"))

    assert spec is not None
    assert spec.asset_symbol == "BTC"
    assert spec.barrier_price == 1_000_000


def test_estimate_volatility_from_prices() -> None:
    volatility = estimate_annualized_volatility([100, 102, 101, 105, 107])

    assert volatility > 0


def test_barrier_probability_is_bounded() -> None:
    probability, steps = simulate_barrier_hit_probability(
        spot_price=100,
        barrier_price=120,
        days_remaining=30,
        annualized_volatility=0.5,
        simulations=200,
    )

    assert 0 <= probability <= 1
    assert steps > 0
