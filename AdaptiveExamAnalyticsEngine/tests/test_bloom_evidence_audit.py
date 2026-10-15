"""Diagnostic arithmetic only: these fixture labels do not validate a model."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location('bloom_audit', Path(__file__).resolve().parents[1] / 'scripts/audit_bloom_evidence.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class EvidenceTests(unittest.TestCase):
    def test_confusion_and_absent_class(self):
        result = audit.agreement(['Remember', 'Remember', 'Apply'], ['Remember', 'Apply', 'Apply'])
        self.assertEqual(result['agreement'], 2 / 3)
        self.assertEqual(result['confusion_rows_target_columns_prediction'][0][2], 1)
        self.assertEqual(result['per_class']['Remember']['recall'], 0.5)
        self.assertEqual(result['per_class']['Evaluate']['support'], 0)
        self.assertAlmostEqual(result['macro_f1_all_six'], 2 / 9)

    def test_invalid_pairs_are_rejected(self):
        for targets, predictions in [([], []), (['Apply'], []), (['BT3'], ['Apply'])]:
            with self.assertRaises(ValueError):
                audit.agreement(targets, predictions)

    def test_normalization_retains_punctuation(self):
        self.assertEqual(audit.normalize('  Define\n SQL. '), 'define sql.')
        self.assertNotEqual(audit.normalize('SQL?'), audit.normalize('SQL.'))

    def test_csv_quoted_newline_is_one_record(self):
        path = Mock()
        path.read_bytes.return_value = b'Questions,Category\n"Define\nSQL",BT1\nDefine SQL,BT2\n'
        rows, grouped, evidence = audit.csv_evidence(path)
        self.assertEqual(len(rows), 2)
        self.assertEqual(grouped['define sql'], {'BT1', 'BT2'})
        self.assertEqual(evidence['conflicting_label_texts'], 1)
