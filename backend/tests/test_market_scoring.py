from app.core.market_scoring import score_market
from app.schemas.market import Market


def test_score_market_adds_frontend_fields() -> None:
    candidate = score_market(
        Market(
            id="btc-120k",
            question="Will Bitcoin hit $120k before December?",
            category="crypto",
            volume=50_000,
            liquidity=10_000,
            market_probability=0.42,
        )
    )

    assert candidate.model_type == "financial_barrier"
    assert candidate.category_guess == "crypto"
    assert candidate.selected_reason
    assert 0 <= candidate.resolution_score <= 1
