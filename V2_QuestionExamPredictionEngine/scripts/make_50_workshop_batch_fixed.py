import sys, pathlib, random, csv
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app.services.recommendation import recommend_questions
from app.evaluation.metrics import write_usefulness_labeling_template
from app.services.weakness_scoring import weakness_for_document

# Only topics with tutorial coverage: SQL, Schema, Security, Programming, Intro
# From Counter: SQL 25, Schema 9, Security 9, Programming 7, Intro 5
profiles = [
    ("IT2040@Final2023_B1_SQLweak_Apply", {'Structured Query Language (SQL)': 45, 'Schema Refinement': 75, 'Database Security': 88, 'bloom':'Apply'}),
    ("IT2040@Final2023_B2_SchemaWeak_Analyze", {'Schema Refinement': 38, 'Structured Query Language (SQL)': 78, 'Database Security': 82, 'bloom':'Analyze'}),
    ("IT2040@Final2023_B3_SecurityWeak_Understand", {'Database Security': 42, 'Structured Query Language (SQL)': 80, 'Schema Refinement': 75, 'bloom':'Understand'}),
    ("IT2040@Final2023_B4_ProgWeak_Apply", {'Database Programming': 40, 'Structured Query Language (SQL)': 85, 'Schema Refinement': 80, 'bloom':'Apply'}),
    ("IT2040@Final2023_B5_IntroWeak_Understand", {'Introduction to DBMS & Conceptual Database Design': 44, 'Structured Query Language (SQL)': 82, 'Schema Refinement': 78, 'bloom':'Understand'}),
]

all_rows=[]
for snap_id, mapping in profiles:
    bloom = mapping.pop('bloom')
    doc={'topic_performance':[{'topic':k,'average_percentage':v} for k,v in mapping.items()],
         'bloom_performance':[{'level':bloom,'average_percentage':42},{'level':'Apply','average_percentage':48}]}
    recs=recommend_questions(doc, limit=10)
    weak_ctx={k:v['weakness'] for k,v in weakness_for_document(doc)['weakness_scores'].items()}
    # mixed 5 weak top + 5 strong distractors (strong = least weak)
    weak_topic=max(weak_ctx, key=lambda k: weak_ctx[k])
    strong_topic=min(weak_ctx, key=lambda k: weak_ctx[k])
    # for mixed: take top5 recs (should be weak_topic) + 5 from strong_topic bank via direct query
    from app.ingestion.question_bank import build_question_bank
    bank=build_question_bank()
    strong_cands=[r for r in bank if r['canonical_topic']==strong_topic and r['source_type']=='tutorial'][:5]
    if len(strong_cands)<5:
        strong_cands+= [r for r in bank if r['source_type']=='tutorial' and r['canonical_topic']!=weak_topic][:5-len(strong_cands)]
    mixed=[]
    for r in recs[:5]:
        mixed.append(r)
    for cand in strong_cands[:5]:
        mixed.append({'question_id':cand['question_id'],'text':cand['text'],'canonical_topic':cand['canonical_topic'],'bloom_level':cand['bloom_level'],'difficulty':cand['difficulty'],'source_type':cand['source_type'],'source_id':cand['source_id'],'subtopic':cand.get('subtopic',''),'recommendation_score': round(0.35*weak_ctx.get(cand['canonical_topic'],0.15)+0.20*1.0+0.15*0.7+0.15*0.5+0.15*0.58,4),'priority':'Low','weakness':weak_ctx.get(cand['canonical_topic'],0.15),'lecture_coverage':1.0,'tutorial_evidence':0.7,'exam_relevance':0.5,'bloom_gap':0.58,'reason':{'weakness_pct':round(weak_ctx.get(cand['canonical_topic'],0.15)*100,1),'lecture':True,'tutorial_count':3,'exam_recent_count':2,'bloom_gap':0.58}})
    random.seed(hash(snap_id)%10000)
    random.shuffle(mixed)
    tmp=f"/tmp/{snap_id}.csv"
    write_usefulness_labeling_template(mixed, snap_id, weak_ctx, tmp, annotator_id='')
    rows=list(csv.DictReader(open(tmp, encoding='utf-8')))
    all_rows.extend(rows)
    print(f"{snap_id}: weak {weak_topic} {weak_ctx[weak_topic]:.2f} -> top {recs[0]['canonical_topic']} {recs[0]['recommendation_score']}")

out='datasets/bloom_dataset/usefulness_workshop_50.csv'
with open(out,'w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f, fieldnames=all_rows[0].keys())
    w.writeheader(); w.writerows(all_rows)
print(f"Wrote {len(all_rows)} rows to {out}")
import shutil
shutil.copy(out,'datasets/bloom_dataset/usefulness_workshop_50_lec01.csv')
shutil.copy(out,'datasets/bloom_dataset/usefulness_workshop_50_lec02.csv')
print("copied to lec01/lec02")
from collections import Counter
print(Counter(r['canonical_topic'] for r in all_rows))
print(Counter(r['analytics_snapshot_id'] for r in all_rows))
