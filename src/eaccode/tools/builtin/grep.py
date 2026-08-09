"""Grep tool (Task 3.6) — ripgrep when available, pure-Python fallback."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from eaccode.tools.base import Tool, ToolClass, ToolContext, ToolResult


class GrepInput(BaseModel):
    pattern: str = Field(description="Regex pattern to search for")
    path: str | None = Field(default=None, description="File or directory (default: workdir)")
    glob: str | None = Field(default=None, description="Only search files matching this glob")
    context: int = Field(default=0, description="Lines of context before/after each match")


class GrepTool(Tool):
    name = "grep"
    tool_class = ToolClass.IDEMPOTENT
    description = (
        "Search files for a regex pattern. Returns file:line:content matches "
        "with optional context lines. Uses ripgrep when available."
    )
    input_model = GrepInput
    requires_permission = False

    async def run(self, input: GrepInput, ctx: ToolContext) -> ToolResult:
        base = Path(input.path) if input.path else ctx.workdir
        if not base.is_absolute():
            base = ctx.workdir / base
        if shutil.which("rg"):
            return self._run_ripgrep(input, base)
        return self._run_python_fallback(input, base)

    def _run_ripgrep(self, input: GrepInput, base: Path) -> ToolResult:
        cmd = ["rg", "--line-number", "--no-heading", "-e", input.pattern]
        if input.context:
            cmd += ["-C", str(input.context)]
        if input.glob:
            cmd += ["-g", input.glob]
        if base.is_file():
            cmd.append(str(base))
        else:
            cmd.append(str(base))
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            return ToolResult(content="grep timed out after 30s", is_error=True)
        if proc.returncode == 1:  # no matches
            return ToolResult(content="No matches found.")
        if proc.returncode not in (0, 1):
            return ToolResult(content=f"grep error: {proc.stderr[:500]}", is_error=True)
        return ToolResult(content=proc.stdout.strip() or "No matches found.")

    def _run_python_fallback(self, input: GrepInput, base: Path) -> ToolResult:
        try:
            pattern = re.compile(input.pattern)
        except re.error as e:
            return ToolResult(content=f"Invalid regex: {e}", is_error=True)
        files: list[Path]
        if base.is_file():
            files = [base]
        else:
            files = sorted(
                p for p in base.rglob("*") if p.is_file() and not any(
                    part.startswith(".") or part == "__pycache__" for part in p.parts
                )
            )
        if input.glob:
            from fnmatch import fnmatch

            files = [p for p in files if fnmatch(p.name, input.glob)]
        lines_out: list[str] = []
        for path in files:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            lines = text.splitlines()
            for i, line in enumerate(lines):
                if pattern.search(line):
                    rel = path.relative_to(base) if base.is_dir() else path.name
                    lines_out.append(f"{rel}:{i + 1}:{line}")
                    for off in range(1, input.context + 1):
                        if i - off >= 0:
                            lines_out.append(f"{rel}:{i - off + 1}:{lines[i - off]}")
                        if i + off < len(lines):
                            lines_out.append(f"{rel}:{i + off + 1}:{lines[i + off]}")
        return ToolResult(content="\n".join(lines_out) if lines_out else "No matches found.")
