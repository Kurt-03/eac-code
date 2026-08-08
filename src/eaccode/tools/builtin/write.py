"""Write tool (Task 3.3) — create/overwrite files, creates parent dirs."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from eaccode.tools.base import Tool, ToolContext, ToolResult


class WriteInput(BaseModel):
    path: str = Field(description="Absolute or workdir-relative path")
    content: str = Field(description="Full file contents to write")


class WriteTool(Tool):
    name = "write"
    description = "Create or overwrite a file with the given content."
    input_model = WriteInput
    requires_permission = True  # confirmation in default mode

    async def run(self, input: WriteInput, ctx: ToolContext) -> ToolResult:
        path = Path(input.path)
        if not path.is_absolute():
            path = ctx.workdir / path
        from eaccode.tools.safety import write_denied_error

        denied = write_denied_error(path)
        if denied:
            return ToolResult(content=denied, is_error=True)
        from eaccode.tools.checkpoints import save_checkpoint

        save_checkpoint(ctx.workdir, path)  # Phase C.4 snapshot
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(input.content, encoding="utf-8")
        except Exception as e:
            return ToolResult(content=f"Error writing file: {e}", is_error=True)
        return ToolResult(
            content=f"Wrote {len(input.content)} bytes to {path}",
            metadata={"path": str(path), "bytes": len(input.content)},
        )
