"""
Artifact management: creates output/<stem>/ and saves per-stage snapshots.

Output structure:
  output/<stem>/
  ├── 01_detection.json
  ├── 01_detection_debug.jpg   ← original image with bounding boxes + IDs
  ├── 02_segmentation.json
  ├── 03_style.json
  ├── 04_layout.json
  ├── 05_code.jsx  (or .html)
  └── crops/
      ├── btn_1.png
      └── ...
"""

from pathlib import Path

import cv2
from PIL import Image

from app.models.ast import UIJsonAST
from app.models.dsl import ComponentDSL, ComponentLibrary

OUTPUT_ROOT = Path("output")

_STAGE_FILES = {
    "detection": "01_detection.json",
    "toplevel": "02_toplevel.json",
    "segmentation": "02_segmentation.json",
    "style": "03_style.json",
    "layout": "04_layout.json",
}

_CODE_EXT = {
    "react_native": "jsx",
    "html": "html",
}


def make_output_dir(stem: str) -> Path:
    out = OUTPUT_ROOT / stem
    out.mkdir(parents=True, exist_ok=True)
    return out


def save_ast(ast: UIJsonAST, stage: str, output_dir: Path) -> Path:
    filename = _STAGE_FILES[stage]
    path = output_dir / filename
    path.write_text(ast.model_dump_json(indent=2), encoding="utf-8")
    return path


def resize_to_perceived(
    image_path: Path,
    perceived_w: int,
    perceived_h: int,
    output_dir: Path,
) -> Path:
    """Resize original image to perceived dimensions, save to output_dir/00_resized.jpg."""
    with Image.open(image_path) as img:
        resized = img.resize((perceived_w, perceived_h), Image.LANCZOS)
        out_path = output_dir / "00_resized.jpg"
        resized.save(out_path, "JPEG", quality=92)
    return out_path


def save_detection_debug(ast: UIJsonAST, image_path: Path, output_dir: Path) -> Path:
    """
    Draw bounding boxes and component IDs on the original image and save to
    output_dir/01_detection_debug.jpg.
    """
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Cannot read image: {image_path}")

    img_h, img_w = image.shape[:2]

    # Generate a distinct color per component type
    _TYPE_COLORS: dict[str, tuple[int, int, int]] = {
        "button": (57, 197, 255),  # orange
        "card": (86, 219, 108),  # green
        "text": (255, 191, 0),  # cyan-yellow
        "image": (180, 50, 220),  # purple
        "icon": (0, 165, 255),  # amber
        "container": (200, 200, 200),  # gray
        "input": (100, 220, 255),  # yellow
        "unknown": (128, 128, 128),  # dark gray
    }
    default_color = (200, 200, 200)

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = max(0.4, img_w / 1800)
    thickness = max(1, img_w // 600)
    pad = 4  # label background padding

    for comp in ast.components:
        bb = comp.bounding_box
        x1, y1 = max(bb.x, 0), max(bb.y, 0)
        x2, y2 = min(bb.x + bb.width, img_w), min(bb.y + bb.height, img_h)
        color = _TYPE_COLORS.get(comp.type, default_color)

        # Bounding box
        cv2.rectangle(image, (x1, y1), (x2, y2), color, thickness)

        # Label: "id (type)"
        label = f"{comp.id} ({comp.type})"
        (tw, th), baseline = cv2.getTextSize(label, font, font_scale, thickness)

        # Place label inside the box at top-left; shift down if it would clip
        lx = x1 + pad
        ly = y1 + th + pad
        if ly > y2 - pad:
            ly = y2 - pad  # push up if box is very short

        # Filled background for readability
        cv2.rectangle(
            image,
            (lx - pad, ly - th - pad),
            (lx + tw + pad, ly + baseline + pad),
            color,
            cv2.FILLED,
        )
        # Dark text on colored background
        text_color = (20, 20, 20)
        cv2.putText(
            image, label, (lx, ly), font, font_scale, text_color, thickness, cv2.LINE_AA
        )

    out_path = output_dir / "01_detection_debug.jpg"
    cv2.imwrite(str(out_path), image, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return out_path


_CODEGEN_EXT = {
    "react_native": "jsx",
    "react": "jsx",
    "html": "html",
}


def save_library(library: ComponentLibrary, output_dir: Path) -> Path:
    """Save ComponentLibrary to output_dir/03_library.json."""
    path = output_dir / "03_library.json"
    path.write_text(library.model_dump_json(indent=2), encoding="utf-8")
    return path


def save_dsl(dsl: ComponentDSL, output_dir: Path) -> Path:
    """Save an individual ComponentDSL to output_dir/library/<id>.dsl.json."""
    library_dir = output_dir / "library"
    library_dir.mkdir(exist_ok=True)
    path = library_dir / f"{dsl.id}.dsl.json"
    path.write_text(dsl.model_dump_json(indent=2), encoding="utf-8")
    return path


def save_component_code(
    code: str, component_id: str, target: str, output_dir: Path
) -> Path:
    """Save generated component code to output_dir/library/<id>.<ext>."""
    library_dir = output_dir / "library"
    library_dir.mkdir(exist_ok=True)
    ext = _CODEGEN_EXT.get(target, "txt")
    path = library_dir / f"{component_id}.{ext}"
    path.write_text(code, encoding="utf-8")
    return path


def save_code(code: str, target: str, output_dir: Path) -> Path:
    ext = _CODE_EXT.get(target, "txt")
    path = output_dir / f"05_code.{ext}"
    path.write_text(code, encoding="utf-8")
    return path
