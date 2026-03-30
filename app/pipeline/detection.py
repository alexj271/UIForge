"""
Stage 1: UI Detection
Detects UI components using the configured backend
(openai | florence2 | groundingdino | omniparser)
and returns the UI JSON AST plus the image size used for coordinates.
"""

from pathlib import Path

from app.config import settings
from app.models.ast import BoundingBox, StyleInfo, UIComponent, UIJsonAST

if settings.detector == "florence2":
    from app.services.florence_client import detect_components
elif settings.detector == "groundingdino":
    from app.services.grounding_dino_client import detect_components
elif settings.detector == "omniparser":
    from app.services.omniparser_client import detect_components
else:
    from app.services.openai_client import detect_components


async def run_detection(
    image_path: Path,
    image_size: tuple[int, int],
) -> tuple[UIJsonAST, int, int]:
    """
    Returns (UIJsonAST, perceived_width, perceived_height).
    Bounding boxes are in perceived pixel space.
    """
    raw_components, perceived_w, perceived_h = await detect_components(
        image_path, image_size
    )

    components: list[UIComponent] = []
    for raw in raw_components:
        bb = raw.get("bounding_box", {})
        style_raw = raw.get("style") or {}
        components.append(
            UIComponent(
                id=raw.get("id", f"comp_{len(components)}"),
                type=raw.get("type", "unknown"),
                bounding_box=BoundingBox(
                    x=bb.get("x", 0),
                    y=bb.get("y", 0),
                    width=bb.get("width", 0),
                    height=bb.get("height", 0),
                ),
                text=raw.get("text"),
                style=StyleInfo(
                    **{k: v for k, v in style_raw.items() if v is not None}
                ),
            )
        )

    ast = UIJsonAST(
        source_image=image_path.name,
        width=perceived_w,
        height=perceived_h,
        components=components,
    )
    return ast, perceived_w, perceived_h
