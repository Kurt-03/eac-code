"""SearchFiles tool (Phase I.4) — Hermes-style `search_files` (rg-powered).

Complements ``grep`` with a search-engine surface: pattern + optional
path/glob, returns file:line matches. Shares the ripgrep runner with
the grep tool (same output contract, no context lines by default).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from eaccode.tools.base import Tool, ToolClass, ToolContext, ToolResult


class SearchFilesInput(BaseModel):
    pattern: str = Field(description="Regex pattern to search for")
    path: str | None = Field(default=None, description="File or directory (default: workdir)")
    file_glob: str | None = Field(default=None, description="Only search files matching this glob")
    limit: int = Field(default=50, description="Maximum matches to return")


class SearchFilesTool(Tool):
    name = "search_files"
    tool_class = ToolClass.IDEMPOTENT
    description = (
        "Search files for a regex pattern (ripgrep-powered). Returns "
        "file:line:content matches. Use grep for context lines, this for "
        "plain search across many files."
    )
    input_model = SearchFilesInput
    requires_permission = False

    async def run(self, input: SearchFilesInput, ctx: ToolContext) -> ToolResult:
        base = Path(input.path) if input.path else ctx.workdir
        if not base.is_absolute():
            base = ctx.workdir / base

        import shutil

        if shutil.which("rg"):
            return self._run_ripgrep(input, base)
        # Fallback: reuse the grep tool's Python walker via a simple import.
        from eaccode.tools.builtin.grep import GrepInput, GrepTool

        result = await GrepTool().run(
            GrepInput(pattern=input.pattern, path=str(base),
                      glob=input.file_glob, context=0),
            ctx,
        )
        if not result.is_error:
            lines = result.content.splitlines()
            if len(lines) > input.limit:
                result.content = "\n".join(lines[:input.limit]) + (
                    f"\n[... {len(lines) - input.limit} more matches ...]"
                )
        return result

    def _run_ripgrep(self, input: SearchFilesInput, base: Path) -> ToolResult:
        # -m caps per file; the global cap is enforced below on the output
        # so N files can't blow past the limit.
        cmd = ["rg", "--line-number", "--no-heading", "-e", input.pattern]
        if input.file_glob:
            cmd += ["-g", input.file_glob]
        cmd.append(str(base))
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            return ToolResult(content="search_files timed out after 30s", is_error=True)
        if proc.returncode == 1:  # no matches
            return ToolResult(content="No matches found.")
        if proc.returncode not in (0, 1):
            return ToolResult(content=f"search_files error: {proc.stderr[:500]}", is_error=True)
        lines = proc.stdout.strip().splitlines()
        if len(lines) > input.limit:
            content = "\n".join(lines[: input.limit]) + (
                f"\n[... {len(lines) - input.limit} more matches ...]"
            )
        else:
            content = "\n".join(lines)
        content = content or "No matches found."
        if len(content) > 50_000:
            content = content[:50_000] + "\n[...truncated...]"
        return ToolResult(content=content)
