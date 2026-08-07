from app.config import settings


def test_ollama_defaults():
    assert settings.ollama_base_url == "http://localhost:11434"
    assert settings.ollama_model == "qwen2.5:3b-instruct"
    assert settings.ollama_timeout == 120


def test_temperature_defaults():
    assert settings.ollama_classify_temperature == 0.2
    assert settings.ollama_generate_temperature == 0.8


def test_embedding_defaults():
    assert settings.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
    assert settings.embedding_available is True
    assert settings.candidate_similarity_threshold == 0.85