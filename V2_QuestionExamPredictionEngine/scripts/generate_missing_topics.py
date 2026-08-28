"""Generate CandidateQuestions for 0-coverage topics via qwen3:8b.

Missing tutorial topics: Logical Design, JDBC, Indexes, Transaction, Recovery, Utilities
Uses app/services/llm_service.py:209 generate_candidates -> app/llm/roles/generate.py:6 -> Ollama qwen3:8b
Saves to datasets/bloom_dataset/question_bank_generated.json and optionally merges to question_bank.json
"""
import sys, pathlib, json, asyncio
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app.config import settings
from app.llm.ollama import check_llm_detailed_health

# Topics with 0 tutorials (from Counter: SQL25 Schema9 Security9 Programming7 Intro5)
MISSING = [
    ("Logical Database Design", "Apply", "5-10"),
    ("Java Database Connectivity (JDBC)", "Apply", "5-10"),
    ("Database Indexes and Storage Structures", "Analyze", "8-15"),
    ("Database Transaction Management and Concurrency Control", "Analyze", "10-15"),
    ("Database Recovery and Log Management", "Understand", "5-10"),
    ("Database Utilities", "Apply", "5-10"),
]

async def main():
    health = await check_llm_detailed_health()
    print(f"LLM health: {health}")
    if not health['online']:
        print("Ollama not online. For Colab qwen3:8b run:")
        print("  1. Open notebooks/colab_ollama.ipynb -> Run all -> copy OLLAMA_BASE_URL + OLLAMA_API_KEY")
        print("  2. python switch_llm.py colab https://<id>.trycloudflare.com <key>")
        print("  3. python switch_llm.py status # should show model qwen3:8b online")
        print("  4. re-run this script")
        return

    from app.services.llm_service import generate_candidates
    from app.ingestion.question_bank import build_question_bank

    bank = build_question_bank()
    # historical per topic for dedup
    hist_by_topic = {}
    for r in bank:
        hist_by_topic.setdefault(r['canonical_topic'], []).append({"question_id": r['question_id'], "question_text": r['text']})

    all_new = []
    # resume: load existing 3 Utilities if present
    existing = pathlib.Path("datasets/bloom_dataset/question_bank_generated.json")
    if existing.exists():
        try:
            prev = json.loads(existing.read_text(encoding='utf-8'))
            all_new.extend(prev)
            print(f"resumed {len(prev)} existing generated")
            # skip already-done topic
            done_topics = {r['canonical_topic'] for r in prev}
            MISSING[:] = [m for m in MISSING if m[0] not in done_topics]
            print(f"remaining: {[m[0] for m in MISSING]}")
        except: pass
    import asyncio as _asyncio
    for topic, bloom, marks in MISSING:
        rec = {
            "topic": topic,
            "bloom_level": bloom,
            "mark_range": marks,
            "historical_questions": hist_by_topic.get(topic, [])[:5]  # avoid copying
        }
        print(f"\nGenerating 3 for {topic} {bloom} {marks}...")
        result = None
        for attempt in range(3):
            try:
                result = await generate_candidates(rec, count=3)
                if result.get("status") == "ok":
                    break
                print(f"  attempt {attempt+1} degraded {result.get('reason')} retrying in 5s...")
                await _asyncio.sleep(5)
            except Exception as e:
                print(f"  attempt {attempt+1} failed: {e} retrying...")
                await _asyncio.sleep(5)
                continue
        if result.get("status") != "ok":
            print(f" degraded: {result}")
            continue
        print(f"  -> {len(result['candidates'])} candidates, similarity checks: {result.get('similarity_checks')}")
        for c in result['candidates']:
            # map to question_bank schema
            all_new.append({
                "question_id": f"GEN_{topic[:10].replace(' ','_')}_{len(all_new):03d}",
                "source_type": "generated",
                "source_id": f"llm:{settings.llm_model}",
                "canonical_topic": topic,
                "canonical_id": topic.lower().replace(' ','_')[:15],
                "subtopic": c['text'][:300],
                "bloom_level": c['bloom_level'],
                "difficulty": "Medium",
                "marks": int(float(c['marks'])),
                "question_type": "generated",
                "text": c['text'],
                "year": 2024,
                "semester": 1,
                "original_topic_label": topic,
                "rationale": c.get('rationale',''),
                "model_answer": c.get('model_answer',''),
                "rubric_criteria": c.get('rubric_criteria',[]),
            })
            print(f"    - {c['text'][:80]}... marks {c['marks']} bloom {c['bloom_level']}")

    out = pathlib.Path("datasets/bloom_dataset/question_bank_generated.json")
    out.write_text(json.dumps(all_new, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\nWrote {len(all_new)} generated to {out}")

    # Merge preview: total bank would be 161 + len(all_new)
    print(f"Bank would grow 161 -> {161+len(all_new)}")
    print(f"To merge: python -c \"import json,pathlib; b=json.load(open('datasets/bloom_dataset/question_bank.json')); g=json.load(open('datasets/bloom_dataset/question_bank_generated.json')); json.dump(b+g, open('datasets/bloom_dataset/question_bank.json','w'), indent=2)\"")
    print(f"Then re-run: python scripts/make_50_workshop_batch_fixed.py && python scripts/tune_phase4_weights.py")

if __name__ == "__main__":
    asyncio.run(main())
