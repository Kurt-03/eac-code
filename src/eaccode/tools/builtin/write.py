"""Write tool (Task 3.3) — create/overwrite files, creates parent dirs."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from eaccode.tools.base import Tool, ToolClass, ToolContext, ToolResult
from eaccode.tools.file_state import lock_path, touch


class WriteInput(BaseModel):
    path: str = Field(description="Absolute or workdir-relative path")
    content: str = Field(description="Full file contents to write")


class WriteTool(Tool):
    name = "write"
    description = "Create or overwrite a file with the given content."
    input_model = WriteInput
    requires_permission = True
    tool_class = ToolClass.MUTATING  # confirmation in default mode

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
            with lock_path(path):  # P0.5: per-path write coordination
                path.parent.mkdir(parents=True, exist_ok=True)
                import asyncio

                # C6 (audit): file I/O must not block the Textual event loop.
                await asyncio.to_thread(
                    path.write_text, input.content, encoding="utf-8"
                )
                touch(path, writer_id=ctx.writer_id)  # P0.5: record the write
        except Exception as e:
            return ToolResult(content=f"Error writing file: {e}", is_error=True)
        return ToolResult(
            content=f"Wrote {len(input.content)} bytes to {path}",
            metadata={"path": str(path), "bytes": len(input.content)},
        )
