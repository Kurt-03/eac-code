"""Tests for skill preprocessing (A.5) — template vars + inline shell."""

from pathlib import Path

from eaccode.memory.skill_preprocessing import (
    preprocess_skill,
    run_inline_shell,
    substitute_template_vars,
)
from eaccode.memory.skills import Skill


def _skill(content: str) -> Skill:
    return Skill(name="t", description="d", content=content, source=None)


def test_template_vars_replaced(tmp_path):
    out = substitute_template_vars("cwd is {{cwd}}, again {{workdir}}", tmp_path)
    assert out == f"cwd is {tmp_path}, again {tmp_path}"


def test_no_vars_unchanged():
    assert substitute_template_vars("plain", Path(".")) == "plain"


def test_inline_shell_splices_stdout(tmp_path):
    out = run_inline_shell("```shell\necho hello-from-shell\n```", tmp_path)
    assert "hello-from-shell" in out


def test_inline_shell_error_is_visible_not_fatal(tmp_path):
    out = run_inline_shell("```shell\necho oops >&2 && exit 3\n```", tmp_path)
    assert "exited 3" in out
    assert "oops" in out


def test_inline_shell_timeout_graceful(tmp_path):
    out = run_inline_shell("```shell\nsleep 30\n```", tmp_path)
    assert "timed out" in out


def test_preprocess_returns_new_skill_on_change(tmp_path):
    skill = _skill("cwd={{cwd}}")
    processed = preprocess_skill(skill, tmp_path)
    assert processed is not skill
    assert str(tmp_path) in processed.content


def test_preprocess_keeps_metadata(tmp_path):
    skill = _skill("no vars here")
    processed = preprocess_skill(skill, tmp_path)
    assert processed is skill  # unchanged → same object
    assert processed.name == "t"
