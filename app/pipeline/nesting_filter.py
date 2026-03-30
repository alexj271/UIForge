"""
Stage 2 (new pipeline): Nesting Filter
Keeps only top-level (non-nested) components.

A component is considered nested if its bounding box is fully contained within
the bounding box of any other detected component AND that other component is not
approximately the same size (near-duplicate from the detector).

Near-duplicate handling: detectors like Grounding DINO often return multiple
slightly overlapping detections for the same UI element.  If two bboxes are
within NEAR_DUPLICATE_TOL pixels of each other in all dimensions they are
treated as duplicates — one is kept (the first by list order), the other is
not considered a "container" so it won't cause the first to be excluded.
"""

from app.models.ast import BoundingBox, UIJsonAST

# Maximum per-edge pixel difference to treat two boxes as near-duplicates.
NEAR_DUPLICATE_TOL = 8


def run_nesting_filter(ast: UIJsonAST) -> UIJsonAST:
    """Return a new UIJsonAST containing only top-level (non-nested) components.

    The input *ast* is not mutated.
    """
    flat = ast.components
    top_level = [c for c in flat if not _is_nested(c.id, c.bounding_box, flat)]
    return UIJsonAST(
        source_image=ast.source_image,
        width=ast.width,
        height=ast.height,
        components=top_level,
    )


def _is_nested(component_id: str, bbox: BoundingBox, all_components: list) -> bool:
    """Return True if *bbox* is strictly contained within any other component's bbox.

    Near-duplicate boxes (within NEAR_DUPLICATE_TOL px on every edge) are
    ignored — they represent duplicate detections, not true containment.
    """
    for other in all_components:
        if other.id == component_id:
            continue
        if _near_duplicate(bbox, other.bounding_box):
            continue
        if _contains(other.bounding_box, bbox):
            return True
    return False


def _near_duplicate(
    a: BoundingBox, b: BoundingBox, tol: int = NEAR_DUPLICATE_TOL
) -> bool:
    """Return True if two bboxes are within *tol* pixels on every edge."""
    return (
        abs(a.x - b.x) <= tol
        and abs(a.y - b.y) <= tol
        and abs(a.width - b.width) <= tol
        and abs(a.height - b.height) <= tol
    )


def _contains(outer: BoundingBox, inner: BoundingBox) -> bool:
    """Return True if *inner* is fully inside *outer*."""
    return (
        outer.x <= inner.x
        and outer.y <= inner.y
        and outer.x + outer.width >= inner.x + inner.width
        and outer.y + outer.height >= inner.y + inner.height
    )
