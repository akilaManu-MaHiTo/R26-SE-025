"""Offline artifact diagnostics; requested generator targets are NOT gold labels."""
import csv
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEVELS = ('Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create')


def normalize(text):
    return re.sub(r'\s+', ' ', text).strip().casefold()


def csv_evidence(path):
    raw = path.read_bytes()
    rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    grouped = defaultdict(set)
    for row in rows:
        grouped[normalize(row['Questions'])].add(row['Category'])
    return rows, grouped, {
        'rows': len(rows), 'unique_normalized_texts': len(grouped),
        'duplicate_rows': len(rows) - len(grouped),
        'conflicting_label_texts': sum(len(labels) > 1 for labels in grouped.values()),
        'label_counts': dict(Counter(row['Category'] for row in rows)),
        'sha256': hashlib.sha256(raw).hexdigest(),
    }


def agreement(targets, predictions):
    if len(targets) != len(predictions) or not targets:
        raise ValueError('Require equal, nonempty paired labels')
    if any(label not in LEVELS for label in targets + predictions):
        raise ValueError('Unknown Bloom label')
    matrix = [[sum(t == a and p == b for t, p in zip(targets, predictions))
               for b in LEVELS] for a in LEVELS]
    per_class = {}
    for i, label in enumerate(LEVELS):
        support, predicted, tp = sum(matrix[i]), sum(row[i] for row in matrix), matrix[i][i]
        precision = tp / predicted if predicted else 0.0
        recall = tp / support if support else 0.0
        per_class[label] = {'support': support, 'predicted': predicted,
                            'precision': precision, 'recall': recall,
                            'f1': 2 * tp / (support + predicted) if support + predicted else 0.0}
    return {'n': len(targets), 'agreement': sum(t == p for t, p in zip(targets, predictions)) / len(targets),
            'macro_f1_all_six': sum(v['f1'] for v in per_class.values()) / 6,
            'per_class': per_class, 'confusion_rows_target_columns_prediction': matrix}


def main():
    directory = ROOT / 'datasets/bloom_dataset/bloom'
    _, source, source_info = csv_evidence(directory / 'blooms_taxonomy_dataset.csv')
    gold_rows, gold, gold_info = csv_evidence(directory / 'gold_bloom_v2.csv')
    overlap = set(source) & set(gold)
    output = {'interpretation': 'Stored evidence only; no model inference, no held-out accuracy claim.',
              'source_csv': source_info, 'gold_v2_csv': gold_info,
              'gold_v1_bytes': (directory / 'gold_bloom_v1.csv').stat().st_size,
              'source_gold_v2_overlap': {'normalized_texts': len(overlap),
                  'gold_rows_matching_source': sum(normalize(r['Questions']) in source for r in gold_rows),
                  'label_set_disagreements': sum(source[t] != gold[t] for t in overlap)},
              'pilots': {}}
    for path in sorted((ROOT / 'docs/validation/bloom_20').rglob('bloom_results.json')):
        raw = path.read_bytes()
        document = json.loads(raw.decode('utf-8'))
        items = document['items']
        report = {'sha256': hashlib.sha256(raw).hexdigest(),
                  'gold_status': document['metadata'].get('lecturer_gold_labels_status'), 'roles': {}}
        for role in ('question_bloom', 'student_answer_bloom', 'combined_bloom'):
            paired = [item for item in items if role in item]
            if not paired:
                continue
            report['roles'][role] = {
                'prediction_counts': dict(Counter(item[role]['level'] for item in paired)),
                'low_confidence_below_0_6': sum(item[role]['confidence'] < 0.6 for item in paired),
                'truncated': sum(item[role].get('truncated', False) for item in paired),
                'input_hash_mismatches': sum(
                    item[role].get('input_sha256') != hashlib.sha256(item[
                        {'question_bloom': 'text', 'student_answer_bloom': 'student_answer',
                         'combined_bloom': 'combined_bloom_input'}[role]].encode('utf-8')).hexdigest()
                    for item in paired if 'input_sha256' in item[role]),
                'requested_target_agreement_NOT_accuracy': agreement(
                    [item['requested_bloom'] for item in paired], [item[role]['level'] for item in paired])}
        output['pilots'][str(path.relative_to(ROOT)).replace('\\', '/')] = report
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
