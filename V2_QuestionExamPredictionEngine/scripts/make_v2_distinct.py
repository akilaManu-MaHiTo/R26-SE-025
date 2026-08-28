import sys, pathlib, random, csv, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app.services.recommendation import recommend_questions
from app.evaluation.metrics import write_usefulness_labeling_template

# New profiles targeting generated gaps + distinct from gold (gold used SQL/Schema/Security/Programming/Intro)
profiles = [
    ("IT2040@Final2023_C1_JDBCweak_Apply", {'Java Database Connectivity (JDBC)': 40, 'Database Security': 80, 'Structured Query Language (SQL)': 85}),
    ("IT2040@Final2023_C2_IndexesWeak_Analyze", {'Database Indexes and Storage Structures': 38, 'Schema Refinement': 78, 'Database Security': 85}),
    ("IT2040@Final2023_C3_TransactWeak_Analyze", {'Database Transaction Management and Concurrency Control': 41, 'Structured Query Language (SQL)': 80, 'Logical Database Design': 75}),
    ("IT2040@Final2023_C4_RecoveryWeak_Understand", {'Database Recovery and Log Management': 42, 'Database Utilities': 78, 'Structured Query Language (SQL)': 82}),
    ("IT2040@Final2023_C5_UtilitiesWeak_Apply", {'Database Utilities': 44, 'Database Security': 82, 'Schema Refinement': 78}),
]

import csv as _csv
gold_ids = set(r['question_id'] for r in _csv.DictReader(open('datasets/bloom_dataset/gold_workshop_50_lec01.csv', encoding='utf-8')))
print(f"gold has {len(gold_ids)} ids, will avoid duplicates")

all_rows=[]
for snap_id, weak_map in profiles:
    doc={'topic_performance':[{'topic':k,'average_percentage':v} for k,v in weak_map.items()],
         'bloom_performance':[{'level':'Apply','average_percentage':48},{'level':'Analyze','average_percentage':42}]}
    recs=recommend_questions(doc, limit=20)  # get 20 to have pool to deduplicate
    # filter out gold ids, pick top 5 unique
    uniq = [r for r in recs if r['question_id'] not in gold_ids and r['question_id'] not in {x['question_id'] for x in all_rows}]
    # if not enough, allow gold but prioritize new
    if len(uniq) <5:
        uniq += [r for r in recs if r['question_id'] not in {x['question_id'] for x in all_rows}][:5-len(uniq)]
    # need 5 weak-targeted, take top 5 uniq
    weak_top = uniq[:5]
    # strong distractors: least weak topic
    from app.services.weakness_scoring import weakness_for_document
    weak_ctx={k:v['weakness'] for k,v in weakness_for_document(doc)['weakness_scores'].items()}
    strong_topic=min(weak_ctx, key=lambda k: weak_ctx[k])
    from app.ingestion.question_bank import build_question_bank
    bank=build_question_bank()
    strong_cands=[r for r in bank if r['canonical_topic']==strong_topic and r['source_type'] in ('tutorial','generated') and r['question_id'] not in gold_ids and r['question_id'] not in {x['question_id'] for x in all_rows}]
    if len(strong_cands)<5:
        strong_cands+= [r for r in bank if r['source_type'] in ('tutorial','generated') and r['question_id'] not in gold_ids][:5-len(strong_cands)]
    strong_cands=strong_cands[:5]
    mixed=[]
    for r in weak_top:
        mixed.append(r)
    for cand in strong_cands:
        mixed.append({'question_id':cand['question_id'],'text':cand['text'],'canonical_topic':cand['canonical_topic'],'bloom_level':cand['bloom_level'],'difficulty':cand['difficulty'],'source_type':cand['source_type'],'source_id':cand['source_id'],'subtopic':cand.get('subtopic',''),'recommendation_score': round(0.35*weak_ctx.get(cand['canonical_topic'],0.15)+0.20*1.0+0.15*0.7+0.15*0.5+0.15*0.52,4),'priority':'Low','weakness':weak_ctx.get(cand['canonical_topic'],0.15),'lecture_coverage':1.0,'tutorial_evidence':0.7,'exam_relevance':0.5,'bloom_gap':0.52,'reason':{'weakness_pct':round(weak_ctx.get(cand['canonical_topic'],0.15)*100,1),'lecture':True,'tutorial_count':3,'exam_recent_count':2,'bloom_gap':0.52}})
    random.seed(hash(snap_id)%10000)
    random.shuffle(mixed)
    tmp=f"/tmp/{snap_id}.csv"
    write_usefulness_labeling_template(mixed, snap_id, weak_ctx, tmp, annotator_id='')
    rows=list(_csv.DictReader(open(tmp, encoding='utf-8')))
    all_rows.extend(rows)
    print(f"{snap_id}: weak {max(weak_ctx, key=lambda k: weak_ctx[k])} -> {len(rows)} rows, overlap with gold now {len(set(r['question_id'] for r in all_rows) & gold_ids)}")

out='datasets/bloom_dataset/usefulness_workshop_50_v2_template.csv'
with open(out,'w',newline='',encoding='utf-8') as f:
    w=_csv.DictWriter(f, fieldnames=all_rows[0].keys())
    w.writeheader(); w.writerows(all_rows)
print(f"Wrote {len(all_rows)} distinct v2 to {out}")
from collections import Counter
print(Counter(r['canonical_topic'] for r in all_rows))
print(f"Overlap with gold: {len(set(r['question_id'] for r in all_rows) & gold_ids)} /50")
