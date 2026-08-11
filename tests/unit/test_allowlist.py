"""Tests for the permanent allowlist (P0.9/P0.20)."""


from eaccode.config.settings import PermissionMode
from eaccode.permissions.allowlist import (
    AllowlistStore,
    suggest_pattern,
)
from eaccode.permissions.policy import PolicyEngine
from eaccode.permissions.rules import Action, Rule, RuleSet


class TestStore:
    def test_empty_store(self, tmp_path):
        store = AllowlistStore(tmp_path / "allowlist.json")
        assert store.entries() == []

    def test_add_persists_and_roundtrips(self, tmp_path):
        path = tmp_path / "allowlist.json"
        store = AllowlistStore(path)
        store.add("bash", "pytest *", scope="always")
        store.add("write", "*", scope="always")

        reloaded = AllowlistStore(path)
        assert len(reloaded.entries()) == 2
        assert reloaded.check("bash", {"command": "pytest -q"}) is not None
        assert reloaded.check("bash", {"command": "rm -rf /"}) is None

    def test_session_entries_not_persisted(self, tmp_path):
        path = tmp_path / "allowlist.json"
        store = AllowlistStore(path)
        store.add("edit", "*", scope="session")
        assert len(store.entries()) == 1
        reloaded = AllowlistStore(path)
        assert reloaded.entries() == []  # session scope vanished

    def test_matching_respects_pattern(self, tmp_path):
        store = AllowlistStore(tmp_path / "a.json")
        store.add("bash", "git *")
        assert store.check("bash", {"command": "git status"}) is not None
        assert store.check("bash", {"command": "docker ps"}) is None
        assert store.check("write", {"path": "x"}) is None  # wrong tool

    def test_tool_only_entry_matches_all_calls(self, tmp_path):
        store = AllowlistStore(tmp_path / "a.json")
        store.add("read")
        assert store.check("read", {"path": "/etc/passwd"}) is not None

    def test_remove(self, tmp_path):
        path = tmp_path / "allowlist.json"
        store = AllowlistStore(path)
        store.add("bash", "pytest *")
        assert store.remove("bash", "pytest *") is True
        assert store.remove("bash", "pytest *") is False
        assert AllowlistStore(path).entries() == []

    def test_corrupt_file_reads_empty(self, tmp_path):
        path = tmp_path / "allowlist.json"
        path.write_text("{not json", encoding="utf-8")
        assert AllowlistStore(path).entries() == []

    def test_import_from_history_session_scope(self, tmp_path):
        store = AllowlistStore(tmp_path / "a.json")
        added = store.import_from_history(
            [("bash", "pytest *"), ("bash", "pytest *"), ("edit", "*")]
        )
        assert added == 2  # duplicates collapsed
        assert len(store.entries()) == 2
        assert AllowlistStore(tmp_path / "a.json").entries() == []  # not saved

    def test_suggest_pattern(self):
        assert suggest_pattern("bash", {"command": "pytest -q"}) == "pytest *"
        assert suggest_pattern("write", {"path": "x.py"}) == "*"

    def test_suggest_candidate_threshold(self, tmp_path):
        store = AllowlistStore(tmp_path / "a.json")
        args = {"command": "pytest -q"}
        assert store.suggest_candidate("bash", args, approval_count=2) is None
        cand = store.suggest_candidate("bash", args, approval_count=3)
        assert cand == "pytest *"
        # Already allowlisted → no suggestion.
        store.add("bash", "pytest *")
        assert store.suggest_candidate("bash", args, approval_count=5) is None


class TestPolicyIntegration:
    def test_allowlist_beats_mode_default(self, tmp_path):
        """P0.9: an allowlist entry wins over PLAN mode's deny-by-default."""
        store = AllowlistStore(tmp_path / "a.json")
        store.add("bash", "pytest *")
        policy = PolicyEngine(PermissionMode.PLAN, RuleSet(), allowlist=store)
        decision = policy.decide("bash", {"command": "pytest -q"})
        assert decision.action == Action.ALLOW
        assert "allowlist" in decision.reason

    def test_allowlist_not_applied_without_match(self, tmp_path):
        store = AllowlistStore(tmp_path / "a.json")
        store.add("bash", "pytest *")
        policy = PolicyEngine(PermissionMode.PLAN, RuleSet(), allowlist=store)
        decision = policy.decide("bash", {"command": "rm -rf /"})
        assert decision.action == Action.DENY  # PLAN default

    def test_deny_rule_still_beats_allowlist(self, tmp_path):
        store = AllowlistStore(tmp_path / "a.json")
        store.add("bash", "*")
        rules = RuleSet(rules=(Rule(tool="bash", action=Action.DENY, pattern="rm *"),))
        policy = PolicyEngine(PermissionMode.DEFAULT, rules, allowlist=store)
        decision = policy.decide("bash", {"command": "rm -rf /"})
        assert decision.action == Action.DENY
