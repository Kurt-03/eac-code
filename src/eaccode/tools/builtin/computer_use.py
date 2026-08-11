"""computer_use tools (Phase I.5) — desktop automation via cua-driver.

Two tools because the permission policy is tool-name based: read-only
introspection (capture/list) is free, every interaction asks:

- ``computer_use_capture`` — capture (som/vision/ax), list_apps,
  list_windows, cua_browser_state/prepare. No approval needed.
- ``computer_use`` — click/drag/scroll/type/key/set_value/wait/focus,
  capture_after verification, the typed-browser actions, and
  delivery/bring_to_front flags. All ASK (permission modal).

The driver binary is optional: without it the tools report the setup
hint (`eaccode computer install`).
"""

from __future__ import annotations

import contextlib

from pydantic import BaseModel, Field

from eaccode.tools import cua
from eaccode.tools.base import Tool, ToolClass, ToolContext, ToolResult


class CaptureInput(BaseModel):
    mode: str = Field(default="som", description="som | vision | ax")
    app: str | None = Field(default=None, description="Target app name")
    pid: int | None = Field(default=None, description="Target process id")
    window_id: str | None = Field(default=None, description="Target window id")
    max_elements: int = Field(default=100, description="Element cap (max 1000)")


class ComputerUseInput(BaseModel):
    action: str = Field(
        description=(
            "click | double_click | right_click | middle_click | drag | scroll | "
            "type | key | set_value | wait | focus_app | capture_after | "
            "cua_browser_navigate | cua_browser_click | cua_browser_type | "
            "cua_browser_pointer | cua_browser_dialog | cua_browser_set_input_files | "
            "cua_browser_download"
        )
    )
    element: int | None = Field(default=None, description="SOM element index (from capture)")
    coordinate: list[int] | None = Field(default=None, description="[x, y] pixel coordinate")
    text: str | None = Field(default=None, description="type: text to enter")
    combo: str | None = Field(default=None, description="key: combo like 'cmd+s'")
    direction: str | None = Field(default=None, description="scroll: up/down/left/right")
    amount: int = Field(default=3, description="scroll: wheel ticks")
    button: str = Field(default="left", description="left | right | middle")
    modifiers: list[str] | None = Field(default=None, description="cmd/shift/option/alt/ctrl")
    app: str | None = Field(default=None, description="focus_app: app name")
    raise_window: bool = Field(default=False, description="focus_app: raise window")
    label: str | None = Field(default=None, description="set_value: element label")
    value: str | None = Field(default=None, description="set_value: new value")
    seconds: float = Field(default=1.0, description="wait: seconds (max 30)")
    from_element: int | None = Field(default=None, description="drag start element")
    to_element: int | None = Field(default=None, description="drag end element")
    url: str | None = Field(default=None, description="cua_browser_navigate: URL")
    ref: str | None = Field(default=None, description="browser element ref")
    x: int = Field(default=0, description="browser pointer x")
    y: int = Field(default=0, description="browser pointer y")
    pointer_action: str = Field(default="hover",
                                description="hover|right_click|double_click|scroll|drag")
    dialog_action: str = Field(default="inspect",
                               description="inspect|accept|dismiss")
    paths: list[str] | None = Field(
        default=None, description="cua_browser_set_input_files: file paths")
    destination_root: str | None = Field(
        default=None, description="cua_browser_download: target dir")
    delivery: str = Field(default="background", description="background | foreground")
    bring_to_front: bool = Field(default=False, description="raise the app before acting")


class _CuaBase:
    """Shared run plumbing: driver availability + dispatch + error wrap."""

    async def _run(self, action: str, **params) -> ToolResult:
        if not cua.driver_available():
            return ToolResult(
                content=(
                    "cua-driver not installed. Run `eaccode computer install` "
                    "or set EACCODE_CUA_DRIVER to the binary path."
                ),
                is_error=True,
            )
        try:
            reply = cua._dispatch(action, **params)
        except Exception as e:
            return ToolResult(
                content=f"computer_use {action} failed: {type(e).__name__}: {e}",
                is_error=True,
            )
        return ToolResult(content=_format_reply(reply))


class ComputerUseCaptureTool(_CuaBase, Tool):
    name = "computer_use_capture"
    tool_class = ToolClass.IDEMPOTENT
    description = (
        "Read-only desktop introspection via cua-driver: capture the screen "
        "as SOM (numbered elements + accessibility tree), vision (screenshot) "
        "or ax (tree only), list apps/windows. Never mutates anything."
    )
    input_model = CaptureInput
    requires_permission = False

    async def run(self, input: CaptureInput, ctx: ToolContext) -> ToolResult:
        if input.mode not in ("som", "vision", "ax"):
            return ToolResult(content=f"mode must be som|vision|ax, got {input.mode!r}",
                              is_error=True)
        if input.max_elements > 1000:
            return ToolResult(content="max_elements capped at 1000", is_error=True)
        return await self._run(
            "capture", mode=input.mode, app=input.app, pid=input.pid,
            window_id=input.window_id, max_elements=input.max_elements,
        )


class ComputerUseTool(_CuaBase, Tool):
    name = "computer_use"
    tool_class = ToolClass.MUTATING
    description = (
        "Desktop automation via cua-driver: click/drag/scroll/type/key on "
        "SOM elements from a capture, focus apps, plus the typed-browser "
        "route (cua_browser_*). Every action asks for approval."
    )
    input_model = ComputerUseInput
    requires_permission = True

    async def run(self, input: ComputerUseInput, ctx: ToolContext) -> ToolResult:
        a = input.action
        if input.bring_to_front:
            with contextlib.suppress(Exception):
                cua._dispatch("bring_to_front")  # best-effort raise
        try:
            reply = self._dispatch_action(a, input)
        except ValueError as e:
            return ToolResult(content=str(e), is_error=True)
        except Exception as e:
            return ToolResult(
                content=f"computer_use {a} failed: {type(e).__name__}: {e}",
                is_error=True,
            )
        return ToolResult(content=_format_reply(reply))

    def _dispatch_action(self, a: str, input: ComputerUseInput) -> dict:
        if a == "click":
            return cua.cua_click(input.element, input.coordinate, input.button,
                                 input.modifiers, input.delivery)
        if a == "double_click":
            return cua.cua_double_click(input.element, input.coordinate, input.modifiers)
        if a == "right_click":
            return cua.cua_right_click(input.element, input.coordinate, input.modifiers)
        if a == "middle_click":
            return cua.cua_middle_click(input.element, input.coordinate, input.modifiers)
        if a == "drag":
            return cua.cua_drag(input.from_element, input.to_element,
                                input.coordinate, None)
        if a == "scroll":
            return cua.cua_scroll(input.direction, input.amount)
        if a == "type":
            if input.text is None:
                raise ValueError("type requires text")
            return cua.cua_type(input.text)
        if a == "key":
            if not input.combo:
                raise ValueError("key requires combo")
            return cua.cua_key(input.combo)
        if a == "set_value":
            return cua.cua_set_value(input.label or "", input.value or "")
        if a == "wait":
            return cua.cua_wait(input.seconds)
        if a == "focus_app":
            return cua.cua_focus_app(input.app or "", input.raise_window)
        if a == "capture_after":
            return cua.cua_capture_after(action={"click": input.element} if input.element else {})
        if a == "cua_browser_navigate":
            return cua.cua_browser_navigate(input.url or "")
        if a == "cua_browser_click":
            return cua.cua_browser_click(input.ref, input.x, input.y)
        if a == "cua_browser_type":
            return cua.cua_browser_type(input.text or "")
        if a == "cua_browser_pointer":
            return cua.cua_browser_pointer(input.pointer_action, input.x, input.y)
        if a == "cua_browser_dialog":
            return cua.cua_browser_dialog(input.dialog_action)
        if a == "cua_browser_set_input_files":
            return cua.cua_browser_set_input_files(input.paths or [])
        if a == "cua_browser_download":
            return cua.cua_browser_download(input.destination_root or "")
        raise ValueError(f"Unknown computer_use action: {a}")


def _format_reply(reply: dict) -> str:
    """Compact human-readable rendering of a driver reply."""
    if "elements" in reply:
        elements = reply["elements"]
        total = reply.get("total_elements", len(elements))
        truncated = reply.get("truncated_elements", 0)
        lines = [f"{total} elements" + (f" ({truncated} truncated)" if truncated else "")]
        for el in elements[:20]:
            n = el.get("n", "?")
            role = el.get("role", "")
            name = el.get("name", "")
            lines.append(f"  [{n}] {role}: {name}")
        if len(elements) > 20:
            lines.append(f"  … {len(elements) - 20} more")
        return "\n".join(lines)
    if "apps" in reply:
        return "\n".join(f"- {app}" for app in reply["apps"])
    if "windows" in reply:
        return "\n".join(f"- {w}" for w in reply["windows"])
    # Generic: drop the ok flag, render the rest.
    return ", ".join(f"{k}={v}" for k, v in reply.items() if k != "ok")
