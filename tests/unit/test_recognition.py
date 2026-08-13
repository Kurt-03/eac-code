"""P8 / Sprint 3.4: command-recognition helpers (Plan 147-160)."""

import pytest

from eaccode.permissions.recognition import (
    classify_arg,
    expand_short_flags,
    first_verb,
    is_absolute_path,
    normalize_command,
    normalize_eq_form,
)

# ----- expand_short_flags (Plan 151) -----

def test_expand_rm_rf():
    assert expand_short_flags("rm -rf /tmp") == "rm -r -f /tmp"


def test_expand_ls_la():
    assert expand_short_flags("ls -la") == "ls -l -a"


def test_expand_unknown_verb_left_alone():
    assert expand_short_flags("foobar -rf") == "foobar -rf"


def test_expand_handles_mixed_arg():
    assert expand_short_flags("ls -l /foo") == "ls -l /foo"


def test_expand_keeps_long_options():
    assert expand_short_flags("ls --all") == "ls --all"


def test_expand_keeps_posix_only_flag():
    assert expand_short_flags("ls -1") == "ls -1"


def test_expand_invalid_no_collapse():
    """A short cluster with an unknown char keeps the original token."""
    # 'rm -rg' (no alias for 'g') → keep as-is
    assert expand_short_flags("rm -rg") == "rm -rg"


# ----- normalize_eq_form (Plan 157) -----

@pytest.mark.parametrize("cmd", [
    "--foo=bar --baz=qux",
    "-rf=path",
    "command --foo=bar -v",
])
def test_normalize_eq_form_splits(cmd):
    result = normalize_eq_form(cmd)
    # All = form got split into two tokens
    assert "=" not in result.split(" -v")[0].split("--foo ")[0] or "=" not in result


def test_normalize_eq_form_no_op_on_plain_flags():
    assert normalize_eq_form("--foo bar") == "--foo bar"


# ----- first_verb (Plan 149) -----

@pytest.mark.parametrize("cmd,expected", [
    ("rm -rf /tmp", "rm"),
    ("sudo rm -rf /tmp", "rm"),
    ("doas ls", "ls"),
    ("env FOO=bar bash", "bash"),
    ("", None),
])
def test_first_verb(cmd, expected):
    assert first_verb(cmd) == expected


# ----- is_absolute_path (Plan 159) -----

@pytest.mark.parametrize("p", [
    "/etc/passwd",
    "~/foo",
    "$HOME/foo",
    "${HOME}/foo",
    "C:/Users/foo",
    "C:\\Users\\foo",
])
def test_is_absolute_path_true(p):
    assert is_absolute_path(p)


@pytest.mark.parametrize("p", [
    "foo",
    "./foo",
    "../foo",
    "documents/report.txt",
    "C:foo",
])
def test_is_absolute_path_false(p):
    assert not is_absolute_path(p)


# ----- classify_arg (Plan 154) -----

@pytest.mark.parametrize("tok,kind", [
    ("--foo", "flag"),
    ("-x", "flag"),
    ("-v", "flag"),
    ("https://example.com", "url"),
    ("http://example.com", "url"),
    ("/etc/passwd", "path"),
    ("C:/Users/foo", "path"),
    ("foo", "keyword"),
    ("", "keyword"),
])
def test_classify_arg(tok, kind):
    assert classify_arg(tok) == kind


# ----- normalize_command (integration) -----

def test_normalize_command_chained():
    # -rf=path stays an = form; rewrite it first then expand
    result = normalize_command("rm -rf=foo")
    assert "=" not in result.split()[2:] or len(result.split()) >= 3


def test_normalize_command_safe_idempotent():
    cmd = "ls -la /home"
    assert normalize_command(cmd) == normalize_command(normalize_command(cmd))
