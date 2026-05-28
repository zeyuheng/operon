import csv
import io
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class MacroSnapshot:
    cpi_yoy: float | None = None
    unemployment_rate: float | None = None
    fed_funds_rate: float | None = None
    two_year_yield: float | None = None
    ten_year_yield: float | None = None
    data_source: str = "FRED public CSV"


class MacroDataService:
    async def fetch_snapshot(self) -> MacroSnapshot:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            cpi = await self._fetch_fred_series(client, "CPIAUCSL")
            unemployment = await self._fetch_fred_series(client, "UNRATE")
            fed_funds = await self._fetch_fred_series(client, "FEDFUNDS")
            two_year = await self._fetch_fred_series(client, "DGS2")
            ten_year = await self._fetch_fred_series(client, "DGS10")

        return MacroSnapshot(
            cpi_yoy=self._yoy(cpi),
            unemployment_rate=self._latest(unemployment),
            fed_funds_rate=self._latest(fed_funds),
            two_year_yield=self._latest(two_year),
            ten_year_yield=self._latest(ten_year),
        )

    async def _fetch_fred_series(
        self,
        client: httpx.AsyncClient,
        series_id: str,
    ) -> list[tuple[str, float]]:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        response = await client.get(url)
        response.raise_for_status()
        rows = csv.DictReader(io.StringIO(response.text))
        values = []
        for row in rows:
            raw_value = row.get(series_id)
            if raw_value in {None, "."}:
                continue
            try:
                values.append((row["observation_date"], float(raw_value)))
            except ValueError:
                continue
        return values

    def _latest(self, values: list[tuple[str, float]]) -> float | None:
        return values[-1][1] if values else None

    def _yoy(self, values: list[tuple[str, float]]) -> float | None:
        if len(values) < 13:
            return None
        latest = values[-1][1]
        previous = values[-13][1]
        if previous == 0:
            return None
        return (latest / previous - 1) * 100
