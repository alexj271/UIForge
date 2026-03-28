"""
Stage 5: Code Generation
Generates React Native or HTML code from the UI JSON AST.
"""

from app.models.ast import UIComponent, UIJsonAST

Target = str  # "react_native" | "html"


def run_codegen(ast: UIJsonAST, target: Target = "react_native") -> str:
    if target == "react_native":
        return _gen_rn(ast)
    if target == "html":
        return _gen_html(ast)
    raise ValueError(f"Unknown codegen target: {target}")


# ── React Native ──────────────────────────────────────────────────────────────

def _gen_rn(ast: UIJsonAST) -> str:
    imports = "import React from 'react';\nimport { View, Text, Image, TouchableOpacity, StyleSheet } from 'react-native';\n"
    body = "\n".join(_rn_component(c, indent=2) for c in ast.components)
    return f"{imports}\nexport default function Screen() {{\n  return (\n    <View>\n{body}\n    </View>\n  );\n}}\n"


def _rn_component(c: UIComponent, indent: int) -> str:
    pad = " " * indent
    children_code = "\n".join(_rn_component(ch, indent + 2) for ch in c.children)

    if c.type == "button":
        inner = f"{pad}  <Text>{c.text or ''}</Text>"
        return f"{pad}<TouchableOpacity>\n{inner}\n{pad}</TouchableOpacity>"
    if c.type == "text":
        return f"{pad}<Text>{c.text or ''}</Text>"
    if c.type == "image":
        return f"{pad}<Image source={{{{ uri: '' }}}} style={{{{ width: {c.bounding_box.width}, height: {c.bounding_box.height} }}}} />"

    # container / card / unknown
    inner = children_code if children_code else (f"{pad}  <Text>{c.text}</Text>" if c.text else "")
    return f"{pad}<View>\n{inner}\n{pad}</View>"


# ── HTML ──────────────────────────────────────────────────────────────────────

def _gen_html(ast: UIJsonAST) -> str:
    body = "\n".join(_html_component(c, indent=2) for c in ast.components)
    return f"<div class=\"screen\">\n{body}\n</div>"


def _html_component(c: UIComponent, indent: int) -> str:
    pad = " " * indent
    children_code = "\n".join(_html_component(ch, indent + 2) for ch in c.children)

    style = _inline_style(c)

    if c.type == "button":
        return f'{pad}<button style="{style}">{c.text or ""}</button>'
    if c.type == "text":
        return f'{pad}<p style="{style}">{c.text or ""}</p>'
    if c.type == "image":
        return f'{pad}<img src="" style="{style}" />'
    if c.type == "input":
        return f'{pad}<input type="text" placeholder="{c.text or ""}" style="{style}" />'

    inner = children_code if children_code else (f"{pad}  {c.text}" if c.text else "")
    return f'{pad}<div style="{style}">\n{inner}\n{pad}</div>'


def _inline_style(c: UIComponent) -> str:
    s = c.style
    parts: list[str] = [
        f"width:{c.bounding_box.width}px",
        f"height:{c.bounding_box.height}px",
    ]
    if s.background_color:
        parts.append(f"background-color:{s.background_color}")
    if s.border_color and s.border_width:
        parts.append(f"border:{s.border_width}px solid {s.border_color}")
    if s.border_radius:
        parts.append(f"border-radius:{s.border_radius}px")
    if s.text_color:
        parts.append(f"color:{s.text_color}")
    if s.font_size:
        parts.append(f"font-size:{s.font_size}px")
    return ";".join(parts)
