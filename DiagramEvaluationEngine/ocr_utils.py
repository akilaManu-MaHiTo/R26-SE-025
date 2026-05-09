import base64
import csv
import json
import mimetypes
import os
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

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


def _to_data_uri(image_path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(str(image_path))
    if not mime_type:
        mime_type = "application/octet-stream"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _post_ocr_space(payload, timeout_seconds: int) -> dict:
    data = urlencode(payload).encode("utf-8")
    request = Request(
        _OCR_SPACE_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        raw = response.read()
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("OCR.Space API returned non-JSON response.") from exc


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
    for crop_path in sorted(crop_images):
        try:
            payload = {
                "apikey": api_key_value,
                "language": language_value,
                "OCREngine": "3",
                "isOverlayRequired": "false",
                "base64Image": _to_data_uri(crop_path),
            }
            filetype = crop_path.suffix.lower().lstrip(".")
            if filetype:
                payload["filetype"] = filetype

            response_json = _post_ocr_space(payload, timeout_seconds)
            text, error_message = _parse_ocr_space_response(response_json)

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
