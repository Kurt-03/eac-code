"""Tests for file-state coordination (P0.5) — locks, stale detection,
subagent write attribution."""

import time

import pytest

from eaccode.tools.base import ToolContext
from eaccode.tools.file_state import (
    check_stale,
    last_write_ts,
    last_writer,
    lock_path,
    reset,
    touch,
    writes_by,
    writes_since,
)


@pytest.fixture(autouse=True)
def _clean():
    reset()
    yield
    reset()


def test_lock_is_reentrant_per_path(tmp_path):
    p = tmp_path / "a.txt"
    with lock_path(p), lock_path(p):  # re-entrant, same thread
        touch(p, "main")
    assert last_writer(p) == "main"


def test_touch_records_writer_and_timestamp(tmp_path):
    p = tmp_path / "b.txt"
    assert last_write_ts(p) is None
    touch(p, "main")
    assert last_write_ts(p) is not None
    assert last_writer(p) == "main"


def test_check_stale_detects_other_writer(tmp_path):
    p = tmp_path / "c.txt"
    touch(p, "main")
    ts = last_write_ts(p)
    assert ts is not None
    # Same writer re-touching is not stale for itself.
    touch(p, "main")
    assert check_stale("main", p, ts) is False
    # Another writer touching after ts IS stale for main.
    touch(p, "sub:abc")
    assert check_stale("main", p, ts) is True
    # And stale for the subagent's own view of "main's write".
    assert check_stale("sub:abc", p, ts) is False  # it was the writer


def test_writes_since(tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    touch(a, "main")
    ts = time.monotonic()
    time.sleep(0.001)
    touch(b, "sub:1")
    changed = writes_since(ts, [a, b])
    assert changed == [str(b)]


def test_writes_by_attributes_subagent(tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    touch(a, "main")
    ts = time.monotonic()
    time.sleep(0.001)
    touch(b, "sub:deadbeef")
    assert writes_by(ts, {"sub:deadbeef"}) == [(str(b), "sub:deadbeef")]
    assert writes_by(ts, {"sub:other"}) == []


class TestToolIntegration:
    @pytest.mark.asyncio
    async def test_write_tool_records_write(self, tmp_path):
        from eaccode.tools.builtin.write import WriteInput, WriteTool

        ctx = ToolContext(workdir=tmp_path)
        result = await WriteTool().run(
            WriteInput(path="out.txt", content="hello"), ctx
        )
        assert result.is_error is False
        assert last_writer(tmp_path / "out.txt") == "main"

    @pytest.mark.asyncio
    async def test_edit_tool_records_writer_id(self, tmp_path):
        from eaccode.tools.builtin.edit import EditInput, EditTool

        path = tmp_path / "f.py"
        path.write_text("old", encoding="utf-8")
        ctx = ToolContext(workdir=tmp_path, writer_id="sub:1234")
        result = await EditTool().run(
            EditInput(path="f.py", old_string="old", new_string="new"), ctx
        )
        assert result.is_error is False
        assert last_writer(path) == "sub:1234"
