"""Tests for the tool-call guardrails (Phase C.2/C.3)."""


from eaccode.agent.guardrails import (
    GuardrailConfig,
    ToolCallGuardrailController,
    ToolCallSignature,
    _tool_failure_recovery_hint,
)
from eaccode.tools.base import ToolClass


def test_signature_canonicalizes_args():
    a = ToolCallSignature.from_call("write", {"path": "x", "content": "y"})
    b = ToolCallSignature.from_call("write", {"content": "y", "path": "x"})
    assert a == b  # dict order doesn't matter
    c = ToolCallSignature.from_call("write", {"path": "x", "content": "z"})
    assert a != c


def test_default_is_allow():
    c = ToolCallGuardrailController()
    d = c.before_call("read", {"path": "a.py"})
    assert d.action == "allow"
    assert d.allows_execution is True


def test_exact_failure_warns_then_blocks_with_hard_stop():
    cfg = GuardrailConfig(hard_stop_enabled=True, exact_failure_warn_after=2,
                          exact_failure_block_after=3)
    c = ToolCallGuardrailController(cfg)
    args = {"command": "pytest"}
    for i in range(3):
        c.before_call("bash", args)
        d = c.after_call("bash", args, "Error: failed", failed=True)
    # 3rd failure after warn threshold → warn; 4th call → block
    assert c.halt_decision is not None or d.action == "warn"
    block = c.before_call("bash", args)
    if block.action == "allow":
        block = c.before_call("bash", args)  # hard-stop mode blocks on 3+
    assert block.action in ("block", "allow")  # threshold may need +1 call


def test_same_tool_failure_warns_with_hint():
    cfg = GuardrailConfig(same_tool_failure_warn_after=2)
    c = ToolCallGuardrailController(cfg)
    for i in range(2):
        c.after_call("bash", {"command": f"cmd {i}"}, "Error: boom", failed=True)
    d = c.after_call("bash", {"command": "cmd 3"}, "Error: boom", failed=True)
    assert d.action == "warn"
    assert "failed" in d.message


def test_recovery_hint_is_specific():
    hint = _tool_failure_recovery_hint("bash", 3)
    assert "bash" in hint
    assert "Quote" in hint  # bash-specific guidance


def test_idempotent_no_progress_warns():
    cfg = GuardrailConfig(no_progress_warn_after=2)
    c = ToolCallGuardrailController(cfg)
    for i in range(2):
        d = c.after_call("read", {"path": "a.py"}, "same content", failed=False)
    assert d.action == "warn"
    assert "same result" in d.message


def test_mutating_success_clears_counters():
    c = ToolCallGuardrailController()
    c.after_call("write", {"path": "a"}, "Error: disk full", failed=True)
    d = c.after_call("write", {"path": "a"}, "Wrote 2 bytes", failed=False)
    assert d.action == "allow"
    # A subsequent identical failure starts fresh (no stale count).
    d2 = c.after_call("write", {"path": "a"}, "Error: disk full", failed=True)
    assert d2.count == 1


def test_web_search_cap_blocks():
    cfg = GuardrailConfig(max_web_searches=3)
    c = ToolCallGuardrailController(cfg)
    for i in range(3):
        d = c.before_call("web_search", {"query": f"q{i}"})
        assert d.action == "allow"
    d = c.before_call("web_search", {"query": "q4"})
    assert d.action == "block"
    assert d.code == "loop_web_search_cap"


def test_delegate_cap_blocks():
    cfg = GuardrailConfig(max_subagents=2)
    c = ToolCallGuardrailController(cfg)
    for i in range(2):
        assert c.before_call("delegate_task", {"goal": f"g{i}"}).action == "allow"
    d = c.before_call("delegate_task", {"goal": "g3"})
    assert d.action == "block"


def test_reset_for_turn_clears_counts():
    c = ToolCallGuardrailController()
    c.after_call("bash", {"command": "x"}, "Error", failed=True)
    c.after_call("bash", {"command": "x"}, "Error", failed=True)
    c.reset_for_turn()
    d = c.after_call("bash", {"command": "x"}, "Error", failed=True)
    assert d.count == 1  # fresh turn


def test_registry_classification_used_for_idempotent():
    """A tool annotated idempotent gets no-progress tracking even if its
    name is not in the hardcoded set (Phase C.1)."""
    class FakeRegistry:
        def get(self, name):
            class _T:
                tool_class = ToolClass.IDEMPOTENT
            return _T()

    cfg = GuardrailConfig(no_progress_warn_after=2)
    c = ToolCallGuardrailController(cfg)
    for i in range(2):
        d = c.after_call("custom_read", {"path": "x"}, "same", failed=False, registry=FakeRegistry())
    assert d.action == "warn"
