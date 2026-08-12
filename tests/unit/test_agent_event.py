"""P7 (v0.7.2): AgentEvent schema and runner plumbing."""

from eaccode.agent.runner import AgentEvent, resolve_permission


def test_agent_event_text_default_payload():
    ev = AgentEvent(kind="text")
    assert ev.payload == {}


def test_agent_event_text_with_delta():
    ev = AgentEvent(kind="text", payload={"delta": "hi"})
    assert ev.payload["delta"] == "hi"


def test_agent_event_permission_carries_id():
    ev = AgentEvent(kind="permission", payload={"id": 7, "tool": "bash"})
    assert ev.payload["id"] == 7


def test_resolve_permission_no_bus_crash():
    """resolve_permission must be callable; it just puts on the queue."""
    import queue
    bus = type("FakeBus", (), {"resolves": queue.Queue()})()
    from eaccode.permissions.prompts import PermissionChoice

    # No crash when called — it goes onto the queue.
    resolve_permission(bus, 1, PermissionChoice.ALLOW_ONCE)
    assert bus.resolves.get_nowait() == (1, PermissionChoice.ALLOW_ONCE)
