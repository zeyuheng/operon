import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.market_filters import is_viable_market
from app.core.market_scoring import score_market
from app.services.polymarket_gamma_service import PolymarketGammaService


async def main() -> None:
    service = PolymarketGammaService()
    markets = await service.fetch_active_markets(limit=100)
    candidates = [score_market(market) for market in markets if is_viable_market(market)]
    candidates.sort(key=lambda candidate: candidate.operon_score, reverse=True)

    print("Top Operon Candidates:")
    for index, candidate in enumerate(candidates[:20], start=1):
        market = candidate.market
        print(
            f"{index}. {market.question} | "
            f"score={candidate.operon_score:.2f} | "
            f"price={market.market_probability} | "
            f"volume={market.volume} | "
            f"liquidity={market.liquidity}"
        )


if __name__ == "__main__":
    asyncio.run(main())
