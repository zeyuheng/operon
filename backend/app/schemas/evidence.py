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
