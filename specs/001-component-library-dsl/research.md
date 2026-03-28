# Research: Screenshot-to-Component Library

**Phase 0 output** | Feature: `001-component-library-dsl` | Date: 2026-03-28

## 1. Vision LLM for DSL Extraction

**Decision**: Use `gpt-4o` as the default vision model for converting component crops
to ComponentDSL JSON.

**Rationale**:
- The project already has an OpenAI client (`app/services/openai_client.py`) and the
  `OPENAI_API_KEY` / `OPENAI_BASE_URL` settings wired via `app/config.py`.
- `gpt-4o` supports the `response_format={"type": "json_object"}` parameter, enabling
  reliable structured JSON output without post-processing.
- It accurately describes visual properties (hex colors, pixel dimensions, CSS-style
  shadows) when given a clear system prompt.
- Configurable: expose as `DSL_MODEL` env var so users can swap to `gpt-4o-mini`
  (cheaper, faster) or a future model without code changes.

**Alternatives considered**:
- `gpt-4o-mini`: cheaper but less accurate on subtle visual details (gradients, shadows).
  Acceptable as a fallback for cost-sensitive runs.
- `claude-opus-4-6` (Anthropic): also excellent at vision; requires a separate SDK client.
  Can be added as a future DSL backend via the same pluggable pattern used for detectors.
- Local vision models (LLaVA, etc.): no reliable JSON-output mode; accuracy below GPT-4o.

**Prompt strategy**:
Send the crop image with a system prompt that:
1. Specifies the exact JSON schema expected (matches `ComponentDSL`).
2. Asks for pixel values for dimensions, hex codes for colors.
3. Requests `null` for absent properties (no border, no shadow).
4. Instructs the model to describe gradients with start/end color + direction in degrees.

---

## 2. LLM for Code Generation

**Decision**: Use `gpt-4o` as the default code generation model (`CODEGEN_MODEL`).

**Rationale**:
- Same API client; no additional dependency.
- DSL-to-code is a well-structured transformation: input is a small JSON object
  (< 1 KB), output is ~20–50 lines of code. GPT-4o handles this reliably.
- The prompt can include the exact DSL JSON, the target format, and a code skeleton
  to anchor the output style.

**Prompt strategy**:
- System prompt: role as "React/HTML/React Native component generator"; include one
  worked example (few-shot) per target format.
- User message: serialized `ComponentDSL` JSON + target format string.
- Extract code from the response: strip markdown fences if present.

**Alternatives considered**:
- Template-based generation (existing `codegen.py`): deterministic but cannot express
  gradients, complex shadows, or advanced styling without growing the template
  significantly. Replaced by LLM approach.
- Separate model per format: unnecessary complexity; GPT-4o handles all three with
  format-specific prompts.

---

## 3. Nesting Filter Algorithm

**Decision**: Reuse `_contains()` from `app/pipeline/layout.py`; extract to a shared
utility function in `app/pipeline/nesting_filter.py`.

**Algorithm** (O(n²), acceptable for n ≤ 100 components):
1. Sort detected components by area descending.
2. For each component A, check if any other component B (larger area) fully contains A
   using `_contains(B.bounding_box, A.bounding_box)`.
3. If A is contained by any B → A is nested → exclude.
4. Return only non-nested components as "top-level".

**Edge cases**:
- Overlapping but not contained: both treated as top-level.
- Identical bounding boxes: keep both (treat as top-level; likely a detection artefact).
- Single component: always top-level.

**Rationale**: The logic already exists and is correct. Extracting it to a dedicated
stage makes the pipeline stages orthogonal and individually testable.

---

## 4. DSL Schema Design

**Decision**: Flat Pydantic model `ComponentDSL` with optional nested sub-models for
gradient, shadow, and border.

**Key design choices**:
- `background` is a union (`BackgroundDSL`) that holds either a solid color string or
  a `GradientDSL`. This avoids a discriminated union complexity while keeping the
  JSON clean.
- All dimensional values are `float` (not `int`) to accommodate sub-pixel precision
  from the LLM and potential scaling.
- `border_radius` is a single float (uniform radius). Asymmetric radii (`border-radius:
  8px 4px`) are out of scope for v1.
- Shadow is a single drop-shadow. Multiple shadows are out of scope for v1.

See `data-model.md` for the full schema.

---

## 5. Pipeline Order: Filter-Then-Crop

**Decision**: Apply nesting filter on detection output (bounding boxes only) *before*
segmentation (cropping), so only top-level component crops are saved and sent to
the LLM.

**Rationale**:
- Avoids paying for LLM calls on components that will be discarded anyway.
- Reduces disk usage (fewer crop files).
- Crops of nested components (e.g., a button inside a card) are often too small or
  visually ambiguous to produce useful DSL on their own.

---

## 6. Backward Compatibility

**Decision**: Keep existing pipeline stages (`style_extraction.py`, `layout.py`,
`codegen.py`) in place, undisturbed. Add `--legacy` flag to `analyze.py` to run the
old 5-stage pipeline. Remove `--legacy` in a follow-up release.

**Rationale**: Existing users and tests depend on the old pipeline. The new "library"
mode is the default going forward.

---

## 7. Async Strategy for LLM Calls

**Decision**: Make `dsl_extraction.py` and `llm_codegen.py` async; dispatch per-component
LLM calls concurrently with `asyncio.gather()`.

**Rationale**: DSL extraction involves one LLM call per top-level component. For 20
components this is ~20 sequential API calls (potentially 40–100 s). Concurrent dispatch
reduces this to the latency of a single call (2–5 s). The OpenAI Python SDK's async
client (`AsyncOpenAI`) is already available and compatible.

**Constraint**: Rate-limit awareness — add a configurable `CONCURRENT_DSL_CALLS` setting
(default: 5) to cap simultaneous requests.
