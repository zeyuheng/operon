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


def test_score_market_penalizes_fallback_dominated_rules() -> None:
    candidate = score_market(
        Market(
            id="btc-gta",
            question="Will bitcoin hit $1m before GTA VI?",
            description=(
                "This market resolves Yes if BTC hits before GTA VI. "
                "If neither occurs by July 31, 2026, this market will resolve to 50-50."
            ),
            volume=1_000_000,
            liquidity=100_000,
            market_probability=0.49,
        )
    )

    assert candidate.market_structure_type == "resolution_mechanics"
    assert candidate.primary_edge_source == "fallback_clause"
    assert candidate.scout_penalty > 0
    assert "fallback_dominated" in candidate.risk_flags
