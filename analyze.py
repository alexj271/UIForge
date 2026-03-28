#!/usr/bin/env python3
"""
UIForge CLI — analyze a UI screenshot from the command line.

Usage:
    python analyze.py <image_path> [--target react_native|html]

Artifacts are written to output/<image_stem>/:
    01_detection.json   — raw detected components
    02_segmentation.json — components with crop paths
    03_style.json       — components with extracted styles
    04_layout.json      — components with layout hierarchy
    05_code.jsx / .html — generated code
    crops/              — cropped component images
"""

import argparse
import asyncio
import sys
from pathlib import Path

from PIL import Image

from app.pipeline.detection import run_detection
from app.pipeline.segmentation import run_segmentation
from app.pipeline.style_extraction import run_style_extraction
from app.pipeline.layout import run_layout_reconstruction
from app.pipeline.codegen import run_codegen
from app.pipeline.artifacts import make_output_dir, save_ast, save_code, save_detection_debug, resize_to_perceived
from app.services.ocr import init_ocr_reader
from app.config import settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="analyze.py",
        description="Analyze a UI screenshot and generate component code.",
    )
    parser.add_argument("image", type=Path, help="Path to the screenshot file")
    parser.add_argument(
        "--target",
        choices=["react_native", "html"],
        default="react_native",
        help="Code generation target (default: react_native)",
    )
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    image_path: Path = args.image.resolve()

    if not image_path.exists():
        print(f"error: file not found: {image_path}", file=sys.stderr)
        sys.exit(1)

    output_dir = make_output_dir(image_path.stem)

    print(f"[ UIForge ] {image_path.name}  →  {output_dir}/")

    with Image.open(image_path) as img:
        width, height = img.size
    print(f"            {width}×{height}px")

    if settings.detector == "florence2":
        from app.services.florence_client import init_florence
        print(f"  [init] loading Florence-2 ({settings.florence_model_id})...")
        init_florence(settings.florence_model_id)
    elif settings.detector == "groundingdino":
        from app.services.grounding_dino_client import init_grounding_dino
        print(f"  [init] loading Grounding DINO ({settings.grounding_dino_model_id})...")
        init_grounding_dino(settings.grounding_dino_model_id)

    print(f"  [1/5] detecting components via {settings.detector}...")
    ast, perceived_w, perceived_h = await run_detection(image_path, (width, height))
    print(f"        perceived: {perceived_w}×{perceived_h}  actual: {width}×{height}")
    resized_path = resize_to_perceived(image_path, perceived_w, perceived_h, output_dir)
    print(f"        resized image  →  {resized_path.name}")
    artifact = save_ast(ast, "detection", output_dir)
    debug_img = save_detection_debug(ast, resized_path, output_dir)
    print(f"        {len(ast.components)} components  →  {artifact.name}, {debug_img.name}")

    print("  [2/5] segmenting and cropping components...")
    init_ocr_reader(["en"])
    ast = run_segmentation(ast, resized_path, output_dir)
    artifact = save_ast(ast, "segmentation", output_dir)
    print(f"        {len(ast.components)} crops  →  {artifact.name}, crops/")

    print("  [3/5] extracting styles...")
    ast = run_style_extraction(ast)
    artifact = save_ast(ast, "style", output_dir)
    print(f"        →  {artifact.name}")

    print("  [4/5] reconstructing layout hierarchy...")
    ast = run_layout_reconstruction(ast)
    artifact = save_ast(ast, "layout", output_dir)
    print(f"        {len(ast.components)} root components  →  {artifact.name}")

    print(f"  [5/5] generating {args.target} code...")
    code = run_codegen(ast, target=args.target)
    artifact = save_code(code, args.target, output_dir)
    print(f"        →  {artifact.name}")

    # Component summary
    print("\n--- components ---")
    for c in ast.components:
        text_preview = f'  "{c.text[:28]}"' if c.text else ""
        color = f"  {c.style.background_color}" if c.style.background_color else ""
        print(f"  {c.id:<14} {c.type:<12} {c.bounding_box.width}×{c.bounding_box.height}px{text_preview}{color}")

    print(f"\nall artifacts saved to: {output_dir}/")


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run(args))
