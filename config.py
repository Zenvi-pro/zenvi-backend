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

    # Runware (video generation — Kling)
    runware_api_key: str = Field(default="", alias="RUNWARE_API_KEY")

    # Perplexity (research agent)
    perplexity_api_key: str = Field(default="", alias="PERPLEXITY_API_KEY")

    # GitHub (product launch agent)
    github_token: str = Field(default="", alias="GITHUB_TOKEN")

    # Suno (music agent)
    suno_token: str = Field(default="", alias="SUNO_TOKEN")

    # NVIDIA Edge Device
    nvidia_edge_url: str = Field(default="", alias="NVIDIA_EDGE_URL")

    # Remotion rendering services
    remotion_url: str = Field(default="http://localhost:4500/api/v1", alias="REMOTION_URL")
    remotion_product_launch_url: str = Field(default="http://localhost:3100", alias="REMOTION_PRODUCT_LAUNCH_URL")

    # Pexels (stock video search)
    pexels_api_key: str = Field(default="", alias="PEXELS_API_KEY")

    # Supabase (usage tracking + auth verification)
    supabase_url: str = Field(default="https://fmeawyasfffvyoactenu.supabase.co", alias="SUPABASE_URL")
    supabase_anon_key: str = Field(default="", alias="SUPABASE_ANON_KEY")

    # Pinecone (per-session vector memory)
    pinecone_api_key: str = Field(default="", alias="PINECONE_API_KEY")

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
            "perplexity-api-key": self.perplexity_api_key,
            "github-token": self.github_token,
            "suno-token": self.suno_token,
            "nvidia-edge-url": self.nvidia_edge_url,
            "remotion-url": self.remotion_url,
            "remotion-product-launch-url": self.remotion_product_launch_url,
            "ai-default-model": self.default_model,
            "pexels-api-key": self.pexels_api_key,
            "supabase-url": self.supabase_url,
            "supabase-anon-key": self.supabase_anon_key,
            "pinecone-api-key": self.pinecone_api_key,
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
