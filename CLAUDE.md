# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

UIForge converts UI screenshots into structured components and generates React Native or HTML layouts. The goal is "80% ready" components that accelerate manual UI development — not full automation.

## Tech Stack

- **Python** — primary language
- **FastAPI** — web interface for uploading screenshots and visualizing the decomposition process
- **Grounding DINO** (`IDEA-Research/grounding-dino-base`) — default detector; open-vocabulary zero-shot UI element detection via text prompt
- **Florence-2** (`microsoft/Florence-2-base`) — alternative local detector; phrase-grounding task
- **OpenAI Vision API** (`gpt-4o`) — optional detector; highest accuracy but requires API key
- **EasyOCR** — text extraction from cropped components
- **OpenCV** (`opencv-python`) — image preprocessing
- **Pillow** — image loading and manipulation
- **transformers** (`>=4.41,<5.0`) — used by both Grounding DINO and Florence-2 backends

## Architecture

The core pipeline:

```
Screenshot
   ↓
Image Preprocessing (OpenCV / Pillow)
   ↓
UI Detection ─── pluggable backend (Grounding DINO | Florence-2 | OpenAI Vision)
   ↓
Component Segmentation → cropped component images + bounding boxes
   │
   └── Text Extraction (EasyOCR) per crop
   ↓
Style Extraction (colors, borders, shadows, gradients)
   ↓
Layout Reconstruction
   ↓
UI JSON AST  ←── platform-agnostic intermediate representation
   ↓
Code Generation (React Native | HTML)
```

The **UI JSON AST** is the central data contract between pipeline stages.

### Detector Backends

Configured via `DETECTOR` env var (or `app/config.py` default):

| Backend | Env value | Model | Notes |
|---|---|---|---|
| Grounding DINO | `groundingdino` | `IDEA-Research/grounding-dino-base` | **Default.** Best recall on UI screenshots. Open-vocabulary via text prompt. |
| Florence-2 | `florence2` | `microsoft/Florence-2-base` | Local. Uses `<CAPTION_TO_PHRASE_GROUNDING>` task. Lighter but less complete. |
| OpenAI Vision | `openai` | `gpt-4o` | Requires `OPENAI_API_KEY`. Best semantic accuracy + style info. |

All backends expose the same async interface:
```python
async def detect_components(image_path, image_size) -> tuple[list[dict], int, int]
```

Heavy models (Grounding DINO, Florence-2) are loaded once at startup via `lifespan` in `app/main.py` and run synchronously in a thread pool executor.

**Known issues with Florence-2 + transformers 4.46+:**
- Requires `attn_implementation="eager"` and `use_cache=False` in `model.generate()`
- DynamicCache (new default KV cache) breaks Florence-2's custom `prepare_inputs_for_generation`

### Web Interface Role

FastAPI serves a visual inspection UI. The user uploads a screenshot and sees:
- the original image with bounding boxes overlaid per detected component
- each cropped component displayed individually
- the pipeline progressing step by step

The frontend is intentionally minimal (Jinja2 templates or plain HTML — no separate JS framework).

## Project Structure

```
UIForge/
├── app/
│   ├── main.py                          # FastAPI entrypoint + lifespan (model init)
│   ├── config.py                        # pydantic-settings: DETECTOR, model IDs, OpenAI key
│   ├── api/routes.py                    # Route handlers
│   ├── pipeline/
│   │   ├── detection.py                 # Stage 1: routes to active detector backend
│   │   ├── segmentation.py              # Stage 2: crop components, run OCR
│   │   ├── style_extraction.py          # Stage 3: extract colors/borders per crop
│   │   ├── layout.py                    # Stage 4: reconstruct hierarchy
│   │   ├── codegen.py                   # Stage 5: emit React Native or HTML
│   │   └── artifacts.py                 # Save JSON/image artifacts to output/
│   ├── models/ast.py                    # Pydantic: UIJsonAST, UIComponent, BoundingBox, StyleInfo
│   └── services/
│       ├── grounding_dino_client.py     # Grounding DINO inference (default)
│       ├── florence_client.py           # Florence-2 inference
│       ├── openai_client.py             # OpenAI Vision API
│       └── ocr.py                       # EasyOCR wrapper
├── analyze.py                           # CLI: run full pipeline on a single image
├── tests/
│   └── assets/example1.jpg
├── output/<stem>/                       # Per-run artifacts (gitignored)
│   ├── 00_resized.jpg
│   ├── 01_detection.json + 01_detection_debug.jpg
│   ├── 02_segmentation.json + crops/
│   ├── 03_style.json
│   ├── 04_layout.json
│   └── 05_code.jsx / .html
├── static/                              # Served by FastAPI
├── uploads/                             # Uploaded screenshots
├── requirements.txt
└── .env                                 # Secrets — never commit
```

## Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Commands

```bash
# CLI — analyze a single image (fastest for development)
python analyze.py tests/assets/example1.jpg --target html
python analyze.py tests/assets/example1.jpg --target react_native

# Override detector for a single run
DETECTOR=groundingdino python analyze.py <image>
DETECTOR=florence2     python analyze.py <image>
DETECTOR=openai        OPENAI_API_KEY=sk-... python analyze.py <image>

# Web server
uvicorn app.main:app --reload

# Tests / lint
pytest
ruff check .
ruff format .
```

## Key Conventions

- All pipeline stages operate on Pydantic models — `UIJsonAST` is the shared contract.
- Detector prompt engineering is centralized in each service file (`UI_TEXT_PROMPT` in `grounding_dino_client.py`, `ui_prompt` in `florence_client.py`, `DETECTION_PROMPT` in `openai_client.py`).
- Heavy models are loaded once at startup in `lifespan` (`main.py`) and in the `[init]` block of `analyze.py`.
- `DETECTOR`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `FLORENCE_MODEL_ID`, `GROUNDING_DINO_MODEL_ID` are all read from `.env` via `pydantic-settings` (`app/config.py`).
- Cropped component images go to `output/<stem>/crops/` (CLI) or `static/crops/<stem>/` (web).
- `transformers` must stay `<5.0` — Florence-2 custom code is incompatible with transformers 5.x.

## Status

Pipeline wired end-to-end and tested on a real UI screenshot. Grounding DINO detects ~27 components on a complex screen (vs 7 for Florence-2-base). Style extraction and code generation run on all detected components.
