from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mongodb_uri: str = "mongodb://127.0.0.1:27017"
    mongodb_db: str = "dbms_analytics"
    pass_threshold: float = 0.5
    min_students: int = 10
    min_attempts: int = 2
    algorithm_version: str = "analytics-v1"
    env: str = "development"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b-instruct"
    ollama_model_type: str = "base"
    ollama_timeout: float = 120
    ollama_classify_temperature: float = 0.2
    ollama_generate_temperature: float = 0.8
    ollama_api_key: str = ""
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_available: bool = True
    candidate_similarity_threshold: float = 0.85

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()