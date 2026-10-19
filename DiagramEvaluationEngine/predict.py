import base64
import json
import os
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np

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


def _read_image(image_path: Path):
    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(f"Could not read image at {image_path}")
    return image


def _normalize_ocr_label(value: str) -> str:
    """Remove OCR decoration while preserving meaningful label text."""
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("_", " ")
    text = re.sub(r"[^\w\s-]", " ", text, flags=re.UNICODE)
    text = re.sub(r"(?<!\w)-{2,}(?!\w)", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""

    compact = re.sub(r"[\W_]+", "", text).casefold()
    identifier_aliases = {
        "sid": "S_Id",
        "studentid": "S_Id",
        "cid": "C_Id",
        "courseid": "C_Id",
    }
    return identifier_aliases.get(compact, text)


def _normalize_line(line):
    coords = np.asarray(line).reshape(-1)
    if coords.size < 4:
        return None
    return tuple(int(value) for value in coords[:4])


def _detect_lines(
    image,
    canny_low: int = 50,
    canny_high: int = 150,
    hough_threshold: int = 50,
    min_line_length: int = 30,
    max_line_gap: int = 10,
):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, canny_low, canny_high)
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=hough_threshold,
        minLineLength=min_line_length,
        maxLineGap=max_line_gap,
    )
    if lines is None:
        return []

    normalized_lines = []
    for line in lines:
        normalized_line = _normalize_line(line)
        if normalized_line is None:
            continue
        normalized_lines.append(normalized_line)

    return normalized_lines


def _bbox_center(box):
    x1, y1, x2, y2 = box
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def _distance_sq(p1, p2):
    return (p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2


def _closest_object(point, detections):
    best_det = None
    best_dist = None
    for det in detections:
        center = _bbox_center(det["bbox"])
        dist = _distance_sq(point, center)
        if best_dist is None or dist < best_dist:
            best_dist = dist
            best_det = det
    return best_det


def _infer_crop_path(crops_root: Path, label: str, stem: str, index: int) -> str:
    if not crops_root:
        return ""
    label_dir = crops_root / label
    if not label_dir.exists():
        return ""
    suffix = "" if index == 1 else f"-{index}"
    base_name = f"{stem}{suffix}"
    for ext in (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"):
        candidate = label_dir / f"{base_name}{ext}"
        if candidate.exists():
            return str(candidate)
    matches = list(label_dir.glob(f"{base_name}.*"))
    if matches:
        return str(matches[0])
    return str(label_dir / f"{base_name}.jpg")


def _ink_mask(gray):
    """Binary mask of pen strokes, robust to uneven paper shading and texture."""
    height, width = gray.shape[:2]
    kernel = max(15, (min(height, width) // 2) | 1)
    background = cv2.medianBlur(gray, kernel)
    darkness = cv2.subtract(background, gray)
    _, ink = cv2.threshold(darkness, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return ink


def _has_underline(crop) -> bool:
    """Return True when a crop contains a long horizontal underline below its text."""
    if crop is None or crop.size == 0:
        return False

    height, width = crop.shape[:2]
    if height < 8 or width < 16:
        return False

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    ink = _ink_mask(gray)

    # Opening with a wide, flat kernel keeps only long horizontal strokes and
    # drops the letters and the curved oval border.
    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (max(7, int(width * 0.24)), 1)
    )
    horizontal = cv2.morphologyEx(ink, cv2.MORPH_OPEN, kernel)
    contours, _ = cv2.findContours(
        horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    for contour in contours:
        x, y, line_width, line_height = cv2.boundingRect(contour)
        line_center = y + line_height / 2.0
        if line_width < width * 0.28 or line_width > width * 0.80:
            continue
        if line_width / max(line_height, 1) < 6:
            continue
        # Keep the stroke inside the crop: the connector and the oval border
        # touch or hug the crop edges.
        if x < width * 0.04 or x + line_width > width * 0.96:
            continue
        # Underlines sit below the label text but above the oval's bottom arc.
        if line_center < height * 0.50 or line_center > height * 0.82:
            continue

        # Require label ink right above the stroke (the text it underlines).
        band_top = max(0, y - max(3, int(height * 0.28)))
        text_band = ink[band_top:y, x : x + line_width]
        if text_band.size == 0 or cv2.countNonZero(text_band) < line_width * 0.05:
            continue
        return True
    return False


def _crop_detection(image, bbox, padding: float = 0.0):
    height, width = image.shape[:2]
    x1, y1, x2, y2 = [int(round(value)) for value in bbox]
    box_width = max(1, x2 - x1)
    box_height = max(1, y2 - y1)
    x_padding = int(round(box_width * padding))
    y_padding = int(round(box_height * padding))
    x1 -= x_padding
    y1 -= y_padding
    x2 += x_padding
    y2 += y_padding
    x1 = max(0, min(x1, width - 1))
    y1 = max(0, min(y1, height - 1))
    x2 = max(x1 + 1, min(x2, width))
    y2 = max(y1 + 1, min(y2, height))
    return image[y1:y2, x1:x2]


def _save_detection_crops(
    image, detections, crops_root: Path, stem: str
) -> None:
    """Persist every model detection crop before OCR or post-processing."""
    crops_root.mkdir(parents=True, exist_ok=True)
    label_counts = defaultdict(int)

    for detection in detections:
        label = str(detection.get("label", "")).strip() or "Unknown"
        label_counts[label] += 1
        crop = _crop_detection(image, detection.get("bbox", [0, 0, 0, 0]))
        if crop is None or crop.size == 0:
            continue

        label_dir = crops_root / label
        label_dir.mkdir(parents=True, exist_ok=True)
        suffix = "" if label_counts[label] == 1 else f"-{label_counts[label]}"
        crop_path = label_dir / f"{stem}{suffix}.jpg"
        if not cv2.imwrite(str(crop_path), crop):
            raise OSError(f"Could not save detection crop to {crop_path}")
        detection["crop_path"] = str(crop_path)

def _detect_primary_keys(image, detections, save_dir: Path) -> None:
    primary_dir = save_dir / "crops"
    primary_count = 0
    stem = save_dir.name

    for detection in detections:
        model_label = (
            str(detection.get("label", "")).strip().lower().replace("_", " ")
        )
        if model_label == "attributes":
            # The model predicts all attributes with one class. Use the
            # corresponding YOLO crop for the underline decision; the model
            # does not emit a separate primary-key detection.
            saved_crop_path = Path(str(detection.get("crop_path", "")))
            crop = (
                cv2.imread(str(saved_crop_path))
                if saved_crop_path.is_file()
                else None
            )
            crop_source = "attributes_crop"
        else:
            crop = None
            crop_source = "expanded_detection_crop"

        # Keep a fallback for direct callers or runs where save_crop did not
        # produce the expected Attributes image.
        if crop is None:
            crop = _crop_detection(
                image,
                detection.get("bbox", [0, 0, 0, 0]),
                padding=0.35,
            )

        underline_detected = _has_underline(crop)
        is_primary_key = model_label == "primary key" or (
            model_label == "attributes" and underline_detected
        )
        if not is_primary_key:
            continue

        primary_count += 1
        primary_dir.mkdir(parents=True, exist_ok=True)
        crop_path = primary_dir / f"primary-key-{stem}-{primary_count}.jpg"
        if not cv2.imwrite(str(crop_path), crop):
            raise OSError(f"Could not save primary-key crop to {crop_path}")

        detection["label"] = "Primary Key"
        detection["is_primary_key"] = True
        detection["underline_detected"] = underline_detected
        detection["primary_key_crop_path"] = str(crop_path)
        detection["primary_key_crop_source"] = crop_source


def _extract_detections(results, image_path: Path, crops_root: Path):
    if not results:
        return []
    result = results[0]
    boxes = result.boxes
    if boxes is None or len(boxes) == 0:
        return []

    names = result.names
    stem = image_path.stem
    label_counts = defaultdict(int)
    detections = []

    for idx in range(len(boxes)):
        cls_raw = boxes.cls[idx]
        cls_id = int(cls_raw.item()) if hasattr(cls_raw, "item") else int(cls_raw)
        conf_raw = boxes.conf[idx] if boxes.conf is not None else 0.0
        conf = float(conf_raw.item()) if hasattr(conf_raw, "item") else float(conf_raw)
        x1, y1, x2, y2 = boxes.xyxy[idx].tolist()
        if isinstance(names, dict):
            label = names.get(cls_id, str(cls_id))
        else:
            label = names[cls_id]

        label_counts[label] += 1
        crop_path = _infer_crop_path(crops_root, label, stem, label_counts[label])

        detections.append(
            {
                "id": idx,
                "label": label,
                "bbox": [x1, y1, x2, y2],
                "confidence": conf,
                "crop_path": crop_path,
            }
        )

    return detections


def _attach_ocr_text(detections, ocr_rows):
    if not ocr_rows:
        return
    ocr_by_path = {}
    for row in ocr_rows:
        crop_path = row.get("crop_path")
        if not crop_path:
            continue
        ocr_by_path[Path(crop_path).resolve()] = row

    for det in detections:
        crop_path = det.get("crop_path")
        if not crop_path:
            continue
        row = ocr_by_path.get(Path(crop_path).resolve())
        if not row:
            continue
        text = _normalize_ocr_label(row.get("text", ""))
        if text:
            det["text"] = text
            row["text"] = text
        det["ocr_status"] = row.get("status")


def _connect_lines_to_detections(lines, detections):
    if not lines or not detections:
        return []
    connections = []
    seen = set()
    for x1, y1, x2, y2 in lines:
        obj1 = _closest_object((x1, y1), detections)
        obj2 = _closest_object((x2, y2), detections)
        if not obj1 or not obj2:
            continue
        if obj1["id"] == obj2["id"]:
            continue
        key = tuple(sorted((obj1["id"], obj2["id"])))
        if key in seen:
            continue
        seen.add(key)
        connections.append(
            {
                "from_id": obj1["id"],
                "to_id": obj2["id"],
                "from": obj1,
                "to": obj2,
                "line": [x1, y1, x2, y2],
            }
        )
    return connections


def _display_name(det, fallback_prefix: str):
    text = str(det.get("text", "")).strip()
    if text:
        return " ".join(text.split())
    return f"{fallback_prefix}_{det['id'] + 1}"


def _build_er_structure(detections, connections):
    entity_labels = {"Entities", "Weak Entity"}
    attribute_labels = {"Attributes", "Primary Key"}
    relationship_label = "Relationships"

    entity_names = {}
    relationship_names = {}
    attribute_names = {}

    for det in detections:
        if det["label"] in entity_labels:
            entity_names[det["id"]] = _display_name(det, "Entity")
        elif det["label"] == relationship_label:
            relationship_names[det["id"]] = _display_name(det, "Relationship")
        elif det["label"] in attribute_labels:
            attribute_names[det["id"]] = _display_name(det, "Attribute")

    # A duplicate detection of an underlined attribute may carry the connector
    # while the flagged copy does not, so match primary keys by label text too.
    primary_key_names = {
        _display_name(det, "Attribute")
        for det in detections
        if det.get("is_primary_key") and str(det.get("text", "")).strip()
    }

    def is_primary_key(det):
        return bool(det.get("is_primary_key")) or (
            str(det.get("text", "")).strip() != ""
            and _display_name(det, "Attribute") in primary_key_names
        )

    entity_attributes = defaultdict(set)
    entity_primary_keys = defaultdict(set)
    relationship_entities = defaultdict(set)
    relationship_attributes = defaultdict(set)
    unmatched = []

    for conn in connections:
        left = conn["from"]
        right = conn["to"]
        left_label = left["label"]
        right_label = right["label"]

        if left_label in entity_labels and right_label in attribute_labels:
            attribute_name = attribute_names.get(right["id"], _display_name(right, "Attribute"))
            target = entity_primary_keys if is_primary_key(right) else entity_attributes
            target[left["id"]].add(attribute_name)
        elif right_label in entity_labels and left_label in attribute_labels:
            attribute_name = attribute_names.get(left["id"], _display_name(left, "Attribute"))
            target = entity_primary_keys if is_primary_key(left) else entity_attributes
            target[right["id"]].add(attribute_name)
        elif left_label == relationship_label and right_label in entity_labels:
            relationship_entities[left["id"]].add(
                entity_names.get(right["id"], _display_name(right, "Entity"))
            )
        elif right_label == relationship_label and left_label in entity_labels:
            relationship_entities[right["id"]].add(
                entity_names.get(left["id"], _display_name(left, "Entity"))
            )
        elif left_label == relationship_label and right_label in attribute_labels:
            relationship_attributes[left["id"]].add(
                attribute_names.get(right["id"], _display_name(right, "Attribute"))
            )
        elif right_label == relationship_label and left_label in attribute_labels:
            relationship_attributes[right["id"]].add(
                attribute_names.get(left["id"], _display_name(left, "Attribute"))
            )
        else:
            unmatched.append(conn)

    entities = {}
    for entity_id, name in entity_names.items():
        primary_keys = sorted(entity_primary_keys.get(entity_id, set()))
        entities[name] = {
            "attributes": sorted(
                entity_attributes.get(entity_id, set()) | set(primary_keys)
            )
        }
        if primary_keys:
            entities[name]["primary_keys"] = primary_keys

    relationships = []
    for rel_id, rel_name in relationship_names.items():
        rel_entry = {
            "name": rel_name,
            "entities": sorted(relationship_entities.get(rel_id, set())),
        }
        rel_attrs = sorted(relationship_attributes.get(rel_id, set()))
        if rel_attrs:
            rel_entry["attributes"] = rel_attrs
        relationships.append(rel_entry)

    structure = {
        "entities": entities,
        "relationships": relationships,
    }
    if unmatched:
        structure["unmatched_connections"] = [
            {
                "from": _display_name(conn["from"], "Object"),
                "to": _display_name(conn["to"], "Object"),
                "line": conn["line"],
            }
            for conn in unmatched
        ]

    return structure


def _save_json(output_path: Path, payload) -> None:
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)


def _label_color(label: str) -> tuple[int, int, int]:
    normalized = label.strip().lower().replace("_", " ")
    if normalized in {"entities", "weak entity"}:
        return (219, 234, 254)
    if normalized in {"relationships"}:
        return (254, 243, 199)
    if normalized in {"attributes", "primary key"}:
        return (220, 252, 231)
    return (226, 232, 240)


def _annotate_image(image, detections, connections):
    if image is None:
        return image
    annotated = image.copy()
    for det in detections or []:
        x1, y1, x2, y2 = [int(v) for v in det.get("bbox", [0, 0, 0, 0])]
        label = str(det.get("label", "Object"))
        text = str(det.get("text", "")).strip()
        caption = label if not text else f"{label}: {text}"
        color = _label_color(label)
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            annotated,
            caption,
            (x1, max(12, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (30, 41, 59),
            1,
            cv2.LINE_AA,
        )

    for conn in connections or []:
        x1, y1, x2, y2 = [int(v) for v in conn.get("line", [0, 0, 0, 0])]
        cv2.line(annotated, (x1, y1), (x2, y2), (14, 116, 144), 2)

    return annotated


def _encode_image_to_data_uri(image, fmt: str = ".jpg") -> str:
    if image is None:
        return ""
    success, buffer = cv2.imencode(fmt, image)
    if not success:
        return ""
    encoded = base64.b64encode(buffer.tobytes()).decode("ascii")
    mime = "image/jpeg" if fmt.lower() in {".jpg", ".jpeg"} else "image/png"
    return f"data:{mime};base64,{encoded}"


def _emit_progress(progress_callback, payload: dict) -> None:
    if progress_callback is None:
        return
    try:
        progress_callback(payload)
    except Exception:
        pass


def run_er_pipeline(
    image_path: Path,
    model_path: Optional[Path] = None,
    progress_callback: Optional[Callable[[dict], None]] = None,
) -> dict:
    script_dir = Path(__file__).resolve().parent
    _load_dotenv(script_dir / ".env")

    resolved_image = image_path
    if not resolved_image.is_absolute():
        resolved_image = script_dir / resolved_image

    resolved_model = model_path or (script_dir / "engine" / "erExtractionEngine-v1.1.pt")
    if not resolved_model.is_absolute():
        resolved_model = script_dir / resolved_model

    _emit_progress(
        progress_callback,
        {
            "stage": "starting",
            "message": "Preparing diagram evaluation...",
            "progress": 2,
        },
    )

    _, results = run_detection(str(resolved_model), str(resolved_image))
    _emit_progress(
        progress_callback,
        {
            "stage": "detecting",
            "message": "Defining Objects...",
            "progress": 15,
        },
    )
    if not results:
        image = _read_image(resolved_image)
        _emit_progress(
            progress_callback,
            {
                "stage": "completed",
                "message": "No objects detected.",
                "progress": 100,
            },
        )
        return {
            "status": "ok",
            "annotated_image": _encode_image_to_data_uri(image),
            "detections": [],
            "connections": [],
            "structure": {"entities": {}, "relationships": []},
            "ocr": [],
            "save_dir": "",
        }

    save_dir = Path(results[0].save_dir)
    crops_root = save_dir / "crops"

    ocr_rows = []
    ocr_error = ""
    try:
        detections = _extract_detections(results, resolved_image, crops_root)
        image = _read_image(resolved_image)
        _save_detection_crops(
            image,
            detections,
            crops_root,
            resolved_image.stem,
        )
        label_counts = defaultdict(int)
        for detection in detections:
            label_counts[detection.get("label", "")] += 1
        _emit_progress(
            progress_callback,
            {
                "stage": "objects_defined",
                "message": (
                    f"Defined Objects {len(detections)} "
                    f"(Entities {label_counts.get('Entities', 0)}, "
                    f"Relationships {label_counts.get('Relationships', 0)}, "
                    f"Attributes {label_counts.get('Attributes', 0) + label_counts.get('Primary Key', 0)})"
                ),
                "progress": 25,
                "detections": len(detections),
            },
        )

        _emit_progress(
            progress_callback,
            {
                "stage": "labels",
                "message": "Defining Labels...",
                "progress": 30,
            },
        )

        ocr_rows = run_ocr_on_crops(crops_root, progress_callback=progress_callback)
    except Exception as exc:
        ocr_error = str(exc)

    if ocr_rows:
        _attach_ocr_text(detections, ocr_rows)
        save_ocr_outputs(save_dir, ocr_rows)

    _emit_progress(
        progress_callback,
        {
            "stage": "structuring",
            "message": "Building ER structure...",
            "progress": 82,
        },
    )

    image = _read_image(resolved_image)
    _detect_primary_keys(image, detections, save_dir)
    lines = _detect_lines(image)
    connections = _connect_lines_to_detections(lines, detections)
    structure = _build_er_structure(detections, connections)

    _save_json(save_dir / "connections.json", connections)
    _save_json(save_dir / "er_structure.json", structure)

    annotated = _annotate_image(image, detections, connections)

    payload = {
        "status": "ok",
        "annotated_image": _encode_image_to_data_uri(annotated),
        "detections": detections,
        "connections": connections,
        "structure": structure,
        "ocr": ocr_rows,
        "save_dir": str(save_dir),
    }
    if ocr_error:
        payload["ocr_error"] = ocr_error

    _emit_progress(
        progress_callback,
        {
            "stage": "completed",
            "message": "Diagram evaluation complete.",
            "progress": 100,
            "result": payload,
        },
    )

    return payload


def main():
    model_path = "engine/erExtractionEngine-v1.1.pt"
    source_image = "images/label115.jpeg"

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

    if not use_handwritten:
        image = _read_image(source_path)
        detections = _extract_detections(results, source_path, crops_root)
        _save_detection_crops(image, detections, crops_root, source_path.stem)
        rows = run_ocr_on_crops(crops_root)
        print_label_summary(rows)

        _attach_ocr_text(detections, rows)
        save_ocr_outputs(save_dir, rows)

        _detect_primary_keys(image, detections, save_dir)
        lines = _detect_lines(image)
        connections = _connect_lines_to_detections(lines, detections)
        structure = _build_er_structure(detections, connections)

        _save_json(save_dir / "connections.json", connections)
        _save_json(save_dir / "er_structure.json", structure)

        print(
            f"Line detection complete. Lines: {len(lines)}, "
            f"connections: {len(connections)}"
        )

    print(f"OCR complete. {len(rows) if not use_handwritten else 0} crops processed.")
    print(f"Results saved in: {save_dir}")



if __name__ == "__main__":
    main()