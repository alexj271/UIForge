"""
Stage 4: Layout Reconstruction
Infers spatial relationships between components and nests children inside containers.
Simple top-down containment check: a component is a child of the smallest container that fully encloses it.
"""

from app.models.ast import BoundingBox, UIComponent, UIJsonAST


def run_layout_reconstruction(ast: UIJsonAST) -> UIJsonAST:
    flat = ast.components
    ast.components = _build_hierarchy(flat)
    return ast


def _build_hierarchy(components: list[UIComponent]) -> list[UIComponent]:
    # Sort by area descending so larger (container) components come first
    sorted_comps = sorted(
        components,
        key=lambda c: c.bounding_box.width * c.bounding_box.height,
        reverse=True,
    )

    assigned: set[str] = set()
    roots: list[UIComponent] = []

    for i, parent in enumerate(sorted_comps):
        if parent.id in assigned:
            continue
        for child in sorted_comps[i + 1 :]:
            if child.id not in assigned and _contains(
                parent.bounding_box, child.bounding_box
            ):
                parent.children.append(child)
                assigned.add(child.id)
        roots.append(parent)

    return [c for c in roots if c.id not in assigned - {c.id for c in roots}]


def _contains(outer: BoundingBox, inner: BoundingBox) -> bool:
    return (
        outer.x <= inner.x
        and outer.y <= inner.y
        and outer.x + outer.width >= inner.x + inner.width
        and outer.y + outer.height >= inner.y + inner.height
    )
