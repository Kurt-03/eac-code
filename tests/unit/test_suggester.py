"""Tests for the SlashCommandSuggester (Phase F.2/F.4/F.5)."""

import asyncio
from pathlib import Path

from eaccode.ui.suggester import SlashCommandSuggester


def _s(suggester, value):
    """Call the async get_suggestion synchronously."""
    return asyncio.run(suggester.get_suggestion(value))


def test_slash_prefix_returns_matching_command():
    s = SlashCommandSuggester()
    out = _s(s, "/m")
    assert out is not None
    assert out.startswith("/") and out.rstrip() != "/m"


def test_slash_exact_command_gets_trailing_space():
    s = SlashCommandSuggester()
    out = _s(s, "/he")
    assert out == "/help "  # typing "/he" completes to "/help "


def test_picker_commands_get_no_trailing_space():
    s = SlashCommandSuggester()
    out = _s(s, "/mo")
    # /mode and /model are pickers — completion must NOT end with a space
    # so Enter executes the picker instead of filling an argument.
    assert out is not None
    assert not out.endswith(" ")


def test_subcommand_completion():
    s = SlashCommandSuggester()
    out = _s(s, "/mode ac")
    assert out == "/mode acceptEdits"
    out2 = _s(s, "/diff s")
    assert out2 == "/diff staged"


def test_non_slash_plain_text_returns_none():
    s = SlashCommandSuggester()
    assert _s(s, "hello world") is None
    assert _s(s, "") is None


def test_unknown_slash_returns_none():
    s = SlashCommandSuggester()
    assert _s(s, "/zzz") is None


def test_alias_completion():
    s = SlashCommandSuggester()
    out = _s(s, "/qu")
    assert out == "/quit "


def test_at_static_completions():
    s = SlashCommandSuggester()
    assert _s(s, "@di") == "@diff"
    assert _s(s, "@st") == "@staged"
    assert _s(s, "@fi") == "@file:"
    assert _s(s, "@fo") == "@folder:"
    assert _s(s, "@u") == "@url:"


def test_at_file_prefix_with_path():
    s = SlashCommandSuggester(cwd=Path("."))
    out = _s(s, "@file:src/ea")
    assert out is not None
    assert out.startswith("@file:src/eaccode/")


def test_at_completions_ignore_urls():
    s = SlashCommandSuggester()
    # "https://" contains "/" but must NOT be treated as a local path
    assert _s(s, "https://example.com") is None


def test_path_completion(tmp_path):
    (tmp_path / "main.py").touch()
    (tmp_path / "subdir").mkdir()
    s = SlashCommandSuggester(cwd=tmp_path)
    rel = str(tmp_path)
    out = _s(s, f"{rel}/ma")
    assert out is not None and out.endswith("main.py")
    out_dir = _s(s, f"{rel}/su")
    assert out_dir is not None and out_dir.endswith("subdir/")


def test_path_completion_relative_dot():
    s = SlashCommandSuggester()
    out = _s(s, "./src/ea")
    assert out is not None
    assert out.startswith("./src/eaccode/")


def test_path_completion_home():
    s = SlashCommandSuggester()
    out = _s(s, "~")
    assert out is None or out.startswith("~/")
