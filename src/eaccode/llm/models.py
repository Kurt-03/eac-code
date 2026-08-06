"""Vendor-neutral message/tool-call models (Task 2.1).

A single format for all providers — LiteLLM translates into the
provider-specific shape (Anthropic/OpenAI conventions).
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class TextContent(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ImageContent(BaseModel):
    type: Literal["image"] = "image"
    source: dict[str, Any]  # {"type": "base64", "media_type": ..., "data": ...}


ContentBlock = TextContent | ImageContent


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]


class Message(BaseModel):
    role: Role
    content: list[ContentBlock] = Field(default_factory=list)
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None  # for tool roles
    is_error: bool | None = None

    @classmethod
    def system(cls, text: str) -> "Message":
        return cls(role=Role.SYSTEM, content=[TextContent(text=text)])

    @classmethod
    def user(cls, text: str, images: list[ImageContent] | None = None) -> "Message":
        return cls(role=Role.USER, content=[TextContent(text=text), *(images or [])])

    @classmethod
    def assistant(cls, text: str) -> "Message":
        return cls(role=Role.ASSISTANT, content=[TextContent(text=text)])

    @classmethod
    def assistant_with_tool_calls(
        cls, blocks: list[ContentBlock], tool_calls: list[ToolCall]
    ) -> "Message":
        return cls(role=Role.ASSISTANT, content=blocks, tool_calls=tool_calls)

    @classmethod
    def tool_result(
        cls,
        tool_call_id: str,
        content: str,
        *,
        is_error: bool = False,
        name: str | None = None,
    ) -> "Message":
        return cls(
            role=Role.TOOL,
            content=[TextContent(text=content)],
            tool_call_id=tool_call_id,
            is_error=is_error,
            name=name,
        )

    @property
    def text(self) -> str:
        """Full text content of the message (for display/search)."""
        return "".join(b.text for b in self.content if b.type == "text")
