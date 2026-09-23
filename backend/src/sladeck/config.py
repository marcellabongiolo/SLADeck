from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SLADeck API"
    environment: str = "development"
    cors_origins: str = "http://localhost:3000"
    database_url: str = "postgresql+psycopg://sladeck:sladeck@localhost:5432/sladeck"

    model_config = SettingsConfigDict(
        env_prefix="SLADECK_",
        env_file=".env",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
