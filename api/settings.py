"""Pydantic-based settings, loaded from env / .env."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Vertex AI Gemini
    GCP_PROJECT: str = "hivideosum"
    GCP_LOCATION: str = "global"
    FILTER_CONFIG_PATH: str = "configs/filter_gemini.yaml"

    # vLLM
    VLLM_BASE_URL: str = "http://vllm:8001/v1"
    VLLM_MODEL_NAME: str = "hivideosum"
    VLLM_API_KEY: str = "dummy"

    # Redis (used by both arq and the result cache)
    REDIS_URL: str = "redis://redis:6379/0"

    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    RESULT_TTL_SECONDS: int = 86400

    # Collection limits
    COLLECT_MAX_REGULAR: int = 50
    COLLECT_MAX_TIMESTAMP: int = 50


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
