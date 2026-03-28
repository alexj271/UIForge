"""Unit tests for app.services.vision_dsl_client.

TDD: these tests are written first and must FAIL before vision_dsl_client.py exists.
All OpenAI API calls are mocked — no live network access.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.dsl import ComponentDSL


def _make_dsl_json(
    *,
    id_: str = "comp_001",
    label: str = "button",
    width: float = 100.0,
    height: float = 40.0,
    bg_color: str = "#007AFF",
    border_radius: float = 8.0,
) -> str:
    """Return a valid ComponentDSL JSON string as the LLM would produce."""
    return json.dumps(
        {
            "id": id_,
            "label": label,
            "width": width,
            "height": height,
            "background": {"type": "solid", "color": bg_color, "gradient": None},
            "border_radius": border_radius,
            "border": None,
            "shadow": None,
            "opacity": 1.0,
            "crop_path": "output/test/crops/comp_001.png",
        }
    )


class TestVisionDslClient:
    @pytest.mark.asyncio
    async def test_dsl_client_returns_component_dsl(self, tmp_path: Path) -> None:
        """Mock returns valid DSL JSON → extract_dsl returns ComponentDSL."""
        from app.services.vision_dsl_client import extract_dsl

        crop = tmp_path / "crop.png"
        crop.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)  # minimal fake PNG

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = _make_dsl_json()

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        mock_settings = MagicMock()
        mock_settings.dsl_model = "gpt-4o"
        mock_settings.openai_api_key = "sk-test"
        mock_settings.openai_base_url = "https://api.openai.com/v1"

        with patch(
            "app.services.vision_dsl_client.AsyncOpenAI", return_value=mock_client
        ):
            result = await extract_dsl("comp_001", crop, mock_settings)

        assert result is not None
        assert isinstance(result, ComponentDSL)
        assert result.id == "comp_001"
        assert result.label == "button"
        assert result.width == 100.0
        assert result.background.type == "solid"
        assert result.background.color == "#007AFF"
        assert result.border_radius == 8.0

    @pytest.mark.asyncio
    async def test_dsl_client_handles_api_error(self, tmp_path: Path) -> None:
        """Mock raises openai.APIError → extract_dsl returns None (no exception)."""
        import openai

        from app.services.vision_dsl_client import extract_dsl

        crop = tmp_path / "crop.png"
        crop.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=openai.APIError("rate limit", request=MagicMock(), body=None)
        )

        mock_settings = MagicMock()
        mock_settings.dsl_model = "gpt-4o"
        mock_settings.openai_api_key = "sk-test"
        mock_settings.openai_base_url = "https://api.openai.com/v1"

        with patch(
            "app.services.vision_dsl_client.AsyncOpenAI", return_value=mock_client
        ):
            result = await extract_dsl("comp_001", crop, mock_settings)

        assert result is None

    @pytest.mark.asyncio
    async def test_dsl_client_handles_invalid_json(self, tmp_path: Path) -> None:
        """Mock returns invalid JSON → extract_dsl returns None gracefully."""
        from app.services.vision_dsl_client import extract_dsl

        crop = tmp_path / "crop.png"
        crop.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "not valid json {"

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        mock_settings = MagicMock()
        mock_settings.dsl_model = "gpt-4o"
        mock_settings.openai_api_key = "sk-test"
        mock_settings.openai_base_url = "https://api.openai.com/v1"

        with patch(
            "app.services.vision_dsl_client.AsyncOpenAI", return_value=mock_client
        ):
            result = await extract_dsl("comp_001", crop, mock_settings)

        assert result is None

    @pytest.mark.asyncio
    async def test_dsl_client_missing_crop_returns_none(self, tmp_path: Path) -> None:
        """Nonexistent crop path → extract_dsl returns None without calling API."""
        from app.services.vision_dsl_client import extract_dsl

        missing = tmp_path / "does_not_exist.png"

        mock_settings = MagicMock()
        mock_settings.dsl_model = "gpt-4o"
        mock_settings.openai_api_key = "sk-test"
        mock_settings.openai_base_url = "https://api.openai.com/v1"

        with patch("app.services.vision_dsl_client.AsyncOpenAI") as mock_cls:
            result = await extract_dsl("comp_001", missing, mock_settings)

        assert result is None
        mock_cls.assert_not_called()
