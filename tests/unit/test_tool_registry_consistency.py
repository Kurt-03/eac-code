"""P7/A.1 + D.1: tool registry is the single source of truth.

Every name in TOOLSETS must exist in _all_tools(); conversely the
safe-list in permissions/policy.py must not name a tool that does
not exist (this is how 'todo' and 'skill_view' slipped through).
"""

from eaccode.permissions.policy import _SAFE_TOOLS
from eaccode.tools.factory import DEFAULT_TOOLSETS, TOOLSETS, _all_tools


def test_grep_is_registered():
    names = {t.name for t in _all_tools()}
    assert "grep" in names


def test_web_fetch_is_registered():
    names = {t.name for t in _all_tools()}
    assert "web_fetch" in names


def test_every_toolset_name_is_registered():
    """TOOLSETS \u2286 Registry: CI gate against naming drift."""
    names = {t.name for t in _all_tools()}
    bad: set[str] = set()
    for toolset in TOOLSETS.values():
        bad |= toolset - names
    assert not bad, f"TOOLSETS names with no registry entry: {bad}"


def test_default_toolsets_all_resolve():
    names = {t.name for t in _all_tools()}
    for ts in DEFAULT_TOOLSETS:
        missing = TOOLSETS[ts] - names
        assert not missing, f"default toolset {ts!r} missing tools {missing}"


def test_safe_list_no_unknown_tools():
    """A tool name in the safe list must actually be registered."""
    names = {t.name for t in _all_tools()}
    unknown = set(_SAFE_TOOLS) - names
    assert not unknown, f"safe-list references unknown tools: {unknown}"


def test_no_duplicate_toolset_names():
    all_names: list[str] = []
    for ts in TOOLSETS.values():
        all_names.extend(ts)
    assert len(all_names) == len(set(all_names))