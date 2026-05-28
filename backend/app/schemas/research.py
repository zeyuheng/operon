from pydantic import BaseModel, Field


class DataRequirement(BaseModel):
    name: str
    reason: str
    priority: str = "medium"


class SourcePlanItem(BaseModel):
    source_type: str
    query: str
    target_url: str | None = None
    variable: str
    reliability_prior: float = Field(default=0.5, ge=0, le=1)


class EventUnderstanding(BaseModel):
    event_type: str
    target_entity: str | None = None
    trigger_condition: str
    deadline: str | None = None
    resolution_source: list[str] = Field(default_factory=list)
    edge_cases: list[str] = Field(default_factory=list)
    model_type: str


class ResearchPlan(BaseModel):
    understanding: EventUnderstanding
    requirements: list[DataRequirement] = Field(default_factory=list)
    source_plan: list[SourcePlanItem] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    planner: str = "heuristic"
