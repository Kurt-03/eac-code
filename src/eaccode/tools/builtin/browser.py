"""Browser tool (Phase I.7) — full CDP stack via websocket-client.

One tool, action-dispatched (eaccode style, like process): navigate,
snapshot (accessibility tree with @e{n} refs), click/type/press/scroll/
back, evaluate, get_images, console, vision (screenshot → aux vision
model), dialog handling, download dir. The CDP session is cached per
port so the agent's page state survives across calls; ``close`` tears
it down.

Launching is on-demand and best-effort: a system Chrome/Edge/Chromium is
discovered, started headless with a private profile, and targeted via
the DevTools endpoint.
"""

from __future__ import annotations

import threading

from pydantic import BaseModel, Field

from eaccode.tools.base import Tool, ToolClass, ToolContext, ToolResult

_SESSIONS: dict[int, object] = {}
_SESSIONS_LOCK = threading.Lock()


class BrowserInput(BaseModel):
    action: str = Field(
        description=(
            "One of: navigate, snapshot, click, type, press, scroll, back, "
            "evaluate, get_images, console, vision, dialog, handle_dialog, "
            "download_dir, screenshot, close"
        )
    )
    url: str | None = Field(default=None, description="navigate: target URL")
    ref: str | None = Field(default=None, description="click: element ref (@e12)")
    text: str | None = Field(default=None, description="type: text to insert")
    key: str | None = Field(default=None, description="press: key or combo (ctrl+s)")
    direction: str | None = Field(default=None, description="scroll: up/down/left/right")
    amount: int = Field(default=3, description="scroll: wheel ticks")
    expression: str | None = Field(default=None, description="evaluate: JS expression")
    question: str | None = Field(default=None, description="vision: question about the page")
    accept: bool = Field(default=True, description="handle_dialog: accept or dismiss")
    prompt_text: str | None = Field(default=None, description="handle_dialog: prompt answer")
    directory: str | None = Field(default=None, description="download_dir: target folder")
    port: int = Field(default=9222, description="CDP debug port")
    clear_console: bool = Field(default=False, description="console: clear after read")


class BrowserTool(Tool):
    name = "browser"
    tool_class = ToolClass.MUTATING
    description = (
        "Control a headless Chrome/Edge via the DevTools protocol: navigate, "
        "snapshot the accessibility tree, click elements by ref, type, press "
        "keys, scroll, go back, evaluate JS, list images, read console "
        "messages, screenshot for vision analysis, handle dialogs."
    )
    input_model = BrowserInput
    requires_permission = True

    async def run(self, input: BrowserInput, ctx: ToolContext) -> ToolResult:
        try:
            return await self._dispatch(input, ctx)
        except Exception as e:
            return ToolResult(
                content=f"Browser {input.action} failed: {type(e).__name__}: {e}",
                is_error=True,
            )

    # ------------------------------------------------------------------ io

    async def _dispatch(self, input: BrowserInput, ctx: ToolContext) -> ToolResult:
        if input.action == "close":
            self._drop_session(input.port)
            return ToolResult(content="Browser session closed.")
        browser = self._get_browser(input.port, ctx)
        action = input.action

        if action == "navigate":
            if not input.url:
                return ToolResult(content="navigate requires url", is_error=True)
            result = browser.navigate(input.url)
            return ToolResult(content=f"Loaded {result['url']}")

        if action == "snapshot":
            return ToolResult(content=browser.snapshot())

        if action == "click":
            if not input.ref:
                return ToolResult(content="click requires ref (from snapshot)",
                                  is_error=True)
            result = browser.click(input.ref)
            return ToolResult(content=f"Clicked {result['clicked']} at {result['at']}")

        if action == "type":
            if input.text is None:
                return ToolResult(content="type requires text", is_error=True)
            return ToolResult(content=f"Typed {len(input.text)} chars.")

        if action == "press":
            if not input.key:
                return ToolResult(content="press requires key", is_error=True)
            return ToolResult(content=f"Pressed {browser.press(input.key)['pressed']}.")

        if action == "scroll":
            if not input.direction:
                return ToolResult(content="scroll requires direction", is_error=True)
            result = browser.scroll(input.direction, input.amount)
            return ToolResult(content=f"Scrolled {result['scrolled']} x{result['amount']}")

        if action == "back":
            result = browser.back()
            return ToolResult(content=(
                f"Went back to {result['to']}" if result["back"]
                else "No history to go back to."
            ))

        if action == "evaluate":
            if input.expression is None:
                return ToolResult(content="evaluate requires expression",
                                  is_error=True)
            value = browser.evaluate(input.expression)
            return ToolResult(content=str(value))

        if action == "get_images":
            from eaccode.tools.browser import actions

            return ToolResult(content=actions.get_images(browser))

        if action == "console":
            from eaccode.tools.browser import actions

            return ToolResult(content=actions.console_output(
                browser, clear=input.clear_console))

        if action == "vision":
            from eaccode.tools.browser import actions

            return ToolResult(content=actions.vision_ask(
                browser, input.question or "Describe this page."))

        if action == "dialog":
            from eaccode.tools.browser import actions

            return ToolResult(content=actions.dialog_state(browser))

        if action == "handle_dialog":
            from eaccode.tools.browser import actions

            return ToolResult(content=actions.handle_dialog(
                browser, input.accept, input.prompt_text))

        if action == "download_dir":
            from eaccode.tools.browser import actions

            if not input.directory:
                return ToolResult(content="download_dir requires directory",
                                  is_error=True)
            return ToolResult(content=actions.set_download_dir(
                browser, input.directory))

        if action == "screenshot":
            from eaccode.tools.browser import actions

            out = (ctx.workdir / f"eaccode-shot-{input.port}.png").resolve()
            return ToolResult(content=f"Screenshot saved: {actions.screenshot_path(browser, out)}")

        return ToolResult(content=f"Unknown browser action: {action}", is_error=True)

    # ------------------------------------------------------------ sessions

    def _get_browser(self, port: int, ctx: ToolContext) -> object:
        with _SESSIONS_LOCK:
            browser = _SESSIONS.get(port)
            if browser is not None:
                return browser
        from eaccode.tools.browser.session import CdpBrowser, _wait_for_endpoint, launch_browser

        if not _wait_for_endpoint(port, timeout=1.5):
            try:
                self._proc = launch_browser(port=port)
            except FileNotFoundError as e:
                raise RuntimeError(str(e)) from e
            if not _wait_for_endpoint(port, timeout=15):
                raise RuntimeError(
                    f"Browser did not open the debug port {port} in time"
                )
        browser = CdpBrowser.connect(port)
        with _SESSIONS_LOCK:
            _SESSIONS[port] = browser
        return browser

    def _drop_session(self, port: int) -> None:
        with _SESSIONS_LOCK:
            browser = _SESSIONS.pop(port, None)
        if browser is not None:
            browser.session.close()
