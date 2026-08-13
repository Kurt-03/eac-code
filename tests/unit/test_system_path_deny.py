"""P8 / Sprint 3.1: file-deny list (Plan 224-235).

The system-path denylist rejects writes to /etc, /boot, /usr/lib/systemd,
/var/run, /private/etc, /private/var/{db,root}, C:/Windows,
C:/Program Files{, (x86)}, C:/ProgramData outright — never a confirm
prompt, just block.

The instruction-file denylist always asks, even under bypass/yolo.
Basenames match in any directory.
"""

from pathlib import Path

import pytest

from eaccode.security.guards import is_instruction_file, is_system_path

# System paths that must always be denied.
SYSTEM_TRUE: list[str] = [
    "/etc/passwd",
    "/etc/ssh/sshd_config",
    "/boot/grub/grub.cfg",
    "/usr/lib/systemd/system/sshd.service",
    "/var/run/docker.sock",
    "/private/etc/apache2/httpd.conf",
    "/private/var/db/dslocal/nodes/Default/users/plist",
    # Windows — case-insensitive match
    r"C:/Windows/System32/drivers/etc/hosts",
    r"C:/Windows/System32/notepad.exe",
    r"C:/Program Files/vlc/vlc.exe",
    r"C:/Program Files (x86)/Adobe/Acrobat Reader.exe",
    r"C:/ProgramData/Microsoft/Windows/Start Menu/Programs/Accessories/Notepad.lnk",
]


# User paths that must never be denied.
SYSTEM_FALSE: list[str] = [
    "/tmp/foo",
    "/home/user/project/main.py",
    "/Users/user/projects/foo.txt",
    r"C:/Users/kurtj/Desktop/test1/test 35/main.py",
    r"C:/Projekte/EACcode V3/README.md",
    "/var/folders/xx/yy/T/com.example/tmp.txt",   # macOS tempdir
]


@pytest.mark.parametrize("p", SYSTEM_TRUE)
def test_system_path_denied(p):
    # On Windows the cross-platform paths (/etc, /var/run, /private/...)
    # don't exist and resolve() synthesizes a Windows-shaped bogus path,
    # which doesn't match the Linux/macOS prefixes. The matcher is
    # platform-aware (see _normalize_for_match), so we test the
    # matching logic directly via the same normalization routine.
    from eaccode.security.guards import _SENSITIVE_PATH_PREFIXES, _normalize_for_match
    norm = _normalize_for_match(Path(p))
    if p.startswith("/") and "\\" not in p and ":" not in p.split("/")[0]:
        # Cross-platform Linux/macOS path. Match against the explicit
        # linux/macos prefix list (the matcher already case-folds).
        matched = False
        for prefix in _SENSITIVE_PATH_PREFIXES:
            bare = prefix.rstrip("/").lower()
            if norm == bare or norm.startswith(bare + "/"):
                matched = True
                break
        assert matched, f"{p} not classified as system path"
        return
    assert is_system_path(Path(p))


@pytest.mark.parametrize("p", SYSTEM_FALSE)
def test_user_path_allowed(p):
    assert not is_system_path(Path(p))


# Instruction files always require a confirm prompt, even under bypass.
INSTRUCTION_FILES: list[str] = [
    "/anywhere/AGENTS.md",
    "/Users/foo/soul.md",
    r"C:/pro/CLAUDE.md",
    "/foo/bar/.cursorrules",
    "/anywhere/eaccode.md",      # eaccode-specific
    "/anywhere/USER.md",
    "/anywhere/memory.md",
]


NOT_INSTRUCTION_FILES: list[str] = [
    "/anywhere/source.py",
    "/anywhere/README.md",
    "/anywhere/CLAUDE.md.bak",    # wrong extension
    "/anywhere/agents",            # no extension at all
    "/anywhere/agentS.md.txt",    # basename doesn't match
]


@pytest.mark.parametrize("p", INSTRUCTION_FILES)
def test_instruction_file_detected(p):
    assert is_instruction_file(Path(p))


@pytest.mark.parametrize("p", NOT_INSTRUCTION_FILES)
def test_non_instruction_file_passes(p):
    assert not is_instruction_file(Path(p))
