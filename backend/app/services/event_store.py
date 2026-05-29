import json
from pathlib import Path
from uuid import uuid4

from app.core.consensus_guardrail import build_consensus_guardrail
from app.core.financial_barrier_model import (
    build_financial_barrier_diagnostics,
    parse_financial_barrier,
)
from app.core.model_router import EventModelType
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
from app.services.election_data_service import ElectionDataService, ElectionDataSnapshot
from app.services.evidence_collector import EvidenceCollector
from app.services.evidence_extractor import EvidenceExtractor
from app.services.macro_data_service import MacroDataService, MacroSnapshot
from app.services.product_evidence_service import ProductEvidenceService
from app.services.research_planner_service import ResearchPlannerService
from app.services.sports_data_service import SportsDataService, SportsDataSnapshot

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
    election_snapshot = None
    sports_snapshot = None
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
        else:
            general_event = build_general_event_model(candidate.market)
            model_confidence = general_event.confidence
            operon_probability = combine_probabilities(
                scout_probability=operon_probability,
                model_probability=general_event.posterior_probability,
            )
            append_model_result(
                timeline,
                "general_event_model",
                general_event.posterior_probability,
            )
            evidence_items.append(
                "Financial barrier parser rejected this market; Operon fell back to "
                "the conservative general event model."
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
        election_snapshot = await fetch_election_snapshot(
            candidate,
            research_plan.understanding.target_entity,
        )
        election_polling = build_election_polling_model(
            candidate.market,
            observations,
            poll_samples=election_snapshot.polls,
        )
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
            "Election model loaded FiveThirtyEight public polling data when available; "
            "otherwise it falls back to market consensus."
        )
    elif candidate.model_type == "sports_outright":
        sports_snapshot = await fetch_sports_snapshot(candidate)
        sports_outright = build_sports_outright_model(
            candidate.market,
            observations,
            rating_samples=sports_snapshot.ratings,
        )
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
            "Sports outright model loaded ESPN public team records when available; "
            "otherwise it falls back to market-implied strength."
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
        election_snapshot=election_snapshot,
        sports_snapshot=sports_snapshot,
    )
    model_inputs = build_model_inputs(
        candidate=candidate,
        financial_barrier=financial_barrier,
        diagnostics=active_diagnostics,
        election_snapshot=election_snapshot,
        sports_snapshot=sports_snapshot,
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
    event = repair_invalid_financial_event(event)
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


async def fetch_election_snapshot(
    candidate: MarketCandidate,
    target_entity: str | None,
) -> ElectionDataSnapshot:
    try:
        return await ElectionDataService().fetch_snapshot(candidate.market, target_entity)
    except Exception:
        return ElectionDataSnapshot(
            status="fallback",
            note="FiveThirtyEight polling fetch failed; using market consensus proxy.",
        )


async def fetch_sports_snapshot(candidate: MarketCandidate) -> SportsDataSnapshot:
    try:
        return await SportsDataService().fetch_snapshot(candidate.market)
    except Exception:
        return SportsDataSnapshot(
            status="fallback",
            note="ESPN team-record fetch failed; using market-implied team strength.",
        )


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


def repair_invalid_financial_event(event: EventDraft) -> EventDraft:
    if event.model_type != EventModelType.FINANCIAL_BARRIER.value:
        return event
    if parse_financial_barrier(event.market) is not None:
        return event

    prior = event.market_probability if event.market_probability is not None else 0.5
    scout_probability = timeline_probability(event, "scout_adjusted") or prior
    product_like = any(
        term in event.market.question.lower()
        for term in ["airdrop", "mainnet", "testnet", "tge", "launch", "release"]
    )
    if product_like:
        diagnostics = build_product_release_model(event.market, [])
        model_type = EventModelType.PRODUCT_RELEASE.value
        update = {"product_release": diagnostics}
        timeline_label = "product_release_model"
    else:
        diagnostics = build_general_event_model(event.market)
        model_type = EventModelType.GENERAL_EVENT.value
        update = {"general_event": diagnostics}
        timeline_label = "general_event_model"

    operon_probability = combine_probabilities(
        scout_probability=scout_probability,
        model_probability=diagnostics.posterior_probability,
    )
    repaired = event.model_copy(
        update={
            "model_type": model_type,
            "operon_probability": operon_probability,
            "financial_barrier": None,
            "macro_policy": None,
            "election_polling": None,
            "sports_outright": None,
            "logic_consistency": None,
            "data_sources": [],
            "model_inputs": [],
            "probability_timeline": [
                {"label": "market_prior", "probability": prior},
                {"label": "scout_adjusted", "probability": scout_probability},
                {"label": timeline_label, "probability": diagnostics.posterior_probability},
                {"label": "combined_posterior", "probability": operon_probability},
            ],
            "evidence_items": event.evidence_items
            + [
                "Automatic repair: financial barrier parser rejected this market after "
                "stricter validation, so the event was rerouted conservatively."
            ],
            **update,
        }
    )
    EVENT_STORE[repaired.id] = repaired
    save_events()
    return repaired


def timeline_probability(event: EventDraft, label: str) -> float | None:
    for point in event.probability_timeline:
        if point.get("label") == label:
            value = point.get("probability")
            return float(value) if isinstance(value, int | float) else None
    return None


def build_data_sources(
    candidate: MarketCandidate,
    observations: list[EvidenceObservation],
    financial_barrier: FinancialBarrierDiagnostics | None,
    diagnostics: ModelDiagnostics | None,
    election_snapshot: ElectionDataSnapshot | None = None,
    sports_snapshot: SportsDataSnapshot | None = None,
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
        election_snapshot = election_snapshot or ElectionDataSnapshot(
            status="planned",
            note="Polling service was not run for this event.",
        )
        sources.extend(
            [
                DataSourceStatus(
                    name="FiveThirtyEight primary polls",
                    status=election_snapshot.status,
                    source_type="polling_api",
                    used_for=["weighted_polling_average", "pollster_quality", "recency_weight"],
                    variables=["poll_support", "sample_size", "pollster_quality", "field_date"],
                    reliability=0.75 if election_snapshot.polls else 0.25,
                    note=election_snapshot.note,
                ),
                DataSourceStatus(
                    name="FEC fundraising API",
                    status="key_required",
                    source_type="election_data",
                    used_for=["candidate_field_strength"],
                    variables=["fundraising", "endorsements", "candidate_entry_exit"],
                    reliability=0.0,
                    note="Requires a FEC API key and candidate/committee mapping.",
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
        sports_snapshot = sports_snapshot or SportsDataSnapshot(
            status="planned",
            note="Sports data service was not run for this event.",
        )
        sources.extend(
            [
                DataSourceStatus(
                    name="ESPN team records",
                    status=sports_snapshot.status,
                    source_type="sports_rating_api",
                    used_for=["team_strength_proxy", "field_ratings"],
                    variables=["win_percentage", "record_power_proxy"],
                    reliability=0.65 if sports_snapshot.ratings else 0.25,
                    note=sports_snapshot.note,
                ),
                DataSourceStatus(
                    name="Injury feed",
                    status="key_required",
                    source_type="sports_injury_api",
                    used_for=["injury_depth_uncertainty"],
                    variables=["player_status", "minutes_value", "return_timeline"],
                    reliability=0.0,
                    note="Requires a licensed injury or player availability feed.",
                ),
                DataSourceStatus(
                    name="Bookmaker odds consensus",
                    status="key_required",
                    source_type="odds_api",
                    used_for=["bookmaker_implied_power", "market_gap"],
                    variables=["title_odds", "series_odds", "implied_probability"],
                    reliability=0.0,
                    note="Requires an odds API key or licensed sportsbook odds feed.",
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
    election_snapshot: ElectionDataSnapshot | None = None,
    sports_snapshot: SportsDataSnapshot | None = None,
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
                    source=input_source_for(
                        candidate.model_type,
                        name,
                        election_snapshot=election_snapshot,
                        sports_snapshot=sports_snapshot,
                    ),
                    status=input_status_for(
                        candidate.model_type,
                        name,
                        election_snapshot=election_snapshot,
                        sports_snapshot=sports_snapshot,
                    ),
                    role=input_role_for(name),
                    note=input_note_for(candidate.model_type, name),
                )
            )
    return inputs


def input_source_for(
    model_type: str,
    name: str,
    election_snapshot: ElectionDataSnapshot | None = None,
    sports_snapshot: SportsDataSnapshot | None = None,
) -> str:
    if name == "market_consensus" or name == "market_expectation":
        return "Polymarket market price"
    if model_type == "macro_policy":
        return "FRED public CSV"
    if model_type == "product_release":
        return "Official/product web sources and market text"
    if model_type == "election_polling":
        if election_snapshot and election_snapshot.polls:
            return "FiveThirtyEight primary polls"
        return "Polymarket proxy until pollster database is connected"
    if model_type == "sports_outright":
        if sports_snapshot and sports_snapshot.ratings:
            return "ESPN team records"
        return "Polymarket proxy until sports data feeds are connected"
    if model_type == "logic_consistency":
        return "Planned related-market graph"
    return "Market text and generic evidence"


def input_status_for(
    model_type: str,
    name: str,
    election_snapshot: ElectionDataSnapshot | None = None,
    sports_snapshot: SportsDataSnapshot | None = None,
) -> str:
    if name in {"market_consensus", "market_expectation"}:
        return "connected"
    if model_type == "election_polling":
        return "connected" if election_snapshot and election_snapshot.polls else "proxy"
    if model_type == "sports_outright":
        return "connected" if sports_snapshot and sports_snapshot.ratings else "proxy"
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
