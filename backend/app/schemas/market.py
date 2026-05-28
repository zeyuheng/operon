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
    market_structure_type: str = "forecasting_market"
    primary_edge_source: str = "event_forecast"
    scout_penalty: float = Field(default=0.0, ge=0, le=1)


class FinancialBarrierDiagnostics(BaseModel):
    asset: str
    spot_price: float
    barrier_price: float
    deadline: str | None = None
    days_remaining: float
    annualized_volatility: float
    simulations: int
    steps: int
    hit_probability: float = Field(ge=0, le=1)
    expected_contract_value: float = Field(ge=0, le=1)
    fallback_probability: float = Field(default=0.0, ge=0, le=1)
    rule_type: str = "simple_binary_barrier"
    rule_summary: str
    valuation_formula: str
    drift: float
    data_source: str
    notes: list[str] = Field(default_factory=list)


class ModelDiagnostics(BaseModel):
    model_name: str
    posterior_probability: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    uncertainty_interval: list[float] = Field(min_length=2, max_length=2)
    state_scores: dict[str, float] = Field(default_factory=dict)
    key_drivers: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class EventDraft(BaseModel):
    id: str
    market: Market
    model_type: str
    market_probability: float | None = Field(default=None, ge=0, le=1)
    operon_probability: float = Field(ge=0, le=1)
    evidence_items: list[str] = Field(default_factory=list)
    probability_timeline: list[dict[str, float | str]] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    financial_barrier: FinancialBarrierDiagnostics | None = None
    product_release: ModelDiagnostics | None = None
    macro_policy: ModelDiagnostics | None = None
    election_polling: ModelDiagnostics | None = None
    sports_outright: ModelDiagnostics | None = None
    logic_consistency: ModelDiagnostics | None = None
    general_event: ModelDiagnostics | None = None
