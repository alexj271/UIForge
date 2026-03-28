"""
Grounding DINO based UI component detector.

Uses zero-shot object detection with a text prompt of UI element classes.
Runs via HuggingFace transformers — no separate weight download needed.

Model is loaded once at startup via init_grounding_dino() called from lifespan.
Inference runs synchronously in a thread pool to keep the async interface.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from PIL import Image

_model = None
_processor = None
_device: str = "cpu"

# Dot-separated vocabulary fed to Grounding DINO.
# Each term is an open-vocabulary class the model will try to locate.
UI_TEXT_PROMPT = (
    "button . icon . text label . title . heading . navigation bar . "
    "tab bar . card . statistics card . circular badge . input field . "
    "image . container . header . footer ."
)

# Map detected phrases back to UIForge ComponentType
_TYPE_KEYWORDS: list[tuple[list[str], str]] = [
    (["button", "cta", "submit"], "button"),
    (["icon", "logo", "badge", "symbol"], "icon"),
    (["statistics card", "circular badge", "card", "tile", "chip", "panel"], "card"),
    (["input", "field", "textbox", "search"], "input"),
    (
        ["navigation bar", "nav bar", "navbar", "header", "footer", "tab bar"],
        "container",
    ),
    (
        ["title", "heading", "text label", "label", "text", "caption", "subtitle"],
        "text",
    ),
    (["image", "photo", "picture", "thumbnail", "avatar", "banner"], "image"),
    (["container", "section", "layout", "background"], "container"),
]


def _phrase_to_type(phrase: str) -> str:
    low = phrase.lower()
    for keywords, component_type in _TYPE_KEYWORDS:
        if any(kw in low for kw in keywords):
            return component_type
    return "unknown"


def init_grounding_dino(model_id: str = "IDEA-Research/grounding-dino-base") -> None:
    """Load model and processor. Call once at startup."""
    global _model, _processor, _device
    import torch
    from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

    _device = "cuda" if torch.cuda.is_available() else "cpu"

    _processor = AutoProcessor.from_pretrained(model_id)
    _model = AutoModelForZeroShotObjectDetection.from_pretrained(model_id).to(_device)
    _model.eval()


def _run_grounding_dino_sync(
    image: Image.Image,
    box_threshold: float,
    text_threshold: float,
) -> tuple[list[dict], int, int]:
    """Blocking inference — call via run_in_executor."""
    import torch

    if _model is None or _processor is None:
        raise RuntimeError(
            "Grounding DINO not initialised; call init_grounding_dino() first"
        )

    w, h = image.size

    inputs = _processor(
        images=image,
        text=UI_TEXT_PROMPT,
        return_tensors="pt",
    ).to(_device)

    with torch.inference_mode():
        outputs = _model(**inputs)

    results = _processor.post_process_grounded_object_detection(
        outputs,
        inputs.input_ids,
        threshold=box_threshold,
        text_threshold=text_threshold,
        target_sizes=[(h, w)],
    )[0]

    boxes = results["boxes"].tolist()  # [[x1,y1,x2,y2], ...] absolute px
    scores = results["scores"].tolist()
    labels = results["labels"]

    components: list[dict] = []
    for idx, (box, score, label) in enumerate(zip(boxes, scores, labels)):
        x1, y1, x2, y2 = [int(v) for v in box]
        x1 = max(0, min(x1, w - 1))
        y1 = max(0, min(y1, h - 1))
        x2 = max(x1 + 1, min(x2, w))
        y2 = max(y1 + 1, min(y2, h))

        components.append(
            {
                "id": f"comp_{idx}",
                "type": _phrase_to_type(label),
                "bounding_box": {
                    "x": x1,
                    "y": y1,
                    "width": x2 - x1,
                    "height": y2 - y1,
                },
                "text": label,
                "style": {},
                "_score": round(score, 3),
            }
        )

    # Sort by confidence descending
    components.sort(key=lambda c: c.pop("_score"), reverse=True)

    return components, w, h


async def detect_components(
    image_path: Path,
    image_size: tuple[int, int],
    box_threshold: float = 0.3,
    text_threshold: float = 0.25,
) -> tuple[list[dict], int, int]:
    image = Image.open(image_path).convert("RGB")
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        _run_grounding_dino_sync,
        image,
        box_threshold,
        text_threshold,
    )
