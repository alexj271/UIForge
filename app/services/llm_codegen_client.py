"""
LLM Code Generation Client — converts a ComponentDSL into source code for a
chosen target format (html, react, react_native) using the configured LLM.

Returns an empty string on any failure so callers can handle partial failures.
"""

import logging
import re

from openai import AsyncOpenAI

from app.models.dsl import ComponentDSL

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a UI component code generator. Given a ComponentDSL JSON describing the visual
properties of a single UI component, generate clean, ready-to-use code in the requested
target format.

Guidelines:
- Output ONLY the code, no explanation, no markdown fences.
- Inline all styles directly (no external CSS files).
- Use the exact hex color values, pixel dimensions, border-radius, shadow, and gradient
  from the DSL.
- Component should be self-contained and render correctly in the target environment.

Target format examples:

HTML/CSS:
  <div style="width:120px;height:44px;background:#007AFF;border-radius:8px;">...</div>

React (JSX):
  const ComponentName = () => (
    <div style={{width:120,height:44,backgroundColor:'#007AFF',borderRadius:8}}>...</div>
  );
  export default ComponentName;

React Native:
  import { View, StyleSheet } from 'react-native';
  const styles = StyleSheet.create({ container: { width:120,height:44,backgroundColor:'#007AFF',borderRadius:8 } });
  const ComponentName = () => <View style={styles.container} />;
  export default ComponentName;
"""

_TARGET_LABELS = {
    "html": "HTML/CSS",
    "react": "React (JSX)",
    "react_native": "React Native",
}


def _strip_fences(text: str) -> str:
    """Remove leading/trailing markdown code fences if present."""
    text = text.strip()
    # Match opening fence with optional language tag
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()


async def generate_code(
    dsl: ComponentDSL,
    target: str,
    settings: object,
) -> str:
    """Generate component code from *dsl* for the given *target* format.

    Returns the code string, or an empty string on failure.
    """
    target_label = _TARGET_LABELS.get(target, target)
    component_name = "".join(word.capitalize() for word in dsl.label.split())
    if not component_name:
        component_name = "Component"

    user_message = (
        f"Target format: {target_label}\n"
        f"Component name: {component_name}\n\n"
        f"ComponentDSL:\n{dsl.model_dump_json(indent=2)}"
    )

    client = AsyncOpenAI(
        api_key=settings.openai_api_key,  # type: ignore[attr-defined]
        base_url=settings.openai_base_url,  # type: ignore[attr-defined]
    )

    try:
        response = await client.chat.completions.create(
            model=settings.codegen_model,  # type: ignore[attr-defined]
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=1024,
            temperature=0,
        )
    except Exception as exc:
        logger.error("codegen API error for %s (%s): %s", dsl.id, target, exc)
        return ""

    raw = response.choices[0].message.content or ""
    return _strip_fences(raw)
