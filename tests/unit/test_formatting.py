"""Tests for formatting utilities (H.5/H.8)."""

from eaccode.utils.formatting import markdown_table, sizefmt, timefmt


def test_markdown_table_basic():
    table = markdown_table(["name", "count"], [["a", "1"], ["b", "22"]])
    lines = table.splitlines()
    assert lines[0].startswith("| name")
    assert lines[1].startswith("| ----")
    assert "| b" in lines[3]
    assert "22" in lines[3]


def test_markdown_table_escapes_pipes():
    table = markdown_table(["a"], [["x|y"]])
    assert "x\\|y" in table


def test_markdown_table_short_rows():
    table = markdown_table(["a", "b"], [["only-a"]])
    assert table.splitlines()[2].endswith("|")
    assert "| only-a |   |" in table  # missing cells are padded empty


def test_markdown_table_empty():
    assert markdown_table([], []) == ""


def test_sizefmt():
    assert sizefmt(0) == "0 B"
    assert sizefmt(512) == "512 B"
    assert sizefmt(2048) == "2.0 KB"
    assert sizefmt(5 * 1024 * 1024) == "5.0 MB"
    assert sizefmt(3 * 1024 * 1024 * 1024) == "3.0 GB"


def test_timefmt():
    assert timefmt(0) == "0s"
    assert timefmt(45) == "45s"
    assert timefmt(192) == "3m 12s"
    assert timefmt(3900) == "1h 05m"
    assert timefmt(-5) == "0s"
