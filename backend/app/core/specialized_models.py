from datetime import UTC, datetime

from app.core.probability_engine import logit, sigmoid
from app.schemas.market import Market, ModelDiagnostics


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def prior(market: Market) -> float:
    return market.market_probability if market.market_probability is not None else 0.5


def days_remaining(market: Market) -> float:
    if not market.end_date:
        return 180.0
    parsed = datetime.fromisoformat(market.end_date.replace("Z", "+00:00"))
    return max(1.0, (parsed - datetime.now(UTC)).total_seconds() / 86_400)


def interval(center: float, width: float) -> list[float]:
    return [clamp(center - width), clamp(center + width)]


def build_product_release_model(market: Market) -> ModelDiagnostics:
    text = f"{market.question} {market.description or ''}".lower()
    official_signal = 0.75 if any(term in text for term in ["official", "announced"]) else 0.45
    technical_readiness = 0.65 if any(term in text for term in ["release", "launch"]) else 0.45
    organizational_intent = (
        0.60 if any(term in text for term in ["openai", "apple", "rockstar"]) else 0.50
    )
    deadline_pressure = clamp(1.0 - days_remaining(market) / 365)
    timeline_confidence = clamp(0.65 - abs(days_remaining(market) - 120) / 500)

    evidence_weight = (
        0.35 * (official_signal - 0.5)
        + 0.25 * (technical_readiness - 0.5)
        + 0.20 * (organizational_intent - 0.5)
        + 0.15 * (deadline_pressure - 0.5)
        + 0.15 * (timeline_confidence - 0.5)
    )
    posterior = sigmoid(logit(prior(market)) + evidence_weight)

    return ModelDiagnostics(
        model_name="Product Release Model",
        posterior_probability=posterior,
        confidence=0.48,
        uncertainty_interval=interval(posterior, 0.22),
        state_scores={
            "technical_readiness": technical_readiness,
            "organizational_intent": organizational_intent,
            "external_pressure": deadline_pressure,
            "timeline_confidence": timeline_confidence,
            "official_signal_strength": official_signal,
        },
        key_drivers=[
            "Uses market-implied probability as prior.",
            "Scores release readiness from title/rule text until external evidence is connected.",
            "Applies deadline pressure from the market end date.",
        ],
        notes=[
            "v1 does not yet call an LLM or scrape official blogs/news.",
            "Next upgrade: evidence extraction from official sources and developer docs.",
        ],
    )


def build_macro_policy_model(market: Market) -> ModelDiagnostics:
    text = f"{market.question} {market.description or ''}".lower()
    inflation_trend = 0.62 if "cpi" in text or "inflation" in text else 0.50
    labor_market_pressure = 0.58 if "unemployment" in text or "jobs" in text else 0.50
    policy_reaction_function = 0.65 if "fed" in text or "rate" in text else 0.52
    market_expectation = prior(market)
    official_guidance = 0.50

    posterior = sigmoid(
        logit(market_expectation)
        + 0.20 * (inflation_trend - 0.5)
        + 0.20 * (labor_market_pressure - 0.5)
        + 0.30 * (policy_reaction_function - 0.5)
        + 0.15 * (official_guidance - 0.5)
    )

    return ModelDiagnostics(
        model_name="Macro Policy Model",
        posterior_probability=posterior,
        confidence=0.42,
        uncertainty_interval=interval(posterior, 0.18),
        state_scores={
            "inflation_trend": inflation_trend,
            "labor_market_pressure": labor_market_pressure,
            "policy_reaction_function": policy_reaction_function,
            "market_expectation": market_expectation,
            "official_guidance": official_guidance,
        },
        key_drivers=[
            "Treats market price as consensus prior.",
            "Applies lightweight nowcasting heuristics from the market text.",
            "Leaves room for official data and calendar feeds.",
        ],
        notes=[
            "v1 is a Bayesian nowcasting shell, not a live macro feed.",
            "Next upgrade: FRED/economic calendar/latest release ingestion.",
        ],
    )


def build_election_polling_model(market: Market) -> ModelDiagnostics:
    market_consensus = prior(market)
    polling_average = market_consensus
    recency_weight = 0.50
    pollster_quality = 0.50
    correlation_risk = 0.60
    uncertainty = 0.20 + 0.10 * correlation_risk
    posterior = clamp(0.80 * market_consensus + 0.20 * polling_average)

    return ModelDiagnostics(
        model_name="Election / Polling Model",
        posterior_probability=posterior,
        confidence=0.36,
        uncertainty_interval=interval(posterior, uncertainty),
        state_scores={
            "weighted_polling_average": polling_average,
            "pollster_quality": pollster_quality,
            "recency_weight": recency_weight,
            "state_national_correlation_risk": correlation_risk,
            "market_consensus": market_consensus,
        },
        key_drivers=[
            "Uses market price as polling proxy until poll ingestion is available.",
            "Applies a wide uncertainty band for correlated polling errors.",
        ],
        notes=[
            "v1 does not ingest real polls.",
            "Next upgrade: pollster weighting, recency decay, and correlation model.",
        ],
    )


def build_logic_consistency_model(market: Market) -> ModelDiagnostics:
    posterior = prior(market)
    return ModelDiagnostics(
        model_name="Logic / Related Market Consistency Model",
        posterior_probability=posterior,
        confidence=0.30,
        uncertainty_interval=interval(posterior, 0.25),
        state_scores={
            "monotonicity_check": 0.50,
            "mutual_exclusivity_check": 0.50,
            "frechet_bound_check": 0.50,
            "related_market_coverage": 0.10,
        },
        key_drivers=[
            "Keeps market prior unchanged because no related market set is loaded yet.",
            "Prepared to flag monotonicity and mutual-exclusion violations.",
        ],
        notes=[
            "v1 is a consistency shell for single markets.",
            "Next upgrade: fetch related markets and evaluate cross-market constraints.",
        ],
    )


def build_general_event_model(market: Market) -> ModelDiagnostics:
    market_prior = prior(market)
    uncertainty_penalty = 0.18
    posterior = 0.75 * market_prior + 0.25 * 0.5

    return ModelDiagnostics(
        model_name="General Event Model",
        posterior_probability=posterior,
        confidence=0.28,
        uncertainty_interval=interval(posterior, 0.25 + uncertainty_penalty),
        state_scores={
            "source_reliability": 0.45,
            "evidence_specificity": 0.40,
            "resolution_clarity": 0.50,
            "uncertainty_penalty": uncertainty_penalty,
        },
        key_drivers=[
            "Shrinks market prior toward 50% because no specialized model applies.",
            "Uses conservative uncertainty until structured evidence is available.",
        ],
        notes=[
            "v1 does not call an LLM.",
            "Next upgrade: LLM evidence extraction with source reliability scoring.",
        ],
    )
