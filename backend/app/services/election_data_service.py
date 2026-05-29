import csv
import io
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx

from app.schemas.evidence import PollSample
from app.schemas.market import Market

FIVETHIRTYEIGHT_PRIMARY_POLLS_URL = (
    "https://projects.fivethirtyeight.com/polls-page/data/president_primary_polls.csv"
)


@dataclass(frozen=True)
class ElectionDataSnapshot:
    polls: list[PollSample] = field(default_factory=list)
    data_source: str = "FiveThirtyEight president_primary_polls.csv"
    status: str = "connected"
    note: str = "Public polling CSV fetched and parsed."


class ElectionDataService:
    async def fetch_snapshot(
        self,
        market: Market,
        target_entity: str | None,
    ) -> ElectionDataSnapshot:
        if not target_entity:
            return ElectionDataSnapshot(
                status="fallback",
                note="No target candidate extracted, so poll ingestion was skipped.",
            )

        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.get(FIVETHIRTYEIGHT_PRIMARY_POLLS_URL)
            response.raise_for_status()

        polls = self._parse_primary_polls(response.text, target_entity)
        if not polls:
            return ElectionDataSnapshot(
                polls=[],
                status="connected_empty",
                note=f"FiveThirtyEight CSV fetched, but no rows matched {target_entity}.",
            )
        return ElectionDataSnapshot(
            polls=polls[:30],
            note=f"FiveThirtyEight CSV matched {len(polls)} rows for {target_entity}.",
        )

    def _parse_primary_polls(self, csv_text: str, target_entity: str) -> list[PollSample]:
        target_tokens = normalize_name(target_entity)
        rows = csv.DictReader(io.StringIO(csv_text))
        samples = []
        for row in rows:
            candidate = first_present(row, ["candidate_name", "answer", "choice", "candidate"])
            if not candidate or target_tokens not in normalize_name(candidate):
                continue
            support = parse_percent(first_present(row, ["pct", "support", "value", "percent"]))
            if support is None:
                continue
            sample_size = parse_int(
                first_present(row, ["sample_size", "samplesize", "population_size"])
            )
            end_date = first_present(row, ["end_date", "enddate", "last_date"])
            samples.append(
                PollSample(
                    candidate=candidate,
                    support=support,
                    sample_size=sample_size or 800,
                    pollster_quality=pollster_quality(row),
                    age_days=age_days(end_date),
                    source="fivethirtyeight_primary_polls",
                )
            )
        samples.sort(key=lambda sample: sample.age_days)
        return samples


def first_present(row: dict[str, str | None], keys: list[str]) -> str | None:
    normalized = {key.lower(): value for key, value in row.items() if key}
    for key in keys:
        value = normalized.get(key.lower())
        if value not in {None, ""}:
            return value
    return None


def normalize_name(value: str) -> str:
    return " ".join(value.lower().replace(".", "").split())


def parse_percent(value: str | None) -> float | None:
    if not value:
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    if parsed > 1:
        parsed /= 100
    return max(0.0, min(1.0, parsed))


def parse_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        parsed = int(float(value.replace(",", "")))
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def age_days(date_text: str | None) -> float:
    if not date_text:
        return 60.0
    for fmt in ("%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(date_text, fmt).replace(tzinfo=UTC)
            return max(0.0, (datetime.now(UTC) - parsed).total_seconds() / 86_400)
        except ValueError:
            continue
    return 60.0


def pollster_quality(row: dict[str, str | None]) -> float:
    numeric_grade = first_present(row, ["numeric_grade", "pollster_rating", "pollster_score"])
    if numeric_grade:
        try:
            return max(0.35, min(0.95, 0.45 + float(numeric_grade) / 4))
        except ValueError:
            pass
    sample_size = parse_int(first_present(row, ["sample_size", "samplesize", "population_size"]))
    if sample_size:
        return max(0.45, min(0.8, 0.5 + math.sqrt(sample_size) / 200))
    return 0.60
