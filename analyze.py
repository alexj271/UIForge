#!/usr/bin/env python3
"""
UIForge CLI — extract a component library from a UI screenshot.

Usage:
    python analyze.py <image_path> [--target html|react|react_native]

New pipeline (default):
    [1/4] Detection          → 01_detection.json + 01_detection_debug.jpg
    [2/4] Nesting filter     → 02_toplevel.json  (top-level components only)
    [3/4] DSL extraction     → 03_library.json + library/*.dsl.json + crops/
    [4/4] Code generation    → library/*.<ext>

Legacy pipeline (--legacy):
    Original 5-stage layout-reconstruction pipeline.
    Deprecated — will be removed in a future release.

Artifacts are written to output/<image_stem>/.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from PIL import Image

from app.config import settings
from app.pipeline.artifacts import (
    make_output_dir,
    resize_to_perceived,
    save_ast,
    save_component_code,
    save_detection_debug,
    save_dsl,
    save_library,
)
from app.pipeline.detection import run_detection
from app.pipeline.dsl_extraction import run_dsl_extraction
from app.pipeline.llm_codegen import run_llm_codegen
from app.pipeline.nesting_filter import run_nesting_filter
from app.pipeline.segmentation import run_segmentation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="analyze.py",
        description="Extract a component library from a UI screenshot.",
    )
    parser.add_argument("image", type=Path, help="Path to the screenshot file")
    parser.add_argument(
        "--target",
        choices=["react_native", "react", "html"],
        default="react_native",
        help="Code generation target (default: react_native)",
    )
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Run the original 5-stage layout-reconstruction pipeline (deprecated)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# New library pipeline
# ---------------------------------------------------------------------------


async def run_library(args: argparse.Namespace) -> None:
    image_path: Path = args.image.resolve()

    if not image_path.exists():
        print(f"error: file not found: {image_path}", file=sys.stderr)
        sys.exit(1)

    output_dir = make_output_dir(image_path.stem)
    print(f"[ UIForge ] {image_path.name}  →  {output_dir}/")

    with Image.open(image_path) as img:
        width, height = img.size
    print(f"            {width}×{height}px")

    # Initialise detector model once
    if settings.detector == "florence2":
        from app.services.florence_client import init_florence

        print(f"  [init] loading Florence-2 ({settings.florence_model_id})...")
        init_florence(settings.florence_model_id)
    elif settings.detector == "groundingdino":
        from app.services.grounding_dino_client import init_grounding_dino

        print(
            f"  [init] loading Grounding DINO ({settings.grounding_dino_model_id})..."
        )
        init_grounding_dino(settings.grounding_dino_model_id)

    # [1/4] Detection
    print(f"  [1/4] detecting components via {settings.detector}...")
    ast, perceived_w, perceived_h = await run_detection(image_path, (width, height))
    print(f"        perceived: {perceived_w}×{perceived_h}  actual: {width}×{height}")
    resized_path = resize_to_perceived(image_path, perceived_w, perceived_h, output_dir)
    print(f"        resized image  →  {resized_path.name}")
    artifact = save_ast(ast, "detection", output_dir)
    debug_img = save_detection_debug(ast, resized_path, output_dir)
    print(
        f"        {len(ast.components)} components  →  {artifact.name}, {debug_img.name}"
    )

    # [2/4] Nesting filter
    print("  [2/4] filtering to top-level components...")
    toplevel_ast = run_nesting_filter(ast)
    excluded = len(ast.components) - len(toplevel_ast.components)
    artifact = save_ast(toplevel_ast, "toplevel", output_dir)
    print(
        f"        {len(toplevel_ast.components)} top-level"
        f"  ({excluded} nested excluded)  →  {artifact.name}"
    )

    # Crop top-level components only
    from app.services.ocr import init_ocr_reader

    init_ocr_reader(["en"])
    toplevel_ast = run_segmentation(
        toplevel_ast,
        resized_path,
        output_dir,
        components=toplevel_ast.components,
    )
    print("        crops saved  →  crops/")

    # [3/4] DSL extraction
    print(f"  [3/4] extracting component DSL ({settings.dsl_model})...")
    library = await run_dsl_extraction(toplevel_ast, output_dir, settings)

    for dsl in library.components:
        save_dsl(dsl, output_dir)
    artifact = save_library(library, output_dir)

    ok = sum(1 for d in library.components if d.background is not None)
    print(
        f"        {ok}/{len(toplevel_ast.components)} extracted"
        f"  →  {artifact.name}, library/*.dsl.json"
    )

    # [4/4] Code generation
    print(f"  [4/4] generating {args.target} code ({settings.codegen_model})...")
    code_map = await run_llm_codegen(library, args.target, output_dir, settings)

    for comp_id, code in code_map.items():
        save_component_code(code, comp_id, args.target, output_dir)

    # Component summary
    print("\n--- component library ---")
    for dsl in library.components:
        bg = (dsl.background.color or "gradient") if dsl.background else "?"
        radius = f"{dsl.border_radius:.0f}px radius" if dsl.border_radius else ""
        shadow = "  shadow" if dsl.shadow else ""
        print(
            f"  {dsl.id:<16} {dsl.label:<14}"
            f"  {dsl.width:.0f}×{dsl.height:.0f}px"
            f"  {bg}{('  ' + radius) if radius else ''}{shadow}"
        )

    print(f"\nall artifacts saved to: {output_dir}/")


# ---------------------------------------------------------------------------
# Legacy pipeline (deprecated)
# ---------------------------------------------------------------------------


async def run_legacy(args: argparse.Namespace) -> None:
    print(
        "WARNING: --legacy mode is deprecated and will be removed in a future release."
    )

    from app.pipeline.artifacts import save_code
    from app.pipeline.codegen import run_codegen
    from app.pipeline.layout import run_layout_reconstruction
    from app.pipeline.style_extraction import run_style_extraction
    from app.services.ocr import init_ocr_reader

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

        print(
            f"  [init] loading Grounding DINO ({settings.grounding_dino_model_id})..."
        )
        init_grounding_dino(settings.grounding_dino_model_id)

    print(f"  [1/5] detecting components via {settings.detector}...")
    ast, perceived_w, perceived_h = await run_detection(image_path, (width, height))
    print(f"        perceived: {perceived_w}×{perceived_h}  actual: {width}×{height}")
    resized_path = resize_to_perceived(image_path, perceived_w, perceived_h, output_dir)
    artifact = save_ast(ast, "detection", output_dir)
    debug_img = save_detection_debug(ast, resized_path, output_dir)
    print(
        f"        {len(ast.components)} components  →  {artifact.name}, {debug_img.name}"
    )

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

    print("\n--- components ---")
    for c in ast.components:
        text_preview = f'  "{c.text[:28]}"' if c.text else ""
        color = f"  {c.style.background_color}" if c.style.background_color else ""
        print(
            f"  {c.id:<14} {c.type:<12} {c.bounding_box.width}×{c.bounding_box.height}px"
            f"{text_preview}{color}"
        )

    print(f"\nall artifacts saved to: {output_dir}/")


# ---------------------------------------------------------------------------


if __name__ == "__main__":
    args = parse_args()
    if args.legacy:
        asyncio.run(run_legacy(args))
    else:
        asyncio.run(run_library(args))
