"""
app/config.py

Central configuration for the entire application.
Every setting is read from environment variables via pydantic-settings.
Import `settings` anywhere in the app — never read os.environ directly.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    All application settings loaded from .env file.
    Grouped into logical sections for clarity.
    """

    model_config = SettingsConfigDict(
         env_file=[".env", "../.env"],
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ────────────────────────────────────────────────
    app_env: Literal["development", "test", "production"] = "development"
    app_api_key: str = Field(..., description="Master API key for auth middleware")
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # ── Database ───────────────────────────────────────────
    database_url: str = Field(
        ...,
        description="Async postgres URL: postgresql+asyncpg://...",
    )
    sync_database_url: str = Field(
        ...,
        description="Sync postgres URL for alembic: postgresql+psycopg2://...",
    )

    # ── Redis ──────────────────────────────────────────────
    redis_url: str = Field(..., description="Redis URL: redis://...")

    # ── LLM Providers ──────────────────────────────────────
    openai_api_key: str = Field(..., description="OpenAI API key")
    anthropic_api_key: str = Field(..., description="Anthropic API key")
    groq_api_key: str = Field(..., description="Groq API key")

    # ── LLM Routing ────────────────────────────────────────
    default_llm_provider: Literal["openai", "anthropic", "groq"] = "openai"
    default_llm_model: str = "gpt-4o-mini"
    critic_llm_provider: Literal["openai", "anthropic", "groq"] = "groq"
    critic_llm_model: str = "llama3-8b-8192"

    # ── LangSmith ──────────────────────────────────────────
    langchain_api_key: str = ""
    langchain_tracing_v2: bool = False
    langchain_project: str = "self-healing-rag"

    # ── Embeddings ─────────────────────────────────────────
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # ── Retrieval ──────────────────────────────────────────
    retrieval_top_k: int = 10
    rerank_top_k: int = 5

    # ── RAG / Critic ───────────────────────────────────────
    critic_pass_threshold: float = Field(
        0.70,
        ge=0.0,
        le=1.0,
        description="Minimum average critic score to pass without retry",
    )
    max_retry_count: int = Field(
        3,
        ge=1,
        le=5,
        description="Maximum critic retry loops before fallback",
    )

    # ── Chunking ───────────────────────────────────────────
    chunk_size: int = 512
    chunk_overlap: int = 64

    # ── Derived helpers ────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    @field_validator("critic_pass_threshold")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("critic_pass_threshold must be between 0.0 and 1.0")
        return v

    @field_validator("embedding_dim")
    @classmethod
    def validate_embedding_dim(cls, v: int) -> int:
        valid_dims = [384, 768, 1024, 1536, 3072]
        if v not in valid_dims:
            raise ValueError(f"embedding_dim must be one of {valid_dims}")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.
    lru_cache ensures .env is read exactly once per process.
    """
    return Settings()


# Module-level singleton
# Import this directly: from app.config import settings
settings: Settings = get_settings()