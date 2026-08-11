import json
from pathlib import Path

NOTEBOOK_PATH = Path(__file__).resolve().parent.parent / "notebooks" / "colab_ollama.ipynb"


def _cell_text(cell: dict) -> str:
    source = cell["source"]
    return "".join(source) if isinstance(source, list) else source


def test_notebook_contains_required_cells():
    assert NOTEBOOK_PATH.exists(), "notebook missing"
    data = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    source_text = "\n".join(_cell_text(cell) for cell in data["cells"])

    assert "qwen3:8b" in source_text
    assert "cloudflared" in source_text
    assert "trycloudflare" in source_text
    assert "OLLAMA_API_KEY" in source_text
    assert "ollama serve" in source_text


def test_notebook_markdown_documents_switch_commands():
    data = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    md = "\n".join(
        _cell_text(cell) for cell in data["cells"] if cell["cell_type"] == "markdown"
    )
    assert "switch_llm.py colab" in md
    assert "switch_llm.py local" in md
