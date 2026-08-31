import textwrap
from pathlib import Path

import switch_llm


def _write_env(tmp_path: Path, content: str) -> Path:
    env_path = tmp_path / ".env"
    env_path.write_text(textwrap.dedent(content), encoding="utf-8")
    return env_path


def _read(env_path: Path) -> dict[str, str]:
    result = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result


def test_switch_to_colab_sets_only_ollama_lines(tmp_path):
    env_path = _write_env(
        tmp_path,
        """
        # comment line that must survive
        MONGODB_URI=mongodb+srv://user:pass@cluster
        OLLAMA_BASE_URL=http://localhost:11434
        OLLAMA_MODEL=qwen2.5:3b-instruct
        OLLAMA_API_KEY=
        PASS_THRESHOLD=0.5
        """,
    )
    env = switch_llm.SwitchableEnv(env_path)

    env.set_colab("https://abc.trycloudflare.com", "sekret")

    content = env_path.read_text(encoding="utf-8")
    assert "# comment line that must survive" in content
    assert "MONGODB_URI=mongodb+srv://user:pass@cluster" in content
    assert "PASS_THRESHOLD=0.5" in content
    parsed = _read(env_path)
    assert parsed["ENV"] == "colab"
    assert parsed["OLLAMA_BASE_URL"] == "https://abc.trycloudflare.com"
    assert parsed["OLLAMA_MODEL"] == "qwen2.5:3b-instruct"
    assert parsed["OLLAMA_API_KEY"] == "sekret"


def test_switch_to_colab_without_key_clears_api_key(tmp_path):
    env_path = _write_env(
        tmp_path,
        """
        OLLAMA_BASE_URL=http://localhost:11434
        OLLAMA_MODEL=qwen2.5:3b-instruct
        OLLAMA_API_KEY=old
        """,
    )
    env = switch_llm.SwitchableEnv(env_path)

    env.set_colab("https://abc.trycloudflare.com", None)

    parsed = _read(env_path)
    assert parsed["ENV"] == "colab"
    assert parsed["OLLAMA_API_KEY"] == ""
    assert parsed["OLLAMA_BASE_URL"] == "https://abc.trycloudflare.com"
    assert parsed["OLLAMA_MODEL"] == "qwen2.5:3b-instruct"


def test_switch_to_local_restores_defaults(tmp_path):
    env_path = _write_env(
        tmp_path,
        """
        OLLAMA_BASE_URL=https://abc.trycloudflare.com
        OLLAMA_MODEL=qwen3:8b
        OLLAMA_API_KEY=sekret
        """,
    )
    env = switch_llm.SwitchableEnv(env_path)

    env.set_local()

    parsed = _read(env_path)
    assert parsed["ENV"] == "local"
    assert parsed["OLLAMA_BASE_URL"] == "http://localhost:11434"
    assert parsed["OLLAMA_MODEL"] == "qwen2.5:3b-instruct"
    assert parsed["OLLAMA_API_KEY"] == ""


def test_rewrite_is_idempotent(tmp_path):
    content = """
    OLLAMA_BASE_URL=http://localhost:11434
    OLLAMA_MODEL=qwen2.5:3b-instruct
    OLLAMA_API_KEY=
    """
    env_path = _write_env(tmp_path, content)
    env = switch_llm.SwitchableEnv(env_path)

    env.set_colab("https://abc.trycloudflare.com", "k")
    first = env_path.read_text(encoding="utf-8")
    env.set_colab("https://abc.trycloudflare.com", "k")
    second = env_path.read_text(encoding="utf-8")

    assert first == second


def test_adds_missing_ollama_lines(tmp_path):
    env_path = _write_env(tmp_path, "MONGODB_URI=mongodb://x\n")
    env = switch_llm.SwitchableEnv(env_path)

    env.set_local()

    parsed = _read(env_path)
    assert parsed["ENV"] == "local"
    assert parsed["OLLAMA_BASE_URL"] == "http://localhost:11434"
    assert parsed["MONGODB_URI"] == "mongodb://x"


def test_preserves_crlf_line_endings(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_bytes(
        b"# comment\r\nMONGODB_URI=mongodb://x\r\nOLLAMA_BASE_URL=http://localhost:11434\r\n"
    )
    env = switch_llm.SwitchableEnv(env_path)

    env.set_colab("https://abc.trycloudflare.com", "k")

    raw = env_path.read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n")
    assert b"# comment\r\n" in raw
    assert b"MONGODB_URI=mongodb://x\r\n" in raw
    assert b"OLLAMA_BASE_URL=https://abc.trycloudflare.com\r\n" in raw


def test_preserves_lf_line_endings(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_bytes(
        b"# comment\nMONGODB_URI=mongodb://x\nOLLAMA_BASE_URL=http://localhost:11434\n"
    )
    env = switch_llm.SwitchableEnv(env_path)

    env.set_local()

    raw = env_path.read_bytes()
    assert b"\r\n" not in raw
    assert raw.count(b"\n") == 6
