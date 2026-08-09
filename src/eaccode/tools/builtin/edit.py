"""Edit tool (Task 3.4) — string-replace with uniqueness check."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from eaccode.tools.base import Tool, ToolClass, ToolContext, ToolResult


class EditInput(BaseModel):
    path: str = Field(description="File to edit")
    old_string: str = Field(
        description="Exact text to replace (must be unique in the file)"
    )
    new_string: str = Field(description="Replacement text")


class EditTool(Tool):
    name = "edit"
    description = (
        "Replace a unique string in a file. Fails if old_string is missing "
        "or matches multiple times."
    )
    input_model = EditInput
    requires_permission = True
    tool_class = ToolClass.MUTATING

    async def run(self, input: EditInput, ctx: ToolContext) -> ToolResult:
        from eaccode.tools.safety import write_denied_error

        path = Path(input.path)
        if not path.is_absolute():
            path = ctx.workdir / path
        denied = write_denied_error(path)
        if denied:
            return ToolResult(content=denied, is_error=True)
        from eaccode.tools.checkpoints import save_checkpoint

        save_checkpoint(ctx.workdir, path)  # Phase C.4 snapshot
        if not path.exists():
            return ToolResult(content=f"Error: file not found: {path}", is_error=True)
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as e:
            return ToolResult(content=f"Error reading file: {e}", is_error=True)
        occurrences = text.count(input.old_string)
        if occurrences == 0:
            return ToolResult(
                content="Error: old_string not found in file. Read the file "
                "first to see current contents.",
                is_error=True,
            )
        if occurrences > 1:
            return ToolResult(
                content=f"Error: old_string matches {occurrences} locations. "
                "Make it more unique by including surrounding context.",
                is_error=True,
            )
        new_text = text.replace(input.old_string, input.new_string, 1)
        try:
            path.write_text(new_text, encoding="utf-8")
        except Exception as e:
            return ToolResult(content=f"Error writing file: {e}", is_error=True)
        return ToolResult(content=f"Edited {path}", metadata={"path": str(path)})
