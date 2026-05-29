import re
from dataclasses import dataclass, field

import httpx

from app.schemas.evidence import SportsRatingSample
from app.schemas.market import Market

ESPN_NBA_STANDINGS_URL = (
    "https://site.web.api.espn.com/apis/v2/sports/basketball/nba/standings"
)

NBA_TEAM_ALIASES = {
    "oklahoma city thunder": "okc",
    "thunder": "okc",
    "knicks": "ny",
    "new york knicks": "ny",
    "celtics": "bos",
    "boston celtics": "bos",
    "lakers": "lal",
    "los angeles lakers": "lal",
    "warriors": "gs",
    "golden state warriors": "gs",
    "nuggets": "den",
    "denver nuggets": "den",
    "mavericks": "dal",
    "dallas mavericks": "dal",
    "timberwolves": "min",
    "minnesota timberwolves": "min",
    "bucks": "mil",
    "milwaukee bucks": "mil",
    "76ers": "phi",
    "philadelphia 76ers": "phi",
    "heat": "mia",
    "miami heat": "mia",
}


@dataclass(frozen=True)
class SportsDataSnapshot:
    ratings: list[SportsRatingSample] = field(default_factory=list)
    data_source: str = "ESPN public NBA standings endpoint"
    status: str = "connected"
    note: str = "Team records fetched and converted into a simple power proxy."


class SportsDataService:
    async def fetch_snapshot(self, market: Market) -> SportsDataSnapshot:
        target_alias = infer_nba_team_alias(market.question)
        if not target_alias:
            return SportsDataSnapshot(
                status="fallback",
                note="No supported NBA team was recognized in the market title.",
            )

        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.get(ESPN_NBA_STANDINGS_URL)
            response.raise_for_status()
        payload = response.json()
        ratings = parse_espn_standings_ratings(payload, target_alias)
        if not ratings:
            return SportsDataSnapshot(
                status="connected_empty",
                note="ESPN standings endpoint responded, but no team record ratings were parsed.",
            )
        return SportsDataSnapshot(ratings=ratings)


def infer_nba_team_alias(question: str) -> str | None:
    normalized = normalize(question)
    for name, alias in NBA_TEAM_ALIASES.items():
        if name in normalized:
            return alias
    return None


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def parse_espn_standings_ratings(payload: dict, target_alias: str) -> list[SportsRatingSample]:
    teams = []
    for child in payload.get("children", []):
        teams.extend(child.get("standings", {}).get("entries", []))
    parsed = []
    for entry in teams:
        team = entry.get("team", {})
        abbreviation = str(team.get("abbreviation", "")).lower()
        display_name = team.get("displayName") or team.get("name") or abbreviation
        win_pct = extract_win_pct(entry)
        if win_pct is None:
            continue
        parsed.append(
            SportsRatingSample(
                team=display_name,
                rating=max(0.02, min(0.95, win_pct)),
                source_weight=0.65 if abbreviation == target_alias else 0.45,
                source="espn_team_record",
            )
        )
    parsed.sort(key=lambda sample: sample.team.lower() != target_alias)
    target = [
        sample
        for sample in parsed
        if any(
            alias == target_alias and name in normalize(sample.team)
            for name, alias in NBA_TEAM_ALIASES.items()
        )
    ]
    if not target:
        target = [sample for sample in parsed if target_alias in normalize(sample.team)]
    if not target:
        return []
    others = [sample for sample in parsed if sample.team != target[0].team]
    others.sort(key=lambda sample: sample.rating, reverse=True)
    return target[:1] + others[:15]


def extract_win_pct(entry: dict) -> float | None:
    stats = entry.get("stats", [])
    pct = stat_value(stats, {"winPercent", "winpct", "winPercentage"})
    if pct is not None:
        return pct
    wins = stat_value(stats, {"wins"})
    losses = stat_value(stats, {"losses"})
    if wins is not None and losses is not None and wins + losses > 0:
        return wins / (wins + losses)
    return None


def stat_value(stats: list[dict], names: set[str]) -> float | None:
    for stat in stats:
        name = str(stat.get("name") or stat.get("abbreviation") or "").lower()
        if name in {item.lower() for item in names}:
            try:
                return float(stat.get("value"))
            except (TypeError, ValueError):
                return None
    return None
