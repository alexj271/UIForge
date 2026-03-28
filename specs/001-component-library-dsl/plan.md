# Implementation Plan: Screenshot-to-Component Library

**Branch**: `001-component-library-dsl` | **Date**: 2026-03-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/001-component-library-dsl/spec.md`

## Summary

Reorient UIForge from full-page layout reconstruction to a **component library
extractor**: given a screenshot, detect all UI elements, keep only the outermost
(non-nested) ones, send each crop to a vision LLM to extract a format-agnostic
visual DSL (sizes, colors, radii, shadows, gradients, borders), then drive a second
LLM call to emit ready-to-use code in the chosen target format (HTML, React, or
React Native). CLI-first implementation extending the existing `analyze.py` entry
point.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: FastAPI, Pydantic v2, openai SDK (>=1.0), Pillow, OpenCV,
EasyOCR, transformers >=4.41,<5.0
**Storage**: Files — `output/<stem>/library/` per run
**Testing**: pytest + mocks for external LLM calls
**Target Platform**: Linux/macOS developer workstation (CLI), Linux server (web)
**Project Type**: CLI tool + web service (extending existing)
**Performance Goals**: Full pipeline ≤ 2 min for ≤20 top-level components on CPU;
DSL extraction ≤ 10 s per component (network-bound)
**Constraints**: `OPENAI_API_KEY` required for DSL and codegen steps; detector
models optional (Grounding DINO default, falls back to OpenAI vision for detection)
**Scale/Scope**: Single-image batch; no concurrent-user scaling required for CLI

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Check | Status |
|-----------|-------|--------|
| I. Code Quality & PEP 8 | All new modules use type annotations; Pydantic models for cross-module data; `ruff` gates enforced | ✅ PASS |
| II. Testing Standards | TDD: unit tests for nesting filter + DSL parser; LLM calls mocked in tests; integration test fixture uses saved crop + cached DSL | ✅ PASS |
| III. UX Consistency | New CLI pipeline matches `analyze.py` print style; web interface to be updated in a separate PR; per-component status printed | ✅ PASS |
| IV. Performance | Models loaded once in `[init]`; LLM calls are async; segmentation + DSL extraction parallelizable per component | ✅ PASS |

*Post-design re-check: no violations introduced — see Complexity Tracking below.*

## Project Structure

### Documentation (this feature)

```text
specs/001-component-library-dsl/
├── plan.md              ← this file
├── research.md          ← Phase 0
├── data-model.md        ← Phase 1
├── quickstart.md        ← Phase 1
├── contracts/
│   └── cli-interface.md ← Phase 1
└── tasks.md             ← /speckit.tasks output
```

### Source Code (repository root)

```text
app/
├── config.py                       MODIFIED  — add DSL_MODEL, CODEGEN_MODEL settings
├── models/
│   ├── ast.py                      unchanged
│   └── dsl.py                      NEW — ComponentDSL, ComponentLibrary
├── pipeline/
│   ├── detection.py                unchanged
│   ├── segmentation.py             MODIFIED  — crop only provided component list
│   ├── nesting_filter.py           NEW — extract top-level components
│   ├── dsl_extraction.py           NEW — per-crop vision LLM → ComponentDSL
│   ├── llm_codegen.py              NEW — DSL → code via LLM
│   └── artifacts.py                MODIFIED  — save_library(), save_dsl()
├── services/
│   ├── grounding_dino_client.py    unchanged
│   ├── florence_client.py          unchanged
│   ├── openai_client.py            unchanged
│   ├── ocr.py                      unchanged
│   ├── vision_dsl_client.py        NEW — gpt-4o vision call → ComponentDSL JSON
│   └── llm_codegen_client.py       NEW — gpt-4o text call → code string
└── (main.py / api/routes.py)       deferred to web-interface PR

analyze.py                          MODIFIED  — new 4-stage library pipeline
tests/
├── unit/
│   ├── test_nesting_filter.py      NEW
│   ├── test_dsl_extraction.py      NEW (mocked LLM)
│   └── test_llm_codegen.py         NEW (mocked LLM)
└── integration/
    └── test_library_pipeline.py    NEW (fixture crop + cached DSL JSON)
```

**Structure Decision**: Single-project extension of the existing UIForge tree.
No new top-level packages. New pipeline stages follow the `app/pipeline/` convention;
new LLM service clients follow the `app/services/` convention.

## Complexity Tracking

> No constitution violations — table left empty per instructions.

## Phase 0: Research

See `research.md` for full findings. Key decisions:

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Vision LLM for DSL | `gpt-4o` | Already used for detection; best multimodal accuracy; structured JSON output via `response_format` |
| LLM for codegen | `gpt-4o` | Strong code generation; same API client as DSL step; configurable via `CODEGEN_MODEL` |
| Nesting algorithm | Bounding-box containment (reuse `_contains()` from `layout.py`) | Already implemented, tested, O(n²) acceptable for ≤100 components |
| DSL schema | Flat Pydantic model with optional gradient/shadow sub-models | Minimal, JSON-serializable, human-readable |
| Crop-then-filter vs filter-then-crop | Filter first, then crop only top-level | Avoids unnecessary LLM calls for nested components |
| Old pipeline stages | Keep (not deleted) | `style_extraction.py`, `layout.py`, `codegen.py` remain for backward compat; new pipeline is the default mode |

## Phase 1: Design

### New Pipeline Stages (replacing old stages 3–5)

```
Screenshot
   ↓
[1] Detection         (existing) → UIJsonAST (all components, flat)
   ↓
[2] Nesting Filter    (new)      → UIJsonAST (top-level only)
   ↓
[3] Segmentation      (modified) → UIJsonAST + crops saved to output/crops/
   ↓
[4] DSL Extraction    (new)      → ComponentLibrary (one ComponentDSL per crop)
   ↓
[5] LLM Code Gen      (new)      → dict[component_id → code_string]
   ↓
output/<stem>/library/
```

### CLI invocation (new default)

```bash
python analyze.py <image> [--target html|react|react_native]
```

`analyze.py` updated to run the 4-stage library pipeline. Old behavior can be
accessed via `--legacy` flag (kept for one release, then removed).

### Config additions (`app/config.py`)

```python
dsl_model: str = "gpt-4o"       # vision LLM for DSL extraction
codegen_model: str = "gpt-4o"   # LLM for code generation
```

Both readable from `.env` / environment variables `DSL_MODEL` and `CODEGEN_MODEL`.

### Output layout

```text
output/<stem>/
├── 00_resized.jpg
├── 01_detection.json           (all detected components)
├── 01_detection_debug.jpg
├── 02_toplevel.json            (top-level components after nesting filter)
├── 03_library.json             (ComponentLibrary — all DSLs)
├── crops/                      (top-level crops only)
│   └── <id>.jpg
└── library/
    ├── <id>.dsl.json           (individual ComponentDSL)
    └── <id>.<ext>              (generated code: .html / .jsx / .tsx)
```
