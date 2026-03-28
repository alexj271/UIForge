"""
Stage 2: Component Segmentation
Crops each detected component from the original image.
Saves crops to <output_dir>/crops/<component_id>.png.
"""

from pathlib import Path

import cv2
import numpy as np

from typing import Optional

from app.models.ast import UIComponent, UIJsonAST


def run_segmentation(
    ast: UIJsonAST,
    image_path: Path,
    output_dir: Path,
    components: Optional[list[UIComponent]] = None,
) -> UIJsonAST:
    """Crop components from image.

    If *components* is provided, only those components are cropped and
    ast.components is replaced with them. Otherwise all ast.components are cropped.
    """
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Cannot read image: {image_path}")

    h, w = image.shape[:2]
    crops_dir = output_dir / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)

    targets = components if components is not None else ast.components
    for component in targets:
        component.crop_path = _crop_component(image, component, crops_dir, w, h)

    if components is not None:
        ast.components = targets

    return ast


_CROP_PADDING = 4  # extra pixels on each side to preserve shadows/glows


def _crop_component(
    image: np.ndarray,
    component: UIComponent,
    crops_dir: Path,
    img_w: int,
    img_h: int,
) -> str:
    bb = component.bounding_box
    x1 = max(bb.x - _CROP_PADDING, 0)
    y1 = max(bb.y - _CROP_PADDING, 0)
    x2 = min(bb.x + bb.width + _CROP_PADDING, img_w)
    y2 = min(bb.y + bb.height + _CROP_PADDING, img_h)

    crop = image[y1:y2, x1:x2]
    filename = crops_dir / f"{component.id}.png"
    cv2.imwrite(str(filename), crop)
    return str(filename)
