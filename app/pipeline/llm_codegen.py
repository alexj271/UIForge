"""
Stage 4 (new pipeline): LLM Code Generation
Converts each ComponentDSL in the library to source code using the configured LLM.

Uses asyncio.gather() with a semaphore to cap concurrent API calls.
Components whose code generation fails are included as empty strings.
"""

import asyncio
import sys
from pathlib import Path

from app.models.dsl import ComponentLibrary
from app.pipeline.artifacts import save_component_code
from app.services.llm_codegen_client import generate_code


async def run_llm_codegen(
    library: ComponentLibrary,
    target: str,
    output_dir: Path,
    settings: object,
) -> dict[str, str]:
    """Generate code for every component in *library*.

    Saves each file to output_dir/library/<id>.<ext> and returns a
    dict mapping component_id → code_string.
    """
    sem = asyncio.Semaphore(settings.concurrent_dsl_calls)  # type: ignore[attr-defined]

    async def _generate_one(dsl):
        async with sem:
            code = await generate_code(dsl, target, settings)
        if code:
            path = save_component_code(code, dsl.id, target, output_dir)
            print(f"        {dsl.id:<16}  →  library/{path.name}")
        else:
            print(
                f"        {dsl.id:<16}  ✗ (generation failed)",
                file=sys.stderr,
            )
        return dsl.id, code

    pairs = await asyncio.gather(*[_generate_one(d) for d in library.components])
    return {comp_id: code for comp_id, code in pairs}
