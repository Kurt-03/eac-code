"""Tests for the skill linter (A.4)."""

from eaccode.memory.skill_linter import lint_skill, lint_skills_dir


def _skill(tmp_path, text: str):
    p = tmp_path / "skills"
    p.mkdir(exist_ok=True)
    f = p / "demo.md"
    f.write_text(text, encoding="utf-8")
    return f


GOOD = (
    "---\n"
    "name: demo\n"
    "description: Use when doing demo things\n"
    "triggers: [demo]\n"
    "---\n"
    "body steps here"
)


def test_good_skill_has_no_issues(tmp_path):
    assert lint_skill(_skill(tmp_path, GOOD)) == []


def test_missing_frontmatter(tmp_path):
    issues = lint_skill(_skill(tmp_path, "plain markdown"))
    assert [i.rule for i in issues] == ["R1"]


def test_missing_name_and_description(tmp_path):
    issues = lint_skill(_skill(tmp_path, "---\ntriggers: [x]\n---\nbody"))
    rules = {i.rule for i in issues}
    assert {"R2", "R3"} <= rules


def test_description_too_long(tmp_path):
    issues = lint_skill(_skill(
        tmp_path,
        "---\nname: demo\ndescription: " + "x" * 60 + "\n---\nbody",
    ))
    assert any(i.rule == "R4" for i in issues)


def test_name_must_be_slug(tmp_path):
    issues = lint_skill(_skill(
        tmp_path, "---\nname: Demo Skill\ndescription: ok\n---\nbody"
    ))
    assert any(i.rule == "R5" for i in issues)


def test_triggers_must_be_list(tmp_path):
    issues = lint_skill(_skill(
        tmp_path,
        "---\nname: demo\ndescription: ok\ntriggers: pytest\n---\nbody",
    ))
    assert any(i.rule == "R6" for i in issues)


def test_platform_must_be_valid(tmp_path):
    issues = lint_skill(_skill(
        tmp_path,
        "---\nname: demo\ndescription: ok\nplatform: win\n---\nbody",
    ))
    assert any(i.rule == "R7" for i in issues)


def test_empty_body(tmp_path):
    issues = lint_skill(_skill(
        tmp_path, "---\nname: demo\ndescription: ok\n---\n   "
    ))
    assert any(i.rule == "R8" for i in issues)


def test_too_many_lines(tmp_path):
    text = "---\nname: demo\ndescription: ok\n---\n" + "\n".join(
        f"line {i}" for i in range(700)
    )
    issues = lint_skill(_skill(tmp_path, text))
    assert any(i.rule == "R9" for i in issues)


def test_pruned_marker(tmp_path):
    issues = lint_skill(_skill(
        tmp_path, "---\nname: demo\ndescription: ok\n---\n[SKILL_PRUNED]"
    ))
    assert any(i.rule == "R10" for i in issues)


def test_binary_garbage(tmp_path):
    f = tmp_path / "skills"
    f.mkdir(exist_ok=True)
    p = f / "bin.md"
    p.write_bytes(b"\xff\xfe\x00\x01binary")
    issues = lint_skill(p)
    assert [i.rule for i in issues] == ["R11"]


def test_invalid_provenance(tmp_path):
    issues = lint_skill(_skill(
        tmp_path,
        "---\nname: demo\ndescription: ok\nprovenance: cloud\n---\nbody",
    ))
    assert any(i.rule == "R12" for i in issues)


def test_lint_dir_collects_all(tmp_path):
    _skill(tmp_path, GOOD)
    _skill(tmp_path, "---\nname: x\ndescription: ok\n---\n" + "y" * 500)
    (tmp_path / "skills" / "bad.md").write_text("plain")
    result = lint_skills_dir(tmp_path / "skills")
    assert len(result) >= 1
    assert all(isinstance(v, list) for v in result.values())


def test_lint_missing_dir_empty(tmp_path):
    assert lint_skills_dir(tmp_path / "nope") == {}
