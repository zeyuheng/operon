from enum import StrEnum

from pydantic import BaseModel, Field


class EvidenceDirection(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class EvidenceObservation(BaseModel):
    claim: str
    source_url: str | None = None
    source_type: str = "unknown"
    direction: EvidenceDirection = EvidenceDirection.NEUTRAL
    relevance: float = Field(default=0.5, ge=0, le=1)
    strength: float = Field(default=0.0, ge=-1, le=1)
    novelty: float = Field(default=0.5, ge=0, le=1)
    ambiguity: float = Field(default=0.5, ge=0, le=1)


class PollSample(BaseModel):
    candidate: str
    support: float = Field(ge=0, le=1)
    sample_size: int = Field(default=1_000, ge=1)
    pollster_quality: float = Field(default=0.7, ge=0, le=1)
    age_days: float = Field(default=30, ge=0)
    source: str = "derived"


class SportsRatingSample(BaseModel):
    team: str
    rating: float
    source_weight: float = Field(default=0.5, ge=0, le=1)
    source: str = "derived"
