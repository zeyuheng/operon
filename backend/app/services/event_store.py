from uuid import uuid4

from app.core.financial_barrier_model import (
    build_financial_barrier_diagnostics,
    parse_financial_barrier,
)
from app.core.probability_engine import update_log_odds
from app.schemas.market import EventDraft, MarketCandidate
from app.services.crypto_price_service import CryptoPriceService

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
    financial_barrier = None
    if candidate.model_type == "financial_barrier":
        financial_barrier = await run_financial_barrier_model(candidate)
        if financial_barrier is not None:
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

    evidence_items.append("No external text evidence ledger entries have been collected yet.")
    event = EventDraft(
        id=str(uuid4()),
        market=candidate.market,
        model_type=candidate.model_type,
        market_probability=candidate.market.market_probability,
        operon_probability=operon_probability,
        evidence_items=evidence_items,
        probability_timeline=timeline,
        risk_flags=candidate.risk_flags,
        financial_barrier=financial_barrier,
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
