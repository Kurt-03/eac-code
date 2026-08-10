"""Process tool (Phase I.2) — spawn/status/poll/kill background processes.

Ported from Hermes' ``tools/process.py`` (ProcessRegistry pattern):
processes are tracked by a registry keyed on a session id so the agent
can start a long-running server, poll it, read its output, and kill it —
without blocking the tool loop. All children are spawned detached
(no console window on Windows, own process group on POSIX) so a killed
agent can't orphan console handles (Phase A errno-9 class).
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, Field

from eaccode._subprocess_compat import (
    IS_WINDOWS,
    kill_process_tree,
    windows_detach_flags,
)
from eaccode.tools.base import Tool, ToolClass, ToolContext, ToolResult


@dataclass
class ManagedProcess:
    """One tracked background process."""

    pid: int
    name: str
    command: str
    started_at: float
    proc: subprocess.Popen | None = None
    output: list[str] = field(default_factory=list)

    def poll(self) -> str | None:
        """Return the exit code if the process ended, else None."""
        if self.proc is None:
            try:
                os.kill(self.pid, 0)
                return None
            except OSError:
                return "exited"
        code = self.proc.poll()
        return None if code is None else str(code)

    def drain_output(self) -> str:
        """Read any new output lines (best-effort)."""
        if self.proc is None:
            return ""
        try:
            out = self.proc.stdout.readline() if self.proc.stdout else ""
            while out:
                self.output.append(out.rstrip())
                out = self.proc.stdout.readline() if self.proc.stdout else ""
        except Exception:
            pass
        return "\n".join(self.output[-50:])


class _ProcessRegistry:
    """Session-scoped registry of managed processes."""

    def __init__(self) -> None:
        self._processes: dict[str, ManagedProcess] = {}

    def spawn(self, key: str, command: str, cwd: Path | None = None,
              env: dict[str, str] | None = None) -> ManagedProcess:
        kwargs: dict = {
            "shell": True,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "stdin": subprocess.DEVNULL,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "cwd": str(cwd) if cwd else None,
            "env": {**os.environ, **(env or {})},
            "creationflags": windows_detach_flags(),
        }
        if not IS_WINDOWS:
            kwargs["start_new_session"] = True
        proc = subprocess.Popen(command, **kwargs)
        managed = ManagedProcess(
            pid=proc.pid, name=key, command=command,
            started_at=time.time(), proc=proc,
        )
        self._processes[key] = managed
        return managed

    def get(self, key: str) -> ManagedProcess | None:
        return self._processes.get(key)

    def list(self) -> list[ManagedProcess]:
        return list(self._processes.values())

    def kill(self, key: str) -> bool:
        managed = self._processes.get(key)
        if managed is None:
            return False
        if managed.proc is not None:
            kill_process_tree(managed.proc)
        else:
            with contextlib.suppress(OSError):
                os.kill(managed.pid, 9)
        return True

    def remove(self, key: str) -> bool:
        return self._processes.pop(key, None) is not None


class ProcessInput(BaseModel):
    action: str = Field(
        description="Action: spawn | status | list | poll | kill | remove"
    )
    key: str = Field(default="", description="Process registry key (name)")
    command: str = Field(default="", description="Shell command (spawn only)")
    timeout: float = Field(default=2.0, description="Poll wait seconds")


class ProcessTool(Tool):
    name = "process"
    tool_class = ToolClass.MUTATING
    description = (
        "Manage background processes: spawn a shell command detached, "
        "poll its status/output, list all, or kill a process tree. "
        "Use for long-running servers or watchers that would block bash."
    )
    input_model = ProcessInput
    requires_permission = True

    def __init__(self) -> None:
        self._registry = _ProcessRegistry()

    async def run(self, input: ProcessInput, ctx: ToolContext) -> ToolResult:
        action = input.action.lower()
        if action == "spawn":
            if not input.command:
                return ToolResult(content="spawn requires a command", is_error=True)
            managed = self._registry.spawn(input.key or "default", input.command,
                                           cwd=ctx.workdir, env=ctx.env)
            return ToolResult(
                content=f"Started '{input.command}' as '{managed.name}' (pid {managed.pid})"
            )
        if action == "status":
            managed = self._registry.get(input.key)
            if managed is None:
                return ToolResult(content=f"No process '{input.key}'", is_error=True)
            code = managed.poll()
            state = "running" if code is None else f"exited ({code})"
            uptime = time.time() - managed.started_at
            return ToolResult(
                content=f"{managed.name}: {state}, uptime {uptime:.1f}s, "
                        f"pid {managed.pid}"
            )
        if action == "list":
            procs = self._registry.list()
            if not procs:
                return ToolResult(content="No managed processes.")
            lines = [
                f"{p.name}: pid {p.pid}, "
                f"{'running' if p.poll() is None else 'exited'}"
                for p in procs
            ]
            return ToolResult(content="\n".join(lines))
        if action == "poll":
            managed = self._registry.get(input.key)
            if managed is None:
                return ToolResult(content=f"No process '{input.key}'", is_error=True)
            # Wait up to timeout seconds for the process to produce output
            # or exit.
            deadline = time.time() + max(0.0, input.timeout)
            while time.time() < deadline:
                if managed.poll() is not None:
                    break
                time.sleep(0.1)
            output = managed.drain_output()
            code = managed.poll()
            state = "running" if code is None else f"exited ({code})"
            body = f"{managed.name}: {state}\n"
            body += output if output else "(no output yet)"
            return ToolResult(content=body)
        if action == "kill":
            if self._registry.kill(input.key):
                return ToolResult(content=f"Killed '{input.key}' (process tree)")
            return ToolResult(content=f"No process '{input.key}'", is_error=True)
        if action == "remove":
            if self._registry.remove(input.key):
                return ToolResult(content=f"Removed '{input.key}' from registry")
            return ToolResult(content=f"No process '{input.key}'", is_error=True)
        return ToolResult(content=f"Unknown action: {action}", is_error=True)
