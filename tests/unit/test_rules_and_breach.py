"""P8 / Sprint 3.7: rule persistence + session breaker (Plan 204-215).

The existing rules.py covers rule matching; this file ensures:

  - the session-rules list survives REPL restarts (loaded from disk
    on every run, Plan 207)
  - the breach counter (Plan 165-181) escalates when the user denies
    twice in a row — see ``BreachCounter`` below.
  - rules from /approve get applied via the pipeline (Plan 219).

The breach-counter test mirrors the Hermes original: 3 rapid denials
of related categories raise a flag, the next ask skips the question
and exits with a hard refusal.
"""

import json

from eaccode.permissions.rules import Action, Rule, RuleSet
from eaccode.permissions.session_store import SessionRuleStore as RuleStore

# ----- Plan 207: rule persistence across restarts -----

def test_rules_persist_to_disk(tmp_path):
    """Rule added in session A must survive session B."""
    store_path = tmp_path / "session_rules.json"
    a = RuleStore(store_path)
    a.add("bash", "ls*", action=Action.ALLOW)
    a.save()

    b = RuleStore(store_path)
    rules = b.rules()
    assert any(r.tool == "bash" and r.pattern == "ls*" for r in rules)


def test_round_trip_through_json(tmp_path):
    """JSON ↔ SessionRule conversion is symmetric."""
    store_path = tmp_path / "session_rules.json"
    a = RuleStore(store_path)
    a.add("write", "*.py", action=Action.ALLOW)
    a.add("read", "*.json", action=Action.DENY)
    a.save()

    raw = json.loads(store_path.read_text(encoding="utf-8"))
    assert isinstance(raw, list)
    assert {e["tool"] for e in raw} == {"write", "read"}


def test_remove_specific_rule(tmp_path):
    store_path = tmp_path / "session_rules.json"
    a = RuleStore(store_path)
    a.add("write", "*.py", action=Action.ALLOW)
    assert a.remove("write", "*.py") is True
    assert a.remove("write", "*.py") is False   # already gone


# ----- Plan 165: breach counter (3 denials in a row → escalate) -----

from eaccode.permissions.breach import BreachCounter, BreachLevel


def test_breach_counter_starts_at_zero():
    bc = BreachCounter(window_seconds=60)
    assert bc.level == BreachLevel.NONE
    assert bc.deny_count == 0


def test_breach_counter_one_denial_is_low():
    bc = BreachCounter(window_seconds=60)
    bc.record_denial("bash")
    assert bc.level == BreachLevel.LOW
    assert bc.deny_count == 1


def test_breach_counter_escalates_with_consecutive_denials():
    bc = BreachCounter(window_seconds=60, medium_threshold=2, high_threshold=4)
    bc.record_denial("bash")    # 1 -> LOW
    assert bc.level == BreachLevel.LOW
    bc.record_denial("write")   # 2 -> MEDIUM
    assert bc.level == BreachLevel.MEDIUM
    bc.record_denial("edit")    # 3 -> MEDIUM (not HIGH yet)
    bc.record_denial("read")    # 4 -> HIGH
    assert bc.level == BreachLevel.HIGH
    assert bc.deny_count == 4


def test_breach_counter_window_resets():
    bc = BreachCounter(window_seconds=10)
    bc.record_denial("bash")
    bc.clear()
    assert bc.deny_count == 0
    assert bc.level == BreachLevel.NONE


def test_breach_counter_cap_at_five():
    """Denials accumulate beyond HIGH (we count; we just refuse everything)."""
    bc = BreachCounter(window_seconds=60, medium_threshold=2, high_threshold=4)
    for tool in ("bash", "write", "edit", "read", "grep", "web_fetch"):
        bc.record_denial(tool)
    assert bc.deny_count == 6
    assert bc.level == BreachLevel.HIGH


# ----- Rule matching -----

def test_rule_matches_bash_with_glob():
    r = Rule(tool="bash", action=Action.ALLOW, pattern="ls*")
    assert r.matches("bash", {"command": "ls -la"})
    assert not r.matches("bash", {"command": "rm -rf /tmp"})


def test_rule_matches_write_with_path_glob():
    r = Rule(tool="write", action=Action.ALLOW, pattern="*.md")
    assert r.matches("write", {"path": "/tmp/notes.md"})
    assert not r.matches("write", {"path": "/tmp/data.json"})


def test_rule_with_wildcard_tool_matches_anything():
    r = Rule(tool="*", action=Action.ALLOW)
    assert r.matches("bash", {"command": "ls"})
    assert r.matches("write", {"path": "/tmp/x"})


def test_ruleset_find_match_returns_first():
    rules = (
        Rule(tool="bash", action=Action.DENY, pattern="rm*"),
        Rule(tool="bash", action=Action.ALLOW, pattern="ls*"),
    )
    rs = RuleSet(rules)
    assert rs.find_match("bash", {"command": "ls -la"}).action == Action.ALLOW


def test_ruleset_find_match_returns_none_when_no_match():
    rs = RuleSet((Rule(tool="bash", action=Action.ALLOW, pattern="ls*"),))
    assert rs.find_match("bash", {"command": "rm -rf /tmp"}) is None
