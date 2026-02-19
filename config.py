"""
Application configuration loaded from environment / .env file.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Backend settings — loaded from environment variables or .env file."""

    # Server
    host: str = Field(default="0.0.0.0", alias="ZENVI_HOST")
    port: int = Field(default=8500, alias="ZENVI_PORT")
    debug: bool = Field(default=False, alias="ZENVI_DEBUG")
    cors_origins: str = Field(default="*", alias="ZENVI_CORS_ORIGINS")

    # OpenAI
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")

    # Anthropic
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")

    # Ollama
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")

    # Google
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")
    google_cloud_credentials: str = Field(default="", alias="GOOGLE_APPLICATION_CREDENTIALS")

    # AWS
    aws_access_key_id: str = Field(default="", alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(default="", alias="AWS_SECRET_ACCESS_KEY")
    aws_region: str = Field(default="us-east-1", alias="AWS_DEFAULT_REGION")

    # TwelveLabs
    twelvelabs_api_key: str = Field(default="", alias="TWELVELABS_API_KEY")

    # Runware (video generation)
    runware_api_key: str = Field(default="", alias="RUNWARE_API_KEY")

    # Agent config
    agent_max_iterations: int = Field(default=15, alias="ZENVI_AGENT_MAX_ITERATIONS")
    agent_timeout_seconds: int = Field(default=120, alias="ZENVI_AGENT_TIMEOUT")
    default_model: str = Field(default="openai/gpt-4o-mini", alias="ZENVI_DEFAULT_MODEL")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # ---- helpers used by provider modules (mimic old get_settings().get()) ----
    def get(self, key: str, default=None):
        """Dict-like access so existing provider code works unchanged."""
        _map = {
            "openai-api-key": self.openai_api_key,
            "anthropic-api-key": self.anthropic_api_key,
            "ollama-base-url": self.ollama_base_url,
            "google-api-key": self.google_api_key,
            "twelvelabs-api-key": self.twelvelabs_api_key,
            "runware-api-key": self.runware_api_key,
            "ai-default-model": self.default_model,
            "aws-access-key-id": self.aws_access_key_id,
            "aws-secret-access-key": self.aws_secret_access_key,
            "aws-region": self.aws_region,
        }
        return _map.get(key, default)


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
