from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_health import router as health_router
from app.api.routes_market_scout import router as market_scout_router
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="Operon API",
        description="Market-aware event intelligence for prediction markets.",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
        allow_origin_regex=r"https://.*\.lhr\.life",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(market_scout_router, prefix="/market-scout", tags=["Market Scout"])
    return app


app = create_app()


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "Operon", "environment": settings.environment}
