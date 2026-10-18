# Switchable Local ⇄ Colab Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user run the analytics pipeline / dashboard with a Colab-hosted Qwen 3 model or the local Ollama, switching via a helper script, without changing how the app works.

**Architecture:** The LLM endpoint is a setting (`OLLAMA_BASE_URL`, `OLLAMA_MODEL`, plus a new `OLLAMA_API_KEY`), so switching environments is just rewriting three lines in `.env`. A Colab notebook installs Ollama + `qwen3:8b` on the T4 GPU, exposes it over a cloudflared tunnel (with an API key), and optionally runs the FastAPI app. A root-level `switch_llm.py` rewrites `.env` between `local` and `colab` profiles idempotently, preserving all unrelated content.

**Tech Stack:** Python 3 stdlib (switch script), pytest, Ollama, cloudflared, Google Colab, notebook (.ipynb), FastAPI (existing app).

## Global Constraints

- Free Colab T4 GPU (16 GB VRAM); default model `qwen3:8b`.
- MongoDB is remote Atlas — the `MONGODB_URI` line in `.env` must never be touched by the switch script.
- `.env` rewrites must preserve all unrelated lines, comments, and blank lines byte-for-byte.
- Ollama requests from the local client to Colab must carry `Authorization: Bearer <key>` only when `OLLAMA_API_KEY` is set; when empty, behavior is identical to today (no header).
- `switch_llm.py` must depend only on the Python standard library.
- No changes to pipeline, schemas, dashboard, or data model behavior.
- Tests run with the project venv: `.venv\Scripts\python.exe -m pytest`.

---

### Task 1: Optional Ollama API-key auth in the client

**Files:**
- Modify: `app/config.py:4-20` (add `ollama_api_key` setting)
- Modify: `app/llm/ollama.py:16-35` (`generate()` sends auth header when key set)
- Modify: `.env.example:7-8` (document the key)
- Test: `tests/test_ollama_auth.py` (new)

**Interfaces:**
- Consumes: `app.config.settings` (existing).
- Produces: `settings.ollama_api_key: str` (empty default); `ollama.generate(prompt, *, temperature)` now optionally sends `Authorization: Bearer <key>`. Used by Task 2's notebook and `switch_llm.py` to store/set the key.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ollama_auth.py`:

```python
import httpx

from app.config import settings
from app.llm.ollama import OllamaUnavailable, generate


class FakeTransport(httpx.AsyncBaseTransport):
    def __init__(self, handler):
        self._handler = handler

    async def handle_async_request(self, request):
        return await self._handler(request)


def _capture(requests):
    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200, json={"response": '{"ok": true}'}
        )

    return FakeTransport(handler)


async def test_generate_sends_bearer_header_when_key_set(monkeypatch):
    monkeypatch.setattr(settings, "ollama_api_key", "secret-key")
    requests: list[httpx.Request] = []
    client = httpx.AsyncClient(transport=_capture(requests))

    monkeypatch.setattr(
        "app.llm.ollama.httpx.AsyncClient", lambda *a, **k: client
    )

    await generate("hello")

    assert requests
    assert requests[0].headers.get("authorization") == "Bearer secret-key"


async def test_generate_sends_no_auth_header_when_key_empty(monkeypatch):
    monkeypatch.setattr(settings, "ollama_api_key", "")
    requests: list[httpx.Request] = []
    client = httpx.AsyncClient(transport=_capture(requests))

    monkeypatch.setattr(
        "app.llm.ollama.httpx.AsyncClient", lambda *a, **k: client
    )

    await generate("hello")

    assert requests
    assert "authorization" not in requests[0].headers
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_ollama_auth.py -q`
Expected: both tests FAIL — `settings.ollama_api_key` does not exist (pydantic rejects the setattr) / no header sent.

- [ ] **Step 3: Implement the setting and the header**

Modify `app/config.py` — add after `ollama_generate_temperature` (line 17):

```python
    ollama_api_key: str = ""
```

Modify `app/llm/ollama.py` — in `generate()`, after building `body`, build headers and pass them to the POST:

```python
    headers = {}
    if settings.ollama_api_key:
        headers["Authorization"] = f"Bearer {settings.ollama_api_key}"
    try:
        async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
            response = await client.post(url, json=body, headers=headers)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_ollama_auth.py -q`
Expected: 2 PASS.

- [ ] **Step 5: Update `.env.example`**

Add after the `OLLAMA_GENERATE_TEMPERATURE` line (keep blank-line/comment style of the file):

```
# Set when calling a remote Ollama (e.g. Colab tunnel). Leave empty for local.
OLLAMA_API_KEY=
```

- [ ] **Step 6: Run the existing suite**

Run: `.venv\Scripts\python.exe -m pytest tests/test_llm_ollama.py tests/test_ollama_live.py -q`
Expected: no regressions.

- [ ] **Step 7: Commit**

```bash
git add app/config.py app/llm/ollama.py .env.example tests/test_ollama_auth.py
git commit -m "feat: optional OLLAMA_API_KEY auth header for remote Ollama"
```

---

### Task 2: Local switch script `switch_llm.py`

**Files:**
- Create: `switch_llm.py` (repo root, sibling of `run_sample.py`)
- Test: `tests/test_switch_llm.py` (new)

**Interfaces:**
- Consumes: none at import time (stdlib only); reads/writes `.env` in the script's directory.
- Produces: CLI commands:
  - `python switch_llm.py status`
  - `python switch_llm.py colab <base-url> [api-key]`
  - `python switch_llm.py local`
  Exit code 0 on success, 1 on invalid args or missing `.env`. Later tasks (README, notebook instructions) reference these exact commands.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_switch_llm.py`:

```python
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
    assert parsed["OLLAMA_BASE_URL"] == "https://abc.trycloudflare.com"
    assert parsed["OLLAMA_MODEL"] == "qwen3:8b"
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
    assert parsed["OLLAMA_API_KEY"] == ""
    assert parsed["OLLAMA_BASE_URL"] == "https://abc.trycloudflare.com"
    assert parsed["OLLAMA_MODEL"] == "qwen3:8b"


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
    assert parsed["OLLAMA_BASE_URL"] == "http://localhost:11434"
    assert parsed["MONGODB_URI"] == "mongodb://x"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_switch_llm.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'switch_llm'`.

- [ ] **Step 3: Implement `switch_llm.py`**

```python
"""Switch the LLM backend between local Ollama and a Colab-hosted Ollama.

Usage:
    python switch_llm.py status
    python switch_llm.py colab <base-url> [api-key]
    python switch_llm.py local
"""

import sys
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent / ".env"

LOCAL_BASE_URL = "http://localhost:11434"
LOCAL_MODEL = "qwen2.5:3b-instruct"
COLAB_MODEL = "qwen3:8b"

LLM_LINES = (
    "OLLAMA_BASE_URL",
    "OLLAMA_MODEL",
    "OLLAMA_API_KEY",
)


def _line_for(key: str, value: str) -> str:
    return f"{key}={value}"


class SwitchableEnv:
    def __init__(self, env_path: Path):
        self.env_path = env_path

    def _load_lines(self) -> list[str]:
        if not self.env_path.exists():
            raise FileNotFoundError(f"missing .env file: {self.env_path}")
        return self.env_path.read_text(encoding="utf-8").splitlines()

    def _rewrite(self, updates: dict[str, str]) -> None:
        lines = self._load_lines()
        seen: set[str] = set()
        out: list[str] = []
        for line in lines:
            key = line.split("=", 1)[0].strip() if "=" in line else None
            if key in updates:
                out.append(_line_for(key, updates[key]))
                seen.add(key)
            else:
                out.append(line)
        for key in LLM_LINES:
            if key not in seen:
                out.append(_line_for(key, updates.get(key, "")))
        self.env_path.write_text("\n".join(out) + "\n", encoding="utf-8")

    def set_colab(self, base_url: str, api_key: str | None) -> None:
        self._rewrite(
            {
                "OLLAMA_BASE_URL": base_url,
                "OLLAMA_MODEL": COLAB_MODEL,
                "OLLAMA_API_KEY": api_key or "",
            }
        )

    def set_local(self) -> None:
        self._rewrite(
            {
                "OLLAMA_BASE_URL": LOCAL_BASE_URL,
                "OLLAMA_MODEL": LOCAL_MODEL,
                "OLLAMA_API_KEY": "",
            }
        )

    def values(self) -> dict[str, str]:
        result = {}
        for line in self._load_lines():
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                result[key.strip()] = value.strip()
        return result


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        env = SwitchableEnv(ENV_PATH)
        command = args[0] if args else ""
        if command == "status":
            values = env.values()
            for key in LLM_LINES:
                print(f"{key}={values.get(key, '')}")
            return 0
        if command == "colab":
            if len(args) < 2:
                print("usage: python switch_llm.py colab <base-url> [api-key]")
                return 1
            env.set_colab(args[1], args[2] if len(args) > 2 else None)
            print("switched to colab: " + env.values()["OLLAMA_BASE_URL"])
            return 0
        if command == "local":
            env.set_local()
            print("switched to local: " + env.values()["OLLAMA_BASE_URL"])
            return 0
        print(__doc__.strip())
        return 1
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_switch_llm.py -q`
Expected: 5 PASS.

- [ ] **Step 5: Smoke-test against the real `.env`**

Run: `.venv\Scripts\python.exe switch_llm.py status`
Expected: prints `OLLAMA_BASE_URL=...`, `OLLAMA_MODEL=...`, `OLLAMA_API_KEY=`.

Run: `.venv\Scripts\python.exe switch_llm.py colab http://localhost:11434`
then `.venv\Scripts\python.exe switch_llm.py local`
then `.venv\Scripts\python.exe switch_llm.py status`
Expected: `status` again shows local defaults, and `git diff -- .env` shows `.env` unchanged from before the smoke test.

- [ ] **Step 6: Commit**

```bash
git add switch_llm.py tests/test_switch_llm.py
git commit -m "feat: add switch_llm.py to toggle local vs colab LLM backend"
```

---

### Task 3: Colab notebook `notebooks/colab_ollama.ipynb`

**Files:**
- Create: `notebooks/colab_ollama.ipynb`
- Test: `tests/test_notebook_docs.py` (new — asserts required cells exist)

**Interfaces:**
- Consumes: `switch_llm.py` commands (documented in the notebook text) and the `OLLAMA_API_KEY` behavior from Task 1.
- Produces: a runnable notebook whose last cell prints:
  - `OLLAMA_BASE_URL` (the cloudflared tunnel URL to port 11434)
  - `OLLAMA_API_KEY` (the random key generated in the notebook)
  - (full-app mode) the dashboard tunnel URL.

- [ ] **Step 1: Write the failing test**

Create `tests/test_notebook_docs.py`:

```python
import json
from pathlib import Path

NOTEBOOK_PATH = Path(__file__).resolve().parent.parent / "notebooks" / "colab_ollama.ipynb"


def test_notebook_contains_required_cells():
    assert NOTEBOOK_PATH.exists(), "notebook missing"
    data = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    cells = [cell["source"] for cell in data["cells"]]
    source_text = "\n".join(
        "".join(lines) if isinstance(lines, list) else lines
        for lines in cells
    )

    assert "qwen3:8b" in source_text
    assert "cloudflared" in source_text
    assert "trycloudflare" in source_text
    assert "OLLAMA_API_KEY" in source_text
    assert "ollama serve" in source_text


def test_notebook_markdown_documents_switch_commands():
    data = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    md = "".join(
        "".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"]
        for cell in data["cells"]
        if cell["cell_type"] == "markdown"
    )
    assert "switch_llm.py colab" in md
    assert "switch_llm.py local" in md
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_notebook_docs.py -q`
Expected: FAIL — `notebook missing`.

- [ ] **Step 3: Create the notebook**

Create `notebooks/colab_ollama.ipynb` with these cells (JSON; a valid ipynb). The code cells use shell `!` lines plus Python where output must be parsed. The notebook hosts the model only — no repo clone, no dashboard.

Cell 1 (markdown): title + explanation + the two switch commands and the flow (start notebook → copy URL → `python switch_llm.py colab <url> <key>` → run locally → `python switch_llm.py local`).

Cell 2 (code):

```python
import os
import re
import secrets
import subprocess
import time

API_KEY = secrets.token_hex(16)
print(f"OLLAMA_API_KEY={API_KEY}")
```

Cell 3 (code): install and start Ollama.

```python
!curl -fsSL https://ollama.com/install.sh | sh
```

```python
print("starting ollama serve with API key")
env = {**os.environ, "OLLAMA_HOST": "0.0.0.0:11434", "OLLAMA_API_KEY": API_KEY}
subprocess.Popen(
    ["ollama", "serve"],
    env=env,
    stdout=open("/tmp/ollama.log", "w"),
    stderr=subprocess.STDOUT,
)
for _ in range(60):
    try:
        subprocess.run(
            ["curl", "-s", "-f", "http://localhost:11434/api/tags"],
            capture_output=True,
            timeout=5,
        )
        break
    except Exception:
        time.sleep(2)
print("ollama up")
```

```python
!ollama pull qwen3:8b
```

Cell 4 (code): start cloudflared tunnel to Ollama and print the URL.

```python
!curl -L -o /tmp/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
!chmod +x /tmp/cloudflared
```

```python
import re
import subprocess
import time

log = open("/tmp/cf.log", "w")
subprocess.Popen(
    ["/tmp/cloudflared", "tunnel", "--url", "http://localhost:11434", "--no-autoupdate"],
    stdout=log,
    stderr=subprocess.STDOUT,
)
url = None
for _ in range(60):
    text = open("/tmp/cf.log").read()
    match = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", text)
    if match:
        url = match.group(0)
        break
    time.sleep(2)
assert url, "tunnel URL not found in /tmp/cf.log"
print(f"OLLAMA_BASE_URL={url}")
print(f"OLLAMA_API_KEY={API_KEY}")
```

Cell 5 (markdown): "Now on your laptop run: `python switch_llm.py colab <OLLAMA_BASE_URL> <OLLAMA_API_KEY>` — then your existing `python run_sample.py` and the dashboard use Qwen 3. Switch back with `python switch_llm.py local`."

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_notebook_docs.py -q`
Expected: 2 PASS.

- [ ] **Step 5: Validate the notebook parses**

Run: `.venv\Scripts\python.exe -c "import json; json.load(open('notebooks/colab_ollama.ipynb', encoding='utf-8')); print('valid ipynb')"`
Expected: prints `valid ipynb`.

- [ ] **Step 6: Commit**

```bash
git add notebooks/colab_ollama.ipynb tests/test_notebook_docs.py
git commit -m "feat: add Colab notebook for Ollama qwen3:8b with cloudflared tunnel"
```

---

### Task 4: README documentation

**Files:**
- Modify: `README.md` (create if missing; sibling of `run_sample.py`)

**Interfaces:**
- Consumes: the exact commands from Task 2 (`status`, `colab <url> [key]`, `local`) and the notebook from Task 3.

- [ ] **Step 1: Check whether a README exists**

Run: `Test-Path README.md` in the project root.
Expected: note existence; create `README.md` if it does not exist.

- [ ] **Step 2: Add the "Running with Colab" section**

Append a section (create the file if needed):

```markdown
## Running with Colab (Qwen 3)

The LLM backend can run on Google Colab's free T4 GPU with `qwen3:8b`,
while the app and scripts stay on your machine.

1. Open `notebooks/colab_ollama.ipynb` in Colab and run all cells.
   The last output prints `OLLAMA_BASE_URL` and `OLLAMA_API_KEY`.
2. On your machine, point the app at Colab:

   ```
   python switch_llm.py colab https://<id>.trycloudflare.com <api-key>
   ```

3. Run as usual (e.g. `python run_sample.py dbms_analytics_test`).
4. Switch back to local Ollama:

   ```
   python switch_llm.py local
   ```

Check the current backend anytime: `python switch_llm.py status`.

> The Colab tunnel is public, so it is protected by `OLLAMA_API_KEY`
> (set automatically in the notebook). Do not remove the API key when
> using a remote endpoint.
```

- [ ] **Step 3: Review the rendered section**

Read `README.md`; confirm headings, code fences, and commands match Task 2's script exactly.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document Colab Qwen 3 workflow"
```

---

### Task 5: Full-suite regression check

**Files:**
- None.

**Interfaces:**
- Consumes: all prior tasks.

- [ ] **Step 1: Run the entire test suite**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: all previously passing tests plus the new ones pass (167 existing + 9 new = 176 passed, 1 skipped).

- [ ] **Step 2: Manual sanity — local mode still works**

Run: `.venv\Scripts\python.exe switch_llm.py local` then
`.venv\Scripts\python.exe switch_llm.py status`
Expected: local defaults shown; `.env` still has `MONGODB_URI` intact.

- [ ] **Step 3: Final commit if any uncommitted changes**

Run: `git status`
Expected: clean working tree.
