from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    # Which detector backend to use: "openai" | "florence2" | "groundingdino"
    detector: Literal["openai", "florence2", "groundingdino"] = "groundingdino"
    # Florence-2 model ID (override to use Florence-2-base for lighter footprint)
    florence_model_id: str = "microsoft/Florence-2-large"
    # Grounding DINO model ID ("grounding-dino-tiny" for speed)
    grounding_dino_model_id: str = "IDEA-Research/grounding-dino-base"

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    # Vision LLM used for DSL extraction from component crops
    dsl_model: str = "gpt-4o"
    # LLM used for code generation from ComponentDSL
    codegen_model: str = "gpt-4o"
    # Max simultaneous LLM calls during DSL extraction
    concurrent_dsl_calls: int = 5


settings = Settings()
