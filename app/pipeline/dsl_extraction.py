"""
Stage 3 (new pipeline): DSL Extraction
Sends each top-level component crop to the vision LLM and collects ComponentDSL results.

Uses asyncio.gather() with a semaphore to cap concurrent API calls at
settings.concurrent_dsl_calls.  Components whose DSL extraction fails are
skipped; the returned ComponentLibrary contains only successfully extracted entries.
"""

import asyncio
import sys
from pathlib import Path

from app.models.ast import UIJsonAST
from app.models.dsl import ComponentLibrary
from app.services.vision_dsl_client import extract_dsl

_STATUS_OK = "✓"
_STATUS_FAIL = "✗"
_STATUS_SKIP = "—"


async def run_dsl_extraction(
    ast: UIJsonAST,
    output_dir: Path,
    settings: object,
) -> ComponentLibrary:
    """Extract ComponentDSL for every component in *ast* concurrently.

    Prints per-component status to stdout matching the analyze.py style.
    Returns a ComponentLibrary with only the successfully extracted entries.
    """
    sem = asyncio.Semaphore(settings.concurrent_dsl_calls)  # type: ignore[attr-defined]

    async def _extract_one(component):
        if not component.crop_path:
            print(f"        {component.id:<16} {_STATUS_SKIP} (no crop)")
            return None

        crop_path = Path(component.crop_path)
        if not crop_path.exists():
            # Try relative to output_dir
            alt = output_dir / "crops" / crop_path.name
            if alt.exists():
                crop_path = alt
            else:
                print(f"        {component.id:<16} {_STATUS_SKIP} (crop missing)")
                return None

        async with sem:
            dsl = await extract_dsl(component.id, crop_path, settings)

        if dsl is None:
            print(f"        {component.id:<16} {_STATUS_FAIL}", file=sys.stderr)
            return None

        print(f"        {component.id:<16} [{dsl.label}] {_STATUS_OK}")
        return dsl

    results = await asyncio.gather(*[_extract_one(c) for c in ast.components])
    dsls = [r for r in results if r is not None]

    return ComponentLibrary(
        source_image=ast.source_image,
        total_detected=ast.width,  # placeholder — caller has total_detected count
        total_toplevel=len(ast.components),
        components=dsls,
    )
