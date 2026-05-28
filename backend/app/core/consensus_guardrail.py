from app.schemas.market import ConsensusGuardrail, MarketCandidate


def build_consensus_guardrail(
    candidate: MarketCandidate,
    operon_probability: float,
    model_confidence: float,
) -> ConsensusGuardrail:
    market_probability = candidate.market.market_probability
    if market_probability is None:
        return ConsensusGuardrail(
            market_probability=None,
            operon_probability=operon_probability,
            gap=0.0,
            absolute_gap=0.0,
            status="no_market_anchor",
            warning="No market price is available, so consensus sanity check is skipped.",
            confidence_used=model_confidence,
            liquidity_weight=candidate.liquidity_score,
            divergence_risk=0.0,
        )

    gap = operon_probability - market_probability
    absolute_gap = abs(gap)
    divergence_risk = min(
        1.0,
        absolute_gap * (1 - model_confidence) * (0.35 + 0.65 * candidate.liquidity_score) * 3,
    )
    status = consensus_status(absolute_gap, divergence_risk)
    review_required = status == "model_review_required"
    warning = consensus_warning(status, gap, model_confidence)

    return ConsensusGuardrail(
        market_probability=market_probability,
        operon_probability=operon_probability,
        gap=gap,
        absolute_gap=absolute_gap,
        status=status,
        model_review_required=review_required,
        warning=warning,
        confidence_used=model_confidence,
        liquidity_weight=candidate.liquidity_score,
        divergence_risk=divergence_risk,
    )


def consensus_status(absolute_gap: float, divergence_risk: float) -> str:
    if absolute_gap < 0.05:
        return "aligned"
    if absolute_gap < 0.15:
        return "mild_divergence"
    if absolute_gap < 0.30 and divergence_risk < 0.35:
        return "major_divergence"
    return "model_review_required"


def consensus_warning(status: str, gap: float, confidence: float) -> str:
    direction = "above" if gap > 0 else "below"
    if status == "aligned":
        return "Operon is close to market consensus."
    if status == "mild_divergence":
        return f"Operon is mildly {direction} market consensus; explain the difference."
    if status == "major_divergence":
        return (
            f"Operon is materially {direction} market consensus. Check data freshness, "
            "rule interpretation, and missing evidence."
        )
    return (
        f"Operon is far {direction} market consensus while model confidence is "
        f"{confidence:.0%}. Review model assumptions before trusting this estimate."
    )
