"""Quản lý biến môi trường."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://asa:asa_password@postgres:5432/asa_db"
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "asa_documents"

    minio_endpoint: str = "minio:9000"
    minio_root_user: str = "minioadmin"
    minio_root_password: str = "minioadmin"
    minio_bucket: str = "asa-documents"

    redis_url: str = "redis://redis:6379/0"

    llm_model_name: str = "change-me"
    llm_tensor_parallel_size: int = 4
    gpu_memory_utilization: float = 0.85

    max_response_latency_ms: int = 800
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    class Config:
        env_file = ".env"


settings = Settings()
