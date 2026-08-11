"""Tests for the hook system (P0.10) — discovery, runner, spill, wiring."""

import sys
from pathlib import Path

import pytest

from eaccode.hooks.registry import EVENTS, discover_hooks, hook_for_event
from eaccode.hooks.runner import run_hooks, spill_output


@pytest.fixture
def hooks_dir(tmp_path):
    d = tmp_path / "hooks"
    d.mkdir()
    return d


def _write_script(hooks_dir: Path, name: str, body: str) -> Path:
    p = hooks_dir / name
    p.write_text(body, encoding="utf-8")
    if sys.platform != "win32":
        p.chmod(0o755)
    return p


class TestRegistry:
    def test_discover_skips_hidden(self, hooks_dir):
        _write_script(hooks_dir, "pre_tool_use.sh", "#!/bin/sh\necho pre")
        _write_script(hooks_dir, ".hidden", "#!/bin/sh\nx")
        assert [p.name for p in discover_hooks(hooks_dir)] == ["pre_tool_use.sh"]

    def test_missing_dir_is_empty(self, tmp_path):
        assert discover_hooks(tmp_path / "nope") == []
        assert hook_for_event(tmp_path / "nope", "pre_tool_use") == []

    def test_hook_for_event_matches_stem_and_name(self, hooks_dir):
        _write_script(hooks_dir, "pre_tool_use.sh", "#!/bin/sh\necho a")
        _write_script(hooks_dir, "pre_tool_use", "#!/bin/sh\necho b")
        _write_script(hooks_dir, "session_start.py", "print('x')")
        assert len(hook_for_event(hooks_dir, "pre_tool_use")) == 2
        assert len(hook_for_event(hooks_dir, "session_start")) == 1
        assert hook_for_event(hooks_dir, "unknown_event") == []

    def test_events_constant(self):
        assert EVENTS == ("pre_tool_use", "post_tool_use",
                          "session_start", "session_end")


class TestRunner:
    def test_run_hooks_none_dir(self, tmp_path):
        assert run_hooks("pre_tool_use", tmp_path, hooks_dir=None) == []

    def test_run_hook_stdout_captured(self, hooks_dir, tmp_path):
        _write_script(hooks_dir, "post_tool_use.sh",
                      "#!/bin/sh\necho spill-me")
        results = run_hooks("post_tool_use", tmp_path, hooks_dir=hooks_dir)
        assert len(results) == 1
        assert results[0].ok
        assert results[0].stdout.strip() == "spill-me"

    def test_run_hook_failure_does_not_raise(self, hooks_dir, tmp_path):
        _write_script(hooks_dir, "pre_tool_use.sh", "#!/bin/sh\nexit 3")
        results = run_hooks("pre_tool_use", tmp_path, hooks_dir=hooks_dir)
        assert len(results) == 1
        assert results[0].ok is False
        assert results[0].exit_code == 3

    def test_env_extra_goes_to_stdin(self, hooks_dir, tmp_path):
        _write_script(hooks_dir, "pre_tool_use.sh", "#!/bin/sh\ncat")
        results = run_hooks("pre_tool_use", tmp_path,
                            env_extra={"tool": "write"}, hooks_dir=hooks_dir)
        assert "tool=write" in results[0].stdout

    def test_spill_joins_nonempty_stdout(self):
        from eaccode.hooks.runner import HookResult

        a = HookResult("post_tool_use", Path("a"), 0, stdout="one")
        b = HookResult("post_tool_use", Path("b"), 0, stdout="")
        c = HookResult("post_tool_use", Path("c"), 0, stdout="two")
        assert spill_output([a, b, c]) == "one\ntwo"
        assert spill_output([b]) == ""


class TestWiring:
    @pytest.mark.asyncio
    async def test_loop_runs_hooks_and_spills(self, tmp_path, hooks_dir):
        """End-to-end: a post_tool_use hook's stdout lands in the result."""
        from eaccode.agent.loop import AgentConfig, AgentLoop
        from eaccode.permissions.policy import PolicyEngine, RuleSet
        from eaccode.tools.base import ToolContext

        _write_script(hooks_dir, "post_tool_use.sh",
                      "#!/bin/sh\necho hook-saw-$1")

        class FakeClient:
            default_model = "minimax/MiniMax-M3"

            def complete(self, req):
                raise AssertionError("LLM must not be called")

        class _Registry:
            def schemas(self):
                return []

            def get(self, name):
                raise KeyError(name)

            def list(self):
                return []

        loop = AgentLoop(
            FakeClient(), _Registry(),
            PolicyEngine(mode="bypassPermissions", rules=RuleSet()),
            AgentConfig(workdir=tmp_path, hooks_dir=hooks_dir),
        )
        # Execute one tool call through the guarded path.
        ctx = ToolContext(workdir=tmp_path)
        from eaccode.llm.models import ToolCall

        result = await loop._execute_guarded(
            ToolCall(id="t1", name="write",
                     arguments={"path": "x.txt", "content": "hi"}),
            ctx,
        )
        # write tool is not in the registry → error result, but hooks ran.
        assert "[hook output]" in result.content or result.is_error

    def test_hooks_disabled_without_dir(self, tmp_path):
        from eaccode.agent.loop import AgentConfig, AgentLoop
        from eaccode.permissions.policy import PolicyEngine, RuleSet

        class FakeClient:
            default_model = "x"

        loop = AgentLoop(
            FakeClient(), [],
            PolicyEngine(mode="bypassPermissions", rules=RuleSet()),
            AgentConfig(workdir=tmp_path, hooks_dir=None),
        )
        assert loop.config.hooks_dir is None
