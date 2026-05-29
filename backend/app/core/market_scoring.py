import math

from app.core.financial_barrier_model import parse_financial_barrier
from app.core.model_router import route_model
from app.core.rule_parser import RuleType, parse_market_rule
from app.schemas.market import Market, MarketCandidate

CATEGORY_EVIDENCE_PRIOR = {
    "crypto": 0.90,
    "economics": 0.90,
    "politics": 0.85,
    "election": 0.86,
    "technology": 0.80,
    "sports": 0.84,
    "business": 0.74,
    "culture": 0.55,
    "celebrity": 0.35,
}


def normalized_log_score(value: float | None, cap: float) -> float:
    if value is None or value <= 0:
        return 0.0
    return min(1.0, math.log1p(value) / math.log1p(cap))


def evidence_availability_score(market: Market) -> float:
    category = category_guess(market)
    return CATEGORY_EVIDENCE_PRIOR.get(category, 0.60)


def category_guess(market: Market) -> str:
    text = f"{market.question} {market.category or ''}".lower()
    if any(term in text for term in ["airdrop", "mainnet", "testnet", "tge"]):
        return "technology"
    if any(term in text for term in ["btc", "bitcoin", " eth ", "ethereum", "crypto"]):
        return "crypto"
    if any(term in text for term in ["fed", "cpi", "inflation", "rate"]):
        return "economics"
    if any(term in text for term in ["openai", "ai", "model", "launch", "release"]):
        return "technology"
    if any(
        term in text
        for term in [
            "election",
            "poll",
            "president",
            "nomination",
            "nominee",
            "primary",
            "democratic",
            "republican",
            "candidate",
        ]
    ):
        return "election"
    if any(
        term in text
        for term in [
            "nba",
            "nfl",
            "nhl",
            "mlb",
            "stanley cup",
            "finals",
            "super bowl",
            "world series",
            "championship",
        ]
    ):
        return "sports"
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
    if parse_financial_barrier(market) is not None:
        return 0.92
    if any(term in text for term in ["fed", "cpi", "rate", "inflation"]):
        return 0.84
    if any(
        term in text
        for term in ["openai", "ai", "model", "launch", "release", "airdrop", "mainnet", "tge"]
    ):
        return 0.78
    if any(
        term in text
        for term in [
            "election",
            "poll",
            "president",
            "nomination",
            "nominee",
            "primary",
            "democratic",
            "republican",
            "candidate",
        ]
    ):
        return 0.78
    if any(
        term in text
        for term in [
            "nba",
            "nfl",
            "nhl",
            "mlb",
            "stanley cup",
            "finals",
            "super bowl",
            "world series",
            "championship",
        ]
    ):
        return 0.76
    return 0.45


def score_market(market: Market) -> MarketCandidate:
    liquidity_score = normalized_log_score(market.liquidity, 500_000)
    volume_score = normalized_log_score(market.volume, 10_000_000)
    liquidity_blend = 0.6 * liquidity_score + 0.4 * volume_score
    evidence_score = evidence_availability_score(market)
    resolution_score = resolution_clarity_score(market)
    price_score = price_informativeness_score(market)
    fit_score = model_fit_score(market)
    guessed_category = category_guess(market)
    parsed_rule = parse_market_rule(market)
    market_structure_type, primary_edge_source = classify_market_structure(parsed_rule.rule_type)
    scout_penalty = structure_penalty(market, parsed_rule.rule_type)

    raw_score = (
        0.18 * liquidity_blend
        + 0.16 * resolution_score
        + 0.16 * evidence_score
        + 0.14 * fit_score
        + 0.10 * price_score
        + 0.10 * 0.50
        + 0.08 * 0.40
        + 0.08 * 0.50
    )
    operon_score = max(0.0, raw_score - scout_penalty)

    risk_flags = build_risk_flags(
        market,
        resolution_score,
        evidence_score,
        liquidity_blend,
        parsed_rule.rule_type,
    )
    selected_reason = (
        f"Selected because it has {score_label(fit_score)} model fit, "
        f"{score_label(evidence_score)} evidence availability, and "
        f"{score_label(resolution_score)} resolution clarity."
    )
    reason = (
        f"fit={fit_score:.2f}, evidence={evidence_score:.2f}, "
        f"resolution={resolution_score:.2f}, liquidity={liquidity_blend:.2f}, "
        f"penalty={scout_penalty:.2f}"
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
        market_structure_type=market_structure_type,
        primary_edge_source=primary_edge_source,
        scout_penalty=scout_penalty,
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
    rule_type: RuleType,
) -> list[str]:
    flags = []
    if rule_type == RuleType.FALLBACK_50_50_BEFORE_EVENT:
        flags.append("fallback_dominated")
        flags.append("resolution_mechanics")
    if resolution_score < 0.55:
        flags.append("ambiguous_resolution")
    if evidence_score < 0.60:
        flags.append("thin_public_evidence")
    if liquidity_score < 0.45:
        flags.append("low_liquidity")
    if market.market_probability is not None and market.market_probability in {0.0, 1.0}:
        flags.append("stale_or_extreme_price")
    return flags


def classify_market_structure(rule_type: RuleType) -> tuple[str, str]:
    if rule_type == RuleType.FALLBACK_50_50_BEFORE_EVENT:
        return "resolution_mechanics", "fallback_clause"
    return "forecasting_market", "event_forecast"


def structure_penalty(market: Market, rule_type: RuleType) -> float:
    penalty = 0.0
    if rule_type == RuleType.FALLBACK_50_50_BEFORE_EVENT:
        penalty += 0.22

    text = f"{market.question} {market.description or ''}".lower()
    if "gta vi" in text and rule_type == RuleType.FALLBACK_50_50_BEFORE_EVENT:
        penalty += 0.06

    return min(0.35, penalty)
