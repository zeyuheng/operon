import math
import random
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.resolution_adapters import expected_contract_value
from app.core.rule_parser import parse_market_rule
from app.schemas.market import FinancialBarrierDiagnostics, Market

ASSET_ALIASES = {
    "bitcoin": ("bitcoin", "BTC"),
    "btc": ("bitcoin", "BTC"),
    "ethereum": ("ethereum", "ETH"),
    "eth": ("ethereum", "ETH"),
}

PRICE_PATTERN = re.compile(
    r"(?:(?:hit|reach|touch|above|over|exceed|break|cross|to|at)\s+)"
    r"\$?\s*([\d,]+(?:\.\d+)?)\s*(m|million|k|thousand)?\b"
    r"|"
    r"\$\s*([\d,]+(?:\.\d+)?)\s*(m|million|k|thousand)?\b",
    re.IGNORECASE,
)

NON_PRICE_EVENT_TERMS = {
    "airdrop",
    "token generation",
    "tge",
    "mainnet",
    "testnet",
    "launch",
    "release",
    "listing",
    "list on",
    "perform",
    "claim",
}


@dataclass(frozen=True)
class BarrierSpec:
    coingecko_id: str
    asset_symbol: str
    barrier_price: float


def parse_financial_barrier(market: Market) -> BarrierSpec | None:
    text = f"{market.question} {market.description or ''}".lower()
    if any(term in text for term in NON_PRICE_EVENT_TERMS) and not has_price_language(text):
        return None

    asset = next(
        (value for key, value in ASSET_ALIASES.items() if has_asset_token(text, key)),
        None,
    )
    if asset is None:
        return None

    price_match = PRICE_PATTERN.search(market.question.lower())
    if price_match is None:
        return None

    raw_value = float((price_match.group(1) or price_match.group(3)).replace(",", ""))
    suffix = price_match.group(2) or price_match.group(4)
    if suffix is None and raw_value < 100:
        return None
    multiplier = 1.0
    if suffix in {"m", "million"}:
        multiplier = 1_000_000.0
    elif suffix in {"k", "thousand"}:
        multiplier = 1_000.0

    coingecko_id, symbol = asset
    return BarrierSpec(
        coingecko_id=coingecko_id,
        asset_symbol=symbol,
        barrier_price=raw_value * multiplier,
    )


def has_asset_token(text: str, alias: str) -> bool:
    if alias in {"btc", "eth"}:
        return re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", text) is not None
    return re.search(rf"\b{re.escape(alias)}\b", text) is not None


def has_price_language(text: str) -> bool:
    return PRICE_PATTERN.search(text) is not None


def estimate_annualized_volatility(prices: list[float], fallback: float = 0.75) -> float:
    if len(prices) < 3:
        return fallback

    returns = []
    for previous, current in zip(prices, prices[1:], strict=False):
        if previous > 0 and current > 0:
            returns.append(math.log(current / previous))

    if len(returns) < 2:
        return fallback

    mean_return = sum(returns) / len(returns)
    variance = sum((value - mean_return) ** 2 for value in returns) / (len(returns) - 1)
    return max(0.05, min(3.0, math.sqrt(variance) * math.sqrt(365)))


def days_until_deadline(end_date: str | None) -> float:
    if not end_date:
        return 365.0

    parsed = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
    now = datetime.now(UTC)
    return max(1.0, (parsed - now).total_seconds() / 86_400)


def simulate_barrier_hit_probability(
    spot_price: float,
    barrier_price: float,
    days_remaining: float,
    annualized_volatility: float,
    drift: float = 0.0,
    simulations: int = 5_000,
    seed: int = 7,
) -> tuple[float, int]:
    if spot_price <= 0 or barrier_price <= 0:
        return 0.5, 0
    if spot_price >= barrier_price:
        return 1.0, 1

    years = max(days_remaining / 365.0, 1 / 365)
    steps = max(12, min(365, int(days_remaining)))
    dt = years / steps
    rng = random.Random(seed)
    hits = 0

    for _ in range(simulations):
        price = spot_price
        for _step in range(steps):
            shock = rng.gauss(0.0, 1.0)
            price *= math.exp(
                (drift - 0.5 * annualized_volatility**2) * dt
                + annualized_volatility * math.sqrt(dt) * shock
            )
            if price >= barrier_price:
                hits += 1
                break

    return hits / simulations, steps


def build_financial_barrier_diagnostics(
    market: Market,
    spot_price: float,
    historical_prices: list[float],
    data_source: str,
) -> FinancialBarrierDiagnostics | None:
    spec = parse_financial_barrier(market)
    if spec is None:
        return None

    days_remaining = days_until_deadline(market.end_date)
    volatility = estimate_annualized_volatility(historical_prices)
    hit_probability, steps = simulate_barrier_hit_probability(
        spot_price=spot_price,
        barrier_price=spec.barrier_price,
        days_remaining=days_remaining,
        annualized_volatility=volatility,
    )
    parsed_rule = parse_market_rule(market)
    contract_value, fallback_probability, formula = expected_contract_value(
        hit_probability=hit_probability,
        parsed_rule=parsed_rule,
    )

    return FinancialBarrierDiagnostics(
        asset=spec.asset_symbol,
        spot_price=spot_price,
        barrier_price=spec.barrier_price,
        deadline=market.end_date,
        days_remaining=days_remaining,
        annualized_volatility=volatility,
        simulations=5_000,
        steps=steps,
        hit_probability=hit_probability,
        expected_contract_value=contract_value,
        fallback_probability=fallback_probability,
        rule_type=parsed_rule.rule_type.value,
        rule_summary=parsed_rule.summary,
        valuation_formula=formula,
        drift=0.0,
        data_source=data_source,
        notes=[
            "Uses geometric Brownian motion with zero drift.",
            "Volatility is estimated from recent daily historical prices.",
            "Expected contract value is computed by applying the market rule adapter "
            "to simulated outcomes.",
            "This v1 model does not yet use options implied volatility or jump risk.",
        ],
    )
