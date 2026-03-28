"""
EasyOCR reader — initialized once at application startup (model is ~500 MB).
Access via get_ocr_reader() from FastAPI dependency injection or pipeline code.
"""

import easyocr
import numpy as np

_reader: easyocr.Reader | None = None


def init_ocr_reader(languages: list[str] | None = None) -> None:
    """Call once during app lifespan startup."""
    global _reader
    _reader = easyocr.Reader(languages or ["en"], gpu=False)


def get_ocr_reader() -> easyocr.Reader:
    if _reader is None:
        raise RuntimeError("OCR reader not initialized. Call init_ocr_reader() at startup.")
    return _reader


def extract_text(image_array: np.ndarray) -> str:
    """Run OCR on a NumPy image array and return joined text."""
    reader = get_ocr_reader()
    results = reader.readtext(image_array, detail=0)
    return " ".join(results)
