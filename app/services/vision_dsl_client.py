"""
Vision DSL Client — extracts a ComponentDSL from a component crop image
by calling the configured vision LLM (default: gpt-4o).

The model receives the crop as a base64-encoded image and a system prompt
that specifies the exact ComponentDSL JSON schema.  The response is parsed
and validated against the ComponentDSL Pydantic model.

Returns None on any failure (API error, JSON parse error, validation error)
so callers can handle partial failures gracefully.
"""

import base64
import json
import logging
from pathlib import Path
from typing import Optional

from openai import AsyncOpenAI

from app.models.dsl import ComponentDSL

logger = logging.getLogger(__name__)


def _try_repair_json(text: str, component_id: str) -> Optional[dict]:
    """Attempt to fix common LLM JSON issues and re-parse."""
    import re

    repaired = text.strip()
    # Strip markdown fences if present
    repaired = re.sub(r"^```[a-zA-Z]*\n?", "", repaired)
    repaired = re.sub(r"\n?```$", "", repaired.strip())
    # Remove trailing commas before ] or }
    repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError as exc:
        logger.error("DSL JSON parse error for %s: %s", component_id, exc)
        return None


_DSL_SYSTEM_PROMPT = """\
You are a UI component visual analyzer. Given a cropped image of a single UI component,
perform a thorough analysis and return ONLY a JSON object matching this exact schema.
Capture EVERYTHING visible: all text, all icons, the internal layout, and every visual style detail.

IMPORTANT — the crop has 4 px of transparent/background padding on each side intentionally added
to preserve drop shadows and glows.  You MUST measure and describe any shadow you see in that
padding area.  Do not ignore soft edges, halos, or coloured glows around the component — those
are shadows/glows and belong in the "shadow" field.

FULL SCHEMA:
{
  "id": "<string — the component ID provided by the caller>",
  "label": "<short human-readable name, e.g. 'primary button', 'product card', 'bottom nav bar'>",
  "width": <number — rendered width in pixels>,
  "height": <number — rendered height in pixels>,

  "background": {
    "type": "<'solid' or 'gradient'>",
    "color": "<hex — only when type='solid', else null>",
    "gradient": {
      "direction": "<CSS direction e.g. 'to right', '135deg'>",
      "stops": [{"color": "<hex>", "position": <0.0-1.0>}, ...]
    }
  },
  "border_radius": <number — uniform corner radius in px, 0 if square>,
  "border": {"width": <px>, "color": "<hex>", "style": "solid|dashed|dotted"} or null,
  "shadow": {"offset_x": <px>, "offset_y": <px>, "blur": <px>, "spread": <px>, "color": "<hex|rgba>"} or null,
  "opacity": <0.0-1.0, default 1.0>,
  "crop_path": "<the crop_path value provided by the caller>",

  "texts": [
    {
      "content": "<exact text string visible in the component>",
      "font_size": <px or null>,
      "font_weight": "<'normal'|'bold'|'600' etc. or null>",
      "color": "<hex>",
      "text_align": "<'left'|'center'|'right' or null>"
    }
    // one entry per distinct text element; empty array [] if no text
  ],

  "icons": [
    {
      "name": "<icon name if recognizable e.g. 'search', 'home', 'chevron-right', 'star', 'plus' — or null>",
      "color": "<hex or null>",
      "size": <approximate size in px or null>
    }
    // one entry per visible icon/pictogram; empty array [] if none
  ],

  "layout": {
    "direction": "<'row'|'column'|'stack'>",
    "align_items": "<'flex-start'|'center'|'flex-end'|'stretch' or null>",
    "justify_content": "<'flex-start'|'center'|'space-between'|'space-around'|'flex-end' or null>",
    "gap": <spacing between children in px or null>,
    "padding_top": <px or null>,
    "padding_right": <px or null>,
    "padding_bottom": <px or null>,
    "padding_left": <px or null>
  } or null if single atomic element,

  "children": [
    {
      "role": "<'text'|'icon'|'image'|'button'|'badge'|'avatar'|'divider'|'input'|'checkbox'|'tag'|other>",
      "description": "<brief description of this child, e.g. 'blue search icon on the left'>",
      "texts": [ { same TextDSL schema as above } ],
      "icon": { same IconDSL schema } or null,
      "background": { same BackgroundDSL schema } or null,
      "border_radius": <px or null>,
      "width": <px or null>,
      "height": <px or null>
    }
    // one entry per distinct child element inside this component
    // empty array [] if the component is atomic (single icon, single text, etc.)
  ]
}

RULES:
- Transcribe ALL visible text exactly as it appears (including labels, numbers, placeholders).
- Identify every icon/glyph even if the name is uncertain — use a descriptive name like "three-bar-menu".
- For layout: observe the actual arrangement of children (horizontal row, vertical stack, etc.).
- SHADOWS: inspect the 4 px padding zone around the component edge carefully.
  If you see any soft shadow, glow, or coloured halo, fill the "shadow" object with realistic values:
    offset_x/offset_y: direction of the shadow (positive = right/down),
    blur: softness radius (typically 4–20 px for UI shadows),
    spread: extra expansion (0 if tight),
    color: use rgba for semi-transparent shadows, e.g. "rgba(0,0,0,0.25)".
  Never set all shadow fields to 0 if a shadow is visible — estimate honestly.
- All fill colors MUST be hex (e.g. '#FF5733'). Shadow color may be rgba.
- Use null for absent optional fields; do NOT omit keys.
- Output ONLY the JSON object — no markdown, no explanation, no code fences.
"""


async def extract_dsl(
    component_id: str,
    crop_path: Path,
    settings: object,
) -> Optional[ComponentDSL]:
    """Extract a ComponentDSL from a crop image using the vision LLM.

    Returns None if the crop file is missing, the API call fails, or the
    response cannot be parsed into a valid ComponentDSL.
    """
    if not crop_path.exists():
        logger.warning("crop not found, skipping DSL extraction: %s", crop_path)
        return None

    # Encode the image as base64
    try:
        raw = crop_path.read_bytes()
        b64 = base64.b64encode(raw).decode()
        mime = "image/png" if crop_path.suffix.lower() == ".png" else "image/jpeg"
    except OSError as exc:
        logger.error("cannot read crop %s: %s", crop_path, exc)
        return None

    client = AsyncOpenAI(
        api_key=settings.openai_api_key,  # type: ignore[attr-defined]
        base_url=settings.openai_base_url,  # type: ignore[attr-defined]
    )

    user_content = [
        {
            "type": "text",
            "text": (
                f"Component ID: {component_id}\n"
                f"Crop path: {crop_path}\n"
                "Analyze the image and return the ComponentDSL JSON."
            ),
        },
        {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"},
        },
    ]

    try:
        response = await client.chat.completions.create(
            model=settings.dsl_model,  # type: ignore[attr-defined]
            messages=[
                {"role": "system", "content": _DSL_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            max_tokens=2048,
            temperature=0,
        )
    except Exception as exc:
        logger.error("DSL extraction API error for %s: %s", component_id, exc)
        return None

    raw_text = response.choices[0].message.content or ""
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        # Try to repair common LLM JSON issues (trailing commas, etc.)
        data = _try_repair_json(raw_text, component_id)
        if data is None:
            return None

    # Force the correct id and crop_path regardless of what the model returned
    data["id"] = component_id
    data["crop_path"] = str(crop_path)

    try:
        return ComponentDSL.model_validate(data)
    except Exception as exc:
        logger.error("ComponentDSL validation error for %s: %s", component_id, exc)
        return None
