import csv
import importlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


def run_ocr_on_crops(crops_root: Path):
    try:
        easyocr = importlib.import_module("easyocr")
    except ImportError as exc:
        raise ImportError(
            "easyocr is not installed. Install it with: pip install easyocr"
        ) from exc

    reader = easyocr.Reader(["en"], gpu=True)
    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
    crop_images = [
        p for p in crops_root.rglob("*") if p.is_file() and p.suffix.lower() in image_extensions
    ]

    ocr_rows = []
    for crop_path in sorted(crop_images):
        try:
            # EasyOCR expects a 2D grayscale image in some code paths.
            gray_img = Image.open(crop_path).convert("L")
            gray_array = np.array(gray_img)

            detections = reader.readtext(gray_array, detail=1, paragraph=False)
            text = " ".join(d[1] for d in detections).strip()
            avg_conf = (
                sum(float(d[2]) for d in detections) / len(detections) if detections else 0.0
            )
            ocr_rows.append(
                {
                    "label": crop_path.parent.name,
                    "crop_path": str(crop_path),
                    "text": text,
                    "confidence": round(avg_conf, 4),
                    "status": "ok",
                    "error": "",
                }
            )
        except Exception as exc:
            ocr_rows.append(
                {
                    "label": crop_path.parent.name,
                    "crop_path": str(crop_path),
                    "text": "",
                    "confidence": 0.0,
                    "status": "failed",
                    "error": str(exc),
                }
            )

    return ocr_rows


def save_ocr_outputs(save_dir: Path, rows):
    json_path = save_dir / "ocr_results.json"
    csv_path = save_dir / "ocr_results.csv"
    txt_path = save_dir / "ocr_text_only.txt"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["label", "crop_path", "text", "confidence", "status", "error"],
        )
        writer.writeheader()
        writer.writerows(rows)

    with txt_path.open("w", encoding="utf-8") as f:
        for row in rows:
            if row["text"]:
                f.write(f"[{row['label']}] {row['crop_path']}\n")
                f.write(f"{row['text']}\n\n")
