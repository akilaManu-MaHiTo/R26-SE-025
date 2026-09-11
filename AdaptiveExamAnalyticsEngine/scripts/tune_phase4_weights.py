import sys, pathlib, csv, io, json, itertools, random
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app.analytics.recommendation_score import ScoreWeights, recommendation_score
from app.evaluation.metrics import ndcg_at_k, precision_at_k, cohen_kappa

def load(p):
    raw = pathlib.Path(p).read_bytes().decode('utf-8', errors='replace')
    raw = raw.replace('\u201c','"').replace('\u201d','"').replace('\ufffd','')
    return list(csv.DictReader(io.StringIO(raw)))

# Load gold labels - use lec01 as ground truth (or average)
r1 = load('datasets/bloom_dataset/usefulness_workshop_50_lec01.csv')
r2 = load('datasets/bloom_dataset/usefulness_workshop_50_lec02.csv')
print(f"loaded workshop 50: {len(r1)} rows")

# Build per-batch groups (analytics_snapshot_id)
from collections import defaultdict
batches = defaultdict(list)
for row in r1:
    batches[row['analytics_snapshot_id']].append(row)

# Features per row: weakness, lecture_coverage, tutorial_evidence, exam_relevance, bloom_gap
# Use would_use as binary relevance, rating_overall as graded relevance
def score_row(row, w: ScoreWeights):
    # CSV has recommendation_score but not weakness column directly; derive from weakness_context_json or use recomputed
    # Use lecture_coverage etc from CSV, weakness from reason weakness_pct or weakness_context
    weakness = None
    # try weakness column if exists
    if 'weakness' in row and row['weakness'] and str(row['weakness']).strip():
        weakness = float(row['weakness'])
    else:
        # fallback: parse weakness_context_json for canonical_topic
        try:
            ctx = json.loads(row['weakness_context_json'])
            # weakness for this row's topic
            weakness = float(ctx.get(row['canonical_topic'], 0.3))
        except:
            weakness = 0.3
    return recommendation_score(
        weakness=weakness,
        lecture_coverage=float(row['lecture_coverage']),
        tutorial_evidence=float(row['tutorial_evidence']),
        exam_relevance=float(row['exam_relevance']),
        bloom_gap=float(row['bloom_gap']),
        weights=w
    )

# Current default
default = ScoreWeights()
print(f"Default weights: {default.as_dict()}")

def evaluate(w: ScoreWeights):
    ndcgs = []
    precs = []
    for snap_id, rows in batches.items():
        # score and rank
        scored = [(score_row(r, w), r['would_use'].strip().lower()=='true', int(r['rating_overall']) if r['rating_overall'].strip() else 3) for r in rows]
        scored.sort(key=lambda x: x[0], reverse=True)
        # binary relevance for NDCG/P
        rel = [x[1] for x in scored]
        # graded for NDCG graded: use rating_overall as gain
        # Use binary NDCG for simplicity (would_use)
        ndcgs.append(ndcg_at_k(rel, k=5))
        precs.append(precision_at_k(rel, k=5))
    return sum(ndcgs)/len(ndcgs), sum(precs)/len(precs)

ndcg0, prec0 = evaluate(default)
print(f"Default: NDCG@5 {ndcg0:.4f} P@5 {prec0:.4f}")

# Grid search over simplex: step 0.05
best = (ndcg0, prec0, default)
candidates = []
steps = [0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]
# brute force 5-dim simplex sum 1.0 with step 0.05 is huge, so random search 5000 samples + hill around default
import random
random.seed(42)
for _ in range(8000):
    # Dirichlet-like: sample 5 random and normalize
    raw = [random.random() for _ in range(5)]
    s = sum(raw)
    w = ScoreWeights(weakness=raw[0]/s, lecture_coverage=raw[1]/s, tutorial_evidence=raw[2]/s, exam_relevance=raw[3]/s, bloom_gap=raw[4]/s)
    # round to 2 decimals for stability and renormalize exactly
    raw_w = [w.weakness, w.lecture_coverage, w.tutorial_evidence, w.exam_relevance, w.bloom_gap]
    total_raw = sum(raw_w)
    raw_w = [x/total_raw for x in raw_w]
    w = ScoreWeights(weakness=round(raw_w[0],3), lecture_coverage=round(raw_w[1],3), tutorial_evidence=round(raw_w[2],3), exam_relevance=round(raw_w[3],3), bloom_gap=round(raw_w[4],3))
    # fix rounding drift
    s = sum(w.as_dict().values())
    if abs(s - 1.0) > 0.001:
        w = ScoreWeights(weakness=w.weakness + (1.0 - s), lecture_coverage=w.lecture_coverage, tutorial_evidence=w.tutorial_evidence, exam_relevance=w.exam_relevance, bloom_gap=w.bloom_gap)
        if not (0 <= w.weakness <= 1 and w.validates()): continue
    if not w.validates(): continue
    ndcg, prec = evaluate(w)
    candidates.append((ndcg, prec, w))
    if ndcg > best[0] or (ndcg == best[0] and prec > best[1]):
        best = (ndcg, prec, w)

# also grid near default with step 0.05 brute for interpretability
for w1 in [0.25,0.30,0.35,0.40,0.45,0.50]:
    for w2 in [0.10,0.15,0.20,0.25]:
        for w3 in [0.10,0.15,0.20]:
            for w4 in [0.05,0.10,0.15,0.20]:
                w5 = 1.0 - (w1+w2+w3+w4)
                if 0 <= w5 <= 0.30:
                    w = ScoreWeights(weakness=w1, lecture_coverage=w2, tutorial_evidence=w3, exam_relevance=w4, bloom_gap=w5)
                    ndcg, prec = evaluate(w)
                    if ndcg > best[0] or (ndcg == best[0] and prec > best[1]):
                        best = (ndcg, prec, w)

print(f"\nBest: NDCG@5 {best[0]:.4f} P@5 {best[1]:.4f} weights {best[2].as_dict()}")
print(f"Gain over default: NDCG +{best[0]-ndcg0:.4f} P +{best[1]-prec0:.4f}")

# Show top 5 candidates
cands_sorted = sorted(candidates, key=lambda x: (x[0], x[1]), reverse=True)[:5]
print("\nTop 5:")
for ndcg, prec, w in cands_sorted:
    print(f" NDCG {ndcg:.4f} P {prec:.4f} {w.as_dict()}")

# Also evaluate on lec02 as validation
r1_val = load('datasets/bloom_dataset/usefulness_workshop_50_lec02.csv')
batches_val = defaultdict(list)
for row in r1_val:
    batches_val[row['analytics_snapshot_id']].append(row)
def evaluate_val(w):
    ndcgs=[]
    precs=[]
    for rows in batches_val.values():
        scored=[(score_row(r,w), r['would_use'].strip().lower()=='true') for r in rows]
        scored.sort(key=lambda x: x[0], reverse=True)
        rel=[x[1] for x in scored]
        ndcgs.append(ndcg_at_k(rel,k=5))
        precs.append(precision_at_k(rel,k=5))
    return sum(ndcgs)/len(ndcgs), sum(precs)/len(precs)

ndcg_val, prec_val = evaluate_val(best[2])
ndcg_val0, prec_val0 = evaluate_val(default)
print(f"\nValidation lec02 - Default NDCG {ndcg_val0:.4f} P {prec_val0:.4f}")
print(f"Validation lec02 - Tuned   NDCG {ndcg_val:.4f} P {prec_val:.4f}")

# Write tuned weights to config suggestion
print(f"\nSuggested patch for app/analytics/recommendation_score.py:DEFAULT_WEIGHTS:")
print(f"DEFAULT_WEIGHTS = ScoreWeights(weakness={best[2].weakness}, lecture_coverage={best[2].lecture_coverage}, tutorial_evidence={best[2].tutorial_evidence}, exam_relevance={best[2].exam_relevance}, bloom_gap={best[2].bloom_gap})")
