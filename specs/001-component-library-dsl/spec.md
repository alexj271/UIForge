# Feature Specification: Screenshot-to-Component Library

**Feature Branch**: `001-component-library-dsl`
**Created**: 2026-03-28
**Status**: Draft
**Input**: User description: "Extract a reusable component library from a UI screenshot by detecting top-level components, describing each with a visual DSL, and generating code in the chosen target format."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Extract Top-Level Components from Screenshot (Priority: P1)

A developer has a UI screenshot (e.g., a mobile app screen or web page) and wants to
extract the set of visually distinct, top-level UI components from it — things like
buttons, cards, input fields, navigation bars — without capturing sub-elements that are
already contained inside those components. The output is a set of cropped images, one
per top-level component, ready for further processing.

**Why this priority**: This is the foundation of the pipeline. No DSL extraction or code
generation is possible without first isolating the correct components. Delivering this
alone provides immediate value — a developer can browse the cropped components and
manually inspect what was detected.

**Independent Test**: Upload a screenshot containing at least one card with nested buttons.
Verify that only the card appears in the output (the nested buttons are excluded), and that
the card crop matches the visible bounding box.

**Acceptance Scenarios**:

1. **Given** a screenshot with multiple UI elements at different nesting levels,
   **When** the user submits it for processing,
   **Then** the system returns only the outermost (non-nested) components as cropped images,
   with no duplicate or contained sub-elements included.

2. **Given** a screenshot where all detected elements are at the same level (no nesting),
   **When** the user submits it,
   **Then** all detected elements are returned as top-level components.

3. **Given** a screenshot with no detectable UI components,
   **When** the user submits it,
   **Then** the system reports that no components were found and returns an empty result.

---

### User Story 2 - Generate Visual DSL for Each Component (Priority: P2)

For each extracted top-level component, a developer wants a structured description of its
visual properties: dimensions, corner radii, background color, border color and width,
shadow parameters, and any gradient fill. This description (the "Component DSL") is
format-agnostic and can be reviewed or edited independently of any code target.

**Why this priority**: The DSL is the reusable intermediate artifact. It decouples visual
extraction from code generation, allowing developers to target multiple output formats from
a single analysis run and to manually refine the description before generating code.

**Independent Test**: Run DSL extraction on a cropped card image with a known blue
background, 8 px radius, and a bottom shadow. Verify the DSL contains color ≈ blue,
radius = 8, and shadow fields with non-zero values.

**Acceptance Scenarios**:

1. **Given** a cropped component image,
   **When** DSL extraction is requested,
   **Then** the output contains at minimum: width, height, background color, border radius,
   border (color + width), and shadow (offset, blur, color) fields.

2. **Given** a component with a gradient background,
   **When** DSL extraction is requested,
   **Then** the output DSL represents the gradient (start color, end color, direction)
   instead of a flat background color.

3. **Given** a component with no visible border or shadow,
   **When** DSL extraction is requested,
   **Then** the corresponding DSL fields are present but indicate absence (e.g., zero values
   or null), rather than being omitted.

---

### User Story 3 - Generate Component Code in Target Format (Priority: P3)

A developer wants to receive ready-to-integrate code for each component in a format they
choose: HTML/CSS, React (JSX + CSS-in-JS), or React Native. The generated code MUST
faithfully represent the visual DSL — colors, radii, shadows — and MUST be usable with
minimal manual editing ("80% ready").

**Why this priority**: Code generation is the final deliverable. Without it the workflow
stops at the DSL, which is useful but incomplete. This story closes the loop from screenshot
to usable code.

**Independent Test**: Generate React code for a card DSL with a blue background, 12 px
radius, and a drop shadow. Paste the output into a React sandbox and confirm the rendered
result visually matches the original cropped component image.

**Acceptance Scenarios**:

1. **Given** a Component DSL and a selected target format (HTML, React, or React Native),
   **When** code generation is requested,
   **Then** the output is syntactically valid code in the requested format that visually
   reproduces the component when rendered.

2. **Given** the same Component DSL,
   **When** code generation is requested for all three target formats in sequence,
   **Then** each output independently reproduces the same visual appearance in its
   respective runtime environment.

3. **Given** a Component DSL with a gradient and shadow,
   **When** code generation is requested,
   **Then** the output code includes gradient and shadow styling matching the DSL values.

---

### Edge Cases

- What happens when two detected components overlap significantly (neither fully contains
  the other)? Both are treated as top-level and included.
- What happens when a screenshot contains only text with no distinct component boundaries?
  The system reports that no structured components were detected.
- What happens when DSL extraction fails for a specific component? That component is
  skipped and marked "extraction failed"; remaining components continue processing.
- What happens when the requested target format is not supported? The system returns a
  clear error listing the supported formats.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept a screenshot image as input and return a list of
  top-level (non-nested) component crops.
- **FR-002**: System MUST determine nesting relationships between detected components and
  MUST exclude any component whose bounding box is fully contained within another detected
  component's bounding box.
- **FR-003**: System MUST produce a Component DSL for each top-level component capturing:
  width, height, corner radius, background (solid color or gradient), border (color +
  width), and shadow (offset X/Y, blur, spread, color).
- **FR-004**: System MUST support code generation in at least three target formats:
  HTML/CSS, React (JSX), and React Native.
- **FR-005**: Users MUST be able to request code generation for a single component or for
  all components in one batch operation.
- **FR-006**: System MUST preserve all component crops, DSL files, and generated code
  files as artifacts that can be reviewed or re-used without re-running the full pipeline.
- **FR-007**: System MUST report per-component status (success / failed / skipped) so
  that a partial failure does not silently produce an incomplete library.
- **FR-008**: System MUST expose the component library pipeline via both a CLI (for local
  development) and a web interface (for interactive inspection).

### Key Entities

- **Screenshot**: The input image. Has width, height, and source path.
- **Detected Component**: A UI element identified in the screenshot, defined by a bounding
  box (x, y, width, height) and a confidence score.
- **Top-Level Component**: A Detected Component not fully contained within any other
  Detected Component. These form the component library.
- **Component Crop**: The raster image of a Top-Level Component extracted from the
  screenshot at its bounding box.
- **Component DSL**: A structured, format-agnostic visual description of a Component Crop.
  Properties: dimensions, background (solid or gradient), border radius, border, shadow,
  opacity.
- **Component Artifact**: The generated source code for a Top-Level Component in a
  specific target format, derived from its Component DSL.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a screenshot containing clearly distinct top-level components (buttons,
  cards, nav bars), at least 80% of top-level components are correctly extracted with no
  nested sub-elements included in the top-level set.
- **SC-002**: A Component DSL produced for a component with known visual properties
  matches those properties with less than 10% deviation for colors and dimensions.
- **SC-003**: Generated code for a component renders with at least 90% visual similarity
  to the original crop when viewed in the target environment, as judged by a developer
  performing a side-by-side comparison.
- **SC-004**: The full pipeline (screenshot → component library with code) completes
  within 2 minutes for a screenshot yielding up to 20 top-level components.
- **SC-005**: A developer can obtain a working component library from a screenshot in a
  single command or a single web upload with no multi-step manual intervention required.

## Assumptions

- The target user is a developer wanting reusable UI building blocks, not a pixel-perfect
  full-page layout reconstruction.
- "Top-level" is defined purely by bounding-box containment: if component A's box is fully
  inside component B's box, A is nested and excluded.
- Visual DSL accuracy depends on screenshot quality; blurry or low-resolution inputs may
  produce less accurate results.
- A valid AI vision service API key is available in the environment; without it DSL
  extraction is unavailable and the pipeline stops after component cropping.
- The component library output (folder of crops + DSL files + generated code) is sufficient
  for v1; a visual catalog browser UI is out of scope.
- Three code targets (HTML, React, React Native) cover primary use cases; additional
  targets (Vue, Flutter, SwiftUI) are out of scope for this version.
