import os
import tempfile
import uuid
from pathlib import Path

import cv2
import asyncio
import requests
import numpy as np
import pypdfium2 as pdfium
from dotenv import load_dotenv

load_dotenv()

OCR_TOKEN = os.getenv("OCR_TOKEN")
OCR_SPACE_URL = "https://api.ocr.space/parse/image"


def deskew_image(img):
    """
    Adaptive deskew:
    1) Try minAreaRect angle from text foreground.
    2) Fallback to Hough-line angle if minAreaRect is weak/near-zero.
    3) Clamp to plausible range to avoid over-rotation.
    """
    def _estimate_hough_angle(gray_img):
        edges = cv2.Canny(gray_img, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180, threshold=80, minLineLength=80, maxLineGap=12
        )
        if lines is None:
            return None

        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            # Keep only line angles that look like writing baselines.
            if -30 <= angle <= 30:
                angles.append(angle)

        if not angles:
            return None
        return float(np.median(angles))

    # Binarize with text as white for foreground extraction.
    _, binary_inv = cv2.threshold(
        img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    coords = np.column_stack(np.where(binary_inv > 0))
    angle = None

    if coords.shape[0] >= 200:
        rect_angle = cv2.minAreaRect(coords)[-1]
        if rect_angle < -45:
            rect_angle = 90 + rect_angle
        # minAreaRect can be noisy on handwriting; trust only moderate angles.
        if 0.3 <= abs(rect_angle) <= 30:
            angle = float(rect_angle)

    # Fallback when minAreaRect is unavailable or too close to zero.
    if angle is None:
        hough_angle = _estimate_hough_angle(img)
        if hough_angle is not None:
            angle = hough_angle

    if angle is None:
        return img

    # Ignore tiny corrections and clamp to a safe max.
    if abs(angle) < 0.3:
        return img
    angle = float(np.clip(angle, -30, 30))

    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    # Rotate in the opposite direction of detected skew.
    matrix = cv2.getRotationMatrix2D(center, -angle, 1.0)
    return cv2.warpAffine(
        img,
        matrix,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def convert_pdf_to_images(pdf_path: str, max_pages: int | None = None, *, work_dir: str | None = None):
    pdf = pdfium.PdfDocument(pdf_path)
    image_paths = []
    page_count = len(pdf)
    if max_pages is not None:
        page_count = min(page_count, max(0, int(max_pages)))

    out_dir = work_dir or tempfile.mkdtemp(prefix="ocr_pdf_")
    stem = Path(pdf_path).stem
    token = uuid.uuid4().hex[:8]

    for idx in range(page_count):
        page = pdf[idx]
        bitmap = page.render(scale=2.0).to_pil()
        output_path = os.path.join(out_dir, f"pdf_page_{idx + 1}_{token}_{stem}.png")
        bitmap.save(output_path)
        image_paths.append(output_path)

    return image_paths


def _ocr_filetype(path: str) -> str:
    ext = Path(path).suffix.lower().lstrip(".")
    if ext in {"jpg", "jpeg"}:
        return "JPG"
    if ext == "png":
        return "PNG"
    if ext == "gif":
        return "GIF"
    if ext in {"tif", "tiff"}:
        return "TIF"
    if ext == "bmp":
        return "BMP"
    if ext == "pdf":
        return "PDF"
    # OpenCV-written temps usually keep the source extension; default JPG.
    return "JPG"


def _process_image_light(image_path: str, *, work_dir: str | None = None) -> str:
    """Light cleanup: grayscale + mild deskew. Safer for phone photos than hard binarize."""
    img = cv2.imread(image_path)
    if img is None:
        raise RuntimeError(f"Unable to read image: {image_path}")

    # Downscale huge phone photos — OCR.Space often returns blank on oversized uploads.
    h, w = img.shape[:2]
    max_side = max(h, w)
    if max_side > 2200:
        scale = 2200.0 / max_side
        img = cv2.resize(
            img,
            (max(1, int(w * scale)), max(1, int(h * scale))),
            interpolation=cv2.INTER_AREA,
        )

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    straightened = deskew_image(gray)
    # Mild denoise only — avoid adaptiveThreshold/erode which wipe WhatsApp handwriting.
    denoised = cv2.fastNlMeansDenoising(straightened, None, 8, 7, 21)

    out_dir = work_dir or tempfile.mkdtemp(prefix="ocr_proc_")
    token = uuid.uuid4().hex[:8]
    # Always write PNG so OCR.Space gets a real image payload with matching FileType.
    processed_filename = os.path.join(
        out_dir, f"proc_{token}_{Path(image_path).stem}.png"
    )
    ok = cv2.imwrite(processed_filename, denoised)
    if not ok:
        raise RuntimeError(f"Failed to write processed image: {processed_filename}")
    return processed_filename


def _prepare_original_for_ocr(image_path: str, *, work_dir: str | None = None) -> str:
    """
    Send a resized copy of the original when the source is huge.
    Returns ``image_path`` unchanged when small enough.
    """
    try:
        size = os.path.getsize(image_path)
    except OSError:
        return image_path

    img = cv2.imread(image_path)
    if img is None:
        return image_path

    h, w = img.shape[:2]
    max_side = max(h, w)
    needs_resize = max_side > 2400 or size > 1_200_000
    if not needs_resize:
        return image_path

    scale = min(1.0, 2200.0 / max_side)
    if scale < 1.0:
        img = cv2.resize(
            img,
            (max(1, int(w * scale)), max(1, int(h * scale))),
            interpolation=cv2.INTER_AREA,
        )

    out_dir = work_dir or tempfile.mkdtemp(prefix="ocr_orig_")
    token = uuid.uuid4().hex[:8]
    out_path = os.path.join(out_dir, f"orig_{token}_{Path(image_path).stem}.jpg")
    ok = cv2.imwrite(out_path, img, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    if not ok:
        return image_path
    return out_path


def _mime_for_filetype(filetype: str) -> str:
    ft = (filetype or "JPG").upper()
    if ft == "PNG":
        return "image/png"
    if ft in {"TIF", "TIFF"}:
        return "image/tiff"
    if ft == "GIF":
        return "image/gif"
    if ft == "BMP":
        return "image/bmp"
    if ft == "PDF":
        return "application/pdf"
    return "image/jpeg"


def _query_ocr_space_sync(filename: str, *, engine: int = 3):
    if not OCR_TOKEN:
        raise RuntimeError("OCR_TOKEN is missing in environment.")

    filetype = _ocr_filetype(filename)
    payload = {
        "apikey": OCR_TOKEN,
        "language": "eng",
        "isOverlayRequired": False,
        "filetype": filetype,
        "OCREngine": str(engine),
        "scale": "true",
        "detectOrientation": "true",
    }

    with open(filename, "rb") as f:
        files = {"file": (Path(filename).name, f, _mime_for_filetype(filetype))}
        response = requests.post(OCR_SPACE_URL, files=files, data=payload, timeout=120)

    if response.status_code >= 400:
        raise RuntimeError(f"OCR.Space request failed: HTTP {response.status_code} {response.text}")

    result = response.json()
    parsed_results = result.get("ParsedResults") or []
    if result.get("OCRExitCode") in (1, 2) and parsed_results:
        texts = []
        for page in parsed_results:
            if not isinstance(page, dict):
                continue
            texts.append((page.get("ParsedText") or "").strip())
        joined = "\n".join(t for t in texts if t).strip()
        if joined:
            return joined
        # Successful envelope but blank text — treat as empty (caller may retry).
        return ""

    error_message = result.get("ErrorMessage") or result.get("ErrorDetails") or "OCR Error"
    if isinstance(error_message, list):
        error_message = " | ".join(str(e) for e in error_message)
    raise RuntimeError(str(error_message) or "OCR Error")


async def query_ocr_space(filename: str, *, engine: int = 3) -> str:
    try:
        loop = asyncio.get_running_loop()
        extracted_text = await loop.run_in_executor(
            None, lambda: _query_ocr_space_sync(filename, engine=engine)
        )
        return (extracted_text or "").strip()
    except Exception as e:
        return f"[OCR_ERROR] {e}"


def _is_usable_ocr(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if t.startswith("[OCR_ERROR]") or t.startswith("OCR Failed:"):
        return False
    # Ignore tiny noise-only payloads
    alnum = sum(1 for ch in t if ch.isalnum())
    return alnum >= 8


async def process_student_answer(file_path: str, *, max_pages: int | None = None):
    """
    OCR a student answer file.

    ``max_pages`` limits how many PDF pages are read (e.g. 1 for ID-header scan).
    Image files are always a single page; ``max_pages`` does not expand them.

    Strategy per page:
      1) light-processed PNG
      2) if empty/failed → original image as-is
    """
    work_dir = tempfile.mkdtemp(prefix="ocr_job_")
    temp_files: list[str] = []
    final_results: list[str] = []
    pages_processed = 0

    try:
        if file_path.lower().endswith(".pdf"):
            image_paths = convert_pdf_to_images(
                file_path, max_pages=max_pages, work_dir=work_dir
            )
            temp_files.extend(image_paths)
        else:
            image_paths = [file_path]

        if not image_paths:
            return "", 0

        for page_idx, img_path in enumerate(image_paths, start=1):
            text = ""
            light_path: str | None = None
            original_for_ocr = img_path
            try:
                resized = _prepare_original_for_ocr(img_path, work_dir=work_dir)
                if resized != img_path:
                    temp_files.append(resized)
                    original_for_ocr = resized
                light_path = _process_image_light(img_path, work_dir=work_dir)
                temp_files.append(light_path)
                text = await query_ocr_space(light_path, engine=3)
            except Exception as e:
                text = f"[OCR_ERROR] preprocess: {e}"

            # Fallbacks: original bytes often beat hard filters on WhatsApp photos.
            if not _is_usable_ocr(text):
                attempts: list[tuple[str, int]] = [
                    (original_for_ocr, 3),
                    (original_for_ocr, 2),
                ]
                if light_path:
                    attempts.append((light_path, 2))
                for candidate, eng in attempts:
                    fallback = await query_ocr_space(candidate, engine=eng)
                    if _is_usable_ocr(fallback):
                        text = fallback
                        break
                    if not _is_usable_ocr(text) and fallback:
                        text = fallback

            chunk = (text or "").strip()
            if not chunk:
                chunk = f"[OCR_EMPTY] page {page_idx} of {Path(file_path).name}"
            print(
                f"OCR page {page_idx}/{len(image_paths)} "
                f"{Path(file_path).name}: {len(chunk)} chars"
                + (" (weak/empty)" if not _is_usable_ocr(chunk) else "")
            )
            final_results.append(chunk)
            pages_processed += 1

        return "\n\n".join(final_results).strip(), pages_processed
    finally:
        for f in temp_files:
            if os.path.exists(f) and os.path.abspath(f) != os.path.abspath(file_path):
                try:
                    os.remove(f)
                except OSError:
                    pass
        try:
            if os.path.isdir(work_dir) and not os.listdir(work_dir):
                os.rmdir(work_dir)
        except OSError:
            pass
