"""
Component DSL data models.

These are the intermediate representations produced after DSL extraction
and consumed by LLM code generation.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class GradientStop(BaseModel):
    color: str
    position: float  # 0.0 – 1.0


class GradientDSL(BaseModel):
    direction: Optional[str] = "to bottom"  # e.g. "to right", "135deg"
    stops: list[GradientStop] = Field(default_factory=list)


class BackgroundDSL(BaseModel):
    type: Literal["solid", "gradient"]
    color: Optional[str] = None  # hex, used when type="solid"
    gradient: Optional[GradientDSL] = None  # used when type="gradient"


class ShadowDSL(BaseModel):
    offset_x: float
    offset_y: float
    blur: float
    spread: float
    color: str  # hex or rgba string


class BorderDSL(BaseModel):
    width: float
    color: str  # hex
    style: str = "solid"  # "solid" | "dashed" | "dotted"


class TextDSL(BaseModel):
    content: str  # exact visible text
    font_size: Optional[float] = None  # px
    font_weight: Optional[str] = None  # "normal" | "bold" | "600" etc.
    color: str = "#000000"  # hex
    text_align: Optional[str] = None  # "left" | "center" | "right"


class IconDSL(BaseModel):
    name: Optional[str] = (
        None  # recognizable name e.g. "search", "home", "chevron-right"
    )
    color: Optional[str] = None  # hex
    size: Optional[float] = None  # px (approximate)


class LayoutDSL(BaseModel):
    direction: str = "column"  # "row" | "column" | "stack"
    align_items: Optional[str] = (
        None  # "flex-start" | "center" | "flex-end" | "stretch"
    )
    justify_content: Optional[str] = (
        None  # "flex-start" | "center" | "space-between" | "space-around"
    )
    gap: Optional[float] = None  # spacing between children in px
    padding_top: Optional[float] = None
    padding_right: Optional[float] = None
    padding_bottom: Optional[float] = None
    padding_left: Optional[float] = None


class ChildElementDSL(BaseModel):
    role: str  # "text" | "icon" | "image" | "button" | "badge" | "avatar" | "divider" | etc.
    description: str  # brief description of this child element
    texts: list[TextDSL] = Field(default_factory=list)
    icon: Optional[IconDSL] = None
    background: Optional[BackgroundDSL] = None
    border_radius: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None


class ComponentDSL(BaseModel):
    id: str
    label: str  # human-readable name inferred by vision LLM
    width: float
    height: float
    background: BackgroundDSL
    border_radius: float
    border: Optional[BorderDSL] = None
    shadow: Optional[ShadowDSL] = None
    opacity: float = 1.0
    crop_path: str  # relative path to the saved crop image
    # Content
    texts: list[TextDSL] = Field(default_factory=list)
    icons: list[IconDSL] = Field(default_factory=list)
    # Internal structure
    layout: Optional[LayoutDSL] = None
    children: list[ChildElementDSL] = Field(default_factory=list)


class ComponentLibrary(BaseModel):
    source_image: str
    total_detected: int
    total_toplevel: int
    components: list[ComponentDSL] = Field(default_factory=list)
