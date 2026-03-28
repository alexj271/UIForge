import base64
import json
from pathlib import Path

from openai import AsyncOpenAI

from app.config import settings

_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
    return _client


DETECTION_PROMPT = """
You are a UI analysis assistant. Analyze this screenshot and detect all visible UI components.

First, report the pixel dimensions of the image exactly as you perceive them.
Then list all visible UI components.

Return ONLY a single valid JSON object in this exact shape (no markdown, no explanation):
{
  "perceived_width": <integer>,
  "perceived_height": <integer>,
  "components": [
    {
      "id": "btn_1",
      "type": "<button|card|text|image|icon|container|input|unknown>",
      "bounding_box": {"x": <int>, "y": <int>, "width": <int>, "height": <int>},
      "text": "<text or null>",
      "style": {
        "background_color": "<value or null>",
        "border_color": "<value or null>",
        "border_width": <int or null>,
        "border_radius": <int or null>,
        "shadow": "<value or null>",
        "text_color": "<value or null>",
        "font_size": <int or null>
      }
    }
  ]
}
""".strip()


async def detect_components(
    image_path: Path,
    image_size: tuple[int, int],
) -> tuple[list[dict], int, int]:
    """
    Returns (components, perceived_width, perceived_height).
    Coordinates in components are in perceived pixel space — caller must
    resize the image to (perceived_width, perceived_height) before cropping.
    """
    client = get_openai_client()
    actual_w, actual_h = image_size

    image_data = base64.standard_b64encode(image_path.read_bytes()).decode()
    ext = image_path.suffix.lstrip(".")
    media_type = f"image/{ext}" if ext in ("png", "jpg", "jpeg", "webp", "gif") else "image/png"

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": DETECTION_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{media_type};base64,{image_data}"},
                    },
                ],
            }
        ],
        max_tokens=4096,
    )

    raw = response.choices[0].message.content or "{}"
    result = json.loads(_strip_markdown_fences(raw))

    perceived_w = int(result.get("perceived_width", actual_w))
    perceived_h = int(result.get("perceived_height", actual_h))
    components  = result.get("components", [])

    # clamp coords to perceived bounds
    for comp in components:
        bb = comp.get("bounding_box", {})
        x = max(0, min(int(bb.get("x", 0)),     perceived_w - 1))
        y = max(0, min(int(bb.get("y", 0)),     perceived_h - 1))
        w = max(1, min(int(bb.get("width",  1)), perceived_w - x))
        h = max(1, min(int(bb.get("height", 1)), perceived_h - y))
        bb["x"], bb["y"], bb["width"], bb["height"] = x, y, w, h

    return components, perceived_w, perceived_h


def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text[text.index("\n") + 1:] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[: text.rfind("```")]
    return text.strip()
