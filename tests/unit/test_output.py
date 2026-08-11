"""Tests for the CLI output helpers (P0.18)."""

from click.testing import CliRunner

from eaccode.cli._output import (
    print_error,
    print_info,
    print_success,
    print_table,
    print_warn,
)


def _isolation(runner):
    """(out, err) streams from CliRunner.isolation (click-version agnostic)."""
    with runner.isolation() as streams:
        yield streams[0], streams[1]


def test_info_plain_stdout():
    runner = CliRunner()
    out, _err = next(_isolation(runner))
    print_info("hello")
    assert out.getvalue() == "hello\n"


def test_error_goes_to_stderr():
    runner = CliRunner()
    _out, err = next(_isolation(runner))
    print_error("boom")
    assert err.getvalue() == "boom\n"


def test_success_and_warn_stdout_no_color_in_tests():
    runner = CliRunner()
    out, _err = next(_isolation(runner))
    print_success("ok")
    print_warn("careful")
    text = out.getvalue()
    assert "ok\n" in text
    assert "careful\n" in text
    assert "\x1b[" not in text  # no ANSI in non-TTY capture


def test_table_aligned():
    runner = CliRunner()
    out, _err = next(_isolation(runner))
    print_table([("a", "long"), ("bb", "x")], headers=("name", "val"))
    text = out.getvalue()
    assert "name" in text and "val" in text
    assert "bb" in text


def test_empty_table_prints_nothing():
    runner = CliRunner()
    out, _err = next(_isolation(runner))
    print_table([])
    assert out.getvalue() == ""
