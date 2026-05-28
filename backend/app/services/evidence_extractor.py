import json
import re

import httpx

from app.core.config import settings
from app.schemas.evidence import EvidenceDirection, EvidenceObservation
from app.schemas.market import Market


class EvidenceExtractor:
    async def extract_from_market_text(self, market: Market) -> list[EvidenceObservation]:
        text = f"{market.question}\n{market.description or ''}".strip()
        return await self.extract_from_text(text)

    async def extract_from_text(self, text: str) -> list[EvidenceObservation]:
        if settings.openai_api_key:
            try:
                return await self._extract_with_openai(text)
            except Exception:
                pass
        return self._extract_with_heuristics(text)

    async def _extract_with_openai(self, text: str) -> list[EvidenceObservation]:
        prompt = (
            "Extract structured forecasting evidence from this prediction market text. "
            "Return a compact JSON array. Each item must have claim, source_type, "
            "direction positive/negative/neutral, relevance 0-1, strength -1..1, "
            "novelty 0-1, ambiguity 0-1.\n\n"
            f"Market text:\n{text[:6000]}"
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
        items = parsed.get("evidence", parsed if isinstance(parsed, list) else [])
        return [EvidenceObservation(**item) for item in items[:12]]

    def _extract_with_heuristics(self, text: str) -> list[EvidenceObservation]:
        observations = []
        lower = text.lower()
        if any(term in lower for term in ["poll", "nomination", "primary", "election"]):
            observations.append(
                EvidenceObservation(
                    claim="Election market with pollable public opinion and candidate-field data.",
                    source_type="market_rule",
                    direction=EvidenceDirection.NEUTRAL,
                    relevance=0.8,
                    strength=0.0,
                    novelty=0.4,
                    ambiguity=0.35,
                )
            )
        if any(term in lower for term in ["endorsement", "endorsed", "fundraising"]):
            observations.append(
                EvidenceObservation(
                    claim=(
                        "Text mentions campaign-strength covariates such as endorsements "
                        "or fundraising."
                    ),
                    source_type="market_rule",
                    direction=EvidenceDirection.POSITIVE,
                    relevance=0.7,
                    strength=0.18,
                    novelty=0.5,
                    ambiguity=0.4,
                )
            )
        if any(term in lower for term in ["injury", "injured"]):
            observations.append(
                EvidenceObservation(
                    claim="Sports text mentions injury uncertainty.",
                    source_type="market_rule",
                    direction=EvidenceDirection.NEGATIVE,
                    relevance=0.75,
                    strength=-0.20,
                    novelty=0.5,
                    ambiguity=0.5,
                )
            )
        if any(term in lower for term in ["nba", "nfl", "nhl", "mlb", "finals", "stanley cup"]):
            observations.append(
                EvidenceObservation(
                    claim="Sports outright market where team strength, path, and injuries matter.",
                    source_type="market_rule",
                    direction=EvidenceDirection.NEUTRAL,
                    relevance=0.8,
                    strength=0.0,
                    novelty=0.4,
                    ambiguity=0.35,
                )
            )

        if not observations:
            title = re.sub(r"\s+", " ", text[:180])
            observations.append(
                EvidenceObservation(
                    claim=f"Market text parsed for baseline evidence: {title}",
                    source_type="market_rule",
                    direction=EvidenceDirection.NEUTRAL,
                    relevance=0.5,
                    strength=0.0,
                    novelty=0.3,
                    ambiguity=0.5,
                )
            )
        return observations
