"""P7/E.1: prompt history survives a restart.

We simulate a restart by closing the first app, then opening a new one
with the same workdir. Both apps share config_dir, so the second one
must see the first's history.
"""



def _build_app(tmp_path, monkeypatch):
    import eaccode.tui.app as app_mod
    from eaccode.config import paths as paths_mod

    class _FakePaths:
        config_dir = tmp_path
        data_dir = tmp_path / "data"
        memory_dir = tmp_path / "memory"
        skills_dir = tmp_path / "skills"
        hooks_dir = tmp_path / "hooks"
        providers_file = tmp_path / "providers.yaml"
        settings_file = tmp_path / "settings.yaml"
        cron_db = tmp_path / "cron.db"
        sessions_dir = tmp_path / "sessions"
        plugins_dir = tmp_path / "plugins"

    # Patch BOTH the source module and any site that already imported the
    # symbol — _history_path() looks the symbol up at call time.
    if hasattr(app_mod, "EaccodePaths"):
        monkeypatch.setattr(app_mod, "EaccodePaths", _FakePaths)
    monkeypatch.setattr(paths_mod, "EaccodePaths", _FakePaths)
    return _FakePaths


def test_history_persists_across_restart(tmp_path, monkeypatch):
    _build_app(tmp_path, monkeypatch)
    from eaccode.ui.repl import EaccodeApp

    a1 = EaccodeApp(workdir=tmp_path)
    a1._remember_prompt("first prompt")
    a1._remember_prompt("second prompt")
    a1._save_input_history()
    # a1 falls out of scope; the file is on disk.

    a2 = EaccodeApp(workdir=tmp_path)
    assert "first prompt" in a2._input_history
    assert "second prompt" in a2._input_history


def test_history_corrupt_file_does_not_crash(tmp_path, monkeypatch):
    _build_app(tmp_path, monkeypatch)
    # Write garbage first.
    from eaccode.config import paths as paths_mod

    bad = paths_mod.EaccodePaths().config_dir / "history.json"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("{not json", encoding="utf-8")

    from eaccode.ui.repl import EaccodeApp

    # Loading must NOT raise.
    a = EaccodeApp(workdir=tmp_path)
    assert a._input_history == []


def test_history_dedup(tmp_path, monkeypatch):
    _build_app(tmp_path, monkeypatch)
    from eaccode.ui.repl import EaccodeApp

    a = EaccodeApp(workdir=tmp_path)
    a._remember_prompt("hi")
    a._remember_prompt("hi")
    a._remember_prompt("hi")
    assert a._input_history.count("hi") == 1


def test_history_skips_slash_commands(tmp_path, monkeypatch):
    _build_app(tmp_path, monkeypatch)
    from eaccode.ui.repl import EaccodeApp

    a = EaccodeApp(workdir=tmp_path)
    a._remember_prompt("/mode safeAuto")
    a._remember_prompt("real question")
    assert "/mode safeAuto" not in a._input_history
    assert "real question" in a._input_history


def test_history_cap_at_50(tmp_path, monkeypatch):
    _build_app(tmp_path, monkeypatch)
    from eaccode.ui.repl import EaccodeApp

    a = EaccodeApp(workdir=tmp_path)
    for i in range(80):
        a._remember_prompt(f"prompt {i}")
    assert len(a._input_history) == 50
    assert a._input_history[0] == "prompt 30"
    assert a._input_history[-1] == "prompt 79"


def test_history_atomic_save(tmp_path, monkeypatch):
    """Even if the file is replaced mid-write, the live app keeps working."""
    _build_app(tmp_path, monkeypatch)
    from eaccode.ui.repl import EaccodeApp

    a = EaccodeApp(workdir=tmp_path)
    a._remember_prompt("one")
    a._remember_prompt("two")
    # Simulate a torn write by deleting the file then asking for another save.
    hist = a._history_path()
    if hist.exists():
        hist.unlink()
    a._remember_prompt("three")  # should not raise
    assert "three" in a._input_history
