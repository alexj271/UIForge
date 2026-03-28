"""Integration tests for the component library pipeline.

Uses fixture data (saved crop image + pre-built ComponentDSL JSON) so no
live API calls are needed.  The vision_dsl_client and llm_codegen_client
are mocked to return fixture data.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.ast import BoundingBox, UIComponent, UIJsonAST
from app.models.dsl import BackgroundDSL, ComponentDSL, ComponentLibrary
from app.pipeline.nesting_filter import run_nesting_filter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def simple_ast() -> UIJsonAST:
    """A UIJsonAST with one card (outer) and one button (nested inside card)."""
    card = UIComponent(
        id="card_001",
        type="card",
        bounding_box=BoundingBox(x=0, y=0, width=320, height=200),
    )
    button = UIComponent(
        id="btn_001",
        type="button",
        bounding_box=BoundingBox(x=20, y=150, width=100, height=36),
    )
    return UIJsonAST(
        source_image="fixture.png",
        width=375,
        height=812,
        components=[card, button],
    )


@pytest.fixture()
def fixture_dsl() -> ComponentDSL:
    return ComponentDSL(
        id="card_001",
        label="card",
        width=320.0,
        height=200.0,
        background=BackgroundDSL(type="solid", color="#FFFFFF"),
        border_radius=12.0,
        crop_path="crops/card_001.png",
    )


# ---------------------------------------------------------------------------
# Nesting filter integration
# ---------------------------------------------------------------------------


class TestNestingFilterIntegration:
    def test_nesting_filter_returns_only_card(self, simple_ast: UIJsonAST) -> None:
        """Card contains button → only card in top-level result."""
        result = run_nesting_filter(simple_ast)
        ids = {c.id for c in result.components}
        assert ids == {"card_001"}
        assert result.source_image == "fixture.png"

    def test_nesting_filter_preserves_metadata(self, simple_ast: UIJsonAST) -> None:
        result = run_nesting_filter(simple_ast)
        assert result.width == 375
        assert result.height == 812


# ---------------------------------------------------------------------------
# DSL extraction integration (mocked)
# ---------------------------------------------------------------------------


class TestDslExtractionIntegration:
    @pytest.mark.asyncio
    async def test_run_dsl_extraction_produces_library(
        self, simple_ast: UIJsonAST, fixture_dsl: ComponentDSL, tmp_path: Path
    ) -> None:
        """run_dsl_extraction with mocked client returns a ComponentLibrary."""
        from app.pipeline.dsl_extraction import run_dsl_extraction

        # Simulate a crop file existing
        crops_dir = tmp_path / "crops"
        crops_dir.mkdir()
        crop_file = crops_dir / "card_001.png"
        crop_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)

        # Put crop_path on the component
        toplevel = run_nesting_filter(simple_ast)
        toplevel.components[0].crop_path = str(crop_file)

        mock_settings = MagicMock()
        mock_settings.dsl_model = "gpt-4o"
        mock_settings.openai_api_key = "sk-test"
        mock_settings.openai_base_url = "https://api.openai.com/v1"
        mock_settings.concurrent_dsl_calls = 5

        with patch(
            "app.pipeline.dsl_extraction.extract_dsl",
            new=AsyncMock(return_value=fixture_dsl),
        ):
            library = await run_dsl_extraction(toplevel, tmp_path, mock_settings)

        assert isinstance(library, ComponentLibrary)
        assert len(library.components) == 1
        assert library.components[0].id == "card_001"
        assert library.components[0].label == "card"


# ---------------------------------------------------------------------------
# Code generation integration (mocked)
# ---------------------------------------------------------------------------


class TestLlmCodegenIntegration:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("target", ["html", "react", "react_native"])
    async def test_run_llm_codegen_produces_files(
        self, fixture_dsl: ComponentDSL, tmp_path: Path, target: str
    ) -> None:
        """run_llm_codegen with mocked client saves code files for all targets."""
        from app.pipeline.llm_codegen import run_llm_codegen

        library = ComponentLibrary(
            source_image="fixture.png",
            total_detected=2,
            total_toplevel=1,
            components=[fixture_dsl],
        )

        mock_settings = MagicMock()
        mock_settings.codegen_model = "gpt-4o"
        mock_settings.openai_api_key = "sk-test"
        mock_settings.openai_base_url = "https://api.openai.com/v1"
        mock_settings.concurrent_dsl_calls = 5

        fake_code = "<div>card</div>"
        with patch(
            "app.pipeline.llm_codegen.generate_code",
            new=AsyncMock(return_value=fake_code),
        ):
            code_map = await run_llm_codegen(library, target, tmp_path, mock_settings)

        assert "card_001" in code_map
        assert code_map["card_001"] == fake_code

        # Verify file written
        ext = {"html": "html", "react": "jsx", "react_native": "jsx"}[target]
        expected_file = tmp_path / "library" / f"card_001.{ext}"
        assert expected_file.exists()
        assert expected_file.read_text() == fake_code
