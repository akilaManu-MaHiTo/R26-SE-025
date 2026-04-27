from ultralytics import YOLO
model = YOLO('yolov8l.pt')
model.train(data='train_custom.yaml', epochs=100, imgsz=640, batch=8, name='yolov8l_custom', workers=0, device=0)