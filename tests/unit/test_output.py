"""Tests for the CLI output helpers (P0.18)."""

from click.testing import CliRunner

from eaccode.cli._output import (
    print_error,
    print_info,
    print_success,
    print_table,
    print_warn,
)


def test_info_plain_stdout():
    runner = CliRunner()
    with runner.isolation() as (out, _err):
        print_info("hello")
        assert out.getvalue() == "hello\n"


def test_error_goes_to_stderr():
    runner = CliRunner()
    with runner.isolation() as (_out, err):
        print_error("boom")
        assert err.getvalue() == "boom\n"


def test_success_and_warn_stdout_no_color_in_tests():
    runner = CliRunner()
    with runner.isolation() as (out, _err):
        print_success("ok")
        print_warn("careful")
        text = out.getvalue()
        assert "ok\n" in text
        assert "careful\n" in text
        assert "\x1b[" not in text  # no ANSI in non-TTY capture


def test_table_aligned():
    runner = CliRunner()
    with runner.isolation() as (out, _err):
        print_table([("a", "long"), ("bb", "x")], headers=("name", "val"))
        text = out.getvalue()
        assert "name" in text and "val" in text
        assert "bb" in text


def test_empty_table_prints_nothing():
    runner = CliRunner()
    with runner.isolation() as (out, _err):
        print_table([])
        assert out.getvalue() == ""
