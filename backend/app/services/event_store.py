from uuid import uuid4

from app.core.consensus_guardrail import build_consensus_guardrail
from app.core.financial_barrier_model import (
    build_financial_barrier_diagnostics,
    parse_financial_barrier,
)
from app.core.probability_engine import update_log_odds
from app.core.specialized_models import (
    build_election_polling_model,
    build_general_event_model,
    build_logic_consistency_model,
    build_macro_policy_model,
    build_product_release_model,
    build_sports_outright_model,
)
from app.schemas.market import EventDraft, MarketCandidate
from app.services.crypto_price_service import CryptoPriceService
from app.services.evidence_extractor import EvidenceExtractor

EVENT_STORE: dict[str, EventDraft] = {}


async def promote_candidate_to_event(candidate: MarketCandidate) -> EventDraft:
    prior = (
        candidate.market.market_probability
        if candidate.market.market_probability is not None
        else 0.50
    )
    evidence_weight = (
        0.35 * (candidate.evidence_score - 0.5)
        + 0.25 * (candidate.resolution_score - 0.5)
        + 0.20 * (candidate.liquidity_score - 0.5)
    )
    operon_probability = update_log_odds(prior, evidence_weight)
    timeline = [
        {"label": "market_prior", "probability": prior},
        {"label": "scout_adjusted", "probability": operon_probability},
    ]
    evidence_items = [
        candidate.selected_reason,
        f"Initial scout scores: {candidate.reason}",
    ]
    observations = await EvidenceExtractor().extract_from_market_text(candidate.market)
    evidence_items.extend(
        f"Extracted evidence: {item.claim} "
        f"(direction={item.direction}, strength={item.strength:.2f}, source={item.source_type})"
        for item in observations[:4]
    )
    financial_barrier = None
    product_release = None
    macro_policy = None
    election_polling = None
    sports_outright = None
    logic_consistency = None
    general_event = None
    model_confidence = 0.35
    if candidate.model_type == "financial_barrier":
        financial_barrier = await run_financial_barrier_model(candidate)
        if financial_barrier is not None:
            model_confidence = 0.62
            operon_probability = combine_probabilities(
                scout_probability=operon_probability,
                model_probability=financial_barrier.expected_contract_value,
            )
            timeline.extend(
                [
                    {
                        "label": "barrier_model",
                        "probability": financial_barrier.hit_probability,
                    },
                    {
                        "label": "expected_contract_value",
                        "probability": financial_barrier.expected_contract_value,
                    },
                    {"label": "combined_posterior", "probability": operon_probability},
                ]
            )
            evidence_items.append(
                "Financial barrier model ran a Monte Carlo simulation using current "
                f"{financial_barrier.asset} spot price and recent volatility."
            )
            evidence_items.append(
                "Rule adapter applied: "
                f"{financial_barrier.rule_type}. {financial_barrier.rule_summary}"
            )
    elif candidate.model_type == "product_release":
        product_release = build_product_release_model(candidate.market)
        model_confidence = product_release.confidence
        operon_probability = combine_probabilities(
            scout_probability=operon_probability,
            model_probability=product_release.posterior_probability,
        )
        append_model_result(
            timeline,
            "product_release_model",
            product_release.posterior_probability,
        )
        evidence_items.append(
            "Product release model estimated latent readiness from release language, "
            "deadline pressure, and official-signal placeholders."
        )
    elif candidate.model_type == "macro_policy":
        macro_policy = build_macro_policy_model(candidate.market)
        model_confidence = macro_policy.confidence
        operon_probability = combine_probabilities(
            scout_probability=operon_probability,
            model_probability=macro_policy.posterior_probability,
        )
        append_model_result(timeline, "macro_policy_model", macro_policy.posterior_probability)
        evidence_items.append(
            "Macro policy model applied a Bayesian nowcasting shell using market consensus "
            "and macro-state placeholders."
        )
    elif candidate.model_type == "election_polling":
        election_polling = build_election_polling_model(candidate.market, observations)
        model_confidence = election_polling.confidence
        operon_probability = combine_probabilities(
            scout_probability=operon_probability,
            model_probability=election_polling.posterior_probability,
        )
        append_model_result(
            timeline,
            "election_polling_model",
            election_polling.posterior_probability,
        )
        evidence_items.append(
            "Election model used market consensus as a polling proxy until poll ingestion "
            "is connected."
        )
    elif candidate.model_type == "sports_outright":
        sports_outright = build_sports_outright_model(candidate.market, observations)
        model_confidence = sports_outright.confidence
        operon_probability = combine_probabilities(
            scout_probability=operon_probability,
            model_probability=sports_outright.posterior_probability,
        )
        append_model_result(
            timeline,
            "sports_outright_model",
            sports_outright.posterior_probability,
        )
        evidence_items.append(
            "Sports outright model used market consensus as a team-strength prior until "
            "standings, injuries, and odds feeds are connected."
        )
    elif candidate.model_type == "logic_consistency":
        logic_consistency = build_logic_consistency_model(candidate.market)
        model_confidence = logic_consistency.confidence
        operon_probability = combine_probabilities(
            scout_probability=operon_probability,
            model_probability=logic_consistency.posterior_probability,
        )
        append_model_result(
            timeline,
            "logic_consistency_model",
            logic_consistency.posterior_probability,
        )
        evidence_items.append(
            "Logic consistency model prepared cross-market checks but needs a related "
            "market set for full constraint analysis."
        )
    else:
        general_event = build_general_event_model(candidate.market)
        model_confidence = general_event.confidence
        operon_probability = combine_probabilities(
            scout_probability=operon_probability,
            model_probability=general_event.posterior_probability,
        )
        append_model_result(timeline, "general_event_model", general_event.posterior_probability)
        evidence_items.append(
            "General event model conservatively shrank the market prior toward 50%."
        )

    evidence_items.append("No external text evidence ledger entries have been collected yet.")
    consensus_guardrail = build_consensus_guardrail(
        candidate=candidate,
        operon_probability=operon_probability,
        model_confidence=model_confidence,
    )
    if consensus_guardrail.model_review_required:
        evidence_items.append(f"Consensus guardrail warning: {consensus_guardrail.warning}")

    event = EventDraft(
        id=str(uuid4()),
        market=candidate.market,
        model_type=candidate.model_type,
        market_probability=candidate.market.market_probability,
        operon_probability=operon_probability,
        evidence_items=evidence_items,
        probability_timeline=timeline,
        risk_flags=candidate.risk_flags,
        consensus_guardrail=consensus_guardrail,
        financial_barrier=financial_barrier,
        product_release=product_release,
        macro_policy=macro_policy,
        election_polling=election_polling,
        sports_outright=sports_outright,
        logic_consistency=logic_consistency,
        general_event=general_event,
    )
    EVENT_STORE[event.id] = event
    return event


def get_event(event_id: str) -> EventDraft | None:
    return EVENT_STORE.get(event_id)


async def run_financial_barrier_model(candidate: MarketCandidate):
    spec = parse_financial_barrier(candidate.market)
    if spec is None:
        return None

    service = CryptoPriceService()
    try:
        spot_price = await service.fetch_spot_price(spec.coingecko_id)
        historical_prices = await service.fetch_daily_prices(spec.coingecko_id)
        data_source = "CoinGecko simple price + market chart"
    except Exception:
        spot_price = spec.barrier_price * 0.10
        historical_prices = []
        data_source = "fallback synthetic spot/volatility"

    return build_financial_barrier_diagnostics(
        market=candidate.market,
        spot_price=spot_price,
        historical_prices=historical_prices,
        data_source=data_source,
    )


def combine_probabilities(scout_probability: float, model_probability: float) -> float:
    return 0.35 * scout_probability + 0.65 * model_probability


def append_model_result(
    timeline: list[dict[str, float | str]],
    label: str,
    probability: float,
) -> None:
    timeline.extend(
        [
            {"label": label, "probability": probability},
            {
                "label": "combined_posterior",
                "probability": combine_probabilities(
                    scout_probability=float(timeline[1]["probability"]),
                    model_probability=probability,
                ),
            },
        ]
    )
