import json

import httpx

from app.core.config import settings
from app.schemas.market import Market


class PolymarketGammaService:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.polymarket_gamma_base_url).rstrip("/")

    async def fetch_active_markets(self, limit: int = 100) -> list[Market]:
        params = {"active": "true", "closed": "false", "limit": limit}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{self.base_url}/markets", params=params)
            response.raise_for_status()
            payload = response.json()
        return [self._to_market(item) for item in payload]

    def _to_market(self, item: dict) -> Market:
        probability = self._extract_probability(item)
        return Market(
            id=str(item.get("id") or item.get("conditionId") or item.get("slug")),
            question=item.get("question") or item.get("title") or "Untitled market",
            slug=item.get("slug"),
            description=item.get("description"),
            category=item.get("category"),
            active=bool(item.get("active", True)),
            closed=bool(item.get("closed", False)),
            volume=self._to_float(item.get("volume") or item.get("volumeNum")),
            liquidity=self._to_float(item.get("liquidity") or item.get("liquidityNum")),
            market_probability=probability,
            end_date=item.get("endDate") or item.get("end_date_iso"),
        )

    def _extract_probability(self, item: dict) -> float | None:
        raw_prices = item.get("outcomePrices")
        if isinstance(raw_prices, str):
            try:
                raw_prices = json.loads(raw_prices)
            except json.JSONDecodeError:
                return None
        if isinstance(raw_prices, list) and raw_prices:
            return self._to_float(raw_prices[0])
        return None

    def _to_float(self, value: object) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
