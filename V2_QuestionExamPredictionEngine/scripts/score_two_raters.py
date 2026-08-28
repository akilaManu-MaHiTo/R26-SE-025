import csv, io, pathlib, json, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app.evaluation.metrics import cohen_kappa, ndcg_at_k, precision_at_k

def load(p):
    raw = pathlib.Path(p).read_bytes().decode('utf-8', errors='replace')
    # replace smart quotes that snuck in from Excel
    raw = raw.replace('\u201c','"').replace('\u201d','"').replace('\ufffd','')
    rows = list(csv.DictReader(io.StringIO(raw)))
    return rows

import os
# auto-detect: prefer mixed if exists, else original
candidates = [
    ('datasets/bloom_dataset/usefulness_mixed_lec01.csv', 'datasets/bloom_dataset/usefulness_mixed_lec02.csv'),
    ('datasets/bloom_dataset/usefulness_lec01.csv', 'datasets/bloom_dataset/usefulness_lec02.csv'),
]
r1_path = r2_path = None
for a,b in candidates:
    if pathlib.Path(a).exists() and pathlib.Path(b).exists():
        # if mixed has ratings filled (rating_overall not empty), prefer it
        try:
            test = load(a)
            if test and test[0].get('rating_overall','').strip() != '':
                r1_path, r2_path = a, b
                break
        except: pass
        if r1_path is None:
            r1_path, r2_path = a, b
# allow override via args
if len(sys.argv) > 2:
    r1_path, r2_path = sys.argv[1], sys.argv[2]
print(f"scoring {r1_path} vs {r2_path}")
r1 = load(r1_path)
r2 = load(r2_path)
print(f"loaded r1={len(r1)} r2={len(r2)}")

def mean(k, rows): return sum(int(r[k]) for r in rows)/len(rows)

for k in ['rating_overall','rating_weakness_fit','rating_curriculum_fit','rating_difficulty_fit','rating_clarity']:
    print(f"{k:22} lec01 {mean(k,r1):.2f}  lec02 {mean(k,r2):.2f}  diff {mean(k,r2)-mean(k,r1):+.2f}")

# kappas
print("kappa would_use", cohen_kappa([r['would_use'].strip().lower() for r in r1],[r['would_use'].strip().lower() for r in r2]))
print("kappa would_edit", cohen_kappa([r['would_edit'].strip().lower() for r in r1],[r['would_edit'].strip().lower() for r in r2]))
print("kappa overall exact", cohen_kappa([r['rating_overall'].strip() for r in r1],[r['rating_overall'].strip() for r in r2]))
a_bin=['high' if int(r['rating_overall'])>=4 else 'low' for r in r1]
b_bin=['high' if int(r['rating_overall'])>=4 else 'low' for r in r2]
print("kappa overall binned >=4", cohen_kappa(a_bin,b_bin))
print("kappa weakness_fit", cohen_kappa([r['rating_weakness_fit'].strip() for r in r1],[r['rating_weakness_fit'].strip() for r in r2]))
print("kappa difficulty", cohen_kappa([r['rating_difficulty_fit'].strip() for r in r1],[r['rating_difficulty_fit'].strip() for r in r2]))
print("kappa clarity", cohen_kappa([r['rating_clarity'].strip() for r in r1],[r['rating_clarity'].strip() for r in r2]))

# precision as retrieval: all would_use true => 1.0, not discriminative
a_would=[r['would_use'].strip().lower()=='true' for r in r1]
print("P@5", precision_at_k(a_would,5), "NDCG@5", ndcg_at_k(a_would,5))
print("would_edit lec01 true", sum(1 for r in r1 if r['would_edit'].strip().lower()=='true'), "/10")
print("would_edit lec02 true", sum(1 for r in r2 if r['would_edit'].strip().lower()=='true'), "/10")
print("\nweakness_fit lec01", [r['rating_weakness_fit'] for r in r1])
print("weakness_fit lec02", [r['rating_weakness_fit'] for r in r2])
print("overall lec01", [r['rating_overall'] for r in r1])
print("overall lec02", [r['rating_overall'] for r in r2])
