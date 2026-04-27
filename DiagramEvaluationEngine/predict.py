from pathlib import Path
from label_summary import print_label_summary
from ocr_utils import run_ocr_on_crops, save_ocr_outputs
from predict_detection import run_detection


def main():
    model_path = "engine/research_model.pt"
    source_image = "images/image4.jpg"

    _, results = run_detection(model_path, source_image)
    save_dir = Path(results[0].save_dir)
    crops_root = save_dir / "crops"

    rows = run_ocr_on_crops(crops_root)
    save_ocr_outputs(save_dir, rows)
    print_label_summary(rows)

    print(f"OCR complete. {len(rows)} crops processed.")
    print(f"Results saved in: {save_dir}")



if __name__ == "__main__":
    main()