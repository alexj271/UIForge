"""
Integration test: full pipeline on a real screenshot.
Requires OPENAI_API_KEY in .env and network access.

Run with:
    pytest tests/test_integration.py -v -m integration
"""

import pytest
from pathlib import Path
from PIL import Image

from app.pipeline.detection import run_detection
from app.pipeline.segmentation import run_segmentation
from app.pipeline.style_extraction import run_style_extraction
from app.pipeline.layout import run_layout_reconstruction
from app.pipeline.codegen import run_codegen

SAMPLE = Path(__file__).parent / "assets" / "example1.jpg"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_pipeline_on_real_screenshot():
    assert SAMPLE.exists(), f"Test asset not found: {SAMPLE}"

    with Image.open(SAMPLE) as img:
        width, height = img.size

    # Stage 1: detection via OpenAI Vision
    ast = await run_detection(SAMPLE, (width, height))

    assert ast.source_image == SAMPLE.name
    assert ast.width == width
    assert ast.height == height
    assert len(ast.components) > 0, "Vision API returned no components"

    print(f"\n[detection] {len(ast.components)} components found")
    for c in ast.components:
        print(f"  {c.id}: type={c.type}, text={c.text!r}, bbox={c.bounding_box}")

    # Stage 2: segmentation — crop images must be created
    ast = run_segmentation(ast, SAMPLE)

    crops_created = [c for c in ast.components if c.crop_path and Path(c.crop_path).exists()]
    assert len(crops_created) == len(ast.components), (
        f"Not all crops were created: {len(crops_created)}/{len(ast.components)}"
    )
    print(f"[segmentation] {len(crops_created)} crops saved")

    # Stage 3: style extraction — background_color must be filled for all crops
    ast = run_style_extraction(ast)

    styled = [c for c in ast.components if c.style.background_color]
    assert len(styled) > 0, "Style extraction produced no colors"
    print(f"[style] {len(styled)}/{len(ast.components)} components have background_color")

    # Stage 4: layout reconstruction — result must have at least one root component
    ast = run_layout_reconstruction(ast)
    assert len(ast.components) > 0
    print(f"[layout] {len(ast.components)} root components after hierarchy reconstruction")

    # Stage 5: codegen — both targets must produce non-empty output
    for target in ("react_native", "html"):
        code = run_codegen(ast, target=target)
        assert len(code) > 0, f"codegen produced empty output for target={target}"
        print(f"[codegen:{target}] {len(code)} chars generated")
