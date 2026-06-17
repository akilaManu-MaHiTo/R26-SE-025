import cv2
import os
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

def convert_pdf_to_images(pdf_path: str):
    pdf = pdfium.PdfDocument(pdf_path)
    image_paths = []

    for idx in range(len(pdf)):
        page = pdf[idx]
        bitmap = page.render(scale=2.0).to_pil()
        output_path = f"pdf_page_{idx + 1}_{os.path.basename(pdf_path)}.png"
        bitmap.save(output_path)
        image_paths.append(output_path)

    return image_paths


def _process_image_to_clean_version(image_path: str):
    img = cv2.imread(image_path)
    if img is None:
        raise RuntimeError(f"Unable to read image: {image_path}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    straightened = deskew_image(gray)
    denoised = cv2.medianBlur(straightened, 3)
    processed = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 10
    )
    kernel = np.ones((2, 2), np.uint8)
    healed = cv2.erode(processed, kernel, iterations=1)

    processed_filename = f"proc_{os.path.basename(image_path)}"
    cv2.imwrite(processed_filename, healed)
    return processed_filename


def _query_ocr_space_sync(filename: str):
    if not OCR_TOKEN:
        raise RuntimeError("OCR_TOKEN is missing in environment.")

    payload = {
        "apikey": OCR_TOKEN,
        "language": "eng",
        "isOverlayRequired": False,
        "FileType": "JPG",
        "OCREngine": 3,
    }

    with open(filename, "rb") as f:
        files = {"file": f}
        response = requests.post(OCR_SPACE_URL, files=files, data=payload, timeout=90)

    if response.status_code >= 400:
        raise RuntimeError(f"OCR.Space request failed: HTTP {response.status_code} {response.text}")

    result = response.json()
    if result.get("OCRExitCode") == 1 and result.get("ParsedResults"):
        return (result["ParsedResults"][0].get("ParsedText", "") or "").strip()

    error_message = result.get("ErrorMessage") or result.get("ErrorDetails") or "OCR Error"
    if isinstance(error_message, list):
        error_message = " | ".join(str(e) for e in error_message)
    raise RuntimeError(str(error_message))


async def query_ocr_space(filename: str):
    try:
        loop = asyncio.get_event_loop()
        extracted_text = await loop.run_in_executor(None, _query_ocr_space_sync, filename)
        return extracted_text.strip()
    except Exception as e:
        return f"OCR Failed: {str(e)}"


async def process_student_answer(file_path: str):
    temp_files = []
    final_results = []
    pages_processed = 0

    try:
        if file_path.lower().endswith(".pdf"):
            image_paths = convert_pdf_to_images(file_path)
            temp_files.extend(image_paths)
        else:
            image_paths = [file_path]

        if not image_paths:
            return "", 0

        for img_path in image_paths:
            proc_path = _process_image_to_clean_version(img_path)
            temp_files.append(proc_path)

            text = await query_ocr_space(proc_path)
            if text:
                final_results.append(text.strip())
            pages_processed += 1

        return " ".join(final_results).strip(), pages_processed
    finally:
        for f in temp_files:
            if os.path.exists(f) and f != file_path:
                os.remove(f)