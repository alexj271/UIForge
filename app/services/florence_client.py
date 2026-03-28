"""
Florence-2 based UI component detector.

Uses DENSE_REGION_CAPTION task to get rich region descriptions, then maps
them to UIForge component types via keyword matching.

Model is loaded once at startup via init_florence() called from lifespan.
Inference runs synchronously in a thread pool to keep the async interface.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from PIL import Image

_model = None
_processor = None
_device: str = "cpu"


def init_florence(model_id: str = "microsoft/Florence-2-large") -> None:
    """Load model and processor into module-level singletons. Call once at startup."""
    global _model, _processor, _device
    import torch
    from transformers import AutoModelForCausalLM, AutoProcessor

    _device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if _device == "cuda" else torch.float32

    _processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
    _model = AutoModelForCausalLM.from_pretrained(
        model_id,
        trust_remote_code=True,
        dtype=dtype,
        attn_implementation="eager",  # Florence-2 custom code doesn't declare _supports_sdpa
    ).to(_device)
    _model.eval()


# ---------------------------------------------------------------------------
# Label → ComponentType mapping
# ---------------------------------------------------------------------------

_TYPE_KEYWORDS: list[tuple[list[str], str]] = [
    (["button", "btn", "cta", "submit", "click", "tap"], "button"),
    (["icon", "logo", "symbol", "badge", "glyph", "emoji"], "icon"),
    (["image", "photo", "picture", "thumbnail", "avatar", "banner", "illustration"], "image"),
    (["input", "field", "textbox", "search bar", "text field", "form", "edittext"], "input"),
    (["card", "panel", "tile", "chip"], "card"),
    (["text", "label", "title", "heading", "paragraph", "caption", "subtitle"], "text"),
    (["container", "section", "layout", "background", "header", "footer", "navbar", "nav", "toolbar", "tab bar"], "container"),
]


def _label_to_type(label: str) -> str:
    low = label.lower()
    for keywords, component_type in _TYPE_KEYWORDS:
        if any(kw in low for kw in keywords):
            return component_type
    return "unknown"


# ---------------------------------------------------------------------------
# Sync inference
# ---------------------------------------------------------------------------

def _run_florence_sync(
    image: Image.Image,
) -> tuple[list[dict], int, int]:
    """Blocking inference — call via run_in_executor."""
    import torch

    if _model is None or _processor is None:
        raise RuntimeError("Florence-2 model not initialised; call init_florence() first")

    w, h = image.size

    # CAPTION_TO_PHRASE_GROUNDING: ground explicit UI vocabulary in the image.
    # More reliable than DENSE_REGION_CAPTION for UI screenshots because we
    # tell the model exactly what elements to find.
    task = "<CAPTION_TO_PHRASE_GROUNDING>"
    ui_prompt = (
        "button. text label. title heading. icon. navigation bar. tab bar. "
        "card. input field. image. container. header."
    )
    inputs = _processor(text=task + ui_prompt, images=image, return_tensors="pt").to(_device)

    with torch.inference_mode():
        generated_ids = _model.generate(
            input_ids=inputs["input_ids"],
            pixel_values=inputs["pixel_values"],
            max_new_tokens=1024,
            do_sample=False,
            num_beams=1,
            use_cache=False,  # DynamicCache (transformers 4.46+) breaks Florence-2 custom code
        )

    generated_text = _processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
    parsed = _processor.post_process_generation(
        generated_text,
        task=task,
        image_size=(w, h),
    )

    result = parsed.get(task, {})
    bboxes: list[list[float]] = result.get("bboxes", [])
    labels: list[str] = result.get("labels", [])

    components: list[dict] = []
    for idx, (bbox, label) in enumerate(zip(bboxes, labels)):
        x1, y1, x2, y2 = [int(v) for v in bbox]
        # clamp to image bounds
        x1 = max(0, min(x1, w - 1))
        y1 = max(0, min(y1, h - 1))
        x2 = max(x1 + 1, min(x2, w))
        y2 = max(y1 + 1, min(y2, h))

        components.append({
            "id": f"comp_{idx}",
            "type": _label_to_type(label),
            "bounding_box": {
                "x": x1,
                "y": y1,
                "width": x2 - x1,
                "height": y2 - y1,
            },
            "text": label,  # pass raw caption as text; OCR will refine it
            "style": {},
        })

    return components, w, h


# ---------------------------------------------------------------------------
# Async entry-point (matches openai_client interface)
# ---------------------------------------------------------------------------

async def detect_components(
    image_path: Path,
    image_size: tuple[int, int],  # kept for interface parity; Florence reads actual size
) -> tuple[list[dict], int, int]:
    image = Image.open(image_path).convert("RGB")
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run_florence_sync, image)
