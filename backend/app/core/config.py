"""Application configuration using Pydantic Settings."""

from pydantic import field_validator
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
    s3_endpoint_url: str | None = "http://localhost:9000"  # MinIO for dev
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_name: str = "legal-doc-analyzer"
    s3_region: str = "us-east-1"

    # --- Qdrant Vector DB ---
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection_name: str = "documents"
    # "qdrant" in production; "memory" for tests/dev without a Qdrant instance
    vector_search_backend: str = "qdrant"

    # --- LLM Providers ---
    # Claude (Anthropic)
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    anthropic_fast_model: str = "claude-3-5-haiku-20241022"

    # OpenAI
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"
    openai_fast_model: str = "gpt-4o-mini"

    # Google Gemini (interim provider: LLM + embeddings share one API key)
    gemini_api_key: str | None = None
    gemini_llm_model: str = "gemini-3.6-flash"
    gemini_llm_fast_model: str = "gemini-3.5-flash-lite"
    # 0 disables thinking (supported on Gemini 2.5-era models only; Gemini 3
    # models REJECT thinkingBudget=0, so leave unset for them). None omits
    # thinkingConfig entirely — the default and correct choice for 3.x.
    gemini_thinking_budget: int | None = None
    # Minimum seconds between Gemini LLM requests (client-side rate pacing,
    # shared across all worker jobs in the process). Free-tier keys allow
    # ~10 requests/minute, so 6s ≈ 10 RPM. 0 disables pacing.
    gemini_min_request_interval: float = 6.0

    # Default provider
    default_llm_provider: str = "anthropic"
    mock_llm: bool = True

    # --- Embeddings (Gemini API — uses gemini_api_key above) ---
    mock_embeddings: bool = True
    embedding_model_name: str = "gemini-embedding-001"

    # --- Logging ---
    log_level: str = "INFO"

    # --- Upload / ingestion ---
    max_upload_mb: int = 50
    storage_backend: str = "s3"  # "s3" or "local"
    local_storage_path: str = "/tmp/legal-doc-storage"
    run_ingestion_inline: bool = False
    run_ai_pipeline_inline: bool = False
    chunk_target_tokens: int = 400
    chunk_max_tokens: int = 800
    chunk_overlap_ratio: float = 0.1
    ocr_skip_min_chars_per_page: int = 50
    ocr_low_confidence_threshold: float = 0.7

    # --- Search & RAG Q&A (07-feature-spec-comparison-search.md §3–4) ---
    search_default_limit: int = 20
    semantic_candidate_k: int = 50
    rrf_k: int = 60
    rag_top_k: int = 6
    # Below this best-match similarity the Q&A endpoint answers "not found"
    # instead of forcing a generation on weak context. 0 disables the check.
    rag_similarity_threshold: float = 0.0
    rag_history_turns: int = 3
    rag_conversation_ttl_seconds: int = 24 * 60 * 60

    @field_validator("gemini_thinking_budget", mode="before")
    @classmethod
    def _empty_str_to_none(cls, v: object) -> object:
        # docker-compose interpolates unset vars to "" — treat as unset.
        return None if v == "" else v

    @field_validator("gemini_min_request_interval", mode="before")
    @classmethod
    def _empty_interval_to_default(cls, v: object) -> object:
        return 6.0 if v == "" else v

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
