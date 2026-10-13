from app.config import Settings, settings


def test_ollama_defaults():
    fresh = Settings(_env_file=None)
    assert fresh.ollama_base_url == "http://localhost:11434"
    assert fresh.ollama_model == "qwen2.5:3b-instruct"
    assert fresh.ollama_timeout == 120


def test_temperature_defaults():
    assert settings.ollama_classify_temperature == 0.2
    assert settings.ollama_generate_temperature == 0.8


def test_embedding_defaults():
    assert settings.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
    assert settings.embedding_available is True
    assert settings.candidate_similarity_threshold == 0.85


def test_llm_model_resolves_to_local_model_in_local_env(monkeypatch):
    monkeypatch.setattr(settings, "env", "local")
    monkeypatch.setattr(settings, "ollama_model", "qwen2.5:3b-instruct")
    monkeypatch.setattr(settings, "colab_model", "qwen3:8b")
    assert settings.llm_model == "qwen2.5:3b-instruct"


def test_llm_base_url_resolves_to_localhost_in_local_env(monkeypatch):
    monkeypatch.setattr(settings, "env", "local")
    monkeypatch.setattr(settings, "ollama_base_url", "https://stale.trycloudflare.com")
    assert settings.llm_base_url == "http://localhost:11434"


def test_llm_model_uses_colab_model_when_env_is_colab(monkeypatch):
    monkeypatch.setattr(settings, "env", "colab")
    monkeypatch.setattr(settings, "colab_model", "qwen3:14b")
    assert settings.llm_model == "qwen3:14b"


def test_llm_base_url_uses_ollama_base_url_when_env_is_colab(monkeypatch):
    monkeypatch.setattr(settings, "env", "colab")
    monkeypatch.setattr(settings, "ollama_base_url", "https://abc.trycloudflare.com")
    assert settings.llm_base_url == "https://abc.trycloudflare.com"