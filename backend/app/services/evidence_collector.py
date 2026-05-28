import re
from urllib.parse import quote_plus

import httpx

from app.schemas.evidence import EvidenceDirection, EvidenceObservation
from app.schemas.research import ResearchPlan, SourcePlanItem
from app.services.evidence_extractor import EvidenceExtractor


class EvidenceCollector:
    async def collect(self, plan: ResearchPlan) -> list[EvidenceObservation]:
        observations: list[EvidenceObservation] = []
        extractor = EvidenceExtractor()
        for item in plan.source_plan:
            if item.source_type == "market_rule":
                observations.append(self._market_rule_observation(item))
            elif item.source_type == "direct_url" and item.target_url:
                observations.extend(await self._collect_direct_url(item, extractor))
            elif item.source_type == "web_search":
                observations.extend(await self._collect_web_search(item, extractor))
            elif item.source_type == "api":
                observations.append(
                    EvidenceObservation(
                        claim=f"API requirement registered: {item.query}",
                        source_type="api",
                        direction=EvidenceDirection.NEUTRAL,
                        relevance=0.65,
                        strength=0.0,
                        novelty=0.5,
                        ambiguity=0.25,
                    )
                )
        return observations[:20]

    def _market_rule_observation(self, item: SourcePlanItem) -> EvidenceObservation:
        return EvidenceObservation(
            claim=f"Market rule requirement: {item.variable}",
            source_type="market_rule",
            direction=EvidenceDirection.NEUTRAL,
            relevance=0.65,
            strength=0.0,
            novelty=0.35,
            ambiguity=0.35,
        )

    async def _collect_direct_url(
        self,
        item: SourcePlanItem,
        extractor: EvidenceExtractor,
    ) -> list[EvidenceObservation]:
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                response = await client.get(item.target_url)
                response.raise_for_status()
            text = clean_html(response.text)
        except Exception:
            return []
        observations = await extractor.extract_from_text(text[:6_000])
        for observation in observations:
            observation.source_url = item.target_url
            observation.source_type = item.source_type
        return observations[:4]

    async def _collect_web_search(
        self,
        item: SourcePlanItem,
        extractor: EvidenceExtractor,
    ) -> list[EvidenceObservation]:
        try:
            url = f"https://duckduckgo.com/html/?q={quote_plus(item.query)}"
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                response.raise_for_status()
            text = clean_html(response.text)
        except Exception:
            return [
                EvidenceObservation(
                    claim=f"Search planned but not fetched: {item.query}",
                    source_type="search_plan",
                    direction=EvidenceDirection.NEUTRAL,
                    relevance=0.45,
                    strength=0.0,
                    novelty=0.3,
                    ambiguity=0.6,
                )
            ]

        snippets = text[:4_000]
        if is_blocked_search_text(snippets):
            return [
                EvidenceObservation(
                    claim=f"Search blocked by provider challenge: {item.query}",
                    source_type="source_failed",
                    direction=EvidenceDirection.NEUTRAL,
                    relevance=0.20,
                    strength=0.0,
                    novelty=0.1,
                    ambiguity=0.9,
                )
            ]
        observations = await extractor.extract_from_text(snippets)
        for observation in observations:
            observation.source_type = "web_search"
            observation.source_url = url
        return observations[:4]


def clean_html(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def is_blocked_search_text(text: str) -> bool:
    normalized = text.lower()
    blocked_markers = [
        "please complete the following challenge",
        "confirm this search was made by a human",
        "unfortunately, bots use duckduckgo too",
        "captcha",
        "access denied",
        "unusual traffic",
    ]
    return any(marker in normalized for marker in blocked_markers)
