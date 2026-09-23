from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SLADeck API"
    environment: str = "development"
    cors_origins: str = "http://localhost:3000"
    database_url: str = "postgresql+psycopg://sladeck:sladeck@localhost:5432/sladeck"
    jwt_secret: str = "development-only-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 14

    model_config = SettingsConfigDict(
        env_prefix="SLADECK_",
        env_file=".env",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_production_secret(self) -> "Settings":
        if self.environment == "production" and self.jwt_secret == "development-only-change-me":
            raise ValueError("SLADECK_JWT_SECRET must be configured in production")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
