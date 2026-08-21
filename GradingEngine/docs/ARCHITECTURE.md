# GradingEngine Architecture

## End-to-end grading flow

```mermaid
flowchart TD
  subgraph UI["Gradex_AI_Client"]
    P8["Page 8: Knowledge Base\nmanage courses + upload PDF/PPTX"]
    P2["Page 2: Session Init\nselect course + rubric"]
    P4["Page 4: Student batch upload"]
    P6["Page 6: Review\nOCR + scores + RAG badge"]
  end

  subgraph API["GradingEngine FastAPI"]
    Courses["/courses CRUD"]
    Lectures["/lecture-notes\nupload / list / delete"]
    Grade["grade-batch / /api/grade"]
    OCR["ocr_service\nOpenCV deskew + OCR.Space"]
    Split["answer_splitter\nQ1 / Question 1 markers"]
    RAG["rag_service\nChroma course filter top-3"]
    Eval["evaluate_grading"]
  end

  subgraph Engines["Grading engines"]
    Colab["Colab primary\nngrok /evaluate"]
    Groq["Groq fallback"]
    Emergency["Emergency mock"]
  end

  subgraph Store["Persistence"]
    Mongo["MongoDB\nrubrics, submissions, courses"]
    Chroma["ChromaDB\nlecture chunks + course metadata"]
  end

  P8 --> Courses
  P8 --> Lectures
  Lectures --> Chroma
  Courses --> Mongo

  P2 --> Courses
  P2 --> Mongo
  P4 --> OCR
  OCR --> Split
  Split --> RAG
  RAG --> Chroma
  RAG --> Eval
  Eval --> Colab
  Colab -->|timeout / error| Groq
  Groq -->|no API key| Emergency
  Eval --> Mongo
  Mongo --> P6
```

## Knowledge Base â†” grading alignment

```mermaid
flowchart LR
  A["Add course SE3040"] --> B["Upload lectures tagged SE3040"]
  B --> C["Session subject = SE3040"]
  C --> D["RAG where course = SE3040"]
  D --> E["snippet + rag_chunks / rag_context_used"]
  E --> F["Colab or Groq grades each question"]
```

## Per-question grading path

1. OCR produces one full transcript.
2. Local regex split buckets answers by `Q1` / `Question 1` markers (else full text per question).
3. For each rubric question: RAG enrich â†’ Colab â†’ Groq â†’ emergency.
4. Scores are summed; response includes `grading_source`, `rag_context_used`, `rag_chunks`.

## Local Colab mock (when live Colab is down)

```bash
# Terminal A
set COLAB_USE_MOCK=1
python colab/colab_evaluate_server.py

# In .env (or for the smoke test via --with-local-colab):
COLAB_EVALUATE_URL=http://127.0.0.1:5000/evaluate

# Terminal B (or one-shot)
python -m app.scripts.test_per_question_grading --with-local-colab
```

For normal grading, set `COLAB_EVALUATE_URL` in `.env` to your live ngrok `/evaluate` URL.
If it is empty/unset, Colab is skipped and Groq is used.

## Session identity (rubric + each submission)

Copied from Session Initialization onto the rubric, then onto every graded student:

- `subject_code`, `subject_name` (name auto-filled from `courses`)
- `year`, `month`, `semester` (dropdowns)
- `session_name` âˆˆ Final Examination | Mid Term Examination | Tutorial Examination | Quiz
- `rubric_ref` on submissions
## RAG snippets for cognitive analysis

Each graded question stores the retrieved lecture text under
`evaluation.rag_per_question.<q_no>.rag_snippet` (plus `rag_chunks` /
`rag_context_used`). Teammates can use student OCR + these snippets from Mongo
without needing the local `chroma_db/` folder.
