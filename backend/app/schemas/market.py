from pydantic import BaseModel, Field


class Market(BaseModel):
    id: str
    question: str
    slug: str | None = None
    description: str | None = None
    category: str | None = None
    active: bool = True
    closed: bool = False
    volume: float | None = None
    liquidity: float | None = None
    market_probability: float | None = Field(default=None, ge=0, le=1)
    end_date: str | None = None


class MarketCandidate(BaseModel):
    market: Market
    operon_score: float = Field(ge=0, le=1)
    reason: str
    model_type: str
    category_guess: str
    risk_flags: list[str] = Field(default_factory=list)
    selected_reason: str
    resolution_score: float = Field(ge=0, le=1)
    evidence_score: float = Field(ge=0, le=1)
    liquidity_score: float = Field(ge=0, le=1)


class EventDraft(BaseModel):
    id: str
    market: Market
    model_type: str
    market_probability: float | None = Field(default=None, ge=0, le=1)
    operon_probability: float = Field(ge=0, le=1)
    evidence_items: list[str] = Field(default_factory=list)
    probability_timeline: list[dict[str, float | str]] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
