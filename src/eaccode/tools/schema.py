"""JSON Schema generation from Pydantic models (Task 3.1, H.16).

``sanitize_schema`` strips fields some backends choke on: bundled
``$defs`` (flattened into inline types instead), ``additionalProperties``
(most providers reject it on nested objects), and ``title`` noise.
"""

from __future__ import annotations

import copy

from pydantic import BaseModel


def to_json_schema(model: type[BaseModel]) -> dict:
    """Pydantic model → JSON Schema (Anthropic/OpenAI-compatible)."""
    return sanitize_schema(model.model_json_schema())


def sanitize_schema(schema: dict) -> dict:
    """H.16: backend-safe schema (no $defs, no additionalProperties)."""
    schema = copy.deepcopy(schema)

    def _walk(node: dict) -> dict:
        if "$defs" in node:
            defs = node.pop("$defs")
            for name, sub in defs.items():
                _walk(sub)
                # Inline the definition where it is referenced.
                _inline_refs(node, name, sub)
        for key, value in list(node.items()):
            if key == "additionalProperties" or key == "title":
                node.pop(key)
            elif isinstance(value, dict):
                node[key] = _walk(value)
            elif isinstance(value, list):
                node[key] = [
                    _walk(v) if isinstance(v, dict) else v for v in value
                ]
        return node

    def _inline_refs(node: dict, name: str, sub: dict) -> None:
        for key, value in node.items():
            if isinstance(value, dict):
                if value.get("$ref") == f"#/$defs/{name}":
                    node[key] = copy.deepcopy(sub)
                else:
                    _inline_refs(value, name, sub)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        _inline_refs(item, name, sub)

    return _walk(schema)
