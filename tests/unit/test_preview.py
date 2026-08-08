"""Tests for tool-call preview rendering (Claude-Code style)."""
from eaccode.ui.preview import (
    CHEVRON,
    VerboseLevel,
    build_call_card,
    summarize_shell_command,
)


def test_call_expression_primary_argument():
    card = build_call_card("read", {"path": "src/main.py", "offset": 1})
    assert card.call == 'read(path="src/main.py")'
    card = build_call_card("web_search", {"query": "python async"})
    assert card.call == 'web_search(query="python async")'


def test_call_expression_bash_summarized():
    card = build_call_card("bash", {"command": "cd /tmp && git status && ls"})
    assert card.call == 'bash(command="git status + 1 command")'


def test_call_expression_no_args():
    assert build_call_card("skill_list", {}).call == "skill_list"


def test_call_expression_full_args():
    card = build_call_card(
        "read", {"path": "x.py", "offset": 10}, full_args=True
    )
    assert card.call == 'read(path="x.py", offset=10)'
    card = build_call_card("write", {"path": "x.py", "content": "y" * 200}, full_args=True)
    assert "..." in card.call  # long values truncated


def test_chevron_defined():
    assert CHEVRON == "⎿"


def test_shell_summary_single_command():
    assert summarize_shell_command("git status") == "git status"


def test_shell_summary_chain_collapsed():
    s = summarize_shell_command("cd /tmp && git status && ls -la")
    assert s == "git status + 1 command"


def test_shell_summary_silent_heads_dropped():
    s = summarize_shell_command("export FOO=1 && python test.py")
    assert s == "python test.py"


def test_shell_summary_two_commands():
    s = summarize_shell_command("git add . && git commit -m x")
    assert s == "git add . + 1 command"


def test_verbose_cycle():
    assert VerboseLevel.next("off") == "new"
    assert VerboseLevel.next("new") == "all"
    assert VerboseLevel.next("all") == "verbose"
    assert VerboseLevel.next("verbose") == "off"
    assert VerboseLevel.show_start("off") is False
    assert VerboseLevel.show_start("new") is True
    assert VerboseLevel.show_result("off", is_error=False) is False
    assert VerboseLevel.show_result("off", is_error=True) is True
    assert VerboseLevel.show_result("new", is_error=False) is True  # compact ✓
    assert VerboseLevel.show_full_args("new") is False
    assert VerboseLevel.show_full_args("all") is True
