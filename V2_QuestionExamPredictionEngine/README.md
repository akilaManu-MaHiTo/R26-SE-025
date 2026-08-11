# V2 Question Exam Prediction Engine

DBMS learning analytics pipeline: materializes per-student analytics from graded
submissions, classifies question semantics (Bloom levels, topics), and serves a
FastAPI dashboard.

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

> The Colab tunnel is public, so it is protected by `OLLAMA_API_KEY`
> (set automatically in the notebook). Do not remove the API key when
> using a remote endpoint.
