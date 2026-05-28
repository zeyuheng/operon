from fastapi import APIRouter, HTTPException, Query

from app.core.market_filters import is_viable_market
from app.core.market_scoring import score_market
from app.core.model_router import route_model
from app.schemas.market import EventDraft, Market, MarketCandidate
from app.services.event_store import get_event, promote_candidate_to_event
from app.services.polymarket_gamma_service import PolymarketGammaService

router = APIRouter()


@router.post("/run", response_model=list[MarketCandidate])
async def run_market_scout(
    limit: int = Query(default=100, ge=1, le=500),
    top_n: int = Query(default=20, ge=1, le=100),
) -> list[MarketCandidate]:
    service = PolymarketGammaService()
    markets = await service.fetch_active_markets(limit=limit)
    candidates = [score_market(market) for market in markets if is_viable_market(market)]
    candidates.sort(key=lambda candidate: candidate.operon_score, reverse=True)
    return candidates[:top_n]


@router.get("/model-route")
def get_model_route(question: str) -> dict[str, str]:
    market = Market(id="ad-hoc", question=question)
    return {"model_type": route_model(market)}


@router.post("/promote-to-event", response_model=EventDraft)
async def promote_to_event(candidate: MarketCandidate) -> EventDraft:
    return await promote_candidate_to_event(candidate)


@router.get("/events/{event_id}", response_model=EventDraft)
def read_event(event_id: str) -> EventDraft:
    event = get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event
