"""Tests for skill bundles (A.11)."""

from pathlib import Path

from eaccode.memory.skill_bundles import (
    bundle_skill_files,
    install_bundle,
    scan_bundles,
)


def _make_bundle(root: Path, name: str, body: str = "body") -> None:
    d = root / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: bundle {name}\n---\n{body}",
        encoding="utf-8",
    )
    (d / "scripts").mkdir()
    (d / "scripts" / "run.py").write_text("print(1)", encoding="utf-8")


def test_scan_finds_bundles_with_skill_md(tmp_path):
    _make_bundle(tmp_path, "tdd")
    _make_bundle(tmp_path, "git")
    (tmp_path / "nobundle").mkdir()  # no SKILL.md
    bundles = scan_bundles([tmp_path])
    assert set(bundles) == {"tdd", "git"}


def test_scan_skips_missing_dirs(tmp_path):
    assert scan_bundles([tmp_path / "nope"]) == {}


def test_install_copies_into_bundled_subdir(tmp_path):
    _make_bundle(tmp_path, "tdd")
    target = tmp_path / "skills"
    installed = install_bundle("tdd", [tmp_path], target)
    assert installed is not None
    assert (target / "bundled" / "tdd" / "SKILL.md").exists()
    assert (target / "bundled" / "tdd" / "scripts" / "run.py").exists()
    # provenance is bundled because of the directory layout
    from eaccode.memory.skills import discover_skills

    skills = discover_skills([target])
    assert skills[0].provenance == "bundled"


def test_install_missing_bundle_returns_none(tmp_path):
    assert install_bundle("nope", [tmp_path], tmp_path / "skills") is None


def test_bundle_skill_files_orders_skill_md_first(tmp_path):
    _make_bundle(tmp_path, "tdd")
    files = bundle_skill_files(tmp_path / "tdd")
    assert files[0].name == "SKILL.md"
