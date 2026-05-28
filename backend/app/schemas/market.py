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
