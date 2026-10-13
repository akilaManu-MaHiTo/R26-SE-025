import sys, json, random
sys.path.insert(0, '.')
from app.services.recommendation import recommend_questions, _load_question_bank
from app.evaluation.metrics import write_usefulness_labeling_template
from app.services.weakness_scoring import weakness_for_document

# 1) Weak snapshot: SQL weak (0.55), Schema 0.48 -> top should be SQL
doc_weak = {
    'topic_performance': [
        {'topic': 'Structured Query Language (SQL)', 'average_percentage': 45},
        {'topic': 'Schema Refinement', 'average_percentage': 52},
        {'topic': 'Database Security', 'average_percentage': 88},
    ],
    'bloom_performance': [{'level': 'Apply', 'average_percentage': 48}, {'level': 'Analyze','average_percentage':42}]
}
recs_weak = recommend_questions(doc_weak, limit=10)
weak_ctx = {k: v['weakness'] for k,v in weakness_for_document(doc_weak)['weakness_scores'].items()}
print("weak_ctx", weak_ctx)
print("top weak", [(r['question_id'], r['canonical_topic'], r['recommendation_score']) for r in recs_weak[:3]])

# 2) Take 5 weak-targeted (top 5) + 5 strong-topic distractors (lowest scored SQL? Actually lowest weakness => Security)
# Find Security tutorials directly from bank as distractors
bank = _load_question_bank()
security_cands = [r for r in bank if r['canonical_topic']=='Database Security' and r['source_type']=='tutorial'][:5]
print("security distractors", [(r['question_id'], r['canonical_topic']) for r in security_cands])
# If not enough, fallback to any low-weakness topic
if len(security_cands) <5:
    extra = [r for r in bank if r['source_type']=='tutorial' and r['canonical_topic'] not in ['Structured Query Language (SQL)']][:5-len(security_cands)]
    security_cands += extra

# Build mixed list: 5 weak top + 5 security distractors (as if recommended but low score)
# For distractors, craft fake rec dict with low recommendation_score
mixed = []
for r in recs_weak[:5]:
    mixed.append(r)
# convert security_cands to rec-like dicts with low scores (simulate rank 6-10 but actually strong topic)
for cand in security_cands:
    # compute what score would be with weak_ctx (weakness for Security=0.12) -> approx 0.55
    # reuse recs_weak scoring logic: we can just call recommend with swapped doc to get score, or hardcode
    mixed.append({
        'question_id': cand['question_id'],
        'text': cand['text'],
        'canonical_topic': cand['canonical_topic'],
        'bloom_level': cand['bloom_level'],
        'difficulty': cand['difficulty'],
        'source_type': cand['source_type'],
        'source_id': cand['source_id'],
        'subtopic': cand.get('subtopic',''),
        'recommendation_score': 0.35*0.12 + 0.20*1.0 + 0.15*0.7 + 0.15*0.5 + 0.15*0.52,  # approx low
        'priority': 'Low',
        'weakness': 0.12,
        'lecture_coverage': 1.0,
        'tutorial_evidence': 0.7,
        'exam_relevance': 0.5,
        'bloom_gap': 0.52,
        'reason': {'weakness_pct': 12.0, 'lecture': True, 'tutorial_count': 3, 'exam_recent_count': 2, 'bloom_gap': 0.52}
    })

# shuffle blind: keep weak vs strong interleaved but rater doesn't know
random.seed(42)
random.shuffle(mixed)

# Write as template for raters (single mixed snapshot)
# Use weak_ctx as context (so raters see SQL is weak, Security is strong)
out = 'datasets/bloom_dataset/usefulness_mixed.csv'
write_usefulness_labeling_template(mixed, 'IT2040@Final2023_mixed_SQLweak_vs_SecurityStrong', weak_ctx, out, annotator_id='')
print(f"Wrote {len(mixed)} mixed to {out}")
for i,r in enumerate(mixed,1):
    print(f"{i}. {r['question_id']} | {r['canonical_topic']} | {r['bloom_level']} | score {round(r['recommendation_score'],4)} | {r['text'][:80]}")

# also write two copies for lec01/lec02
import shutil
shutil.copy(out, 'datasets/bloom_dataset/usefulness_mixed_lec01.csv')
shutil.copy(out, 'datasets/bloom_dataset/usefulness_mixed_lec02.csv')
print("copied to usefulness_mixed_lec01.csv and _lec02.csv")
