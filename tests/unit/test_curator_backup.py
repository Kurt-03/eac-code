"""Tests for the curator backup (C.6)."""

from eaccode.curator.backup import backup_snapshot, list_backups, restore_backup


def _tree(base, rel: str, content: str = "data"):
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def test_backup_and_list(tmp_path):
    skills = tmp_path / "skills"
    memory = tmp_path / "memory"
    backups = tmp_path / "backups"
    _tree(skills, "a.md")
    _tree(memory, "projects/h1/MEMORY.md")
    dest = backup_snapshot(skills, memory, backups)
    assert dest.exists()
    assert dest.name.startswith("eaccode-backup-")
    assert list_backups(backups) == [dest]


def test_backup_missing_dirs_is_empty_zip(tmp_path):
    dest = backup_snapshot(tmp_path / "nope", tmp_path / "nope2",
                           tmp_path / "backups")
    assert dest.exists()


def test_restore_roundtrip(tmp_path):
    skills = tmp_path / "skills"
    memory = tmp_path / "memory"
    _tree(skills, "git.md", "git content")
    _tree(memory, "USER.md", "user content")
    dest = backup_snapshot(skills, memory, tmp_path / "backups")

    target = tmp_path / "restored"
    restore_backup(dest, target)
    assert (target / "git.md").read_text(encoding="utf-8") == "git content"
    assert (target / "USER.md").read_text(encoding="utf-8") == "user content"
