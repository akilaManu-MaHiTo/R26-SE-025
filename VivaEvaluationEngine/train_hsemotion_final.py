# =============================================================================
# train_hsemotion_final.py
# HSEmotion Fine-Tuning Pipeline — Final Version
# =============================================================================

import os
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import (
    DataLoader,
    ConcatDataset,
    WeightedRandomSampler,
)
from torchvision import datasets, transforms
import timm
import numpy as np

# ── paths ────────────────────────────────────────────────────
RAFDB_TRAIN   = "data/RAF-DB/train"
RAFDB_TEST    = "data/RAF-DB/test"
FERPLUS_TRAIN = "data/FERPlus/train"
VIVA_DIR      = "data/viva_faces"

PRETRAINED    = "models/enet_b0_8_best_afew.pt"
SAVE_PT       = "models/hsemotion_improved.pt"
SAVE_ONNX     = "models/hsemotion_improved.onnx"

# ── hyperparameters ─────────────────────────────────────────
BATCH         = 128
LR            = 5e-5

EPOCHS_P1     = 5
EPOCHS_P2     = 15
EPOCHS_P3     = 5

PATIENCE      = 3
MAX_SAMPLES   = 50000

# ── unified class map ───────────────────────────────────────
CLASS_MAP = {
    "neutral":  0,
    "happy":    1,
    "sad":      2,
    "surprise": 3,
    "fear":     4,
    "disgust":  5,
    "anger":    6,
    "contempt": 7,
}

NUM_CLASSES = len(CLASS_MAP)

IDX_TO_CLASS = {
    v: k for k, v in CLASS_MAP.items()
}

FOLDER_ALIASES = {
    "happiness": "happy",
    "angry": "anger",
    "sadness": "sad",
}

if not torch.cuda.is_available():
    raise RuntimeError(
        "CUDA is required for this training script. "
        "Install a CUDA-enabled PyTorch build and run on a GPU system."
    )
device = torch.device("cuda")

torch.backends.cudnn.benchmark = True
torch.backends.cuda.matmul.allow_tf32 = True
torch.set_float32_matmul_precision("high")

print(f"Device: {device}")

# ── dataset ─────────────────────────────────────────────────
class MappedImageFolder(datasets.ImageFolder):

    def __init__(self, root, transform=None):
        super().__init__(root, transform=transform)

        self._remap = {}

        for folder_name, ds_idx in self.class_to_idx.items():

            canonical = folder_name.lower().strip()
            canonical = FOLDER_ALIASES.get(canonical, canonical)

            self._remap[ds_idx] = CLASS_MAP.get(canonical, -1)

    def __getitem__(self, index):
        img, original_label = super().__getitem__(index)

        mapped_label = self._remap.get(original_label, -1)

        return img, mapped_label

    def get_valid_indices(self):

        return [
            i for i, (_, lbl) in enumerate(self.samples)
            if self._remap.get(lbl, -1) != -1
        ]

# ── dataloader helper ───────────────────────────────────────
def make_loader(dataset, batch_size, shuffle=True, sampler=None):

    valid_idx = dataset.get_valid_indices()

    subset = torch.utils.data.Subset(dataset, valid_idx)

    return DataLoader(
        subset,
        batch_size=batch_size,
        shuffle=(shuffle and sampler is None),
        sampler=sampler,
        num_workers=min(8, max(2, (os.cpu_count() or 4) // 2)),
        pin_memory=True,
        persistent_workers=True,
        prefetch_factor=4,
    )

# ── balanced sampler ────────────────────────────────────────
def combined_sampler(raf_ds, ferplus_ds):

    def get_targets(ds):

        valid = ds.get_valid_indices()

        return [
            ds._remap[ds.samples[i][1]]
            for i in valid
        ]

    all_targets = (
        get_targets(raf_ds) +
        get_targets(ferplus_ds)
    )

    counts = np.bincount(
        all_targets,
        minlength=NUM_CLASSES
    ).astype(float)

    counts = np.where(counts == 0, 1, counts)

    weights = [
        1.0 / counts[t]
        for t in all_targets
    ]

    return WeightedRandomSampler(
        weights,
        num_samples=min(len(all_targets), MAX_SAMPLES),
        replacement=True,
    )

# ── transforms ──────────────────────────────────────────────
train_tf = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomRotation(10),

    transforms.ColorJitter(
        brightness=0.3,
        contrast=0.3,
        saturation=0.2,
    ),

    transforms.RandomGrayscale(p=0.1),

    transforms.ToTensor(),

    transforms.Normalize(
        [0.485, 0.456, 0.406],
        [0.229, 0.224, 0.225],
    ),

    transforms.RandomErasing(p=0.2),
])

val_tf = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),

    transforms.Normalize(
        [0.485, 0.456, 0.406],
        [0.229, 0.224, 0.225],
    ),
])

# ── loss ────────────────────────────────────────────────────
class LabelSmoothLoss(nn.Module):

    def __init__(
        self,
        classes,
        smoothing=0.1,
        weight=None
    ):
        super().__init__()

        self.smoothing = smoothing
        self.cls = classes
        self.weight = weight

    def forward(self, pred, target):
        confidence = 1.0 - self.smoothing

        smooth_val = self.smoothing / (self.cls - 1)

        one_hot = torch.full_like(pred, smooth_val)

        one_hot.scatter_(
            1,
            target.unsqueeze(1),
            confidence
        )

        log_prob = F.log_softmax(pred, dim=1)

        loss = -(one_hot * log_prob).sum(dim=1)

        if self.weight is not None:

            w = self.weight.to(pred.device)

            loss = loss * w[target]

        return loss.mean()

# ── class weights ───────────────────────────────────────────
def compute_class_weights(dataset):

    valid_idx = dataset.get_valid_indices()

    targets = [
        dataset._remap[dataset.samples[i][1]]
        for i in valid_idx
    ]

    counts = np.bincount(
        targets,
        minlength=NUM_CLASSES
    ).astype(float)

    counts = np.where(counts == 0, 1, counts)

    weights = 1.0 / counts

    weights = (
        weights / weights.sum()
    ) * NUM_CLASSES

    return torch.tensor(
        weights,
        dtype=torch.float
    )

# ── build model ─────────────────────────────────────────────
def build_model():

    model = timm.create_model(
        "efficientnet_b0",
        pretrained=False,
        num_classes=NUM_CLASSES,
    )

    try:
        checkpoint = torch.load(
            PRETRAINED,
            map_location="cpu",
            weights_only=False,
        )
    except TypeError:
        checkpoint = torch.load(
            PRETRAINED,
            map_location="cpu"
        )

    if isinstance(checkpoint, nn.Module):
        state_dict = checkpoint.state_dict()
    elif isinstance(checkpoint, dict) and "state_dict" in checkpoint:
        state_dict = checkpoint["state_dict"]
    else:
        state_dict = checkpoint

    if any(key.startswith("classifier.0.") for key in state_dict):
        state_dict = {
            key.replace("classifier.0.", "classifier.", 1): value
            for key, value in state_dict.items()
        }

    model.load_state_dict(state_dict, strict=True)

    return model.to(device)

# ── evaluation ──────────────────────────────────────────────
def evaluate(model, data_dir, label):

    ds = MappedImageFolder(
        data_dir,
        transform=val_tf
    )

    loader = make_loader(
        ds,
        batch_size=64,
        shuffle=False
    )

    model.eval()

    correct = 0
    total = 0

    per_c = [0] * NUM_CLASSES
    per_t = [0] * NUM_CLASSES

    with torch.no_grad():

        for x, y in loader:

            x = x.to(device, non_blocking=True)
            y = y.to(device, non_blocking=True)

            preds = model(x).argmax(dim=1)

            for p, t in zip(preds.cpu(), y.cpu()):

                per_c[t.item()] += int(p == t)
                per_t[t.item()] += 1

            correct += (preds == y).sum().item()
            total += y.size(0)

    overall = 100 * correct / total

    print(f"\n{label}: {overall:.1f}%")

    for idx, cls in IDX_TO_CLASS.items():

        n = per_t[idx]

        acc = (
            100 * per_c[idx] / n
            if n > 0 else 0
        )

        print(
            f"{cls:<12} {acc:.1f}% ({n} samples)"
        )

    return overall

# ── training phase ──────────────────────────────────────────
def run_phase(
    model,
    loader,
    val_loader,
    criterion,
    scaler,
    lr,
    n_epochs,
    phase_name,
    freeze_backbone=False,
):

    if freeze_backbone:

        for name, p in model.named_parameters():

            p.requires_grad = (
                "classifier" in name
            )

    else:

        for p in model.parameters():
            p.requires_grad = True

    optimiser = torch.optim.AdamW(
        filter(
            lambda p: p.requires_grad,
            model.parameters()
        ),
        lr=lr,
        weight_decay=1e-4,
    )

    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimiser,
        T_max=n_epochs
    )

    best_acc = 0.0
    patience_left = PATIENCE

    print(f"\n{'='*50}")
    print(phase_name)
    print(f"{'='*50}")

    for epoch in range(n_epochs):

        model.train()

        loss_sum = 0.0

        for x, y in loader:

            x = x.to(device, non_blocking=True)
            y = y.to(device, non_blocking=True)
            optimiser.zero_grad()

            with torch.amp.autocast(
                device_type="cuda",
                enabled=True
            ):
                loss = criterion(model(x), y)

            scaler.scale(loss).backward()

            scaler.unscale_(optimiser)

            torch.nn.utils.clip_grad_norm_(
                model.parameters(),
                1.0
            )

            scaler.step(optimiser)
            scaler.update()

            loss_sum += loss.item()

        scheduler.step()

        # validation
        model.eval()

        correct = 0
        total = 0

        with torch.no_grad():

            for x, y in val_loader:

                x = x.to(device, non_blocking=True)
                y = y.to(device, non_blocking=True)

                preds = model(x).argmax(1)

                correct += (
                    preds == y
                ).sum().item()

                total += y.size(0)

        val_acc = 100 * correct / total

        improved = val_acc > best_acc

        print(
            f"Epoch {epoch+1}/{n_epochs} | "
            f"loss={loss_sum/len(loader):.4f} | "
            f"val={val_acc:.1f}%"
        )

        if improved:

            best_acc = val_acc

            patience_left = PATIENCE

            torch.save(
                model.state_dict(),
                SAVE_PT
            )

            print("→ model saved")

        else:

            patience_left -= 1

            if patience_left == 0:

                print(
                    f"Early stopping triggered "
                    f"({PATIENCE} epochs no improvement)"
                )

                break

    if os.path.exists(SAVE_PT):
        model.load_state_dict(
            torch.load(
                SAVE_PT,
                map_location=device,
                weights_only=True,
            )
        )

    return model, best_acc

# ── phase 3 viva adaptation ─────────────────────────────────
def phase3_viva(model, criterion, scaler):

    if not os.path.exists(VIVA_DIR):

        print(
            "\nPhase 3 skipped "
            "(viva dataset missing)"
        )

        return model

    viva_ds = MappedImageFolder(
        VIVA_DIR,
        transform=train_tf
    )

    if len(viva_ds.get_valid_indices()) < 50:

        print(
            f"\nPhase 3 skipped "
            f"({len(viva_ds.get_valid_indices())} images)"
        )

        return model

    loader = make_loader(
        viva_ds,
        batch_size=16,
        shuffle=True
    )

    optimiser = torch.optim.AdamW(
        model.parameters(),
        lr=LR / 20,
        weight_decay=1e-4,
    )

    print(f"\n{'='*50}")
    print("Phase 3 — Viva Domain Adaptation")
    print(f"{'='*50}")

    for epoch in range(EPOCHS_P3):

        model.train()

        loss_sum = 0.0

        for x, y in loader:

            x = x.to(device, non_blocking=True)
            y = y.to(device, non_blocking=True)

            optimiser.zero_grad()

            with torch.amp.autocast(
                device_type="cuda",
                enabled=True
            ):
                loss = criterion(model(x), y)

            scaler.scale(loss).backward()

            scaler.unscale_(optimiser)

            torch.nn.utils.clip_grad_norm_(
                model.parameters(),
                1.0
            )

            scaler.step(optimiser)
            scaler.update()

            loss_sum += loss.item()

        print(
            f"Epoch {epoch+1}/{EPOCHS_P3} | "
            f"loss={loss_sum/len(loader):.4f}"
        )

    torch.save(
        model.state_dict(),
        SAVE_PT
    )

    return model

# ── export onnx ─────────────────────────────────────────────
def export_onnx(model, save_path):

    import onnxruntime as ort

    model.eval()

    dummy = torch.randn(
        1,
        3,
        224,
        224,
        device=device,
    )

    torch.onnx.export(
        model,
        dummy,
        save_path,
        input_names=["face_image"],
        output_names=["emotion_logits"],

        dynamic_axes={
            "face_image": {
                0: "batch_size"
            },
            "emotion_logits": {
                0: "batch_size"
            },
        },

        opset_version=17,
    )

    print(f"\nONNX exported → {save_path}")

    providers = ["CUDAExecutionProvider"]

    sess = ort.InferenceSession(
        save_path,
        providers=providers
    )

    out = sess.run(
        None,
        {
            "face_image": dummy.cpu().numpy()
        }
    )

    print(
        f"ONNX verify OK → {out[0].shape}"
    )

# ── main ────────────────────────────────────────────────────
def train():

    os.makedirs("models", exist_ok=True)

    print("\nLoading datasets...")

    raf_ds = MappedImageFolder(
        RAFDB_TRAIN,
        transform=train_tf
    )

    ferplus_ds = MappedImageFolder(
        FERPLUS_TRAIN,
        transform=train_tf
    )

    combined = ConcatDataset([
        raf_ds,
        ferplus_ds
    ])

    print(
        f"RAF-DB: "
        f"{len(raf_ds.get_valid_indices())}"
    )

    print(
        f"FERPlus: "
        f"{len(ferplus_ds.get_valid_indices())}"
    )

    sampler = combined_sampler(
        raf_ds,
        ferplus_ds
    )

    train_loader = DataLoader(
        combined,
        batch_size=BATCH,
        sampler=sampler,
        drop_last=True,
        num_workers=2,
        pin_memory=True,
    )

    val_loader = make_loader(

        MappedImageFolder(
            RAFDB_TEST,
            transform=val_tf
        ),

        batch_size=64,
        shuffle=False,
    )

    class_weights = compute_class_weights(raf_ds)

    criterion = LabelSmoothLoss(
        NUM_CLASSES,
        smoothing=0.1,
        weight=class_weights,
    )

    scaler = torch.amp.GradScaler(
        "cuda",
        enabled=True
    )

    model = build_model()

    evaluate(
        model,
        RAFDB_TEST,
        "BEFORE fine-tune"
    )

    # Phase 1
    model, _ = run_phase(
        model,
        train_loader,
        val_loader,
        criterion,
        scaler,

        lr=LR,

        n_epochs=EPOCHS_P1,

        phase_name="Phase 1 — Head Only",

        freeze_backbone=True,
    )

    # Phase 2
    model, _ = run_phase(
        model,
        train_loader,
        val_loader,
        criterion,
        scaler,

        lr=LR / 5,

        n_epochs=EPOCHS_P2,

        phase_name="Phase 2 — Full Fine-Tune",

        freeze_backbone=False,
    )

    # Phase 3
    model = phase3_viva(
        model,
        criterion,
        scaler
    )

    evaluate(
        model,
        RAFDB_TEST,
        "AFTER fine-tune"
    )

    export_onnx(
        model,
        SAVE_ONNX
    )

    print("\nTraining complete")

    print(f"PyTorch → {SAVE_PT}")
    print(f"ONNX → {SAVE_ONNX}")

if __name__ == "__main__":
    train()