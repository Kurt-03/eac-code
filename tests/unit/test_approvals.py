"""Tests for the pending approval registry (B.4)."""

import asyncio

import pytest

from eaccode.permissions.approvals import ApprovalRegistry
from eaccode.permissions.prompts import PermissionChoice


@pytest.mark.asyncio
async def test_register_assigns_incrementing_ids():
    registry = ApprovalRegistry()
    f1 = asyncio.get_running_loop().create_future()
    f2 = asyncio.get_running_loop().create_future()
    assert registry.register("bash", {"command": "ls"}, "run ls?", f1) == 1
    assert registry.register("write", {"path": "x"}, "write x?", f2) == 2
    assert len(registry) == 2


@pytest.mark.asyncio
async def test_resolve_approves_pending_future():
    registry = ApprovalRegistry()
    future = asyncio.get_running_loop().create_future()
    registry.register("bash", {"command": "ls"}, "run?", future)
    assert registry.resolve(1, PermissionChoice.ALLOW_ONCE) is True
    assert await future == PermissionChoice.ALLOW_ONCE
    assert len(registry) == 0  # no longer pending


@pytest.mark.asyncio
async def test_resolve_deny():
    registry = ApprovalRegistry()
    future = asyncio.get_running_loop().create_future()
    registry.register("bash", {"command": "x"}, "run?", future)
    assert registry.resolve(1, PermissionChoice.DENY) is True
    assert await future == PermissionChoice.DENY


@pytest.mark.asyncio
async def test_double_resolve_is_safe():
    registry = ApprovalRegistry()
    future = asyncio.get_running_loop().create_future()
    registry.register("bash", {"command": "x"}, "run?", future)
    assert registry.resolve(1, PermissionChoice.DENY) is True
    # Second resolve (e.g. the modal answering late) must not raise.
    assert registry.resolve(1, PermissionChoice.ALLOW_ONCE) is False
    assert await future == PermissionChoice.DENY


@pytest.mark.asyncio
async def test_unknown_id_resolve_fails():
    registry = ApprovalRegistry()
    assert registry.resolve(99, PermissionChoice.DENY) is False


@pytest.mark.asyncio
async def test_modal_resolution_marks_done():
    registry = ApprovalRegistry()
    future = asyncio.get_running_loop().create_future()
    registry.register("bash", {"command": "x"}, "run?", future)
    future.set_result(PermissionChoice.DENY)
    await asyncio.sleep(0)  # let the done-callback run
    assert len(registry) == 0
    assert registry.resolve(1, PermissionChoice.ALLOW_ONCE) is False


@pytest.mark.asyncio
async def test_on_approve_callback_runs_on_allow():
    registry = ApprovalRegistry()
    future = asyncio.get_running_loop().create_future()
    applied: list[str] = []
    registry.register(
        "memory_remember", {"fact": "x"}, "save x?",
        future, on_approve=lambda: applied.append("x"),
    )
    assert registry.resolve(1, PermissionChoice.ALLOW_ONCE) is True
    assert applied == ["x"]


@pytest.mark.asyncio
async def test_on_approve_not_called_on_deny():
    registry = ApprovalRegistry()
    future = asyncio.get_running_loop().create_future()
    applied: list[str] = []
    registry.register(
        "memory_remember", {"fact": "x"}, "save x?",
        future, on_approve=lambda: applied.append("x"),
    )
    assert registry.resolve(1, PermissionChoice.DENY) is True
    assert applied == []
