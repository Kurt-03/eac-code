"""Tests for the V4A patch parser (H.13)."""


from eaccode.utils.patch_parser import apply_patch, parse_patch


def test_parse_extracts_files_and_hunks():
    patch = (
        "*** Begin Patch\n"
        "*** Update File: a.py\n"
        "@@ main @@\n"
        " context\n"
        "-old line\n"
        "+new line\n"
        "*** Update File: b.py\n"
        "-gone\n"
        "*** End Patch\n"
    )
    hunks = parse_patch(patch)
    assert [h.path for h in hunks] == ["a.py", "b.py"]
    assert hunks[0].context == "main"


def test_apply_replace(tmp_path):
    (tmp_path / "a.py").write_text("line1\nold line\nline3\n", encoding="utf-8")
    patch = (
        "*** Begin Patch\n"
        "*** Update File: a.py\n"
        "-old line\n"
        "+new line\n"
        "*** End Patch\n"
    )
    results = apply_patch(patch, tmp_path)
    assert results == {"a.py": True}
    assert (tmp_path / "a.py").read_text(encoding="utf-8") == \
        "line1\nnew line\nline3\n"


def test_apply_no_match_returns_false(tmp_path):
    (tmp_path / "a.py").write_text("x\n", encoding="utf-8")
    patch = (
        "*** Begin Patch\n"
        "*** Update File: a.py\n"
        "-missing\n"
        "+added\n"
        "*** End Patch\n"
    )
    results = apply_patch(patch, tmp_path)
    assert results == {"a.py": False}
    # File untouched on failure.
    assert (tmp_path / "a.py").read_text(encoding="utf-8") == "x\n"


def test_apply_missing_file_false(tmp_path):
    patch = (
        "*** Begin Patch\n"
        "*** Update File: nope.py\n"
        "-x\n"
        "+y\n"
        "*** End Patch\n"
    )
    assert apply_patch(patch, tmp_path) == {"nope.py": False}


def test_parse_ignores_text_outside_patch():
    text = ("some prompt text\n*** Begin Patch\n*** Update File: a.py\n"
            "-x\n+y\n*** End Patch\nmore text")
    hunks = parse_patch(text)
    assert len(hunks) == 1
    assert hunks[0].path == "a.py"


def test_apply_absolute_path_ignores_base_dir(tmp_path):
    target = tmp_path / "abs.py"
    target.write_text("x\n", encoding="utf-8")
    patch = (
        "*** Begin Patch\n"
        f"*** Update File: {target}\n"
        "-x\n"
        "+y\n"
        "*** End Patch\n"
    )
    results = apply_patch(patch, tmp_path)
    assert results == {str(target): True}
    assert target.read_text(encoding="utf-8") == "y\n"
