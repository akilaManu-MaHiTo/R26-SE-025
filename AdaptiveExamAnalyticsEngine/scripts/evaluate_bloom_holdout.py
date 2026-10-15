"""Validate a human-labeled external holdout before optional local model inference."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import sys

from audit_bloom_evidence import ROOT, LEVELS, agreement, validate_holdout


def read_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('holdout', type=Path)
    parser.add_argument('--exclude-source', type=Path, action='append', default=[],
                        help='Additional training/tuning CSV; Questions or question_text column')
    parser.add_argument('--evaluate', action='store_true', help='Run frozen local ModernBERT after validation')
    args = parser.parse_args()
    try:
        sources = [ROOT / 'datasets/bloom_dataset/bloom/blooms_taxonomy_dataset.csv', *args.exclude_source]
        excluded = []
        for path in sources:
            source_rows = read_rows(path)
            if not source_rows:
                raise ValueError(f'Exclusion source is empty: {path}')
            column = 'Questions' if 'Questions' in source_rows[0] else 'question_text'
            if any(not (row.get(column) or '').strip() for row in source_rows):
                raise ValueError(f'Exclusion source has missing question text: {path}')
            excluded.extend(row[column] for row in source_rows)
        rows = validate_holdout(read_rows(args.holdout), excluded)
        report = {
            'status': 'text_overlap_and_recorded_labels_checked',
            'limitation': 'Human provenance and semantic near-duplicates require manual review; this check does not prove independence.',
            'holdout': {'path': str(args.holdout), 'sha256': sha256(args.holdout), 'n': len(rows)},
            'excluded_sources': [{'path': str(p), 'sha256': sha256(p)} for p in sources],
            'label_counts': {level: sum(r['bloom_label'] == level for r in rows) for level in LEVELS},
        }
        if args.evaluate:
            os.environ['HF_HUB_OFFLINE'] = '1'
            os.environ['TRANSFORMERS_OFFLINE'] = '1'
            sys.path.insert(0, str(ROOT))
            from app.classifier.bloom_classifier import _model_dir, predict_bloom_batch
            model_dir = _model_dir()
            weights = model_dir / 'bloom.safetensors'
            if not weights.exists():
                weights = model_dir / 'model.safetensors'
            files = [weights, model_dir / 'config.json', *sorted((model_dir / 'tokenizer').glob('*'))]
            report['model_files'] = {str(p.relative_to(model_dir)): sha256(p) for p in files if p.is_file()}
            predictions = []
            for start in range(0, len(rows), 16):
                predictions.extend(predict_bloom_batch([r['question_text'] for r in rows[start:start + 16]]))
            metrics = agreement([r['bloom_label'] for r in rows], [p['level'] for p in predictions])
            metrics['accuracy'] = metrics.pop('agreement')
            metrics['confusion_rows_gold_columns_prediction'] = metrics.pop('confusion_rows_target_columns_prediction')
            report['metrics'] = metrics
            report['predictions'] = [{'question_id': r['question_id'], 'gold': r['bloom_label'], **p}
                                     for r, p in zip(rows, predictions)]
        print(json.dumps(report, indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Holdout rejected: {exc}\n')


if __name__ == '__main__':
    main()
