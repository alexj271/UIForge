# CLI Interface Contract

**Feature**: `001-component-library-dsl` | Date: 2026-03-28

---

## Command

```
python analyze.py <image> [--target <format>] [--legacy]
```

---

## Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `image` | `Path` (positional) | — | Path to screenshot file (required) |
| `--target` | `str` | `react_native` | Code generation target: `html`, `react`, `react_native` |
| `--legacy` | flag | off | Run the old 5-stage layout-reconstruction pipeline instead |

---

## Environment Variables (via `.env` or shell)

| Variable | Default | Description |
|----------|---------|-------------|
| `DETECTOR` | `groundingdino` | Component detector backend: `groundingdino`, `florence2`, `openai` |
| `DSL_MODEL` | `gpt-4o` | Vision LLM model ID used for DSL extraction |
| `CODEGEN_MODEL` | `gpt-4o` | LLM model ID used for code generation |
| `OPENAI_API_KEY` | _(required for DSL+codegen)_ | OpenAI API key |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Override for proxies / alternative providers |
| `CONCURRENT_DSL_CALLS` | `5` | Max parallel DSL extraction requests |

---

## Standard Output (new library pipeline)

```
[ UIForge ] example.png  →  output/example/
            1024×768px
  [init] loading Grounding DINO (IDEA-Research/grounding-dino-base)...
  [1/4] detecting components via groundingdino...
        perceived: 1024×768  actual: 1024×768
        27 components  →  01_detection.json, 01_detection_debug.jpg
  [2/4] filtering to top-level components...
        12 top-level  (15 nested excluded)  →  02_toplevel.json
  [3/4] extracting component DSL (gpt-4o)...
        component_001 [button]         ✓
        component_002 [card]           ✓
        component_003 [navbar]         ✓
        ...
        12/12 extracted  →  03_library.json, crops/
  [4/4] generating react_native code (gpt-4o)...
        component_001  →  library/component_001.jsx
        component_002  →  library/component_002.jsx
        ...
        12/12 generated

--- component library ---
  component_001   button      88×36px   #007AFF bg   8px radius
  component_002   card        320×200px #FFFFFF bg   12px radius   shadow
  component_003   navbar      375×56px  #F5F5F5 bg   0px radius
  ...

all artifacts saved to: output/example/
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success — all components processed |
| `1` | Fatal error — image not found, API key missing, detector failed |
| `2` | Partial success — some components failed DSL extraction (printed per-component) |

---

## Output Directory Structure

```
output/<image_stem>/
├── 00_resized.jpg                 ← resized input (matching detected resolution)
├── 01_detection.json              ← all detected UIComponent list (UIJsonAST)
├── 01_detection_debug.jpg         ← bounding boxes overlaid on resized image
├── 02_toplevel.json               ← top-level components only (UIJsonAST)
├── 03_library.json                ← ComponentLibrary (all DSLs)
├── crops/
│   └── <component_id>.jpg         ← one crop per top-level component
└── library/
    ├── <component_id>.dsl.json    ← individual ComponentDSL
    └── <component_id>.<ext>       ← generated code (.html / .jsx / .tsx)
```

---

## Error Messages

All errors go to `stderr`. Format:

```
error [<stage>]: <message>
```

Examples:
```
error [detection]: OPENAI_API_KEY is not set; cannot use openai detector
error [dsl_extraction]: component_005 — vision LLM call failed (rate limit); skipped
error [llm_codegen]: unsupported target format "svelte" — choose html, react, or react_native
```

---

## Per-Component Status in Output

Each component line during DSL extraction shows one of:

| Symbol | Meaning |
|--------|---------|
| `✓` | DSL extracted successfully |
| `✗` | Extraction failed (reason logged to stderr) |
| `—` | Skipped (crop too small: < 10×10 px) |
