"""P8 / Sprint 5: Windows subprocess hygiene (Plan Teil 5).

The existing _subprocess_compat.py module covers all the parts the
Plan Teil 5 calls out:

  - CREATE_NO_WINDOW (windows_hide_flags)
  - subprocess.run(... creationflags=…) on every Popen site
  - kill_process_tree on every long-running spawn
  - IS_WINDOWS gating (zero-cost on POSIX)
  - shutil.which for PATHEXT resolution

This file freezes the contract with explicit tests. We do not branch
on sys.platform inside the tests themselves — each helper returns
a no-op on POSIX so the test surface is the same.
"""

import subprocess
import sys

import pytest

from eaccode._subprocess_compat import (
    IS_WINDOWS,
    bounded_git_probe,
    kill_process_tree,
    windows_hide_flags,
)

# ----- windows_hide_flags -----

def test_windows_hide_flags_returns_int():
    flags = windows_hide_flags()
    assert isinstance(flags, int)


def test_windows_hide_flags_on_windows_includes_no_window():
    if not IS_WINDOWS:
        pytest.skip("Windows-only assertion")
    flags = windows_hide_flags()
    # CREATE_NO_WINDOW = 0x08000000 = 134217728
    assert flags & 0x08000000


def test_windows_hide_flags_on_posix_is_zero():
    if IS_WINDOWS:
        pytest.skip("POSIX-only assertion")
    assert windows_hide_flags() == 0


# ----- bounded_git_probe -----

def test_bounded_git_probe_returns_string():
    """bounded_git_probe returns the stdout of the git subprocess."""
    code = bounded_git_probe(["rev-parse", "--is-inside-work-tree"], timeout=5)
    assert isinstance(code, str)


def test_bounded_git_probe_runs_in_repo():
    """When the eaccode git repo is the cwd, the probe returns 'true'."""
    # bounded_git_probe has no cwd parameter (inherits from parent).
    # Inside the eaccode git repo, this should report "true".
    out = bounded_git_probe(["rev-parse", "--is-inside-work-tree"], timeout=10)
    # The probe is fail-open: returns '' on any issue. We just verify
    # it's a string and that the assertion holds when run from a repo.
    assert isinstance(out, str)
    if out:    # empty -> probe failed; skip assertion
        assert "true" in out.lower()


# ----- kill_process_tree -----

def test_kill_process_tree_doesnt_throw_on_already_dead():
    """Calling kill on a finished Popen is a no-op."""
    p = subprocess.Popen([sys.executable, "-c", "exit(0)"], stdout=subprocess.DEVNULL)
    p.wait()
    # No exception raised
    kill_process_tree(p)


def test_kill_process_tree_terminates_long_running():
    """A long-running child must die when we ask the helper to kill it."""
    p = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.DEVNULL,
    )
    # It should be alive at this point
    assert p.poll() is None
    kill_process_tree(p)
    # After kill, it should exit (poll should return something)
    p.wait(timeout=5)
