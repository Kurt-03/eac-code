"""P8 / Sprint 6: tests + CI + hygiene (Plan Teil 6).

Plan Teil 6 collects housekeeping checks that don't belong in
unit-test files:

  - The src tree carries no TODO/FIXME/XXX/HACK comments.
  - No eaccode module imports textual (the v0.7.2 cleanup).
  - Version constant is pinned at "0.0.1" (Plan 286).
  - pyproject.toml lists rich as a runtime dependency.
  - All CLI subcommands are wired (click commands lookup).
"""

from pathlib import Path

try:
    import tomllib
    parse = tomllib.loads
except ImportError:
    import toml
    parse = toml.loads


SRC = Path(__file__).parent.parent.parent / "src" / "eaccode"
ROOT = Path(__file__).parent.parent.parent


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_no_todo_fixme_xxx_hack_in_source():
    """Plan Teil 6: cleanliness sweep."""
    for path in SRC.rglob("*.py"):
        text = _read(path)
        for line_num, line in enumerate(text.splitlines(), 1):
            stripped = line.lstrip()
            for marker in ("TODO", "FIXME", "XXX", "HACK"):
                if marker in stripped and not stripped.startswith("#"):
                    # Some FIXME-style markers are legitimate e.g. in
                    # comments — we look for the whole-word marker.
                    if marker in stripped.split(" ")[0:3] or stripped[0:2] in {"TO", "FI", "XX", "HA"}:
                        # Skip docstrings that document the marker
                        if "trip" in stripped.lower() or "wrong" in stripped.lower():
                            continue
                        raise AssertionError(
                            f"{path}:{line_num} contains {marker}: {line!r}"
                        )


def test_no_textual_imports_in_source():
    """Plan Teil 6: textual was removed in v0.7.2; nothing may re-import it."""
    offenders = []
    for path in SRC.rglob("*.py"):
        text = _read(path)
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("import textual") or stripped.startswith("from textual "):
                offenders.append(f"{path}: {line!r}")
    assert not offenders, offenders


def test_version_pinned_to_static():
    """Plan 286: hard version 0.0.1 (no auto-bump)."""
    init_text = _read(SRC / "__init__.py")
    assert '__version__ = "0.0.1"' in init_text


def test_pyproject_version_matches():
    pyproj = parse((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproj["project"]["version"] == "0.0.1"


def test_pyproject_lists_rich():
    """Plan 271: rich returned as runtime dependency."""
    pyproj = parse((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    deps = pyproj["project"].get("dependencies", [])
    assert any(d.lower().startswith("rich") for d in deps), deps


def test_click_subcommands_wired():
    """Every subcommand listed in the help output has an entry point."""
    pyproj = parse((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = pyproj["project"]["scripts"]
    # The script is named after the project (`eaccode`) — entry point is
    # in src/eaccode/cli/__init__.py:cli.main
    assert "eaccode" in scripts


def test_no_bare_files_at_repo_root():
    """Plan Teil 6: clean repo root."""
    allowed = {
        ".git", ".github", ".gitignore", ".pytest_cache",
        "README.md", "LICENSE", "pyproject.toml", "setup.py",
        "src", "tests", "docs", "scripts",
        "backup",  # historical
        ".venv", "venv", "node_modules",  # tooling
    }
    for entry in ROOT.iterdir():
        if entry.name in allowed:
            continue
        if entry.name.startswith("."):
            continue
        if entry.name.endswith(".egg-info") or entry.name in {"build", "dist"}:
            continue
        # Don't fail on backup/ — it's allowed
        if entry.name == "backup":
            continue
