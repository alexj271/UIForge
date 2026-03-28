"""Unit tests for app.pipeline.nesting_filter.

TDD: these tests are written first and must FAIL before nesting_filter.py exists.
"""

from app.models.ast import BoundingBox, UIComponent, UIJsonAST


def _make_component(id_: str, x: int, y: int, w: int, h: int) -> UIComponent:
    return UIComponent(
        id=id_,
        type="unknown",
        bounding_box=BoundingBox(x=x, y=y, width=w, height=h),
    )


def _make_ast(components: list[UIComponent]) -> UIJsonAST:
    return UIJsonAST(
        source_image="test.png", width=1000, height=1000, components=components
    )


class TestNestingFilter:
    def test_nested_component_excluded(self) -> None:
        """Component B fully inside A → only A in top-level result."""
        from app.pipeline.nesting_filter import run_nesting_filter

        card = _make_component("card", x=0, y=0, w=300, h=200)
        button = _make_component("button", x=10, y=10, w=80, h=30)
        ast = _make_ast([card, button])

        result = run_nesting_filter(ast)

        ids = {c.id for c in result.components}
        assert "card" in ids
        assert "button" not in ids

    def test_overlapping_components_both_kept(self) -> None:
        """Components that overlap but neither contains the other → both kept."""
        from app.pipeline.nesting_filter import run_nesting_filter

        a = _make_component("a", x=0, y=0, w=200, h=200)
        b = _make_component("b", x=100, y=100, w=200, h=200)
        ast = _make_ast([a, b])

        result = run_nesting_filter(ast)

        ids = {c.id for c in result.components}
        assert "a" in ids
        assert "b" in ids

    def test_all_toplevel_when_no_nesting(self) -> None:
        """Side-by-side components with no containment → all returned unchanged."""
        from app.pipeline.nesting_filter import run_nesting_filter

        a = _make_component("a", x=0, y=0, w=100, h=100)
        b = _make_component("b", x=200, y=0, w=100, h=100)
        c = _make_component("c", x=400, y=0, w=100, h=100)
        ast = _make_ast([a, b, c])

        result = run_nesting_filter(ast)

        assert len(result.components) == 3

    def test_empty_input(self) -> None:
        """Empty component list → empty result."""
        from app.pipeline.nesting_filter import run_nesting_filter

        ast = _make_ast([])
        result = run_nesting_filter(ast)
        assert result.components == []

    def test_deeply_nested_only_root_kept(self) -> None:
        """Three levels of nesting: only the outermost root is kept."""
        from app.pipeline.nesting_filter import run_nesting_filter

        outer = _make_component("outer", x=0, y=0, w=500, h=500)
        middle = _make_component("middle", x=50, y=50, w=300, h=300)
        inner = _make_component("inner", x=100, y=100, w=100, h=100)
        ast = _make_ast([outer, middle, inner])

        result = run_nesting_filter(ast)

        ids = {c.id for c in result.components}
        assert ids == {"outer"}

    def test_original_ast_components_not_mutated(self) -> None:
        """run_nesting_filter must not mutate the input ast.components list."""
        from app.pipeline.nesting_filter import run_nesting_filter

        card = _make_component("card", x=0, y=0, w=300, h=200)
        button = _make_component("button", x=10, y=10, w=80, h=30)
        ast = _make_ast([card, button])
        original_count = len(ast.components)

        run_nesting_filter(ast)

        # Input ast must be unchanged
        assert len(ast.components) == original_count

    def test_near_duplicate_boxes_both_kept(self) -> None:
        """Two components with identical bboxes (detector duplicates) → both kept."""
        from app.pipeline.nesting_filter import run_nesting_filter

        a = _make_component("a", x=46, y=254, w=159, h=157)
        b = _make_component("b", x=46, y=254, w=159, h=157)  # exact duplicate
        ast = _make_ast([a, b])

        result = run_nesting_filter(ast)

        ids = {c.id for c in result.components}
        assert "a" in ids
        assert "b" in ids

    def test_near_duplicate_1px_diff_both_kept(self) -> None:
        """Two components differing by 1px (detector near-duplicate) → both kept."""
        from app.pipeline.nesting_filter import run_nesting_filter

        a = _make_component("a", x=394, y=255, w=157, h=156)
        b = _make_component("b", x=394, y=255, w=157, h=155)  # 1px height diff
        ast = _make_ast([a, b])

        result = run_nesting_filter(ast)

        ids = {c.id for c in result.components}
        assert "a" in ids
        assert "b" in ids

    def test_total_detected_preserved(self) -> None:
        """The returned UIJsonAST width/height/source_image are unchanged."""
        from app.pipeline.nesting_filter import run_nesting_filter

        card = _make_component("card", x=0, y=0, w=300, h=200)
        ast = _make_ast([card])
        ast.width = 1920
        ast.height = 1080

        result = run_nesting_filter(ast)

        assert result.width == 1920
        assert result.height == 1080
        assert result.source_image == "test.png"
