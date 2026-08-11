"""Tests for the CLI output helpers (P0.18)."""

import io
import sys

from eaccode.cli._output import (
    print_error,
    print_info,
    print_success,
    print_table,
    print_warn,
)


def _capture(monkeypatch):
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    return out, err


def test_info_plain_stdout(monkeypatch):
    out, _err = _capture(monkeypatch)
    print_info("hello")
    assert out.getvalue() == "hello\n"


def test_error_goes_to_stderr(monkeypatch):
    _out, err = _capture(monkeypatch)
    print_error("boom")
    assert err.getvalue() == "boom\n"


def test_success_and_warn_stdout_no_color_in_tests(monkeypatch):
    out, _err = _capture(monkeypatch)
    print_success("ok")
    print_warn("careful")
    text = out.getvalue()
    assert "ok\n" in text
    assert "careful\n" in text
    assert "\x1b[" not in text  # StringIO is not a TTY → no ANSI


def test_table_aligned(monkeypatch):
    out, _err = _capture(monkeypatch)
    print_table([("a", "long"), ("bb", "x")], headers=("name", "val"))
    text = out.getvalue()
    assert "name" in text and "val" in text
    assert "bb" in text


def test_empty_table_prints_nothing(monkeypatch):
    out, _err = _capture(monkeypatch)
    print_table([])
    assert out.getvalue() == ""
