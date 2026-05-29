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


def test_score_market_recognizes_nomination_as_election() -> None:
    candidate = score_market(
        Market(
            id="newsom",
            question="Will Gavin Newsom win the 2028 Democratic presidential nomination?",
            volume=2_000_000,
            liquidity=250_000,
            market_probability=0.24,
        )
    )

    assert candidate.model_type == "election_polling"
    assert candidate.category_guess == "election"
    assert candidate.evidence_score > 0.8
    assert "fit=0.78" in candidate.reason


def test_score_market_recognizes_sports_outright() -> None:
    candidate = score_market(
        Market(
            id="knicks",
            question="Will the New York Knicks win the 2026 NBA Finals?",
            volume=2_000_000,
            liquidity=250_000,
            market_probability=0.20,
        )
    )

    assert candidate.model_type == "sports_outright"
    assert candidate.category_guess == "sports"
    assert candidate.evidence_score > 0.8


def test_score_market_does_not_treat_airdrop_deadline_as_price_barrier() -> None:
    candidate = score_market(
        Market(
            id="megaeth",
            question="Will MegaETH perform an airdrop by June 30?",
            category="crypto",
            volume=1_000_000,
            liquidity=50_000,
            market_probability=0.18,
        )
    )

    assert candidate.model_type == "product_release"
    assert "fit=0.78" in candidate.reason
