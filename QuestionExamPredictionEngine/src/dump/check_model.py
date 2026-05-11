import sys
from pathlib import Path
sys.path.insert(0, '.')

from QuestionExamPredictionEngine.src.analytics.weak_topic_model import DEFAULT_MODEL_PATH

model_path = DEFAULT_MODEL_PATH
if model_path.exists():
    import joblib
    payload = joblib.load(model_path)
    print('✓ Model found at:')
    print(f'  {model_path}')
    print(f'\nThreshold: {payload.get("weak_probability_threshold", 0.55)}')
    print(f'Features ({len(payload["feature_names"])}):')
    for f in payload["feature_names"]:
        print(f'  - {f}')
else:
    print(f'✗ No saved model found at {model_path}')
