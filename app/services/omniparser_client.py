"""
OmniParser-based UI component detector.

Uses the YOLOv8 icon-detection model from microsoft/OmniParser-v2.0.
Optionally captions each detected region with a finetuned Florence-2 model
(same checkpoint shipped in the OmniParser weights bundle).

Model weights must be downloaded once before first use:
    huggingface-cli download microsoft/OmniParser-v2.0 \\
        --local-dir weights --repo-type model

Set OMNIPARSER_MODEL_DIR in .env to override the default "weights/" path.

Inference runs synchronously in a thread-pool executor to preserve the
async detect_components() interface shared by all backends.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

_yolo_model = None
_caption_processor = None
_caption_model = None
_caption_device: str = "cpu"


def init_omniparser(model_dir: str = "weights", load_captions: bool = True) -> None:
    """Load YOLO detection model (and optionally Florence-2 captioner).

    Call once at startup before any detect_components() call.

    Parameters
    ----------
    model_dir:
        Local directory containing the downloaded OmniParser weights
        (icon_detect/ and optionally icon_caption_florence/ sub-dirs).
    load_captions:
        If True, also load the Florence-2 captioning model so that each
        detected region gets a human-readable label.  Adds ~1 GB RAM but
        produces more meaningful component types.  Set to False for speed.
    """
    global _yolo_model, _caption_processor, _caption_model, _caption_device

    from ultralytics import YOLO

    icon_detect_path = Path(model_dir) / "icon_detect" / "model.pt"
    if not icon_detect_path.exists():
        raise FileNotFoundError(
            f"OmniParser YOLO weights not found at {icon_detect_path}.\n"
            "Download with:\n"
            "  huggingface-cli download microsoft/OmniParser-v2.0 "
            "--local-dir weights --repo-type model"
        )

    _yolo_model = YOLO(str(icon_detect_path))
    logger.info("OmniParser YOLO model loaded from %s", icon_detect_path)

    if load_captions:
        caption_dir = Path(model_dir) / "icon_caption"
        if caption_dir.exists():
            import torch
            from transformers import AutoModelForCausalLM, AutoProcessor

            _caption_device = "cuda" if torch.cuda.is_available() else "cpu"
            # Processor configs are not shipped in the weights bundle —
            # load from the base model instead.
            _caption_processor = AutoProcessor.from_pretrained(
                "microsoft/Florence-2-base-ft", trust_remote_code=True
            )
            _caption_model = AutoModelForCausalLM.from_pretrained(
                str(caption_dir),
                torch_dtype=torch.float16
                if _caption_device == "cuda"
                else torch.float32,
                trust_remote_code=True,
                attn_implementation="eager",
            ).to(_caption_device)
            _caption_model.eval()
            logger.info("OmniParser Florence-2 captioner loaded from %s", caption_dir)
        else:
            logger.warning(
                "icon_caption_florence/ not found in %s — captions disabled", model_dir
            )


# ---------------------------------------------------------------------------
# Type mapping helpers
# ---------------------------------------------------------------------------

_TYPE_KEYWORDS: list[tuple[list[str], str]] = [
    (["button", "btn", "cta", "submit", "click"], "button"),
    (["icon", "logo", "symbol", "glyph"], "icon"),
    (["card", "tile", "panel", "chip", "badge"], "card"),
    (["input", "field", "textbox", "search", "text box"], "input"),
    (
        ["navigation", "nav bar", "navbar", "header", "footer", "tab bar", "toolbar"],
        "container",
    ),
    (["text", "label", "title", "heading", "caption", "subtitle"], "text"),
    (["image", "photo", "picture", "thumbnail", "avatar", "banner"], "image"),
    (["checkbox", "toggle", "switch", "radio"], "input"),
    (["dropdown", "select", "menu", "list"], "container"),
]


def _caption_to_type(caption: str) -> str:
    low = caption.lower()
    for keywords, component_type in _TYPE_KEYWORDS:
        if any(kw in low for kw in keywords):
            return component_type
    return "unknown"


# ---------------------------------------------------------------------------
# Sync inference (runs in thread-pool)
# ---------------------------------------------------------------------------


def _caption_regions(
    image: Image.Image,
    boxes_xyxy: list[list[float]],
) -> list[str]:
    """Generate a one-line caption for each bounding-box crop."""
    if _caption_model is None or _caption_processor is None:
        return ["" for _ in boxes_xyxy]

    import torch

    captions: list[str] = []
    w, h = image.size

    for box in boxes_xyxy:
        x1, y1, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
        # clamp
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            captions.append("")
            continue

        crop = image.crop((x1, y1, x2, y2))
        inputs = _caption_processor(
            text="<CAPTION>",
            images=crop,
            return_tensors="pt",
        ).to(_caption_device)

        with torch.inference_mode():
            out = _caption_model.generate(
                **inputs,
                max_new_tokens=32,
                use_cache=False,
            )

        raw = _caption_processor.batch_decode(out, skip_special_tokens=True)[0]
        captions.append(raw.strip())

    return captions


def _run_omniparser_sync(
    image: Image.Image,
    conf_threshold: float,
) -> tuple[list[dict], int, int]:
    """Blocking YOLO inference + optional captioning."""
    if _yolo_model is None:
        raise RuntimeError("OmniParser not initialised — call init_omniparser() first")

    w, h = image.size

    results = _yolo_model.predict(source=image, conf=conf_threshold, verbose=False)

    boxes_obj = results[0].boxes
    if boxes_obj is None or len(boxes_obj) == 0:
        return [], w, h

    xyxy_list: list[list[float]] = boxes_obj.xyxy.tolist()
    conf_list: list[float] = boxes_obj.conf.tolist()

    # Sort by confidence descending
    pairs = sorted(zip(xyxy_list, conf_list), key=lambda p: p[1], reverse=True)
    sorted_boxes = [p[0] for p in pairs]
    sorted_confs = [p[1] for p in pairs]

    captions = _caption_regions(image, sorted_boxes)

    components: list[dict] = []
    for idx, (box, score, caption) in enumerate(
        zip(sorted_boxes, sorted_confs, captions)
    ):
        x1, y1, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
        x1 = max(0, min(x1, w - 1))
        y1 = max(0, min(y1, h - 1))
        x2 = max(x1 + 1, min(x2, w))
        y2 = max(y1 + 1, min(y2, h))

        components.append(
            {
                "id": f"comp_{idx}",
                "type": _caption_to_type(caption) if caption else "unknown",
                "bounding_box": {
                    "x": x1,
                    "y": y1,
                    "width": x2 - x1,
                    "height": y2 - y1,
                },
                "text": caption or None,
                "style": {},
            }
        )

    return components, w, h


# ---------------------------------------------------------------------------
# Async public interface (matches all other detector backends)
# ---------------------------------------------------------------------------


async def detect_components(
    image_path: Path,
    image_size: tuple[int, int],
    conf_threshold: float = 0.3,
) -> tuple[list[dict], int, int]:
    """Detect UI components using OmniParser YOLOv8.

    Returns (components, perceived_width, perceived_height).
    Coordinates are in the original image pixel space.
    """
    image = Image.open(image_path).convert("RGB")
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        _run_omniparser_sync,
        image,
        conf_threshold,
    )
