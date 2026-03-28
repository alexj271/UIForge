"""Unit tests for app.services.llm_codegen_client.

TDD: these tests are written first and must FAIL before llm_codegen_client.py exists.
All OpenAI API calls are mocked — no live network access.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.dsl import BackgroundDSL, ComponentDSL


def _make_dsl(id_: str = "comp_001", label: str = "button") -> ComponentDSL:
    return ComponentDSL(
        id=id_,
        label=label,
        width=120.0,
        height=44.0,
        background=BackgroundDSL(type="solid", color="#007AFF"),
        border_radius=8.0,
        crop_path="crops/comp_001.png",
    )


def _mock_settings(model: str = "gpt-4o") -> MagicMock:
    s = MagicMock()
    s.codegen_model = model
    s.openai_api_key = "sk-test"
    s.openai_base_url = "https://api.openai.com/v1"
    return s


class TestLlmCodegenClient:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("target", ["html", "react", "react_native"])
    async def test_codegen_client_all_targets(self, target: str) -> None:
        """Mock returns code → generate_code returns non-empty string for all targets."""
        from app.services.llm_codegen_client import generate_code

        raw_code = "<div class='btn'>Click me</div>"
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = raw_code

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch(
            "app.services.llm_codegen_client.AsyncOpenAI", return_value=mock_client
        ):
            result = await generate_code(_make_dsl(), target, _mock_settings())

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_codegen_client_strips_markdown_fences(self) -> None:
        """Code wrapped in markdown fences → fences removed from output."""
        from app.services.llm_codegen_client import generate_code

        fenced = "```jsx\nconst Btn = () => <button>Click</button>;\n```"
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = fenced

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch(
            "app.services.llm_codegen_client.AsyncOpenAI", return_value=mock_client
        ):
            result = await generate_code(_make_dsl(), "react", _mock_settings())

        assert "```" not in result
        assert "const Btn" in result

    @pytest.mark.asyncio
    async def test_codegen_client_handles_api_error(self) -> None:
        """Mock raises exception → generate_code returns empty string (no exception)."""
        import openai

        from app.services.llm_codegen_client import generate_code

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=openai.APIError("timeout", request=MagicMock(), body=None)
        )

        with patch(
            "app.services.llm_codegen_client.AsyncOpenAI", return_value=mock_client
        ):
            result = await generate_code(_make_dsl(), "react", _mock_settings())

        assert result == ""

    @pytest.mark.asyncio
    async def test_codegen_client_prompt_contains_target(self) -> None:
        """The API call should include the target format name in the user message."""
        from app.services.llm_codegen_client import generate_code

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "some code"

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch(
            "app.services.llm_codegen_client.AsyncOpenAI", return_value=mock_client
        ):
            await generate_code(_make_dsl(), "react_native", _mock_settings())

        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs.get("messages") or call_args.args[0]
        # Find user message content
        user_messages = [m for m in messages if m.get("role") == "user"]
        user_text = str(user_messages)
        assert (
            "react_native" in user_text.lower() or "react native" in user_text.lower()
        )
