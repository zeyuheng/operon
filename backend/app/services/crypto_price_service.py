import httpx


class CryptoPriceService:
    def __init__(self, base_url: str = "https://api.coingecko.com/api/v3") -> None:
        self.base_url = base_url.rstrip("/")

    async def fetch_spot_price(self, coingecko_id: str) -> float:
        params = {"ids": coingecko_id, "vs_currencies": "usd"}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{self.base_url}/simple/price", params=params)
            response.raise_for_status()
            payload = response.json()
        return float(payload[coingecko_id]["usd"])

    async def fetch_daily_prices(self, coingecko_id: str, days: int = 90) -> list[float]:
        params = {"vs_currency": "usd", "days": days, "interval": "daily"}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{self.base_url}/coins/{coingecko_id}/market_chart",
                params=params,
            )
            response.raise_for_status()
            payload = response.json()
        return [float(price) for _timestamp, price in payload.get("prices", [])]
