# Adaptive Exam Analytics Engine

DBMS learning analytics pipeline: materializes per-student analytics from graded
submissions, classifies question semantics (Bloom levels, topics), and serves a
FastAPI dashboard.

The lecturer Exam Creator includes saved blueprints, draft-aware recommendations,
source-grounded question alternatives, and separate marking-scheme exports.
See [the exam creator guide](EXAM_CREATOR.md) for usage, model configuration and validation limits.

## Models and development checks

Bloom classification requires the local ModernBERT checkpoint. Put
`bloom.safetensors` (or `model.safetensors`) and `config.json` in
`models/bloom_modernbert/`, with the tokenizer files in its `tokenizer/` folder.
The weights must be supplied separately; they are not included in Git. Loading
is lazy and shared within each process, so multiple server workers each need
their own model memory. `BLOOM_MODEL_DIR` resolves relative to this project.
`BLOOM_MODEL_THRESHOLD` flags low-confidence analytics for review; it does not
switch classification to Ollama or rules.

Install core dependencies with `python -m pip install -r requirements.txt`.
For optional candidate similarity and research clustering, also install
`python -m pip install -r requirements-embeddings.txt`. SentenceTransformer loads
on the first similarity request and may download its configured model unless it
is already cached. Set `EMBEDDING_AVAILABLE=false` to disable similarity checks.

Run tests from this directory with `python -m pytest`. Tests using `test_db`
require a disposable MongoDB database named `dbms_analytics_test`; the fixture
drops it on teardown. Live model tests are opt-in. For focused offline cleanup
checks, run `python -m pytest tests/test_model_cleanup.py`.

See [the model audit](MODEL_AUDIT.md) for artifact provenance, retained research
files, cleanup findings, test results and remaining reproducibility limits.

## Running with sample data

```bash
python run_sample.py dbms_analytics_test
```

Seeds `courses`, `rubricCollection`, and `submissions` from `app/sample_data/`,
then runs the analytics pipeline (Bloom-level classification, numeric analysis,
student insights) and persists results to `student_analytics`. A progress bar
shows each LLM step.

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

You can also switch directly by editing `ENV` in `.env` (`ENV=local` /
`ENV=colab`) — it selects both the model and endpoint. The Colab model is
configured with `COLAB_MODEL` (default `qwen3:8b`); the tunnel still needs its
URL set via `python switch_llm.py colab <url> <key>`.

> The Colab tunnel is public, so it is protected by `OLLAMA_API_KEY`
> (set automatically in the notebook). Do not remove the API key when
> using a remote endpoint.
