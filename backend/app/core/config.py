"""Centralised application configuration loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AI Research & Knowledge Synthesis Agent"
    default_user_id: str = "guest"
    vector_store_backend: str = "faiss"
    embedding_provider: str = "local"
    local_embedding_model: str = "all-MiniLM-L6-v2"
    llm_provider: str = "openai"
    openai_base_url: str = "https://api.hcnsec.cn/v1"
    openai_model: str = "deepseek/deepseek-chat-v3.1"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_api_key: str | None = None
    google_api_key: str | None = None
    top_k_chunks: int = 8
    chunk_size: int = 500
    chunk_overlap: int = 50
    data_directory: Path = BACKEND_ROOT / "data"

    # Comma-separated list of browser origins allowed to call the API.
    # Override with CORS_ALLOW_ORIGINS="http://localhost:3000,https://app.example.com".
    cors_allow_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    # When enabled the API reflects ANY origin (Access-Control-Allow-Origin: *).
    # Safe here because allow_credentials=False (browsers send no cookies/tokens).
    # This is how expose.sh lets remote NGrok/localTunnel testers reach the backend.
    cors_allow_any_origin: bool = False


settings = Settings()
