from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = str(Path(__file__).resolve().parents[1] / ".env")


class Settings(BaseSettings):
    mongodb_uri: str = "mongodb+srv://admin:harithe2002@cluster0.ynphhn4.mongodb.net/Grading?retryWrites=true&w=majority&appName=Cluster0"
    mongodb_local_uri: str = "mongodb://127.0.0.1:27017"
    mongodb_mode: str = "local"
    mongodb_db: str = "grading"
    pass_threshold: float = 0.5
    min_students: int = 10
    min_attempts: int = 2
    algorithm_version: str = "analytics-v1"
    env: str = "local"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b-instruct"
    colab_model: str = "qwen3:8b"
    ollama_model_type: str = "base"
    ollama_timeout: float = 120
    ollama_classify_temperature: float = 0.2
    ollama_generate_temperature: float = 0.8
    ollama_api_key: str = ""
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_available: bool = True
    candidate_similarity_threshold: float = 0.85

    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    @property
    def effective_mongodb_uri(self) -> str:
        """Return the MongoDB URI based on ``mongodb_mode`` setting."""
        if self.mongodb_mode == "local":
            return self.mongodb_local_uri
        return self.mongodb_uri

    @property
    def llm_model(self) -> str:
        """Model actually used for requests, resolved from ``env``."""
        return self.colab_model if self.env == "colab" else self.ollama_model

    @property
    def llm_base_url(self) -> str:
        """Ollama endpoint actually used, resolved from ``env``."""
        if self.env == "colab":
            return self.ollama_base_url
        return "http://localhost:11434"


settings = Settings()