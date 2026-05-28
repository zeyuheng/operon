import json
from pathlib import Path
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
from app.schemas.evidence import EvidenceObservation
from app.schemas.market import (
    DataSourceStatus,
    EventDraft,
    FinancialBarrierDiagnostics,
    MarketCandidate,
    ModelDiagnostics,
    ModelInput,
)
from app.services.crypto_price_service import CryptoPriceService
from app.services.evidence_collector import EvidenceCollector
from app.services.evidence_extractor import EvidenceExtractor
from app.services.macro_data_service import MacroDataService, MacroSnapshot
from app.services.product_evidence_service import ProductEvidenceService
from app.services.research_planner_service import ResearchPlannerService

EVENT_STORE: dict[str, EventDraft] = {}
EVENT_STORE_PATH = Path(__file__).resolve().parents[2] / "data" / "events.json"


def load_events() -> None:
    if not EVENT_STORE_PATH.exists():
        return
    try:
        raw_events = json.loads(EVENT_STORE_PATH.read_text(encoding="utf-8"))
        EVENT_STORE.clear()
        for raw_event in raw_events:
            event = EventDraft.model_validate(raw_event)
            EVENT_STORE[event.id] = event
    except Exception:
        EVENT_STORE.clear()


def save_events() -> None:
    EVENT_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = [event.model_dump(mode="json") for event in EVENT_STORE.values()]
    EVENT_STORE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


load_events()


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
    research_plan = await ResearchPlannerService().build_plan(candidate)
    observations = await EvidenceExtractor().extract_from_market_text(candidate.market)
    collected_observations = await EvidenceCollector().collect(research_plan)
    observations.extend(collected_observations)
    evidence_items.append(
        "Research planner generated "
        f"{len(research_plan.requirements)} requirements and "
        f"{len(research_plan.source_plan)} source tasks."
    )
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
        product_observations = await ProductEvidenceService().fetch_evidence(candidate.market)
        observations.extend(product_observations)
        evidence_items.extend(
            f"Product evidence: {item.claim} "
            f"(source={item.source_type}, strength={item.strength:.2f})"
            for item in product_observations[:4]
        )
        product_release = build_product_release_model(candidate.market, observations)
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
        macro_snapshot = await fetch_macro_snapshot()
        macro_policy = build_macro_policy_model(candidate.market, macro_snapshot)
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

    active_diagnostics = (
        product_release
        or macro_policy
        or election_polling
        or sports_outright
        or logic_consistency
        or general_event
    )
    data_sources = build_data_sources(
        candidate=candidate,
        observations=observations,
        financial_barrier=financial_barrier,
        diagnostics=active_diagnostics,
    )
    model_inputs = build_model_inputs(
        candidate=candidate,
        financial_barrier=financial_barrier,
        diagnostics=active_diagnostics,
    )

    event = EventDraft(
        id=str(uuid4()),
        market=candidate.market,
        model_type=candidate.model_type,
        market_probability=candidate.market.market_probability,
        operon_probability=operon_probability,
        evidence_items=evidence_items,
        probability_timeline=timeline,
        data_sources=data_sources,
        model_inputs=model_inputs,
        risk_flags=candidate.risk_flags,
        research_plan=research_plan,
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
    save_events()
    return event


def get_event(event_id: str) -> EventDraft | None:
    event = EVENT_STORE.get(event_id)
    if event is None:
        return None
    if not event.data_sources or not event.model_inputs:
        event = hydrate_event_provenance(event)
        EVENT_STORE[event.id] = event
        save_events()
    return event


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


async def fetch_macro_snapshot() -> MacroSnapshot:
    try:
        return await MacroDataService().fetch_snapshot()
    except Exception:
        return MacroSnapshot(data_source="fallback empty macro snapshot")


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


def hydrate_event_provenance(event: EventDraft) -> EventDraft:
    candidate = MarketCandidate(
        market=event.market,
        operon_score=0.5,
        reason="backfilled from persisted event",
        model_type=event.model_type,
        category_guess=event.model_type,
        selected_reason="Backfilled provenance for an event created before source tracking.",
        resolution_score=0.5,
        evidence_score=0.5,
        liquidity_score=(
            event.consensus_guardrail.liquidity_weight
            if event.consensus_guardrail
            else 0.5
        ),
    )
    diagnostics = (
        event.product_release
        or event.macro_policy
        or event.election_polling
        or event.sports_outright
        or event.logic_consistency
        or event.general_event
    )
    return event.model_copy(
        update={
            "data_sources": build_data_sources(
                candidate=candidate,
                observations=[],
                financial_barrier=event.financial_barrier,
                diagnostics=diagnostics,
            ),
            "model_inputs": build_model_inputs(
                candidate=candidate,
                financial_barrier=event.financial_barrier,
                diagnostics=diagnostics,
            ),
        }
    )


def build_data_sources(
    candidate: MarketCandidate,
    observations: list[EvidenceObservation],
    financial_barrier: FinancialBarrierDiagnostics | None,
    diagnostics: ModelDiagnostics | None,
) -> list[DataSourceStatus]:
    sources = [
        DataSourceStatus(
            name="Polymarket market price",
            status="connected",
            source_type="market_api",
            used_for=["market_prior", "consensus_guardrail", "scout_score"],
            variables=["market_probability", "liquidity", "volume"],
            freshness="live at scout run",
            reliability=candidate.liquidity_score,
            note=(
                "This is the anchor for every model unless external evidence is "
                "strong enough to move it."
            ),
        ),
        DataSourceStatus(
            name="Polymarket market rules",
            status="connected" if candidate.market.description else "partial",
            source_type="market_metadata",
            used_for=["resolution_rules", "risk_flags", "research_plan"],
            variables=["description", "end_date", "resolution_clarity"],
            freshness="live at scout run",
            reliability=candidate.resolution_score,
            note="Used to understand payoff mechanics, deadlines, and edge cases.",
        ),
    ]
    if any(item.source_type == "source_failed" for item in observations):
        sources.append(
            DataSourceStatus(
                name="Web search evidence",
                status="failed",
                source_type="web_search",
                used_for=["evidence_collection"],
                variables=["news_snippets", "source_discovery"],
                reliability=0.2,
                note=(
                    "Search provider returned a bot challenge, so the page is not "
                    "treated as evidence."
                ),
            )
        )
    elif any(item.source_type == "web_search" for item in observations):
        sources.append(
            DataSourceStatus(
                name="Web search evidence",
                status="connected",
                source_type="web_search",
                used_for=["evidence_collection"],
                variables=["news_snippets", "source_discovery"],
                reliability=0.55,
                note=(
                    "Search snippets are parsed into weak evidence until "
                    "higher-quality APIs are connected."
                ),
            )
        )

    if candidate.model_type == "financial_barrier":
        connected = financial_barrier is not None and "CoinGecko" in financial_barrier.data_source
        sources.append(
            DataSourceStatus(
                name="CoinGecko price history",
                status="connected" if connected else "fallback",
                source_type="price_api",
                used_for=["spot_price", "historical_volatility", "monte_carlo_paths"],
                variables=["spot_price", "daily_prices", "annualized_volatility"],
                freshness="live at model run" if connected else None,
                reliability=0.85 if connected else 0.35,
                note=(
                    financial_barrier.data_source
                    if financial_barrier
                    else "Barrier parser did not run."
                ),
            )
        )
    elif candidate.model_type == "product_release":
        official_count = sum(1 for item in observations if item.source_type == "official")
        sources.append(
            DataSourceStatus(
                name="Official product sources",
                status="connected" if official_count else "partial",
                source_type="official_web",
                used_for=["official_signal_strength", "structured_evidence_weight"],
                variables=["official_announcement", "docs_or_product_availability"],
                reliability=0.8 if official_count else 0.45,
                note=(
                    f"{official_count} official observations extracted."
                    if official_count
                    else (
                        "Only planned/static official sources are configured; "
                        "live extraction may fail by site."
                    )
                ),
            )
        )
    elif candidate.model_type == "macro_policy":
        sources.append(
            DataSourceStatus(
                name="FRED public CSV",
                status="connected"
                if diagnostics and "fallback" not in " ".join(diagnostics.notes).lower()
                else "fallback",
                source_type="macro_api",
                used_for=["macro_indicators", "z_scores", "policy_reaction"],
                variables=[
                    "cpi_yoy",
                    "unemployment_rate",
                    "fed_funds_rate",
                    "2y_yield",
                    "10y_yield",
                ],
                freshness="latest FRED observations",
                reliability=0.85,
                note=(
                    "CPI, unemployment, Fed funds, and Treasury yields are pulled "
                    "from FRED public CSV."
                ),
            )
        )
    elif candidate.model_type == "election_polling":
        sources.extend(
            [
                DataSourceStatus(
                    name="Pollster database",
                    status="planned",
                    source_type="polling_api",
                    used_for=["weighted_polling_average", "pollster_quality", "recency_weight"],
                    variables=["poll_support", "sample_size", "pollster_quality", "field_date"],
                    reliability=0.0,
                    note=(
                        "Not connected yet. Current polling average falls back to "
                        "Polymarket consensus."
                    ),
                ),
                DataSourceStatus(
                    name="Fundraising and endorsements",
                    status="planned",
                    source_type="election_data",
                    used_for=["candidate_field_strength"],
                    variables=["fundraising", "endorsements", "candidate_entry_exit"],
                    reliability=0.0,
                    note="Not connected yet. Candidate-field adjustment is conservative.",
                ),
                DataSourceStatus(
                    name="Delegate simulation",
                    status="planned",
                    source_type="simulation_data",
                    used_for=["nomination_path"],
                    variables=["primary_calendar", "delegate_rules", "early_state_momentum"],
                    reliability=0.0,
                    note="Not connected yet. Nomination path risk is represented as uncertainty.",
                ),
            ]
        )
    elif candidate.model_type == "sports_outright":
        sources.extend(
            [
                DataSourceStatus(
                    name="Team Elo / power rating feed",
                    status="planned",
                    source_type="sports_rating_api",
                    used_for=["team_strength_proxy", "field_ratings"],
                    variables=["elo", "net_rating", "strength_of_schedule"],
                    reliability=0.0,
                    note="Not connected yet. Team strength currently uses market-implied proxy.",
                ),
                DataSourceStatus(
                    name="Injury feed",
                    status="planned",
                    source_type="sports_injury_api",
                    used_for=["injury_depth_uncertainty"],
                    variables=["player_status", "minutes_value", "return_timeline"],
                    reliability=0.0,
                    note="Not connected yet. Injury risk remains a broad uncertainty adjustment.",
                ),
                DataSourceStatus(
                    name="Bookmaker odds consensus",
                    status="planned",
                    source_type="odds_api",
                    used_for=["bookmaker_implied_power", "market_gap"],
                    variables=["title_odds", "series_odds", "implied_probability"],
                    reliability=0.0,
                    note="Not connected yet. Polymarket is the only market-pricing input.",
                ),
            ]
        )
    elif candidate.model_type == "logic_consistency":
        sources.append(
            DataSourceStatus(
                name="Related Polymarket graph",
                status="planned",
                source_type="market_graph",
                used_for=["monotonicity", "mutual_exclusivity", "frechet_bounds"],
                variables=["related_markets", "thresholds", "deadlines"],
                reliability=0.0,
                note="Not connected yet. Single-market logic checks remain a shell.",
            )
        )
    return sources


def build_model_inputs(
    candidate: MarketCandidate,
    financial_barrier: FinancialBarrierDiagnostics | None,
    diagnostics: ModelDiagnostics | None,
) -> list[ModelInput]:
    inputs = [
        ModelInput(
            name="market_probability",
            value=(
                candidate.market.market_probability
                if candidate.market.market_probability is not None
                else 0.5
            ),
            source="Polymarket market price",
            status="connected",
            role="prior",
            note="The base probability before model-specific updates.",
        ),
        ModelInput(
            name="liquidity_score",
            value=candidate.liquidity_score,
            source="Polymarket market metadata",
            status="connected",
            role="confidence_weight",
            note="Controls how much respect the consensus guardrail gives the market.",
        ),
    ]
    if financial_barrier:
        inputs.extend(
            [
                ModelInput(
                    name="spot_price",
                    value=financial_barrier.spot_price,
                    source=financial_barrier.data_source,
                    status=(
                        "connected"
                        if "CoinGecko" in financial_barrier.data_source
                        else "fallback"
                    ),
                    role="simulation_start",
                    note="Starting value for simulated asset paths.",
                ),
                ModelInput(
                    name="annualized_volatility",
                    value=financial_barrier.annualized_volatility,
                    source=financial_barrier.data_source,
                    status=(
                        "connected"
                        if "CoinGecko" in financial_barrier.data_source
                        else "fallback"
                    ),
                    role="simulation_noise",
                    note="Estimated from recent daily price history.",
                ),
                ModelInput(
                    name="payoff_rule",
                    value=financial_barrier.rule_type,
                    source="Polymarket market rules",
                    status="connected",
                    role="payoff_adapter",
                    note=financial_barrier.valuation_formula,
                ),
            ]
        )
    if diagnostics:
        for name, value in diagnostics.state_scores.items():
            inputs.append(
                ModelInput(
                    name=name,
                    value=value,
                    source=input_source_for(candidate.model_type, name),
                    status=input_status_for(candidate.model_type, name),
                    role=input_role_for(name),
                    note=input_note_for(candidate.model_type, name),
                )
            )
    return inputs


def input_source_for(model_type: str, name: str) -> str:
    if name == "market_consensus" or name == "market_expectation":
        return "Polymarket market price"
    if model_type == "macro_policy":
        return "FRED public CSV"
    if model_type == "product_release":
        return "Official/product web sources and market text"
    if model_type == "election_polling":
        return "Polymarket proxy until pollster database is connected"
    if model_type == "sports_outright":
        return "Polymarket proxy until sports data feeds are connected"
    if model_type == "logic_consistency":
        return "Planned related-market graph"
    return "Market text and generic evidence"


def input_status_for(model_type: str, name: str) -> str:
    if name in {"market_consensus", "market_expectation"}:
        return "connected"
    if model_type in {"election_polling", "sports_outright"}:
        return "proxy"
    if model_type == "logic_consistency":
        return "planned"
    return "connected"


def input_role_for(name: str) -> str:
    if "confidence" in name or "quality" in name or "clarity" in name:
        return "confidence"
    if "risk" in name or "uncertainty" in name or "variance" in name:
        return "uncertainty"
    if "probability" in name or "average" in name or "consensus" in name:
        return "probability_update"
    return "state_variable"


def input_note_for(model_type: str, name: str) -> str:
    if model_type == "election_polling" and name in {
        "weighted_polling_average",
        "pollster_quality",
        "recency_weight",
    }:
        return "Proxy value: no real poll feed is connected yet."
    if model_type == "sports_outright" and name in {
        "team_strength_proxy",
        "monte_carlo_title_probability",
    }:
        return "Proxy value: no team Elo, injury, or odds consensus feed is connected yet."
    return "Used directly by the model's probability update or confidence band."
