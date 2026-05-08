from ultralytics import YOLO

model = YOLO("yolov8l.pt")

model.train(
    data="/content/DiagramEvaluationEngine/train_custom.yaml",
    epochs=100,
    imgsz=640,
    batch=8
)