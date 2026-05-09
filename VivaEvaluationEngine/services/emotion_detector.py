from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple

import cv2
import numpy as np
import torch
import timm

from config import canonical_emotion_label


CLASS_NAMES = [
    "neutral",
    "happy",
    "sad",
    "surprise",
    "fear",
    "disgust",
    "anger",
    "contempt",
]

MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)


class HSEmotionRecognizer:
    def __init__(self, model_path: str = "models/hsemotion_improved.pt") -> None:
        self.model_path = model_path
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.idx_to_class = {idx: class_name.title() for idx, class_name in enumerate(CLASS_NAMES)}
        self.class_names = list(self.idx_to_class.values())
        self.emotions = list(self.class_names)
        self.labels = list(self.class_names)
        self.img_size = 224
        self.model = self._load_model()

    def _load_model(self) -> torch.nn.Module:
        model_file = Path(self.model_path)
        if not model_file.exists():
            raise FileNotFoundError(f"Emotion model checkpoint not found: {model_file}")

        model = timm.create_model(
            "efficientnet_b0",
            pretrained=False,
            num_classes=len(CLASS_NAMES),
        )

        try:
            checkpoint = torch.load(model_file, map_location="cpu", weights_only=False)
        except TypeError:
            checkpoint = torch.load(model_file, map_location="cpu")

        if isinstance(checkpoint, torch.nn.Module):
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
        model.eval()
        return model.to(self.device)

    def preprocess(self, img: np.ndarray) -> torch.Tensor:
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        rgb = cv2.resize(rgb, (self.img_size, self.img_size), interpolation=cv2.INTER_LINEAR)
        tensor = torch.from_numpy(rgb).float().permute(2, 0, 1).div_(255.0)
        mean = torch.tensor(MEAN, dtype=tensor.dtype).view(3, 1, 1)
        std = torch.tensor(STD, dtype=tensor.dtype).view(3, 1, 1)
        tensor = (tensor - mean) / std
        return tensor.unsqueeze(0).to(self.device)

    @torch.inference_mode()
    def predict_emotions(self, face_img: np.ndarray, logits: bool = True):
        inputs = self.preprocess(face_img)
        scores = self.model(inputs)[0]
        pred = int(torch.argmax(scores).item())

        if logits:
            output_scores = scores.detach().cpu().numpy()
        else:
            output_scores = torch.softmax(scores, dim=0).detach().cpu().numpy()

        return self.idx_to_class[pred], output_scores

    def predict(self, face_img: np.ndarray, logits: bool = True):
        return self.predict_emotions(face_img, logits=logits)


class EmotionDetector:
    def __init__(self, model_path: str = "models/hsemotion_improved.pt", debug: bool = False) -> None:
        self.model_path = model_path
        self.model = HSEmotionRecognizer(model_path=model_path)
        self.idx_to_class = self.model.idx_to_class
        self.class_names = self.model.class_names
        self.emotions = self.model.emotions
        self.labels = self.model.labels
        self._debug = debug

    def predict(self, face_bgr: np.ndarray) -> Tuple[str, float]:
        prediction = self._run_model(face_bgr)
        if self._debug:
            print(f"Raw preds: {prediction}")
        emotion, confidence = self._parse_prediction(prediction)
        return emotion, confidence

    def _run_model(self, face_bgr: np.ndarray) -> Any:
        for method_name in ("predict_emotions", "predict"):
            method = getattr(self.model, method_name, None)
            if method is None:
                continue

            for kwargs in ({"logits": False}, {}, {"logits": True}):
                try:
                    return method(face_bgr, **kwargs)
                except TypeError:
                    continue

            try:
                return method(face_bgr)
            except Exception as exc:
                raise RuntimeError(f"Emotion model inference failed: {exc}") from exc

        if callable(self.model):
            try:
                return self.model(face_bgr)
            except Exception as exc:
                raise RuntimeError(f"Emotion model inference failed: {exc}") from exc

        raise RuntimeError("No compatible prediction method found for HSEmotion model")

    def _parse_prediction(self, prediction: Any) -> Tuple[str, float]:
        labels = self._labels_from_model()

        if isinstance(prediction, str):
            return self._normalize_emotion(prediction), 1.0

        if isinstance(prediction, dict):
            emotion = prediction.get("emotion") or prediction.get("label")
            confidence = prediction.get("confidence") or prediction.get("score")
            if emotion is None:
                emotion, confidence = self._extract_from_scores(prediction, labels)
            return self._normalize_emotion(emotion), self._normalize_confidence(confidence)

        if isinstance(prediction, tuple) and len(prediction) >= 1:
            emotion_candidate = prediction[0]
            confidence = None

            if len(prediction) >= 2:
                second = prediction[1]
                if isinstance(second, (dict, list, tuple, np.ndarray)):
                    parsed_emotion, parsed_conf = self._extract_from_scores(second, labels)
                    if isinstance(emotion_candidate, str):
                        return self._normalize_emotion(emotion_candidate), self._normalize_confidence(parsed_conf)
                    return self._normalize_emotion(parsed_emotion), self._normalize_confidence(parsed_conf)
                confidence = second

            if isinstance(emotion_candidate, str):
                return self._normalize_emotion(emotion_candidate), self._normalize_confidence(confidence)

            emotion, parsed_conf = self._extract_from_scores(emotion_candidate, labels)
            return self._normalize_emotion(emotion), self._normalize_confidence(parsed_conf)

        if isinstance(prediction, (list, tuple, np.ndarray)):
            emotion, confidence = self._extract_from_scores(prediction, labels)
            return self._normalize_emotion(emotion), self._normalize_confidence(confidence)

        return "Unknown", 0.0

    def _labels_from_model(self) -> Optional[List[str]]:
        for attr_name in ("idx_to_class", "class_names", "emotions", "labels"):
            value = getattr(self.model, attr_name, None)
            if value is None:
                continue

            if isinstance(value, dict) and value:
                max_index = max(value.keys())
                return [str(value[i]) for i in range(max_index + 1) if i in value]

            if isinstance(value, Iterable) and not isinstance(value, (str, bytes, dict)):
                labels = [str(x) for x in value]
                if labels:
                    return labels

        return None

    def _extract_from_scores(self, scores_obj: Any, labels: Optional[List[str]]) -> Tuple[str, float]:
        if isinstance(scores_obj, dict):
            if not scores_obj:
                return "Unknown", 0.0

            best_label = max(scores_obj, key=scores_obj.get)
            best_score = float(scores_obj[best_label])
            return str(best_label), best_score

        scores = np.asarray(scores_obj, dtype=float).flatten()
        if scores.size == 0:
            return "Unknown", 0.0

        # Convert logits to probabilities if values are outside a typical probability range.
        if np.min(scores) < 0 or np.max(scores) > 1:
            exp_scores = np.exp(scores - np.max(scores))
            probs = exp_scores / np.sum(exp_scores)
        else:
            total = np.sum(scores)
            probs = scores / total if total > 0 else scores

        best_idx = int(np.argmax(probs))
        best_score = float(probs[best_idx])

        if labels and best_idx < len(labels):
            return labels[best_idx], best_score
        return str(best_idx), best_score

    @staticmethod
    def _normalize_emotion(emotion: Any) -> str:
        if emotion is None:
            return "Unknown"
        return canonical_emotion_label(str(emotion))

    @staticmethod
    def _normalize_confidence(confidence: Any) -> float:
        if confidence is None:
            return 1.0

        try:
            value = float(confidence)
        except (TypeError, ValueError):
            return 1.0

        value = max(0.0, min(1.0, value))
        return value
