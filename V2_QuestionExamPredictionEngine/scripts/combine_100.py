import csv
def combine(a,b,out):
    ha=open(a, encoding='utf-8').readline()
    ra=open(a, encoding='utf-8').read().split('\n',1)[1]
    rb=open(b, encoding='utf-8').read().split('\n',1)[1]
    open(out,'w', encoding='utf-8').write(ha + ra + rb)
    print(f"combined {a}+{b} -> {out} rows {len(list(csv.DictReader(open(out, encoding='utf-8'))))}")
combine('datasets/bloom_dataset/gold_workshop_50_lec01.csv','datasets/bloom_dataset/usefulness_workshop_50_v3_lec01.csv','datasets/bloom_dataset/combined_100_lec01.csv')
combine('datasets/bloom_dataset/gold_workshop_50_lec02.csv','datasets/bloom_dataset/usefulness_workshop_50_v3_lec02.csv','datasets/bloom_dataset/combined_100_lec02.csv')
import csv
g_ids=set(r['question_id'] for r in csv.DictReader(open('datasets/bloom_dataset/gold_workshop_50_lec01.csv', encoding='utf-8')))
v_ids=set(r['question_id'] for r in csv.DictReader(open('datasets/bloom_dataset/usefulness_workshop_50_v3_lec01.csv', encoding='utf-8')))
print(f"overlap {len(g_ids & v_ids)} unique {len(g_ids | v_ids)} total 100")
