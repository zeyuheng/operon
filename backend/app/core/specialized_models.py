import math
import random
from datetime import UTC, datetime

from app.core.probability_engine import logit, sigmoid
from app.schemas.evidence import EvidenceObservation, PollSample, SportsRatingSample
from app.schemas.market import Market, ModelDiagnostics
from app.services.macro_data_service import MacroSnapshot


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


def build_product_release_model(
    market: Market,
    evidence: list[EvidenceObservation] | None = None,
) -> ModelDiagnostics:
    text = f"{market.question} {market.description or ''}".lower()
    evidence = evidence or []
    official_signal = 0.75 if any(term in text for term in ["official", "announced"]) else 0.45
    technical_readiness = 0.65 if any(term in text for term in ["release", "launch"]) else 0.45
    organizational_intent = (
        0.60 if any(term in text for term in ["openai", "apple", "rockstar"]) else 0.50
    )
    deadline_pressure = clamp(1.0 - days_remaining(market) / 365)
    timeline_confidence = clamp(0.65 - abs(days_remaining(market) - 120) / 500)
    evidence_effect = product_evidence_weight(evidence)
    official_signal = clamp(official_signal + 0.30 * official_evidence_score(evidence))

    evidence_weight = (
        0.35 * (official_signal - 0.5)
        + 0.25 * (technical_readiness - 0.5)
        + 0.20 * (organizational_intent - 0.5)
        + 0.15 * (deadline_pressure - 0.5)
        + 0.15 * (timeline_confidence - 0.5)
        + evidence_effect
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
            "structured_evidence_weight": clamp(0.5 + evidence_effect),
        },
        key_drivers=[
            "Uses market-implied probability as prior.",
            "Applies Bayesian log-odds update from structured evidence.",
            "Weights official sources above news/social sources.",
            "Applies deadline hazard pressure from the market end date.",
        ],
        notes=[
            "Evidence extractor uses OpenAI when configured; otherwise heuristic extraction.",
            "Next upgrade: particle filter / SMC over latent readiness states.",
        ],
    )


def build_macro_policy_model(
    market: Market,
    snapshot: MacroSnapshot | None = None,
) -> ModelDiagnostics:
    text = f"{market.question} {market.description or ''}".lower()
    snapshot = snapshot or MacroSnapshot()
    inflation_trend = macro_z_score(snapshot.cpi_yoy, center=2.5, scale=2.5)
    labor_market_pressure = 1 - macro_z_score(snapshot.unemployment_rate, center=4.5, scale=3.0)
    curve_pressure = yield_curve_pressure(snapshot)
    policy_reaction_function = 0.65 if "fed" in text or "rate" in text else 0.52
    market_expectation = prior(market)
    official_guidance = fed_policy_guidance_proxy(snapshot)
    event_direction = macro_event_direction(text)

    posterior = sigmoid(
        logit(market_expectation)
        + event_direction * 0.25 * (inflation_trend - 0.5)
        + event_direction * 0.20 * (labor_market_pressure - 0.5)
        + 0.20 * (curve_pressure - 0.5)
        + 0.25 * (policy_reaction_function - 0.5)
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
            "yield_curve_pressure": curve_pressure,
            "market_expectation": market_expectation,
            "official_guidance": official_guidance,
        },
        key_drivers=[
            "Treats market price as consensus prior.",
            "Uses FRED public CSV for CPI, unemployment, fed funds, and Treasury yields.",
            "Applies macro indicator z-scores in a Bayesian log-odds update.",
        ],
        notes=[
            f"Macro data source: {snapshot.data_source}.",
            "Next upgrade: dynamic linear model / Kalman nowcast ensemble.",
        ],
    )


def product_evidence_weight(evidence: list[EvidenceObservation]) -> float:
    total = 0.0
    seen_claims = set()
    for item in evidence:
        normalized_claim = item.claim.lower().strip()
        duplicate_penalty = 0.5 if normalized_claim in seen_claims else 1.0
        seen_claims.add(normalized_claim)
        reliability = source_quality(item.source_type)
        total += (
            item.strength
            * item.relevance
            * reliability
            * item.novelty
            * (1 - 0.5 * item.ambiguity)
            * duplicate_penalty
        )
    return clamp(total, -0.6, 0.6)


def official_evidence_score(evidence: list[EvidenceObservation]) -> float:
    official_items = [item for item in evidence if source_quality(item.source_type) >= 0.75]
    if not official_items:
        return 0.0
    return clamp(sum(item.relevance * max(0, item.strength) for item in official_items) / 2)


def macro_z_score(value: float | None, center: float, scale: float) -> float:
    if value is None:
        return 0.50
    return clamp(0.5 + (value - center) / (2 * scale))


def yield_curve_pressure(snapshot: MacroSnapshot) -> float:
    if snapshot.two_year_yield is None or snapshot.ten_year_yield is None:
        return 0.50
    spread = snapshot.ten_year_yield - snapshot.two_year_yield
    return clamp(0.5 - spread / 4)


def fed_policy_guidance_proxy(snapshot: MacroSnapshot) -> float:
    if snapshot.fed_funds_rate is None:
        return 0.50
    return clamp(0.45 + (snapshot.fed_funds_rate - 3.0) / 10)


def macro_event_direction(text: str) -> float:
    if any(term in text for term in ["cut", "lower", "below", "under"]):
        return -1.0
    return 1.0


def build_election_polling_model(
    market: Market,
    evidence: list[EvidenceObservation] | None = None,
    poll_samples: list[PollSample] | None = None,
) -> ModelDiagnostics:
    market_consensus = prior(market)
    evidence = evidence or []
    polls = poll_samples or derive_poll_samples(market, evidence)
    if not polls:
        polls = derive_poll_samples(market, evidence)
    polling_average, poll_weight = weighted_polling_average(polls)
    field_score = candidate_field_score(market, evidence)
    recency_weight = clamp(poll_weight / max(len(polls), 1))
    pollster_quality = sum(poll.pollster_quality for poll in polls) / max(len(polls), 1)
    correlation_risk = 0.55 + 0.20 * (1 - recency_weight)
    market_precision = 5.0
    poll_precision = max(1.0, poll_weight)
    field_adjustment = 0.35 * (field_score - 0.5)
    posterior = sigmoid(
        (
            market_precision * logit(market_consensus)
            + poll_precision * logit(polling_average)
        )
        / (market_precision + poll_precision)
        + field_adjustment
    )
    uncertainty = clamp(0.12 + 0.16 * correlation_risk + 0.10 * (1 - pollster_quality), 0.12, 0.35)

    return ModelDiagnostics(
        model_name="Election / Polling Model",
        posterior_probability=posterior,
        confidence=clamp(0.25 + 0.45 * recency_weight + 0.20 * pollster_quality),
        uncertainty_interval=interval(posterior, uncertainty),
        state_scores={
            "weighted_polling_average": polling_average,
            "pollster_quality": pollster_quality,
            "recency_weight": recency_weight,
            "state_national_correlation_risk": correlation_risk,
            "candidate_field_strength": field_score,
            "market_consensus": market_consensus,
        },
        key_drivers=[
            "Aggregates poll-like samples with pollster-quality and recency decay weights.",
            "Combines market prior and polling likelihood in log-odds space.",
            "Adds candidate-field adjustment for entry/exit, endorsements, and consolidation.",
        ],
        notes=[
            (
                "External polling samples were loaded."
                if poll_samples
                else (
                    "If no external polls are loaded, market price becomes a "
                    "low-weight consensus poll."
                )
            ),
            "Next upgrade: live poll ingestion, delegate simulation, fundraising, endorsements.",
        ],
    )


def build_sports_outright_model(
    market: Market,
    evidence: list[EvidenceObservation] | None = None,
    rating_samples: list[SportsRatingSample] | None = None,
) -> ModelDiagnostics:
    market_consensus = prior(market)
    evidence = evidence or []
    ratings = rating_samples or derive_sports_ratings(market, evidence)
    if not ratings:
        ratings = derive_sports_ratings(market, evidence)
    team_strength_proxy = ratings[0].rating
    season_stage_certainty = clamp(1.0 - days_remaining(market) / 365)
    injury_depth_uncertainty = injury_uncertainty(evidence)
    schedule_path_clarity = 0.45 + 0.20 * season_stage_certainty
    playoff_variance = 0.65
    monte_carlo_probability = simulate_outright_probability(
        target_rating=team_strength_proxy,
        field_ratings=[rating.rating for rating in ratings],
        path_clarity=schedule_path_clarity,
    )
    posterior = clamp(0.50 * market_consensus + 0.50 * monte_carlo_probability)

    return ModelDiagnostics(
        model_name="Sports Outright Model",
        posterior_probability=posterior,
        confidence=clamp(0.28 + 0.30 * season_stage_certainty + 0.20 * schedule_path_clarity),
        uncertainty_interval=interval(posterior, 0.24),
        state_scores={
            "team_strength_proxy": team_strength_proxy,
            "monte_carlo_title_probability": monte_carlo_probability,
            "season_stage_certainty": season_stage_certainty,
            "schedule_path_clarity": schedule_path_clarity,
            "injury_depth_uncertainty": injury_depth_uncertainty,
            "playoff_variance": playoff_variance,
            "market_consensus": market_consensus,
        },
        key_drivers=[
            "Converts market consensus into a team-strength prior.",
            "Runs a simple field Monte Carlo over championship outcomes.",
            "Adjusts confidence for season stage, path clarity, and injury uncertainty.",
        ],
        notes=[
            (
                "External team rating samples were loaded."
                if rating_samples
                else (
                    "If no standings/odds feeds are loaded, ratings are synthesized "
                    "from market prior."
                )
            ),
            "Next upgrade: team ratings, bracket path, injuries, and bookmaker consensus.",
        ],
    )


def derive_poll_samples(
    market: Market,
    evidence: list[EvidenceObservation],
) -> list[PollSample]:
    samples = [
        PollSample(
            candidate=market.question,
            support=prior(market),
            sample_size=1_000,
            pollster_quality=0.55,
            age_days=21,
            source="market_consensus",
        )
    ]
    for item in evidence:
        if item.relevance < 0.55:
            continue
        support_shift = 0.08 * item.strength * (1 - item.ambiguity)
        samples.append(
            PollSample(
                candidate=market.question,
                support=clamp(prior(market) + support_shift),
                sample_size=800,
                pollster_quality=source_quality(item.source_type),
                age_days=7 + 45 * (1 - item.novelty),
                source=item.source_type,
            )
        )
    return samples


def weighted_polling_average(samples: list[PollSample]) -> tuple[float, float]:
    weighted_sum = 0.0
    total_weight = 0.0
    for sample in samples:
        recency = math.exp(-sample.age_days / 45)
        size_weight = math.sqrt(sample.sample_size / 1_000)
        weight = sample.pollster_quality * recency * size_weight
        weighted_sum += sample.support * weight
        total_weight += weight
    if total_weight == 0:
        return 0.5, 0.0
    return clamp(weighted_sum / total_weight), total_weight


def candidate_field_score(market: Market, evidence: list[EvidenceObservation]) -> float:
    score = 0.50
    text = f"{market.question} {market.description or ''}".lower()
    if "nomination" in text or "primary" in text:
        score -= 0.04
    for item in evidence:
        score += 0.12 * item.strength * item.relevance * source_quality(item.source_type)
    return clamp(score)


def source_quality(source_type: str) -> float:
    normalized = source_type.lower()
    if normalized in {"official", "pollster", "fec", "market_rule"}:
        return 0.80
    if normalized in {"major_news", "news"}:
        return 0.68
    if normalized in {"social", "unknown"}:
        return 0.45
    return 0.55


def derive_sports_ratings(
    market: Market,
    evidence: list[EvidenceObservation],
) -> list[SportsRatingSample]:
    target = implied_rating_from_probability(prior(market))
    for item in evidence:
        target += 0.12 * item.strength * item.relevance * source_quality(item.source_type)
    target = clamp(target, 0.05, 0.95)
    field = [target]
    remaining_strength = max(0.05, 1 - target)
    for index in range(15):
        decay = math.exp(-index / 5)
        field.append(clamp((remaining_strength / 15) * (0.55 + decay), 0.01, 0.40))
    return [
        SportsRatingSample(team=market.question, rating=rating, source="market_implied_field")
        for rating in field
    ]


def implied_rating_from_probability(probability: float) -> float:
    return clamp(probability, 0.01, 0.95)


def injury_uncertainty(evidence: list[EvidenceObservation]) -> float:
    base = 0.45
    for item in evidence:
        if "injury" in item.claim.lower() or "injured" in item.claim.lower():
            base += 0.20 * item.relevance
    return clamp(base)


def simulate_outright_probability(
    target_rating: float,
    field_ratings: list[float],
    path_clarity: float,
    simulations: int = 4_000,
) -> float:
    rng = random.Random(11)
    wins = 0
    noise_scale = 0.18 + 0.22 * (1 - path_clarity)
    for _ in range(simulations):
        sampled = [
            max(0.001, rating * math.exp(rng.gauss(0, noise_scale)))
            for rating in field_ratings
        ]
        total = sum(sampled)
        draw = rng.random() * total
        cumulative = 0.0
        winner = 0
        for index, value in enumerate(sampled):
            cumulative += value
            if cumulative >= draw:
                winner = index
                break
        if winner == 0:
            wins += 1
    return wins / simulations


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
