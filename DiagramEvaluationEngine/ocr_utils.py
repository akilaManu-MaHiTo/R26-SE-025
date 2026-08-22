import base64
import csv
import json
import os
import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import cv2
import numpy as np

_OCR_SPACE_URL = "https://api.ocr.space/parse/image"


def _get_ocr_space_api_key(explicit_key: Optional[str]) -> str:
    if explicit_key:
        return explicit_key
    env_key = os.getenv("OCR_SPACE_API_KEY") or os.getenv("OCR_SPACE_APIKEY")
    if not env_key:
        raise RuntimeError(
            "OCR.Space API key not set. Provide api_key or set OCR_SPACE_API_KEY."
        )
    return env_key


def _to_data_uri(image_bytes: bytes, mime_type: str = "image/png") -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _normalize_grayscale_for_ocr(gray: np.ndarray) -> np.ndarray:
    normalized = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(gray)
    denoised = cv2.bilateralFilter(normalized, d=7, sigmaColor=45, sigmaSpace=45)
    sharpen_kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
    sharpened = cv2.filter2D(denoised, -1, sharpen_kernel)
    return sharpened


def _score_text_candidate(image: np.ndarray) -> float:
    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    image_u8 = np.clip(image, 0, 255).astype(np.uint8)
    contrast = float(image_u8.std()) / 255.0
    edges = cv2.Canny(image_u8, 50, 150)
    edge_density = float(np.count_nonzero(edges)) / float(edges.size)

    _, binary = cv2.threshold(image_u8, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    foreground_ratio = float(np.count_nonzero(binary == 0)) / float(binary.size)
    balance_penalty = abs(foreground_ratio - 0.18)

    return (edge_density * 2.5) + (contrast * 1.25) - (balance_penalty * 1.5)


def _encode_candidate_for_ocr(image: np.ndarray) -> tuple[bytes, str]:
    success, encoded = cv2.imencode(".png", image)
    if not success:
        raise RuntimeError("Failed to encode preprocessed OCR image.")
    return encoded.tobytes(), "image/png"


def _log_ocr_request(crop_path: Path, image_digest: str, attempt: int, total_unique: int) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(
        f"[{timestamp}] OCR send {attempt}/{total_unique} | "
        f"digest={image_digest[:12]} | crop={crop_path}",
        flush=True,
    )


def _preprocess_image_for_ocr(image_path: Path) -> tuple[bytes, str]:
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"Could not read image at {image_path}")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape[:2]
    scale = 1.0
    if max(height, width) < 1200:
        scale = 2.0
    elif max(height, width) < 1800:
        scale = 1.5

    if scale != 1.0:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    normalized = _normalize_grayscale_for_ocr(gray)
    binary_adaptive = cv2.adaptiveThreshold(
        normalized,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )
    binary_otsu = cv2.threshold(
        cv2.GaussianBlur(normalized, (3, 3), 0),
        0,
        255,
        cv2.THRESH_BINARY | cv2.THRESH_OTSU,
    )[1]

    candidates = [
        normalized,
        binary_adaptive,
        binary_otsu,
        cv2.bitwise_not(binary_adaptive) if np.mean(binary_adaptive) < 127 else binary_adaptive,
        cv2.bitwise_not(binary_otsu) if np.mean(binary_otsu) < 127 else binary_otsu,
    ]

    best_candidate = max(candidates, key=_score_text_candidate)
    return _encode_candidate_for_ocr(best_candidate)


def _post_ocr_space(payload, timeout_seconds: int, max_attempts: int = 4) -> dict:
    data = urlencode(payload).encode("utf-8")
    request = Request(
        _OCR_SPACE_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read()
            try:
                return json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise RuntimeError("OCR.Space API returned non-JSON response.") from exc
        except HTTPError as exc:
            last_error = exc
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            should_retry = exc.code in {429, 500, 502, 503, 504}
            if not should_retry or attempt == max_attempts:
                raise

            delay_seconds = 1.0 * (2 ** (attempt - 1))
            if retry_after:
                try:
                    delay_seconds = max(delay_seconds, float(retry_after))
                except ValueError:
                    pass
            time.sleep(min(delay_seconds, 10.0))

    if last_error is not None:
        raise last_error
    raise RuntimeError("OCR.Space request failed unexpectedly.")


def _parse_ocr_space_response(response_json: dict) -> tuple[str, str]:
    if response_json.get("IsErroredOnProcessing"):
        error_message = response_json.get("ErrorMessage") or response_json.get(
            "ErrorDetails"
        )
        if isinstance(error_message, list):
            error_message = "; ".join(msg for msg in error_message if msg)
        return "", str(error_message or "Unknown OCR error.")

    parsed_results = response_json.get("ParsedResults") or []
    if not parsed_results:
        return "", "No parsed results returned."

    texts = []
    error_messages = []
    for result in parsed_results:
        text = (result.get("ParsedText") or "").strip()
        if text:
            texts.append(text)
        result_error = result.get("ErrorMessage") or result.get("ErrorDetails")
        if result_error:
            if isinstance(result_error, list):
                error_messages.extend([msg for msg in result_error if msg])
            else:
                error_messages.append(str(result_error))

    combined_text = "\n".join(texts).strip()
    if combined_text:
        return combined_text, ""
    if error_messages:
        return "", "; ".join(error_messages)
    return "", "OCR completed but no text was returned."


def run_ocr_on_crops(
    crops_root: Path,
    api_key: Optional[str] = None,
    language: str = "auto",
    timeout_seconds: int = 60,
    progress_callback=None,
):
    language_value = language.strip().lower()
    if language_value != "auto":
        raise ValueError("OCR Engine 3 only supports language='auto'.")

    api_key_value = _get_ocr_space_api_key(api_key)
    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
    crop_images = [
        p for p in crops_root.rglob("*") if p.is_file() and p.suffix.lower() in image_extensions
    ]

    ocr_rows = []
    cached_results = {}
    unique_request_count = 0
    total_crops = len(crop_images)
    for index, crop_path in enumerate(sorted(crop_images), start=1):
        try:
            if progress_callback is not None:
                progress_callback(
                    {
                        "stage": "ocr",
                        "message": f"{index}/{total_crops} >> progress {round((index / total_crops) * 100)}%",
                        "current": index,
                        "total": total_crops,
                        "progress": round((index / total_crops) * 100),
                        "label": crop_path.parent.name,
                        "crop_path": str(crop_path),
                    }
                )

            image_bytes, mime_type = _preprocess_image_for_ocr(crop_path)
            image_digest = hashlib.sha256(image_bytes).hexdigest()

            cached_result = cached_results.get(image_digest)
            if cached_result is not None:
                text, error_message = cached_result
            else:
                unique_request_count += 1
                _log_ocr_request(crop_path, image_digest, unique_request_count, len(crop_images))
                payload = {
                    "apikey": api_key_value,
                    "language": language_value,
                    "OCREngine": "3",
                    "isOverlayRequired": "false",
                    "base64Image": _to_data_uri(image_bytes, mime_type=mime_type),
                    "filetype": "png",
                }

                response_json = _post_ocr_space(payload, timeout_seconds)
                text, error_message = _parse_ocr_space_response(response_json)
                cached_results[image_digest] = (text, error_message)

            ocr_rows.append(
                {
                    "label": crop_path.parent.name,
                    "crop_path": str(crop_path),
                    "text": text,
                    "confidence": 0.0,
                    "status": "ok" if not error_message else "failed",
                    "error": error_message,
                }
            )
        except (HTTPError, URLError, RuntimeError, ValueError) as exc:
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

        if progress_callback is not None:
            progress_callback(
                {
                    "stage": "ocr",
                    "message": f"Processed {index}/{total_crops} crops",
                    "current": index,
                    "total": total_crops,
                    "progress": round((index / total_crops) * 100),
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
