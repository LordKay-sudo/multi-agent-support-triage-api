from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    app_name: str = "Multi-Agent Support Triage API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    environment: str = "local"
    llm_provider: Literal["mock", "bedrock"] = "mock"
    aws_region: str = "eu-west-2"
    bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    langfuse_enabled: bool = False
    langfuse_public_key: str | None = Field(default=None, repr=False)
    langfuse_secret_key: str | None = Field(default=None, repr=False)
    langfuse_host: str = "https://cloud.langfuse.com"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
