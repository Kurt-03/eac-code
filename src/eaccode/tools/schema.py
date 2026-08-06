"""JSON Schema generation from Pydantic models (Task 3.1)."""
from __future__ import annotations

from pydantic import BaseModel


def to_json_schema(model: type[BaseModel]) -> dict:
    """Pydantic model → JSON Schema (Anthropic/OpenAI-compatible)."""
    return model.model_json_schema()
