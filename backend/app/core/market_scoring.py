import math

from app.core.model_router import route_model
from app.schemas.market import Market, MarketCandidate

CATEGORY_EVIDENCE_PRIOR = {
    "crypto": 0.90,
    "economics": 0.90,
    "politics": 0.85,
    "technology": 0.80,
    "sports": 0.78,
    "business": 0.74,
    "culture": 0.55,
    "celebrity": 0.35,
}


def normalized_log_score(value: float | None, cap: float) -> float:
    if value is None or value <= 0:
        return 0.0
    return min(1.0, math.log1p(value) / math.log1p(cap))


def evidence_availability_score(market: Market) -> float:
    category = (market.category or "").lower()
    return CATEGORY_EVIDENCE_PRIOR.get(category, 0.60)


def category_guess(market: Market) -> str:
    text = f"{market.question} {market.category or ''}".lower()
    if any(term in text for term in ["btc", "bitcoin", "eth", "ethereum", "crypto"]):
        return "crypto"
    if any(term in text for term in ["fed", "cpi", "inflation", "rate"]):
        return "economics"
    if any(term in text for term in ["openai", "ai", "model", "launch", "release"]):
        return "technology"
    if any(term in text for term in ["election", "poll", "president"]):
        return "politics"
    return (market.category or "general").lower()


def price_informativeness_score(market: Market) -> float:
    price = market.market_probability
    if price is None:
        return 0.50
    return max(0.0, 1.0 - abs(price - 0.5) * 2)


def resolution_clarity_score(market: Market) -> float:
    text = " ".join(part for part in [market.question, market.description] if part)
    if not text:
        return 0.35
    clear_terms = ["by", "before", "on", "will", "resolve", "according to", "?"]
    hits = sum(1 for term in clear_terms if term.lower() in text.lower())
    return min(1.0, 0.45 + hits * 0.10)


def model_fit_score(market: Market) -> float:
    text = f"{market.question} {market.category or ''}".lower()
    if any(term in text for term in ["btc", "bitcoin", "eth", "ethereum", "$"]):
        return 0.92
    if any(term in text for term in ["fed", "cpi", "rate", "inflation"]):
        return 0.84
    if any(term in text for term in ["openai", "ai", "model", "launch", "release"]):
        return 0.78
    if "election" in text or "poll" in text:
        return 0.68
    return 0.45


def score_market(market: Market) -> MarketCandidate:
    liquidity_score = normalized_log_score(market.liquidity, 100_000)
    volume_score = normalized_log_score(market.volume, 1_000_000)
    liquidity_blend = 0.6 * liquidity_score + 0.4 * volume_score
    evidence_score = evidence_availability_score(market)
    resolution_score = resolution_clarity_score(market)
    price_score = price_informativeness_score(market)
    fit_score = model_fit_score(market)
    guessed_category = category_guess(market)

    operon_score = (
        0.18 * liquidity_blend
        + 0.16 * resolution_score
        + 0.16 * evidence_score
        + 0.14 * fit_score
        + 0.10 * price_score
        + 0.10 * 0.50
        + 0.08 * 0.40
        + 0.08 * 0.50
    )

    risk_flags = build_risk_flags(market, resolution_score, evidence_score, liquidity_blend)
    selected_reason = (
        f"Selected because it has {score_label(fit_score)} model fit, "
        f"{score_label(evidence_score)} evidence availability, and "
        f"{score_label(resolution_score)} resolution clarity."
    )
    reason = (
        f"fit={fit_score:.2f}, evidence={evidence_score:.2f}, "
        f"resolution={resolution_score:.2f}, liquidity={liquidity_blend:.2f}"
    )
    return MarketCandidate(
        market=market,
        operon_score=operon_score,
        reason=reason,
        model_type=route_model(market).value,
        category_guess=guessed_category,
        risk_flags=risk_flags,
        selected_reason=selected_reason,
        resolution_score=resolution_score,
        evidence_score=evidence_score,
        liquidity_score=liquidity_blend,
    )


def score_label(score: float) -> str:
    if score >= 0.75:
        return "strong"
    if score >= 0.50:
        return "usable"
    return "weak"


def build_risk_flags(
    market: Market,
    resolution_score: float,
    evidence_score: float,
    liquidity_score: float,
) -> list[str]:
    flags = []
    if resolution_score < 0.55:
        flags.append("ambiguous_resolution")
    if evidence_score < 0.60:
        flags.append("thin_public_evidence")
    if liquidity_score < 0.45:
        flags.append("low_liquidity")
    if market.market_probability is not None and market.market_probability in {0.0, 1.0}:
        flags.append("stale_or_extreme_price")
    return flags
