# Adaptive Exam Analytics Engine

DBMS learning analytics pipeline: materializes per-student analytics from graded
submissions, classifies question semantics (Bloom levels, topics), and serves a
FastAPI dashboard.

## Student accounts

Computing exam analytics creates missing student accounts from that exam's graded
submissions. Students sign in at `/login/student` with
`<student-id>@my.sliit.lk` (lowercase) and the default password `Student@123`.
Existing accounts and passwords are preserved when an exam is analyzed again.
For previously analyzed exams, use **Reanalyse** to create missing accounts;
opening a cached result does not provision accounts.

Exam Creator can retrieve course evidence from an independent analytics-owned
index. See [course RAG setup, import, and search](COURSE_RAG.md).

## Reconstruct an exam paper (read only)

```bash
python scripts/reconstruct_exam_paper.py EXAM-2025-S1-Apr
```

Uses the existing analytics MongoDB settings. Prints exam validation and counts
without student IDs/answers. Exit codes: 0 valid, 2 incomplete/ambiguous, 1 I/O
failure. To export student evidence to a **new** local file, explicitly request:

```bash
python scripts/reconstruct_exam_paper.py EXAM-2025-S1-Apr --include-student-data --output paper.json
```

Full exports use MongoDB Extended JSON and contain private assessment data.
The service keeps question definitions, rubric references and each student's
results separate. It reads both known essay-rubric collection spellings, joins
exact references, and reports conflicts/duplicates without choosing a result.
No grading, indexing, collection creation or database updates are performed.

The 2025 exam now has five essays plus one diagram, as confirmed by the user.
Student `grading` adds the two verified rubric maxima (35 + 20 = 55) and the
existing component scores. Percentage = combined awarded marks / 55 * 100.
Missing evaluations produce a pending grade with null total/percentage;
duplicates or inconsistent grading evidence require review. Review-needed
numeric totals are provisional. No letter-grade boundaries are invented.

Grade completeness is separate from recovering the original question paper:
no numbered original diagram question/prompt is stored, so its question
definition remains unresolved even when both component grades are available.
Saved diagram grades remain linked by exact exam/student/guideline references. See the
[database audit and matching rules](EXAM_PAPER_AUDIT.md).
See [verification results and remaining source gaps](EXAM_PAPER_VERIFICATION.md)
and the [synthetic reconstruction](examples/exam_paper.synthetic.json).

Lecturer diagram views now read the saved `diagram_evaluations` agent schema,
resolve rubrics by guideline ID and refresh diagram results even for cached essay
analytics. See [diagram dashboard verification](DIAGRAM_DASHBOARD_VALIDATION.md).

The lecturer student list now includes pending/roster students with separate
essay, diagram and overall grading statuses. The overall average excludes
pending and review-needed grades. See [grading progress and verification](LECTURER_GRADING_STATUS.md).

The lecturer header also offers a read-only [question-paper/rubric preview](EXAM_PAPER_PREVIEW.md).
See the [lecturer cleanup audit](LECTURER_CLEANUP_AUDIT.md) for corrected matching,
validation and calculation errors, removed legacy code, checks and remaining cache/index
limitations. Calculation versions are now 1.4; older snapshots are rebuilt when possible,
and retained results are marked stale if refresh fails.

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

For the verified 20-student dataset copied/extended from gradev5 into gradev6,
see [the gradev6 dataset guide](GRADEV6_DATASET.md). It contains five original
students and fifteen clearly labelled synthetic students, preserving three pending
real essays. The running application's database setting is unchanged.

```bash
python run_sample.py dbms_analytics_test
```

Seeds `courses`, `rubricCollection`, and `submissions` from `app/sample_data/`,
then runs the analytics pipeline (Bloom-level classification, numeric analysis,
student insights) and persists results to `student_analytics`. A progress bar
shows each LLM step.

Individual student analyses run in a FIFO queue, one at a time per backend
process. Current saved results bypass the queue; waiting requests recheck the
cache before generating. The lecturer bell shows each student's queued,
analyzing, complete, or failed status, even after selecting another student.
This queue is in memory: run one backend worker for shared ordering. Pending
work is not restored after a server restart, and notifications are not restored
after a browser refresh. Full-exam batch analysis uses its existing workflow.

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
