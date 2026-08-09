"""Tests for @-reference expansion (Phase H.3)."""


from eaccode.ui.context_refs import (
    parse_context_references,
    preprocess_context_references,
)


def test_parse_extracts_kinds():
    refs = parse_context_references("@file:a.py und @git:3 und @url:https://x.de")
    kinds = [k for k, _ in refs]
    assert kinds == ["file", "git", "url"]


def test_file_reference_expands_to_fenced_content(tmp_path):
    (tmp_path / "a.py").write_text("x = 1", encoding="utf-8")
    out = preprocess_context_references(f"@file:{tmp_path / 'a.py'} warum?", cwd=tmp_path)
    assert "a.py" in out
    assert "x = 1" in out
    assert "```python" in out  # code fence with language
    assert "warum?" in out  # surrounding text preserved


def test_relative_file_reference(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')", encoding="utf-8")
    out = preprocess_context_references("@file:src/main.py", cwd=tmp_path)
    assert "print('hi')" in out


def test_missing_file_left_as_is(tmp_path):
    out = preprocess_context_references("@file:ghost.py", cwd=tmp_path)
    assert out == "@file:ghost.py"  # unresolved token stays


def test_folder_reference_lists_entries(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("", encoding="utf-8")
    (tmp_path / "src" / "sub").mkdir()
    out = preprocess_context_references("@folder:src", cwd=tmp_path)
    assert "a.py" in out
    assert "sub/" in out


def test_git_reference_expands(tmp_path):
    import subprocess

    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], check=True)
    (tmp_path / "f.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "first"], check=True)
    out = preprocess_context_references("@git:1", cwd=tmp_path)
    assert "first" in out  # commit message visible


def test_url_reference_expands_or_stays():
    # No network guarantee in tests: must not crash, either way is fine.
    out = preprocess_context_references("@url:https://example.invalid/x")
    assert isinstance(out, str)
    assert "@url:https://example.invalid/x" in out or "Fetched URL" in out


def test_no_references_unchanged(tmp_path):
    msg = "Schau dir das an"
    assert preprocess_context_references(msg, cwd=tmp_path) == msg
