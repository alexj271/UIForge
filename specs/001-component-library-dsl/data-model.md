# Data Model: Screenshot-to-Component Library

**Phase 1 output** | Feature: `001-component-library-dsl` | Date: 2026-03-28

All new models live in `app/models/dsl.py`. Existing models in `app/models/ast.py`
are unchanged.

---

## New Models (`app/models/dsl.py`)

### `GradientStop`

One color stop within a gradient.

| Field | Type | Description |
|-------|------|-------------|
| `color` | `str` | Hex color code, e.g. `"#FF5733"` |
| `position` | `float` | Position along gradient axis, 0.0–1.0 |

---

### `GradientDSL`

A linear gradient fill.

| Field | Type | Description |
|-------|------|-------------|
| `direction` | `str` | CSS-compatible direction, e.g. `"to right"`, `"135deg"` |
| `stops` | `list[GradientStop]` | Ordered list of color stops (minimum 2) |

---

### `BackgroundDSL`

Discriminated background: either solid color or gradient.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | `Literal["solid", "gradient"]` | ✅ | Background kind |
| `color` | `str \| None` | when `type="solid"` | Hex color, e.g. `"#FFFFFF"` |
| `gradient` | `GradientDSL \| None` | when `type="gradient"` | Gradient definition |

Invariant: exactly one of `color` or `gradient` is non-null.

---

### `ShadowDSL`

A CSS-compatible drop shadow.

| Field | Type | Description |
|-------|------|-------------|
| `offset_x` | `float` | Horizontal offset in px (negative = left) |
| `offset_y` | `float` | Vertical offset in px (negative = up) |
| `blur` | `float` | Blur radius in px (≥ 0) |
| `spread` | `float` | Spread radius in px |
| `color` | `str` | Shadow color, hex or rgba string |

---

### `BorderDSL`

Component border.

| Field | Type | Description |
|-------|------|-------------|
| `width` | `float` | Border width in px |
| `color` | `str` | Border color, hex |
| `style` | `str` | CSS border-style: `"solid"`, `"dashed"`, `"dotted"` |

---

### `ComponentDSL`

The primary intermediate artifact. One instance per extracted top-level component.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | ✅ | Matches `UIComponent.id` from detection stage |
| `label` | `str` | ✅ | Human-readable name inferred by vision LLM |
| `width` | `float` | ✅ | Rendered width in px |
| `height` | `float` | ✅ | Rendered height in px |
| `background` | `BackgroundDSL` | ✅ | Fill: solid color or gradient |
| `border_radius` | `float` | ✅ | Uniform corner radius in px (0 = square) |
| `border` | `BorderDSL \| None` | — | Null if no visible border |
| `shadow` | `ShadowDSL \| None` | — | Null if no visible shadow |
| `opacity` | `float` | ✅ | 0.0–1.0, default 1.0 |
| `crop_path` | `str` | ✅ | Relative path to saved crop image |

---

### `ComponentLibrary`

Top-level output artifact for a single screenshot run.

| Field | Type | Description |
|-------|------|-------------|
| `source_image` | `str` | Original screenshot filename |
| `total_detected` | `int` | Total components found by detector |
| `total_toplevel` | `int` | Components after nesting filter |
| `components` | `list[ComponentDSL]` | DSL entries for each top-level component |

---

## Relationship to Existing Models

```
UIJsonAST (ast.py)
  └── components: list[UIComponent]
          └── bounding_box: BoundingBox
                              ↓ (nesting filter)
              top-level UIComponent list
                              ↓ (segmentation → crop saved)
              UIComponent.crop_path set
                              ↓ (DSL extraction)
ComponentLibrary (dsl.py)
  └── components: list[ComponentDSL]
                              ↓ (LLM codegen)
              dict[id → code_string]
```

The `UIJsonAST` / `UIComponent` models are used through stages 1–3. From stage 4
onward, `ComponentLibrary` is the primary data contract.

---

## Serialization

Both `ComponentDSL` and `ComponentLibrary` serialize to JSON via
`model.model_dump_json(indent=2)`. Saved files:

- `output/<stem>/03_library.json` — full `ComponentLibrary`
- `output/<stem>/library/<id>.dsl.json` — individual `ComponentDSL`
