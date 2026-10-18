import sys, pathlib, random, csv, io, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app.services.recommendation import recommend_questions, _load_question_bank
from app.evaluation.metrics import write_usefulness_labeling_template
from app.services.weakness_scoring import weakness_for_document

bank = _load_question_bank()

# 5 diverse weak profiles (SQL already done as batch1, include 4 new)
profiles = [
    ("IT2040@Final2023_B1_SQLweak", {'Structured Query Language (SQL)': 45, 'Schema Refinement': 52, 'Database Security': 88}),
    ("IT2040@Final2023_B2_SchemaWeak", {'Schema Refinement': 42, 'Structured Query Language (SQL)': 80, 'Database Security': 85}),
    ("IT2040@Final2023_B3_JDBCweak", {'Java Database Connectivity (JDBC)': 40, 'Structured Query Language (SQL)': 85, 'Database Security': 80}),
    ("IT2040@Final2023_B4_IndexesWeak", {'Database Indexes and Storage Structures': 38, 'Structured Query Language (SQL)': 82, 'Database Security': 88}),
    ("IT2040@Final2023_B5_TransactWeak", {'Database Transaction Management and Concurrency Control': 41, 'Structured Query Language (SQL)': 78, 'Logical Database Design': 75}),
]

all_rows = []  # for combined 50-row file
for snap_id, weak_map in profiles:
    # build doc for recommendation
    topic_perf = [{'topic': k, 'average_percentage': v} for k,v in weak_map.items()]
    doc = {'topic_performance': topic_perf, 'bloom_performance': [{'level':'Apply','average_percentage':48},{'level':'Analyze','average_percentage':42}]}
    recs = recommend_questions(doc, limit=10)
    # weakness context
    from app.services.weakness_scoring import weakness_for_document
    weak_ctx = {k: v['weakness'] for k,v in weakness_for_document(doc)['weakness_scores'].items()}
    # weak ctx for csv header
    # take top 5 weak as positives, bottom 5 as distractors: pick 5 lowest-scored from recs or force strong-topic
    # simpler: top5 = recs[:5] (weak), bottom5 = recs[-5:] is still weak-topic, so inject strong-topic distractors from bank
    weak_topic = min(weak_ctx, key=lambda k: weak_ctx[k] if weak_ctx[k]>0 else 1)  # actually max weakness = lowest pct
    # max weakness = most weak
    weak_topic = max(weak_ctx, key=lambda k: weak_ctx[k])
    strong_topic = min(weak_ctx, key=lambda k: weak_ctx[k])
    print(f"{snap_id}: weak={weak_topic} ({weak_ctx[weak_topic]:.2f}) strong={strong_topic} ({weak_ctx[strong_topic]:.2f}) top={[r['canonical_topic'] for r in recs[:2]]}")

    # get 5 distractors from strong_topic pool
    distractors = [r for r in bank if r['canonical_topic']==strong_topic and r['source_type']=='tutorial']
    if len(distractors) <5:
        distractors += [r for r in bank if r['source_type']=='tutorial' and r['canonical_topic']!=weak_topic][:5]
    distractors = distractors[:5]
    # build mixed 10 for this snapshot
    mixed = []
    for r in recs[:5]:
        mixed.append(r)
    for cand in distractors:
        # fake low score rec
        mixed.append({
            'question_id': cand['question_id'],
            'text': cand['text'],
            'canonical_topic': cand['canonical_topic'],
            'bloom_level': cand['bloom_level'],
            'difficulty': cand['difficulty'],
            'source_type': cand['source_type'],
            'source_id': cand['source_id'],
            'subtopic': cand.get('subtopic',''),
            'recommendation_score': 0.35*weak_ctx.get(cand['canonical_topic'],0.12) + 0.20*1.0 + 0.15*0.7 + 0.15*0.5 + 0.15*0.52,
            'priority': 'Low',
            'weakness': weak_ctx.get(cand['canonical_topic'],0.12),
            'lecture_coverage': 1.0,
            'tutorial_evidence': 0.7,
            'exam_relevance': 0.5,
            'bloom_gap': 0.52,
            'reason': {'weakness_pct': round(weak_ctx.get(cand['canonical_topic'],0.12)*100,1), 'lecture': True, 'tutorial_count': 3, 'exam_recent_count': 2, 'bloom_gap': 0.52}
        })
    random.seed(hash(snap_id) % 10000)
    random.shuffle(mixed)
    # write per-batch temp to collect rows for combined
    tmp = f"/tmp/{snap_id}.csv"
    write_usefulness_labeling_template(mixed, snap_id, weak_ctx, tmp, annotator_id='')
    # read back rows to accumulate
    rows = list(csv.DictReader(open(tmp, encoding='utf-8')))
    all_rows.extend(rows)
    print(f"  -> {len(rows)} rows, mixed: {[r['canonical_topic'][:15] for r in rows[:3]]}")

# write combined 50-row file
out = 'datasets/bloom_dataset/usefulness_workshop_50.csv'
with open(out, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=all_rows[0].keys())
    w.writeheader()
    w.writerows(all_rows)
print(f"Wrote {len(all_rows)} rows to {out}")

# split copies for two raters
import shutil
shutil.copy(out, 'datasets/bloom_dataset/usefulness_workshop_50_lec01.csv')
shutil.copy(out, 'datasets/bloom_dataset/usefulness_workshop_50_lec02.csv')
print("copied to usefulness_workshop_50_lec01.csv / _lec02.csv")
# quick stats
from collections import Counter
print(Counter(r['canonical_topic'] for r in all_rows))
print(Counter(r['priority'] for r in all_rows))
