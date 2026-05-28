from app.core.consensus_guardrail import build_consensus_guardrail
from app.schemas.market import Market, MarketCandidate


def make_candidate(market_probability: float, liquidity_score: float = 1.0) -> MarketCandidate:
    return MarketCandidate(
        market=Market(id="1", question="Test market", market_probability=market_probability),
        operon_score=0.7,
        reason="test",
        model_type="general_event",
        category_guess="general",
        selected_reason="test",
        resolution_score=0.8,
        evidence_score=0.7,
        liquidity_score=liquidity_score,
    )


def test_guardrail_aligned_when_close_to_market() -> None:
    guardrail = build_consensus_guardrail(make_candidate(0.50), 0.53, 0.5)

    assert guardrail.status == "aligned"
    assert not guardrail.model_review_required


def test_guardrail_requires_review_for_large_low_confidence_gap() -> None:
    guardrail = build_consensus_guardrail(make_candidate(0.50), 0.10, 0.2)

    assert guardrail.status == "model_review_required"
    assert guardrail.model_review_required
