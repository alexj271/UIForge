<!--
SYNC IMPACT REPORT
==================
Version change: 0.0.0 (uninitialized template) → 1.0.0
Bump rationale: MAJOR — first concrete ratification; all placeholders replaced.

Modified principles:
  [PRINCIPLE_1_NAME] → I. Code Quality & PEP 8 Compliance
  [PRINCIPLE_2_NAME] → II. Testing Standards
  [PRINCIPLE_3_NAME] → III. User Experience Consistency
  [PRINCIPLE_4_NAME] → IV. Performance Requirements
  [PRINCIPLE_5_NAME] → REMOVED (user requested 4 principles)

Added sections:
  Technology Constraints (replaces generic [SECTION_2_NAME])
  Development Workflow   (replaces generic [SECTION_3_NAME])

Removed sections:
  None (template placeholders replaced with content)

Templates requiring updates:
  ✅ .specify/templates/plan-template.md  — Constitution Check gates now defined;
     template structure already compatible, no edits required.
  ✅ .specify/templates/spec-template.md  — Success Criteria / Performance goals
     align with Principle IV; no structural edits required.
  ✅ .specify/templates/tasks-template.md — Phase T003 "Configure linting and
     formatting tools" aligns with Principle I; no edits required.

Deferred TODOs:
  None — all fields resolved from repo context and user input.
-->

# UIForge Constitution

## Core Principles

### I. Code Quality & PEP 8 Compliance

All Python source MUST conform to PEP 8. `ruff check` and `ruff format` are the
canonical enforcement tools and MUST pass with zero violations before any code is
merged. Type annotations MUST be present on all public functions and class methods.
Pydantic models are the mandated data-contract layer between pipeline stages — raw
`dict` objects MUST NOT cross module boundaries. Code reviews MUST flag any
deviation from these rules as a blocker.

**Rationale**: A consistent style removes cognitive friction, makes automated
refactoring safe, and ensures that Pydantic validation catches contract mismatches
at the boundary rather than deep inside pipeline logic.

### II. Testing Standards

Every new pipeline stage and every detector backend MUST have at least one `pytest`
unit test covering the happy path and one covering an error/edge case. Tests MUST
be written before implementation (TDD) for new features. The full test suite MUST
pass (`pytest`) before any PR is merged. Integration tests covering the end-to-end
pipeline (screenshot → code output) MUST be maintained in `tests/` and MUST NOT
rely on external network calls — mock or use fixtures instead.

**Rationale**: UIForge has multiple interchangeable backends and a multi-stage
pipeline; regressions are hard to spot without automated coverage. TDD surfaces
interface ambiguities before implementation effort is sunk.

### III. User Experience Consistency

The web interface MUST provide visual feedback for every pipeline stage (bounding
boxes, cropped components, per-stage status). Error messages shown to the end user
MUST be actionable — they MUST identify the failing stage and suggest a remedy
(e.g., "Detector 'florence2' failed — check transformers version or switch to
'groundingdino'"). The CLI (`analyze.py`) and the FastAPI web interface MUST
produce semantically equivalent output for the same input. Any change to the UI
JSON AST schema MUST be accompanied by an update to all downstream code-generation
targets (React Native and HTML).

**Rationale**: UIForge targets developers who rely on visual inspection to judge
pipeline quality. Inconsistent output between CLI and web erodes trust in the tool
and increases debugging time.

### IV. Performance Requirements

Model loading MUST happen exactly once at startup (via `lifespan` in `main.py` and
the `[init]` block in `analyze.py`) — loading inside request handlers is
prohibited. Grounding DINO and Florence-2 inference MUST run in a thread-pool
executor to avoid blocking the FastAPI event loop. Single-image processing (resize
→ detect → segment → style → codegen) MUST complete in under 60 seconds on CPU for
images up to 1920×1080. Memory footprint of loaded models MUST be documented in
`README.md` when a new backend is added.

**Rationale**: Heavy CV models are the dominant cost; lazy loading or in-handler
loading would make the web interface unusable and break the event-loop contract of
async FastAPI.

## Technology Constraints

- **Language**: Python 3.10+ is required; f-strings and `match` statements are
  permitted.
- **Formatting / Lint**: `ruff` (check + format) is the sole style tool; `black`
  and `flake8` MUST NOT be introduced as duplicates.
- **Dependencies**: `transformers` MUST stay `>=4.41,<5.0` — Florence-2 is
  incompatible with transformers 5.x. Any PR that bumps transformers outside this
  range MUST include a full Florence-2 regression test.
- **Secrets**: `.env` is gitignored and MUST never be committed. All secrets
  (`OPENAI_API_KEY`) MUST be read via `pydantic-settings` from `app/config.py`.
- **Detector extension**: New detector backends MUST implement the async interface
  `async def detect_components(image_path, image_size) -> tuple[list[dict], int, int]`
  and MUST be selectable via the `DETECTOR` env var without code changes outside
  the new service file and `app/config.py`.

## Development Workflow

- **Linting gate**: `ruff check .` and `ruff format --check .` MUST be clean
  before committing.
- **Test gate**: `pytest` MUST pass with no failures before merging.
- **PR scope**: Each PR MUST correspond to a single pipeline stage or a single
  detector backend. Cross-cutting refactors are a separate PR.
- **Artifact review**: When adding or changing a pipeline stage, the developer
  MUST include a sample `output/<stem>/` artifact (or diff) in the PR description
  to demonstrate visual correctness.
- **Constitution compliance**: The plan-template Constitution Check section MUST
  be completed for every new feature, verifying alignment with all four principles
  above before Phase 0 research begins.

## Governance

This Constitution supersedes all informal conventions. Amendments require:

1. A written rationale explaining which principle is affected and why the change
   is necessary.
2. A version bump following semantic versioning (MAJOR / MINOR / PATCH as defined
   in the header comment).
3. An update to this file's `Last Amended` date and `SYNC IMPACT REPORT`.
4. Review and approval by at least one other contributor before merge.

All PRs and code reviews MUST verify compliance with the four Core Principles. Any
violation flagged during review is a merge blocker unless a justified exception is
recorded in the Complexity Tracking table of the relevant `plan.md`.

Refer to `CLAUDE.md` for runtime development guidance (commands, environment
setup, project structure).

**Version**: 1.0.0 | **Ratified**: 2026-03-28 | **Last Amended**: 2026-03-28
