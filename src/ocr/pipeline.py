import os
import subprocess
import cv2
import numpy as np
import pytesseract
from pathlib import Path
from typing import Optional
from ..log_config import get_logger

log = get_logger(__name__)

_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    r"C:\Users\laksh\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
]


def _find_tesseract() -> Optional[str]:
    for path in _TESSERACT_PATHS:
        if os.path.isfile(path):
            return path
    try:
        result = subprocess.run(["tesseract", "--version"],
                                capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return "tesseract"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


tesseract_path = _find_tesseract()
if tesseract_path:
    pytesseract.pytesseract.tesseract_cmd = tesseract_path
    log.info("Tesseract found at: %s", tesseract_path)
else:
    log.critical("Tesseract OCR not found! Install from: "
                 "https://github.com/UB-Mannheim/tesseract/wiki")
    log.critical("Searched paths: %s", ", ".join(_TESSERACT_PATHS))

_DEBUG_SAVE_DIR = None


def enable_debug_saves(save_dir: str = "debug_captures"):
    global _DEBUG_SAVE_DIR
    _DEBUG_SAVE_DIR = save_dir
    Path(save_dir).mkdir(parents=True, exist_ok=True)
    log.info("Debug image saves enabled -> %s", save_dir)


def _maybe_save_debug(name: str, img: np.ndarray):
    if _DEBUG_SAVE_DIR:
        path = Path(_DEBUG_SAVE_DIR) / f"{name}.png"
        cv2.imwrite(str(path), img)


def _tesseract_or_none(img: np.ndarray, config: str, method: str) -> Optional[str]:
    try:
        return pytesseract.image_to_string(img, config=config).strip()
    except pytesseract.pytesseract.TesseractNotFoundError:
        log.error("TesseractNotFoundError in %s: Tesseract binary not found at '%s'",
                  method, pytesseract.pytesseract.tesseract_cmd)
        return None
    except Exception as e:
        log.warning("Tesseract %s failed: %s", method, e)
        return None


def preprocess(img: np.ndarray, invert: bool = False) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if invert:
        thresh = cv2.bitwise_not(thresh)
    denoised = cv2.fastNlMeansDenoising(thresh, h=30)
    return denoised


def preprocess_digit(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    _, thresh = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    upscaled = cv2.resize(thresh, (0, 0), fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    return upscaled


def _safe_int(val) -> Optional[int]:
    try:
        return int(''.join(c for c in str(val) if c.isdigit()))
    except (ValueError, TypeError):
        return None


def ocr_digits(img: np.ndarray) -> Optional[str]:
    if img is None or img.size == 0:
        log.debug("ocr_digits: empty image")
        return None
    processed = preprocess_digit(img)
    _maybe_save_debug("ocr_digits_input", img)
    _maybe_save_debug("ocr_digits_processed", processed)
    config = "--psm 7 -c tessedit_char_whitelist=0123456789"
    text = _tesseract_or_none(processed, config, "ocr_digits")
    if text:
        log.debug("ocr_digits -> '%s'", text)
    else:
        log.debug("ocr_digits -> None")
    return text if text else None


def ocr_text(img: np.ndarray) -> Optional[str]:
    if img is None or img.size == 0:
        log.debug("ocr_text: empty image")
        return None
    processed = preprocess(img)
    _maybe_save_debug("ocr_text_input", img)
    _maybe_save_debug("ocr_text_processed", processed)
    config = "--psm 7"
    text = _tesseract_or_none(processed, config, "ocr_text")
    if text:
        log.debug("ocr_text -> '%s'", text[:80])
    else:
        log.debug("ocr_text -> None")
    return text if text else None


def ocr_number(img: np.ndarray) -> Optional[int]:
    text = ocr_digits(img)
    if text:
        try:
            val = int(''.join(c for c in text if c.isdigit()))
            log.debug("ocr_number -> %d", val)
            return val
        except ValueError:
            log.warning("ocr_number: failed to parse '%s' as int", text)
            return None
    return None


def ocr_scoreboard_row(img: np.ndarray) -> Optional[dict]:
    if img is None or img.size == 0:
        log.debug("ocr_scoreboard_row: empty image")
        return None
    processed = preprocess(img, invert=False)
    _maybe_save_debug("scoreboard_row", processed)
    config = "--psm 6"
    text = _tesseract_or_none(processed, config, "ocr_scoreboard_row")
    if not text:
        log.debug("ocr_scoreboard_row: no text detected")
        return None
    parts = text.split()
    if len(parts) < 4:
        log.debug("ocr_scoreboard_row: too few parts (%d): '%s'", len(parts), text)
        return None
    row = {
        "name": parts[0],
        "kills": _safe_int(parts[1]),
        "deaths": _safe_int(parts[2]),
        "assists": _safe_int(parts[3]),
    }
    log.debug("ocr_scoreboard_row -> %s", row)
    return row
