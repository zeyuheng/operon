import json
import re

import httpx

from app.core.config import settings
from app.schemas.market import MarketCandidate
from app.schemas.research import (
    DataRequirement,
    EventUnderstanding,
    ResearchPlan,
    SourcePlanItem,
)


class ResearchPlannerService:
    async def build_plan(self, candidate: MarketCandidate) -> ResearchPlan:
        if settings.openai_api_key:
            try:
                return await self._build_with_openai(candidate)
            except Exception:
                pass
        return self._build_with_heuristics(candidate)

    async def _build_with_openai(self, candidate: MarketCandidate) -> ResearchPlan:
        market = candidate.market
        prompt = (
            "You are a research planner for a prediction-market analysis engine. "
            "Read the market title and resolution rules, then return JSON with: "
            "understanding {event_type,target_entity,trigger_condition,deadline,"
            "resolution_source,edge_cases,model_type}, requirements[], source_plan[], "
            "missing_data[]. source_plan items need source_type, query, target_url, "
            "variable, reliability_prior. Prefer official sources and APIs.\n\n"
            f"Model type: {candidate.model_type}\n"
            f"Question: {market.question}\n"
            f"End date: {market.end_date}\n"
            f"Rules: {market.description or ''}"
        )
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-5-mini",
                    "input": prompt,
                    "text": {"format": {"type": "json_object"}},
                },
            )
            response.raise_for_status()
            payload = response.json()
        raw_text = payload.get("output_text", "{}")
        parsed = json.loads(raw_text)
        parsed["planner"] = "openai"
        return ResearchPlan(**parsed)

    def _build_with_heuristics(self, candidate: MarketCandidate) -> ResearchPlan:
        market = candidate.market
        text = f"{market.question}\n{market.description or ''}"
        model_type = candidate.model_type
        entity = infer_entity(text, model_type)
        understanding = EventUnderstanding(
            event_type=model_type,
            target_entity=entity,
            trigger_condition=market.question,
            deadline=market.end_date,
            resolution_source=extract_resolution_sources(text),
            edge_cases=extract_edge_cases(text),
            model_type=model_type,
        )
        requirements = requirements_for_model(model_type)
        source_plan = source_plan_for_model(market.question, model_type, entity, text)
        return ResearchPlan(
            understanding=understanding,
            requirements=requirements,
            source_plan=source_plan,
            missing_data=missing_data_for_model(model_type),
            planner="heuristic",
        )


def infer_entity(text: str, model_type: str) -> str | None:
    clean = re.sub(r"\s+", " ", text)
    if model_type == "product_release":
        for entity in ["OpenAI", "Apple", "Rockstar", "Take-Two", "Tesla", "Google", "Microsoft"]:
            if entity.lower() in clean.lower():
                return entity
    if model_type == "macro_policy":
        if "fed" in clean.lower():
            return "Federal Reserve"
        if "cpi" in clean.lower():
            return "BLS CPI"
    if model_type == "financial_barrier":
        if "bitcoin" in clean.lower() or "btc" in clean.lower():
            return "BTC"
        if "ethereum" in clean.lower() or "eth" in clean.lower():
            return "ETH"
    match = re.search(r"Will ([A-Z][A-Za-z .'-]+?) ", clean)
    return match.group(1).strip() if match else None


def extract_resolution_sources(text: str) -> list[str]:
    sources = []
    for line in text.splitlines():
        if "resolution source" in line.lower() or "source for" in line.lower():
            sources.append(line.strip())
    urls = re.findall(r"https?://[^\s)]+", text)
    sources.extend(urls)
    return sources[:8]


def extract_edge_cases(text: str) -> list[str]:
    edge_cases = []
    lower = text.lower()
    if "50-50" in lower:
        edge_cases.append("50-50 fallback")
    if "cancel" in lower:
        edge_cases.append("cancellation clause")
    if "postpon" in lower:
        edge_cases.append("postponement clause")
    if "official" in lower:
        edge_cases.append("official-source dependency")
    return edge_cases


def requirements_for_model(model_type: str) -> list[DataRequirement]:
    mapping = {
        "product_release": [
            ("official_announcement", "Direct release confirmation controls resolution.", "high"),
            (
                "docs_or_product_availability",
                "Docs/API/app availability can confirm launch.",
                "high",
            ),
            ("credible_news", "Major reporting can reveal timing and ambiguity.", "medium"),
            (
                "deadline_and_edge_cases",
                "Release markets often hinge on definition and date.",
                "high",
            ),
        ],
        "macro_policy": [
            ("macro_indicators", "CPI, unemployment, rates and yields drive policy odds.", "high"),
            ("event_calendar", "Release/FOMC dates condition the event window.", "high"),
            ("official_guidance", "Fed/BLS/BEA statements affect interpretation.", "medium"),
        ],
        "election_polling": [
            ("polling_average", "Poll aggregation is the core observable.", "high"),
            (
                "candidate_field",
                "Entry/exit and coalition consolidation affect nominations.",
                "high",
            ),
            ("endorsements_fundraising", "Elite support and money shift primary odds.", "medium"),
        ],
        "sports_outright": [
            ("team_rating", "Elo/odds ratings estimate team strength.", "high"),
            ("injuries", "Key injuries can dominate playoff probabilities.", "high"),
            ("schedule_or_bracket_path", "Path difficulty changes outright probability.", "medium"),
        ],
        "financial_barrier": [
            (
                "specified_price_source",
                "Rules may specify exchange, pair, candle and high/close.",
                "high",
            ),
            ("spot_and_history", "Spot price and volatility drive barrier probability.", "high"),
            ("options_or_jump_risk", "Implied vol and tail risk improve estimates.", "medium"),
        ],
    }
    items = mapping.get(
        model_type,
        [("structured_evidence", "General model needs source-weighted observations.", "high")],
    )
    return [
        DataRequirement(name=name, reason=reason, priority=priority)
        for name, reason, priority in items
    ]


def source_plan_for_model(
    question: str,
    model_type: str,
    entity: str | None,
    text: str,
) -> list[SourcePlanItem]:
    query_entity = entity or question
    urls = re.findall(r"https?://[^\s)]+", text)
    plan = [
        SourcePlanItem(
            source_type="market_rule",
            query=question,
            variable="resolution_rules",
            reliability_prior=0.75,
        )
    ]
    for url in urls[:4]:
        plan.append(
            SourcePlanItem(
                source_type="direct_url",
                query=url,
                target_url=url,
                variable="resolution_source",
                reliability_prior=0.85,
            )
        )
    if model_type == "product_release":
        plan.extend(
            [
                SourcePlanItem(
                    source_type="web_search",
                    query=f"{query_entity} official release announcement {question}",
                    variable="official_announcement",
                    reliability_prior=0.80,
                ),
                SourcePlanItem(
                    source_type="web_search",
                    query=f"{query_entity} docs availability launch release",
                    variable="docs_or_product_availability",
                    reliability_prior=0.70,
                ),
            ]
        )
    elif model_type == "macro_policy":
        plan.extend(
            [
                SourcePlanItem(
                    source_type="api",
                    query="FRED CPI unemployment fed funds treasury yields",
                    variable="macro_indicators",
                    reliability_prior=0.90,
                ),
                SourcePlanItem(
                    source_type="web_search",
                    query=f"Federal Reserve official statement {question}",
                    variable="official_guidance",
                    reliability_prior=0.75,
                ),
            ]
        )
    elif model_type == "election_polling":
        plan.extend(
            [
                SourcePlanItem(
                    source_type="web_search",
                    query=f"{query_entity} polling nomination primary latest",
                    variable="polling_average",
                    reliability_prior=0.70,
                ),
                SourcePlanItem(
                    source_type="web_search",
                    query=f"{query_entity} endorsements fundraising campaign 2028",
                    variable="candidate_field",
                    reliability_prior=0.60,
                ),
            ]
        )
    elif model_type == "sports_outright":
        plan.extend(
            [
                SourcePlanItem(
                    source_type="web_search",
                    query=f"{query_entity} standings injuries odds power rating",
                    variable="team_rating",
                    reliability_prior=0.65,
                ),
                SourcePlanItem(
                    source_type="web_search",
                    query=f"{query_entity} injury report schedule playoff path",
                    variable="injuries",
                    reliability_prior=0.65,
                ),
            ]
        )
    return plan[:10]


def missing_data_for_model(model_type: str) -> list[str]:
    if model_type == "product_release":
        return ["live search API ranking", "source freshness timestamps", "duplicate clustering"]
    if model_type == "macro_policy":
        return ["economic calendar", "CME FedWatch", "live Fed statements parser"]
    if model_type == "election_polling":
        return ["pollster database", "fundraising data", "delegate simulation"]
    if model_type == "sports_outright":
        return ["team Elo feed", "injury feed", "bookmaker odds consensus"]
    return ["model-specific external data adapters"]
