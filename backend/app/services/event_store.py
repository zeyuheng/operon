from uuid import uuid4

from app.core.probability_engine import update_log_odds
from app.schemas.market import EventDraft, MarketCandidate

EVENT_STORE: dict[str, EventDraft] = {}


def promote_candidate_to_event(candidate: MarketCandidate) -> EventDraft:
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
    event = EventDraft(
        id=str(uuid4()),
        market=candidate.market,
        model_type=candidate.model_type,
        market_probability=candidate.market.market_probability,
        operon_probability=operon_probability,
        evidence_items=[
            candidate.selected_reason,
            f"Initial scout scores: {candidate.reason}",
            "No external evidence ledger entries have been collected yet.",
        ],
        probability_timeline=[
            {"label": "market_prior", "probability": prior},
            {"label": "scout_adjusted", "probability": operon_probability},
        ],
        risk_flags=candidate.risk_flags,
    )
    EVENT_STORE[event.id] = event
    return event


def get_event(event_id: str) -> EventDraft | None:
    return EVENT_STORE.get(event_id)
