---
description: "Task list for Screenshot-to-Component Library"
---

# Tasks: Screenshot-to-Component Library

**Input**: Design documents from `specs/001-component-library-dsl/`
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/ ✅

**Tests**: Included — constitution mandates TDD for new pipeline stages.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2 / US3 — maps to spec.md user stories
- File paths shown relative to repo root

---

## Phase 1: Setup

**Purpose**: Ensure dev environment and tooling are ready before any code is written.

- [x] T001 Verify `openai>=1.0` is present in `requirements.txt`; add/update if missing and run `pip install -r requirements.txt`
- [x] T002 [P] Run `ruff check . && ruff format --check .` — resolve any pre-existing violations so the baseline is clean

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared infrastructure that MUST be complete before any user story begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T003 [P] Create `app/models/dsl.py` with Pydantic models: `GradientStop`, `GradientDSL`, `BackgroundDSL`, `ShadowDSL`, `BorderDSL`, `ComponentDSL`, `ComponentLibrary` — see `specs/001-component-library-dsl/data-model.md`
- [x] T004 [P] Add `dsl_model: str = "gpt-4o"`, `codegen_model: str = "gpt-4o"`, `concurrent_dsl_calls: int = 5` settings to `app/config.py` (env vars `DSL_MODEL`, `CODEGEN_MODEL`, `CONCURRENT_DSL_CALLS`)
- [x] T005 [P] Add `save_library(library: ComponentLibrary, output_dir: Path) -> Path` and `save_dsl(dsl: ComponentDSL, output_dir: Path) -> Path` to `app/pipeline/artifacts.py`; save files to `output_dir/03_library.json` and `output_dir/library/<id>.dsl.json` respectively
- [x] T006 [P] Modify `app/pipeline/segmentation.py` — add optional `components: list[UIComponent] | None = None` parameter to `run_segmentation()`; when provided, crop only those components instead of `ast.components`

**Checkpoint**: Foundation ready — user story implementation can begin.

---

## Phase 3: User Story 1 — Extract Top-Level Components (Priority: P1) 🎯 MVP

**Goal**: Detection → nesting filter → crop only top-level components.
Stages 1–2 of the new pipeline wired in `analyze.py`.

**Independent Test**: Run `python analyze.py tests/assets/example1.jpg`; confirm
`output/example1/02_toplevel.json` contains fewer components than `01_detection.json`
and `output/example1/crops/` holds only the outermost component crops.

### Tests for User Story 1 ⚠️ Write FIRST — must FAIL before T008

- [x] T007 [P] [US1] Write unit tests for nesting filter in `tests/unit/test_nesting_filter.py`:
  - `test_nested_component_excluded()` — component B inside component A → only A in result
  - `test_overlapping_components_both_kept()` — overlapping but not contained → both kept
  - `test_all_toplevel_when_no_nesting()` — flat list unchanged
  - `test_empty_input()` — returns empty list

### Implementation for User Story 1

- [x] T008 [US1] Implement `app/pipeline/nesting_filter.py` — `run_nesting_filter(ast: UIJsonAST) -> UIJsonAST` that returns a new `UIJsonAST` containing only top-level components; reuse `_contains()` logic from `app/pipeline/layout.py` (copy and adapt); mark excluded components in stage output (depends T007)
- [x] T009 [US1] Update `analyze.py` — replace old 5-stage pipeline with new 4-stage skeleton; wire stages 1–3: `[1/4] detection` → `[2/4] nesting filter` (save `02_toplevel.json`) → `[3/4] crop top-level components`; use `run_segmentation(ast, resized_path, output_dir, components=toplevel.components)` from T006; print progress matching existing style (depends T006, T008)

**Checkpoint**: US1 fully functional — detection + filter + crops work end-to-end.

---

## Phase 4: User Story 2 — Generate Visual DSL (Priority: P2)

**Goal**: Send each top-level crop to the vision LLM and receive a `ComponentDSL`.
Stage 3 of the new pipeline wired in `analyze.py`.

**Independent Test**: Run pipeline on `tests/assets/example1.jpg`; verify
`output/example1/03_library.json` parses as valid `ComponentLibrary` and each entry
contains non-null `background.color` or `background.gradient`.

### Tests for User Story 2 ⚠️ Write FIRST — must FAIL before T011

- [x] T010 [P] [US2] Write unit test for vision DSL client in `tests/unit/test_dsl_extraction.py` using `unittest.mock.patch` on `openai.AsyncOpenAI`:
  - `test_dsl_client_returns_component_dsl()` — mock returns valid JSON; assert parsed `ComponentDSL` fields match
  - `test_dsl_client_handles_api_error()` — mock raises `openai.APIError`; assert `None` returned (no exception raised)

### Implementation for User Story 2

- [x] T011 [US2] Implement `app/services/vision_dsl_client.py` — async function `extract_dsl(component_id: str, crop_path: Path, settings) -> ComponentDSL | None`; encode crop as base64; call `AsyncOpenAI` with `settings.dsl_model`, system prompt specifying the ComponentDSL JSON schema, `response_format={"type": "json_object"}`; parse response to `ComponentDSL`; return `None` on failure (depends T003, T004, T010)
- [x] T012 [US2] Implement `app/pipeline/dsl_extraction.py` — async function `run_dsl_extraction(ast: UIJsonAST, output_dir: Path, settings) -> ComponentLibrary`; use `asyncio.gather()` limited by semaphore (`settings.concurrent_dsl_calls`) to call `extract_dsl()` per component; collect results; mark failed components with status; return `ComponentLibrary` (depends T003, T011)
- [x] T013 [US2] Update `analyze.py` — wire stage 3 `[3/4] extracting component DSL`; call `run_dsl_extraction()`; save `03_library.json` via `save_library()` and individual `library/*.dsl.json` via `save_dsl()`; print per-component ✓ / ✗ / — status (depends T005, T009, T012)

**Checkpoint**: US1 + US2 both independently functional — crops and DSLs produced.

---

## Phase 5: User Story 3 — Generate Component Code (Priority: P3)

**Goal**: Transform each `ComponentDSL` into ready-to-use code in the requested format.
Stage 4 (final stage) wired in `analyze.py`.

**Independent Test**: Run `python analyze.py tests/assets/example1.jpg --target react`;
verify `output/example1/library/` contains `.jsx` files that are syntactically valid
(paste one into a React sandbox — should render without errors).

### Tests for User Story 3 ⚠️ Write FIRST — must FAIL before T015

- [x] T014 [P] [US3] Write unit test for LLM codegen client in `tests/unit/test_llm_codegen.py` using `unittest.mock.patch`:
  - `test_codegen_client_returns_code_string()` — mock returns code wrapped in markdown fences; assert fences stripped, valid code returned
  - `test_codegen_client_all_targets()` — parametrize over `html`, `react`, `react_native`; assert non-empty string returned for each
  - `test_codegen_client_handles_api_error()` — mock raises error; assert empty string returned

### Implementation for User Story 3

- [x] T015 [US3] Implement `app/services/llm_codegen_client.py` — async function `generate_code(dsl: ComponentDSL, target: str, settings) -> str`; call `AsyncOpenAI` with `settings.codegen_model`; system prompt includes one worked example per target format; user message is serialized DSL JSON + target; strip markdown fences from response; return code string or empty string on failure (depends T003, T004, T014)
- [x] T016 [US3] Implement `app/pipeline/llm_codegen.py` — async function `run_llm_codegen(library: ComponentLibrary, target: str, output_dir: Path, settings) -> dict[str, str]`; use `asyncio.gather()` with semaphore; call `generate_code()` per component; save each to `output_dir/library/<id>.<ext>` (`.html`, `.jsx`, `.tsx` for `react_native`); return `dict[id → code]` (depends T003, T015)
- [x] T017 [US3] Update `analyze.py` — add `--target` choices `html`, `react`, `react_native` (default `react_native`); wire stage 4 `[4/4] generating {target} code`; call `run_llm_codegen()`; print per-component output paths; print final `--- component library ---` summary table showing id, label, dimensions, background color, radius, shadow indicator (depends T005, T013, T016)

**Checkpoint**: All three user stories functional — full pipeline screenshot → component library.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Integration tests, backward compat, documentation, lint gate.

- [x] T018 [P] Write integration test `tests/integration/test_library_pipeline.py` — fixture: pre-saved crop image from `tests/assets/` + pre-generated `ComponentDSL` JSON; test `run_nesting_filter()`, `run_segmentation()` without live API; mock `vision_dsl_client` and `llm_codegen_client` to return fixture data; assert `ComponentLibrary` structure and code file creation
- [x] T019 Add `--legacy` flag to `analyze.py` — when present, run original 5-stage pipeline (import and call existing `run_style_extraction`, `run_layout_reconstruction`, `run_codegen`); print deprecation notice
- [x] T020 [P] Update `CLAUDE.md` — revise Status section and pipeline diagram to reflect new 4-stage component-library pipeline; add `DSL_MODEL`, `CODEGEN_MODEL` to Commands section
- [x] T021 Run `ruff check . && ruff format . && pytest` — fix all violations and failing tests before marking phase complete

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational — no dependency on US2 or US3
- **US2 (Phase 4)**: Depends on Foundational + US1 (analyze.py stages 1–2 must exist)
- **US3 (Phase 5)**: Depends on Foundational + US2 (ComponentLibrary must exist in pipeline)
- **Polish (Phase 6)**: Depends on all user stories complete

### Task-Level Dependencies

| Task | Depends on |
|------|-----------|
| T008 | T003, T007 |
| T009 | T006, T008 |
| T011 | T003, T004, T010 |
| T012 | T003, T011 |
| T013 | T005, T009, T012 |
| T015 | T003, T004, T014 |
| T016 | T003, T015 |
| T017 | T005, T013, T016 |
| T018 | T017 |
| T019 | T009 |
| T020 | T017 |
| T021 | T018, T019, T020 |

### Parallel Opportunities Within Phases

**Phase 2** (all parallel after T001–T002):
```
T003 app/models/dsl.py        ─┐
T004 app/config.py             ├─ all different files, no deps
T005 app/pipeline/artifacts.py ─┤
T006 app/pipeline/segmentation ─┘
```

**Phase 3** (T007 parallel with other US2/US3 prep):
```
T007 tests/unit/test_nesting_filter.py  (write test first)
  ↓
T008 app/pipeline/nesting_filter.py
  ↓
T009 analyze.py (stages 1-3)
```

**Phase 4** (T010 parallel with Phase 3 implementation):
```
T010 tests/unit/test_dsl_extraction.py  (write test first)
  ↓
T011 app/services/vision_dsl_client.py
  ↓
T012 app/pipeline/dsl_extraction.py
  ↓
T013 analyze.py (stage 3 added)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (all 4 tasks)
3. Complete Phase 3: US1 (T007 → T008 → T009)
4. **STOP and VALIDATE**: Run `python analyze.py tests/assets/example1.jpg`; inspect `02_toplevel.json` and `crops/`
5. Demo / review before proceeding to US2

### Incremental Delivery

1. Setup + Foundational → shared infrastructure ready
2. Add US1 → test independently → top-level crop extraction works
3. Add US2 → test independently → DSL files appear in `library/`
4. Add US3 → test independently → code files appear in `library/`
5. Polish → integration tests + lint gate

---

## Notes

- `[P]` tasks touch different files — safe to run in parallel
- `[Story]` label maps each task to its user story for traceability
- TDD enforced by constitution: test tasks (T007, T010, T014) MUST be written and FAIL before corresponding implementations
- Mock `openai.AsyncOpenAI` in unit tests — never call live API in `pytest`
- `ruff check + format` MUST pass after every phase before moving to the next
