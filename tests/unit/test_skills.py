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
