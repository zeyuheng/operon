from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    log_level: str = "INFO"
    polymarket_gamma_base_url: str = "https://gamma-api.polymarket.com"
    polymarket_clob_base_url: str = "https://clob.polymarket.com"
    database_url: str = "sqlite:///./operon.db"
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPERON_OPENAI_API_KEY", "OPENAI_API_KEY"),
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="OPERON_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
