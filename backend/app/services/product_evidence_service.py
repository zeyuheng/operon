import re

import httpx

from app.schemas.evidence import EvidenceDirection, EvidenceObservation
from app.schemas.market import Market
from app.services.evidence_extractor import EvidenceExtractor

PRODUCT_SOURCE_MAP = {
    "openai": [
        "https://openai.com/news/",
        "https://help.openai.com/en/",
    ],
    "apple": [
        "https://www.apple.com/newsroom/",
    ],
    "gta": [
        "https://www.rockstargames.com/VI",
        "https://www.rockstargames.com/newswire",
        "https://www.take2games.com/ir/news",
    ],
    "rockstar": [
        "https://www.rockstargames.com/VI",
        "https://www.rockstargames.com/newswire",
    ],
}


class ProductEvidenceService:
    async def fetch_evidence(self, market: Market) -> list[EvidenceObservation]:
        urls = self._source_urls(market)
        observations: list[EvidenceObservation] = []
        extractor = EvidenceExtractor()
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            for url in urls[:4]:
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    text = self._clean_html(response.text)
                except Exception:
                    continue
                extracted = await extractor.extract_from_text(text[:6_000])
                for item in extracted[:3]:
                    item.source_url = url
                    item.source_type = self._source_type(url)
                    observations.append(item)

        if observations:
            return observations
        return self._fallback_observations(market)

    def _source_urls(self, market: Market) -> list[str]:
        text = f"{market.question} {market.description or ''}".lower()
        urls = []
        for keyword, source_urls in PRODUCT_SOURCE_MAP.items():
            if keyword in text:
                urls.extend(source_urls)
        return list(dict.fromkeys(urls))

    def _source_type(self, url: str) -> str:
        if any(domain in url for domain in ["openai.com", "apple.com", "rockstargames.com"]):
            return "official"
        if "take2games.com" in url:
            return "official"
        return "news"

    def _clean_html(self, html: str) -> str:
        text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
        text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _fallback_observations(self, market: Market) -> list[EvidenceObservation]:
        text = f"{market.question} {market.description or ''}".lower()
        observations = []
        if "official" in text or "announced" in text:
            observations.append(
                EvidenceObservation(
                    claim="Market text references official announcement or official sources.",
                    source_type="market_rule",
                    direction=EvidenceDirection.POSITIVE,
                    relevance=0.75,
                    strength=0.18,
                    novelty=0.45,
                    ambiguity=0.35,
                )
            )
        observations.append(
            EvidenceObservation(
                claim="No external product-release sources were fetched; using market text only.",
                source_type="market_rule",
                direction=EvidenceDirection.NEUTRAL,
                relevance=0.45,
                strength=0.0,
                novelty=0.25,
                ambiguity=0.6,
            )
        )
        return observations
