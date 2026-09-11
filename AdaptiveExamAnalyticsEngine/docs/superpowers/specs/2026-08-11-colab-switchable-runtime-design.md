# Design: Switchable Local ⇄ Colab Runtime

Date: 2026-08-11
Status: Draft

## Problem

The analytics pipeline and FastAPI dashboard currently run only on the local
machine, where the LLM backend is a local Ollama server (`qwen2.5:3b-instruct`,
~37s per call). The user wants to:

1. Also run the workload from Google Colab, where a free T4 GPU can host a
   stronger model (`qwen3:8b`).
2. Keep the local setup fully working.
3. Switch between the two backends with a simple command.

## Constraints

- Colab free tier: T4 GPU, 16 GB VRAM, sessions terminate after a few hours.
- MongoDB is already remote (Atlas), so both environments share the same
  database and the connection string stays in `.env` untouched.
- Only the LLM backend (`OLLAMA_BASE_URL`, `OLLAMA_MODEL`) differs between
  environments. Optionally an API key for authenticated remote access.
- The public tunnel created by Colab is unauthenticated by default; it must not
  allow strangers to burn the user's Colab GPU quota.

## Approach

Two switchable modes, orchestrated by a local helper script and a Colab
notebook. The core principle: **the LLM endpoint is a setting, not a
deployment**. `ENV` in `.env` is the master switch — `ENV=local` uses
`localhost:11434` + `OLLAMA_MODEL`; `ENV=colab` uses `OLLAMA_BASE_URL` (the
tunnel) + `COLAB_MODEL`. `switch_llm.py` keeps `ENV`, the tunnel URL, and the
API key in sync.

### 1. Colab notebook `notebooks/colab_ollama.ipynb`

Cells, run in order:

1. **Generate API key** — `secrets.token_hex(16)`, printed as `OLLAMA_API_KEY`.
2. **Start Ollama** — install the Ollama binary, start `ollama serve` on
   `0.0.0.0:11434` with an `OLLAMA_API_KEY` set, wait until `/api/tags`
   responds, then `ollama pull qwen3:8b`.
3. **Public tunnel** — download `cloudflared` (linux-amd64), open a quick
   tunnel `--url http://localhost:11434`, parse and print the
   `https://<id>.trycloudflare.com` URL, plus the matching API key.

No repo is cloned and no dashboard is served on Colab — the notebook hosts the
model only. All application code stays on the user's machine.

Output contract: the notebook ends by printing the two values the user needs to
paste into the local switch script: `OLLAMA_BASE_URL` and `OLLAMA_API_KEY`.

### 2. Local switch script `switch_llm.py`

Root-level script (sibling of `run_sample.py`). No third-party deps.

- `python switch_llm.py status` — print the current effective LLM settings
  (from `.env`).
- `python switch_llm.py colab <base-url> [api-key]` — rewrite only the
  `OLLAMA_BASE_URL`, `OLLAMA_MODEL` (`qwen3:8b`), and `OLLAMA_API_KEY` lines in
  `.env`. All other lines, comments, and blank lines are preserved byte-for-byte
  (Mongo URI, thresholds, etc. untouched). Blank API key clears the line.
- `python switch_llm.py local` — restore `http://localhost:11434`,
  `qwen2.5:3b-instruct`, and an empty API key.

Rewrites are idempotent. A non-interactive, deterministic edit is preferred over
`dotenv` round-tripping so comments/formatting in the user's `.env` are never
clobbered.

### 3. Optional API-key auth (small code change)

- `app/config.py`: add `ollama_api_key: str = ""`.
- `app/llm/ollama.py`: when `settings.ollama_api_key` is non-empty, send
  `Authorization: Bearer <key>` on the generate request. When empty (the local
  default), send no header — behavior identical to today.
- `.env.example`: document `OLLAMA_API_KEY` and the two switch commands.

### 4. Docs and tests

- README section: "Running with Colab" — how to start the notebook, copy the
  tunnel URL, switch, and switch back.
- Unit tests:
  - `switch_llm.py`: rewrites a temp `.env` correctly in all three modes;
    preserves unrelated lines; idempotent.
  - `ollama.py`: `generate()` sends `Authorization` header only when the API
    key is set (mock `httpx`).

## Non-goals

- No changes to the pipeline, schemas, dashboard, or data model.
- No embedding/model hosting on Colab beyond Ollama (embeddings stay local and
  degrade gracefully if unavailable).
- No CI/CD, no Docker, no autoscaling.

## Open questions

- None blocking. The notebook defaults to the free-tier model `qwen3:8b`.
