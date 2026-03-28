from app.models.ast import BoundingBox, UIComponent, UIJsonAST
from app.pipeline.layout import run_layout_reconstruction, _contains
from app.pipeline.codegen import run_codegen


def _make_component(id: str, type: str, x: int, y: int, w: int, h: int) -> UIComponent:
    return UIComponent(id=id, type=type, bounding_box=BoundingBox(x=x, y=y, width=w, height=h))


def _make_ast(*components: UIComponent) -> UIJsonAST:
    return UIJsonAST(source_image="test.png", width=800, height=600, components=list(components))


# ── Layout ────────────────────────────────────────────────────────────────────

def test_contains_inner_inside_outer():
    outer = BoundingBox(x=0, y=0, width=200, height=200)
    inner = BoundingBox(x=10, y=10, width=50, height=50)
    assert _contains(outer, inner)


def test_contains_partial_overlap():
    outer = BoundingBox(x=0, y=0, width=100, height=100)
    inner = BoundingBox(x=80, y=80, width=50, height=50)
    assert not _contains(outer, inner)


def test_layout_nests_child_inside_container():
    container = _make_component("c1", "container", 0, 0, 300, 300)
    button = _make_component("btn1", "button", 10, 10, 80, 40)
    ast = run_layout_reconstruction(_make_ast(container, button))
    root_ids = [c.id for c in ast.components]
    assert "c1" in root_ids
    assert "btn1" not in root_ids
    nested = next(c for c in ast.components if c.id == "c1")
    assert any(ch.id == "btn1" for ch in nested.children)


# ── Codegen ───────────────────────────────────────────────────────────────────

def test_codegen_html_contains_button():
    ast = _make_ast(_make_component("btn1", "button", 0, 0, 100, 40))
    ast.components[0].text = "Click me"
    code = run_codegen(ast, target="html")
    assert "<button" in code
    assert "Click me" in code


def test_codegen_rn_contains_touchable():
    ast = _make_ast(_make_component("btn1", "button", 0, 0, 100, 40))
    code = run_codegen(ast, target="react_native")
    assert "TouchableOpacity" in code
