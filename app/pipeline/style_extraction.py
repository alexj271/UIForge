"""
Stage 3: Style Extraction
Refines style information from cropped component images using OpenCV color analysis.
Fills in StyleInfo fields that the Vision API may have left null.
"""

from pathlib import Path

import cv2
import numpy as np

from app.models.ast import StyleInfo, UIJsonAST


def run_style_extraction(ast: UIJsonAST) -> UIJsonAST:
    for component in ast.components:
        if component.crop_path:
            component.style = _extract_style(Path(component.crop_path), component.style)
    return ast


def _extract_style(crop_path: Path, existing: StyleInfo) -> StyleInfo:
    image = cv2.imread(str(crop_path))
    if image is None:
        return existing

    # Fill background_color if missing
    if existing.background_color is None:
        existing.background_color = _dominant_color(image)

    return existing


def _dominant_color(image: np.ndarray) -> str:
    """Returns the most common color in the image as a hex string."""
    pixels = image.reshape(-1, 3)
    # Use k-means with k=1 for the dominant color
    pixels_f = np.float32(pixels)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _, _, centers = cv2.kmeans(
        pixels_f, 1, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS
    )
    b, g, r = centers[0].astype(int)
    return f"#{r:02x}{g:02x}{b:02x}"
