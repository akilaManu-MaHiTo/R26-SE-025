import os
from pathlib import Path
from label_summary import print_label_summary
from ocr_utils import run_ocr_on_crops, save_ocr_outputs
from predict_detection import run_detection


def _load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip().strip("\"").strip("'")
        if key not in os.environ:
            os.environ[key] = value


def main():
    model_path = "engine/erExtractionEngine-v1.1.pt"
    source_image = "images/label25.jpeg"

    script_dir = Path(__file__).resolve().parent
    _load_dotenv(script_dir / ".env")
    source_path = Path(source_image)
    if not source_path.is_absolute():
        source_path = script_dir / source_path

    detection_mode = os.getenv("DETECTION_MODE", "er").lower()
    use_handwritten = detection_mode in {"handwritten", "handwriting", "text"}
    if use_handwritten:
        save_dir = run_handwritten_detection(source_path, script_dir)
    else:
        resolved_model_path = Path(model_path)
        if not resolved_model_path.is_absolute():
            resolved_model_path = script_dir / resolved_model_path
        _, results = run_detection(str(resolved_model_path), str(source_path))
        save_dir = Path(results[0].save_dir)
    crops_root = save_dir / "crops"

    rows = run_ocr_on_crops(crops_root)
    save_ocr_outputs(save_dir, rows)
    if not use_handwritten:
        print_label_summary(rows)

    print(f"OCR complete. {len(rows)} crops processed.")
    print(f"Results saved in: {save_dir}")



if __name__ == "__main__":
    main()