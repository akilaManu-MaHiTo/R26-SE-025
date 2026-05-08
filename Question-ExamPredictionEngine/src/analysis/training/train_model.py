import json
from pathlib import Path

from sentence_transformers import InputExample, SentenceTransformer, losses
from torch.utils.data import DataLoader


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_PATH = PROJECT_ROOT / "data" / "train_data_v2.json"
MODEL_OUTPUT_PATH = PROJECT_ROOT / "model" / "similarity" / "exam_similarity_model"

# Load dataset
if not DATA_PATH.exists() or DATA_PATH.stat().st_size == 0:
    raise ValueError(f"Training data file is missing or empty: {DATA_PATH}")

with DATA_PATH.open("r", encoding="utf-8") as f:
    data = json.load(f)

# Convert to training format
train_examples = []
for item in data:
    train_examples.append(
        InputExample(
            texts=[item["model_answer"], item["student_answer"]],
            label=float(item["score"])
        )
    )

# Load pre-trained model
model = SentenceTransformer("all-MiniLM-L6-v2")

# Create DataLoader
train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=4)

# Loss function
train_loss = losses.CosineSimilarityLoss(model)

# Train model
model.fit(
    train_objectives=[(train_dataloader, train_loss)],
    epochs=5,
    warmup_steps=10,
    show_progress_bar=True
)

# Save model
model.save(str(MODEL_OUTPUT_PATH))

print("Model training complete and saved!")