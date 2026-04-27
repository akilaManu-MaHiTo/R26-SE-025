from ultralytics import YOLO


def run_detection(model_path: str, source_image: str):
    model = YOLO(model_path)
    results = model.predict(
        source=source_image,
        show=False,
        save=True,
        conf=0.6,
        line_width=2,
        save_crop=True,
        save_txt=True,
    )
    return model, results
