"""Tests for skill discovery (Task 6.1)."""
from eaccode.memory.skills import discover_skills, skills_to_system_prompt_section


def test_skill_parses_markdown(tmp_path):
    skill_dir = tmp_path / "skills"
    skill_dir.mkdir()
    (skill_dir / "git.md").write_text(
        "---\n"
        "name: git\n"
        "description: Use when working with git repos\n"
        "---\n"
        "Always run `git status` before commits."
    )
    skills = discover_skills([skill_dir])
    assert len(skills) == 1
    assert skills[0].name == "git"
    assert "git status" in skills[0].content


def test_skill_defaults_to_filename(tmp_path):
    skill_dir = tmp_path / "skills"
    skill_dir.mkdir()
    (skill_dir / "docker.md").write_text("plain markdown without frontmatter")
    skills = discover_skills([skill_dir])
    assert skills[0].name == "docker"


def test_missing_dir_returns_empty(tmp_path):
    assert discover_skills([tmp_path / "nope"]) == []


def test_skills_to_prompt_section(tmp_path):
    skill_dir = tmp_path / "skills"
    skill_dir.mkdir()
    (skill_dir / "a.md").write_text(
        "---\nname: a\ndescription: Skill A\n---\nsteps for a"
    )
    section = skills_to_system_prompt_section(discover_skills([skill_dir]))
    assert "Skill A" in section
    assert "steps for a" in section


def test_empty_skills_no_section():
    assert skills_to_system_prompt_section([]) == ""


# ---------------------------------------------------------------- A.1/A.3


def _write(tmp_path, rel: str, text: str):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def test_frontmatter_triggers_and_platform_parsed(tmp_path):
    _write(tmp_path, "skills/t.md",
           "---\nname: t\ndescription: T\ntriggers: [pytest, tests]\n"
           "platform: windows\n---\nbody")
    skills = discover_skills([tmp_path / "skills"])
    assert skills[0].triggers == ["pytest", "tests"]
    assert skills[0].platform == "windows"


def test_broken_frontmatter_does_not_crash(tmp_path):
    _write(tmp_path, "skills/broken.md",
           "---\nname: [unclosed\ndescription: 'x\n---\nbody text")
    skills = discover_skills([tmp_path / "skills"])
    assert len(skills) == 1
    assert skills[0].name == "broken"
    assert "body text" in skills[0].content


def test_platform_mismatch_skips_skill(tmp_path):
    _write(tmp_path, "skills/linux.md",
           "---\nname: l\nplatform: linux\n---\nbody")
    _write(tmp_path, "skills/any.md", "---\nname: a\n---\nbody")
    skills = discover_skills([tmp_path / "skills"])
    assert [s.name for s in skills] == ["a"]


def test_provenance_bundled_via_subdir(tmp_path):
    _write(tmp_path, "skills/bundled/b.md", "---\nname: b\n---\nbody")
    _write(tmp_path, "skills/u.md", "---\nname: u\n---\nbody")
    by_name = {s.name: s for s in discover_skills([tmp_path / "skills"])}
    assert by_name["b"].provenance == "bundled"
    assert by_name["u"].provenance == "user"


def test_provenance_frontmatter_override(tmp_path):
    _write(tmp_path, "skills/c.md",
           "---\nname: c\nprovenance: curator\n---\nbody")
    skills = discover_skills([tmp_path / "skills"])
    assert skills[0].provenance == "curator"
