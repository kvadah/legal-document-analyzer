"""Application configuration using Pydantic Settings."""
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- App ---
    app_name: str = "Legal Document Analyzer"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False

    # --- Server ---
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # --- Database ---
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/legal_doc_analyzer"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- JWT ---
    jwt_secret_key: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24

    # --- S3 / Object Storage ---
    s3_endpoint_url: Optional[str] = "http://localhost:9000"  # MinIO for dev
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_name: str = "legal-doc-analyzer"
    s3_region: str = "us-east-1"

    # --- Qdrant Vector DB ---
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection_name: str = "documents"

    # --- LLM Providers ---
    # Claude (Anthropic)
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-5-sonnet-20241022"

    # OpenAI
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o"

    # Default provider
    default_llm_provider: str = "anthropic"

    # --- Logging & Observability ---
    log_level: str = "INFO"
    sentry_dsn: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
