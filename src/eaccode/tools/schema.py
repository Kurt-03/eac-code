"""JSON-Schema-Erzeugung aus Pydantic-Modellen (Task 3.1)."""
from __future__ import annotations

from pydantic import BaseModel


def to_json_schema(model: type[BaseModel]) -> dict:
    """Pydantic-Modell → JSON-Schema (Anthropic/OpenAI-kompatibel)."""
    return model.model_json_schema()
