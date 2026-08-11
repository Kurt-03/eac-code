"""Tests for the permission prompt layer (Phase B.1) and diff preview (B.2)."""

import asyncio

import pytest

from eaccode.permissions.prompts import (
    PermissionChoice,
    build_permission_question,
    prompt_for_permission,
    prompt_for_permission_async,
)
from eaccode.permissions.rules import Action, Rule
from eaccode.ui.permission_modal import (
    PermissionModal,
    build_unified_diff,
    diff_for_write,
)


class TestPermissionPrompt:
    def test_build_question_bash(self):
        q = build_permission_question("bash", {"command": "rm -rf /tmp/x"})
        assert "Run command?" in q
        assert "rm -rf /tmp/x" in q

    def test_build_question_write(self):
        q = build_permission_question("write", {"path": "a.py", "content": "x" * 10})
        assert "Modify file?" in q
        assert "a.py" in q

    def test_allow_once_returns_true(self):
        result = prompt_for_permission(
            "bash", {"command": "ls"}, ask_callback=lambda q: PermissionChoice.ALLOW_ONCE
        )
        assert result is True

    def test_deny_returns_false(self):
        result = prompt_for_permission(
            "bash", {"command": "ls"}, ask_callback=lambda q: PermissionChoice.DENY
        )
        assert result is False

    def test_always_allow_records_session_rule(self):
        rules: list[Rule] = []
        result = prompt_for_permission(
            "bash", {"command": "pytest tests"},
            session_rules=rules,
            ask_callback=lambda q: PermissionChoice.ALLOW_ALWAYS,
        )
        assert result is True
        assert len(rules) == 1
        assert rules[0].tool == "bash"
        assert rules[0].action == Action.ALLOW
        assert "pytest" in rules[0].pattern

    def test_headless_denies_without_callback(self, monkeypatch):
        monkeypatch.setattr("eaccode.permissions.prompts.sys.stdin.isatty", lambda: False)
        result = prompt_for_permission("bash", {"command": "ls"})
        assert result is False

    @pytest.mark.asyncio
    async def test_async_allow_once(self):
        async def ask(q):
            return PermissionChoice.ALLOW_ONCE

        result = await prompt_for_permission_async(
            "bash", {"command": "ls"}, ask_async=ask
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_async_timeout_denies(self):
        async def ask(q):
            await asyncio.sleep(5)  # longer than the timeout

            return PermissionChoice.ALLOW_ONCE

        result = await prompt_for_permission_async(
            "bash", {"command": "ls"}, ask_async=ask, timeout=0.1
        )
        assert result is False  # fail closed

    @pytest.mark.asyncio
    async def test_pause_choice_pauses_session(self):
        """P0.8: the P level sets the pause flag and denies the call."""
        from eaccode.permissions.session import PauseFlag

        flag = PauseFlag()

        async def ask(q):
            return PermissionChoice.PAUSE

        result = await prompt_for_permission_async(
            "bash", {"command": "ls"}, ask_async=ask, pause_flag=flag
        )
        assert result is False
        assert flag.paused is True

    def test_sync_pause_choice_pauses_session(self):
        from eaccode.permissions.session import PauseFlag

        flag = PauseFlag()
        result = prompt_for_permission(
            "bash", {"command": "ls"},
            ask_callback=lambda q: PermissionChoice.PAUSE,
            pause_flag=flag,
        )
        assert result is False
        assert flag.paused is True

    def test_pause_without_flag_denies_but_does_not_crash(self):
        result = prompt_for_permission(
            "bash", {"command": "ls"},
            ask_callback=lambda q: PermissionChoice.PAUSE,
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_async_always_allow_records_rule(self):
        rules: list[Rule] = []

        async def ask(q):
            return PermissionChoice.ALLOW_ALWAYS

        result = await prompt_for_permission_async(
            "write", {"path": "f.txt", "content": "x"},
            session_rules=rules, ask_async=ask,
        )
        assert result is True
        assert len(rules) == 1
        assert rules[0].tool == "write"


class TestDiffPreview:
    def test_unified_diff_shows_added_removed(self):
        diff = build_unified_diff("old line\n", "new line\n", "f.py")
        assert "-old line" in diff
        assert "+new line" in diff
        assert "a/f.py" in diff and "b/f.py" in diff

    def test_diff_for_new_file_all_additions(self, tmp_path):
        path = tmp_path / "new.txt"
        diff = diff_for_write(path, "hello\nworld\n")
        assert diff is not None
        assert "+hello" in diff
        assert "+world" in diff

    def test_diff_for_existing_file(self, tmp_path):
        path = tmp_path / "exists.txt"
        path.write_text("before\n", encoding="utf-8")
        diff = diff_for_write(path, "after\n")
        assert diff is not None
        assert "-before" in diff
        assert "+after" in diff

    def test_diff_capped_at_max_lines(self, tmp_path):
        path = tmp_path / "big.txt"
        content = "\n".join(f"line {i}" for i in range(100))
        diff = diff_for_write(path, content, max_lines=10)
        assert diff is not None
        assert "more lines" in diff

    def test_edit_diff_shows_correct_direction(self, tmp_path):
        """P0.6 Bug 2: the edit preview must render current→edited, not the
        inverted direction (old/new were swapped before the fix)."""
        path = tmp_path / "f.py"
        path.write_text("old line\nunchanged\n", encoding="utf-8")
        modal = PermissionModal(
            "edit",
            {"path": str(path), "old_string": "old line",
             "new_string": "new line"},
            question="Allow edit?",
        )
        diff = modal._diff_preview()
        assert diff is not None
        assert "-old line" in diff
        assert "+new line" in diff
        assert "unchanged" in diff
