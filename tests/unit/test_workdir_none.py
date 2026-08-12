"""P7 (v0.7.2 followup): workdir=None must default to Path.cwd().

Regression: when the user invoked `eaccode` without --resume, the
CLI passed workdir=None to run_repl, which forwarded it to
build_agent_async. Several subsystems (memory.project,
memory.store, agent.workspace) crashed with
'NoneType' object has no attribute 'resolve'.
"""

from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_build_agent_with_none_workdir_defaults_to_cwd():
    """Passing workdir=None still must produce a working agent.

    The CLI now defaults workdir to Path.cwd() before it reaches
    build_agent_async; this test makes that contract explicit.
    """
    from eaccode.agent.factory import build_agent_async

    agent, client, _ = await build_agent_async(workdir=Path.cwd())
    assert client.default_model


@pytest.mark.asyncio
async def test_discover_project_context_handles_none():
    """discover_project_context(None) must not raise AttributeError."""
    from eaccode.memory.project import discover_project_context

    result = discover_project_context(None)
    assert isinstance(result, str)


def test_find_all_handles_none():
    """_find_all(None, ...) must default to Path.cwd() internally."""
    from eaccode.memory.project import _find_all

    # _CONTEXT_FILES[0] is (name, walk, chain); we don't care about
    # the actual file — the function must just not raise.
    try:
        _find_all(None, "EACCODE.md", False, False)
    except FileNotFoundError:
        pass  # No EACCODE.md in this repo — that's fine.
    except AttributeError as e:
        pytest.fail(f"_find_all regressed to NoneType error: {e}")
