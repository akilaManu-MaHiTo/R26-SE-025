import sys, pathlib, csv, io, json, random
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app.analytics.recommendation_score import ScoreWeights, recommendation_score
import math

def load(p):
    raw = pathlib.Path(p).read_bytes().decode('utf-8', errors='replace').replace('\u201c','"').replace('\u201d','"')
    return list(csv.DictReader(io.StringIO(raw)))

r1 = load('datasets/bloom_dataset/usefulness_workshop_50_lec01.csv')
print(len(r1))

from collections import defaultdict
batches = defaultdict(list)
for row in r1:
    batches[row['analytics_snapshot_id']].append(row)

def score_row(row, w):
    try:
        ctx=json.loads(row['weakness_context_json'])
        weakness=float(ctx.get(row['canonical_topic'],0.3))
    except: weakness=0.3
    return recommendation_score(weakness, float(row['lecture_coverage']), float(row['tutorial_evidence']), float(row['exam_relevance']), float(row['bloom_gap']), w)

def dcg_graded(ranked_ratings):
    # ranked by score, ratings are graded gain
    return sum((2**r -1)/math.log2(i+2) for i,r in enumerate(ranked_ratings))

def ndcg_graded(ratings_by_rank):
    dcg = dcg_graded(ratings_by_rank)
    ideal = sorted(ratings_by_rank, reverse=True)
    idcg = dcg_graded(ideal)
    return dcg/idcg if idcg else 0

default = ScoreWeights()
def eval_graded(w):
    ndccs=[]
    for rows in batches.values():
        scored=[(score_row(r,w), int(r['rating_overall']) if r['rating_overall'].strip() else 3) for r in rows]
        scored.sort(key=lambda x: x[0], reverse=True)
        ratings=[x[1] for x in scored]
        ndccs.append(ndcg_graded(ratings))
    return sum(ndccs)/len(ndccs)

print(f"default graded NDCG {eval_graded(default):.4f}")

# random search for graded
best=eval_graded(default)
best_w=default
random.seed(1)
for _ in range(10000):
    raw=[random.random() for _ in range(5)]
    s=sum(raw)
    w=ScoreWeights(*[round(x/s,3) for x in raw])
    # fix sum
    tot=sum(w.as_dict().values())
    if abs(tot-1.0)>0.001:
        w=ScoreWeights(weakness=w.weakness+(1-tot), lecture_coverage=w.lecture_coverage, tutorial_evidence=w.tutorial_evidence, exam_relevance=w.exam_relevance, bloom_gap=w.bloom_gap)
        if not w.validates(): continue
    val=eval_graded(w)
    if val>best:
        best=val
        best_w=w
print(f"best graded NDCG {best:.4f} weights {best_w.as_dict()} gain {best-eval_graded(default):+.4f}")

# also correlation with rating_overall
import numpy as np
def spearman(w):
    scores=[]
    ratings=[]
    for rows in batches.values():
        for r in rows:
            scores.append(score_row(r,w))
            ratings.append(int(r['rating_overall']) if r['rating_overall'].strip() else 3)
    # rank correlation
    # simple pearson
    if len(set(scores))==1: return 0
    return float(np.corrcoef(scores, ratings)[0,1])

print(f"default pearson {spearman(default):.4f} best pearson {spearman(best_w):.4f}")
