# Quickstart: Screenshot-to-Component Library

**Feature**: `001-component-library-dsl` | Date: 2026-03-28

---

## Prerequisites

1. Python 3.10+ virtual environment active:
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. `.env` file at project root with your OpenAI key (required for DSL + codegen):
   ```bash
   OPENAI_API_KEY=sk-...
   ```

3. For Grounding DINO detector (default): ~700 MB model download on first run.
   For faster first run, use the OpenAI detector instead:
   ```bash
   DETECTOR=openai
   ```

---

## Basic Usage

```bash
# Extract component library as React Native components (default)
python analyze.py tests/assets/example1.jpg

# HTML output
python analyze.py tests/assets/example1.jpg --target html

# React (JSX) output
python analyze.py tests/assets/example1.jpg --target react
```

All artifacts land in `output/example1/`.

---

## Inspecting the Output

```bash
# View the component library DSL
cat output/example1/03_library.json

# View individual component DSL
cat output/example1/library/component_001.dsl.json

# View generated code for a component
cat output/example1/library/component_001.jsx

# List all generated code files
ls output/example1/library/
```

---

## Switching the LLM Model

```bash
# Use gpt-4o-mini for faster, cheaper runs (lower accuracy)
DSL_MODEL=gpt-4o-mini CODEGEN_MODEL=gpt-4o-mini python analyze.py screenshot.png

# Use a custom OpenAI-compatible endpoint
OPENAI_BASE_URL=https://my-proxy.example.com/v1 python analyze.py screenshot.png
```

---

## Switching the Detector

```bash
# Grounding DINO (default — best recall)
DETECTOR=groundingdino python analyze.py screenshot.png

# Florence-2 (lighter, faster)
DETECTOR=florence2 python analyze.py screenshot.png

# OpenAI Vision for detection (no local model needed)
DETECTOR=openai python analyze.py screenshot.png
```

---

## Legacy Mode (old layout-reconstruction pipeline)

The original full-page layout pipeline is still available:

```bash
python analyze.py screenshot.png --legacy --target react_native
```

---

## Validation Checklist

After a run, verify the following:

- [ ] `output/<stem>/01_detection_debug.jpg` shows bounding boxes on all major UI elements
- [ ] `output/<stem>/02_toplevel.json` contains only outermost components (no nested ones)
- [ ] `output/<stem>/crops/` has one image per top-level component
- [ ] `output/<stem>/03_library.json` has a `ComponentDSL` entry for each crop
- [ ] DSL `background.color` values are recognizable hex codes from the screenshot
- [ ] `output/<stem>/library/` has one code file per component in the requested format
- [ ] Generated code is syntactically valid (paste into a sandbox to verify)

---

## Running Tests

```bash
# All tests
pytest

# Only new library pipeline tests
pytest tests/unit/test_nesting_filter.py tests/unit/test_dsl_extraction.py
pytest tests/integration/test_library_pipeline.py

# Lint check
ruff check . && ruff format --check .
```
