from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

ComponentType = Literal[
    "button",
    "card",
    "text",
    "image",
    "icon",
    "container",
    "input",
    "unknown",
]


class BoundingBox(BaseModel):
    x: int
    y: int
    width: int
    height: int


class StyleInfo(BaseModel):
    background_color: Optional[str] = None
    border_color: Optional[str] = None
    border_width: Optional[int] = None
    border_radius: Optional[int] = None
    shadow: Optional[str] = None
    text_color: Optional[str] = None
    font_size: Optional[int] = None

    @field_validator("border_radius", "border_width", "font_size", mode="before")
    @classmethod
    def coerce_to_int(cls, v: object) -> Optional[int]:
        if v is None:
            return None
        if isinstance(v, int):
            return v
        # strip units like "50%", "12px", "1.5rem" → take leading digits
        m = re.match(r"\d+", str(v))
        return int(m.group()) if m else None


class UIComponent(BaseModel):
    id: str
    type: ComponentType
    bounding_box: BoundingBox
    text: Optional[str] = None
    style: StyleInfo = Field(default_factory=StyleInfo)
    children: list[UIComponent] = Field(default_factory=list)
    # relative path to the cropped image saved under static/crops/
    crop_path: Optional[str] = None


class UIJsonAST(BaseModel):
    source_image: str  # original filename
    width: int
    height: int
    components: list[UIComponent] = Field(default_factory=list)
