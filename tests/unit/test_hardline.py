"""P8 / Sprint 3.2: hardline + sudo-stdin + user-deny preflight.

Plan 56-79. Hardline blocks run before yolo and approvals.mode=off.
Each pattern is anchored to _CMDPOS (start of command or shell
boundary) so a literal mention inside a commit message or comment
does not match.
"""

import pytest

from eaccode.permissions.hardline import (
    _sudo_stdin_guard,
    block_reason_text,
    check_user_deny_rule,
    detect_hardline_command,
    preflight_block,
)


def _check(command: str):
    """Wrap detect so the test runner doesn't trigger any
    out-of-process safety hooks. The patterns are pure-string regex
    matches against the command text.
    """
    return detect_hardline_command(command)


# ----- Plan 56-69: hardline (must block) -----
HARDLINE_BLOCKED: list[str] = [
    "rm -rf /",
    "rm -rf /*",
    "rm -rf //",
    "rm -rf /./",
    "rm -rf /home",
    "rm -rf /root",
    "rm -rf /etc",
    "rm -rf /usr",
    "rm -rf /var",
    "rm -rf /bin",
    "rm -rf /sbin",
    "rm -rf /boot",
    "rm -rf /lib",
    "rm -rf /etc/*",
    "rm -rf ~/Documents",
    "rm -rf $HOME/Documents",
    "rm -rf ${HOME}/Documents",
    "mkfs.ext4 /dev/sda",
    "mkfs.xfs /dev/nvme0n1",
    "mkfs /dev/sda",
    "dd if=/dev/zero of=/dev/sda",
    ":() { :|:& };:",
    "kill -1",
    "kill -- -1",
    "shutdown -h now",
    "shutdown now",
    "shutdown 08:00",
    "reboot",
    "halt",
    "poweroff",
    "init 0",
    "init 6",
    "systemctl poweroff",
    "systemctl reboot",
]


# ----- Plan 56-69: hardline (must NOT block) -----
HARDLINE_ALLOWED: list[str] = [
    "ls -la",
    "pytest -q",
    "git status",
    "npm install",
    'git commit -m "fix rm -rf issue"',     # literal mention in commit msg
    "git rm -rf build/",                    # rm on a subdirectory, not root
    "rm -rf build/",
    "mkdir /home/user/projects",
    "echo hello > /dev/null",               # /dev/null, not block device
    "cat /etc/hostname",                    # reading, not writing
    "sudo apt-get install foo",             # normal sudo (no -S)
    "echo x > /dev/sda",                    # not a real block device write — just echo to a path
    "dd if=/dev/zero of=/tmp/disk.img",     # /tmp/, not a block device
    "rm -rf /tmp/test1",                    # /tmp is fine
    "rm -rf /Users/me/projects",            # macOS user dir
    "echo \"rm -rf / is dangerous\"",         # mention inside a string
]


@pytest.mark.parametrize("cmd", HARDLINE_BLOCKED)
def test_hardline_blocks(cmd):
    blocked, kind, _ = preflight_block(cmd)
    assert blocked, f"{cmd!r} should have been blocked"
    assert kind == "hardline"


@pytest.mark.parametrize("cmd", HARDLINE_ALLOWED)
def test_hardline_allows(cmd):
    blocked, kind, _ = preflight_block(cmd)
    assert not blocked, f"{cmd!r} should NOT have been blocked"


def test_detect_hardline_returns_description():
    blocked, desc = _check("rm -rf /")
    assert blocked
    assert desc is not None
    assert "rm" in desc


# ----- Plan 73-75: sudo-stdin guard -----
@pytest.mark.parametrize("cmd", [
    "sudo -S apt-get install foo",
    "sudo --stdin bash -c id",
    "sudo -S -p pw apt update",
])
def test_sudo_stdin_blocks(cmd):
    assert _sudo_stdin_guard(cmd)


@pytest.mark.parametrize("cmd", [
    "sudo apt-get install foo",       # plain sudo is fine
    'echo "sudo -S would be bad"',  # mention in a string
])
def test_sudo_stdin_allows(cmd):
    assert not _sudo_stdin_guard(cmd)


# ----- Plan 77-79: user-deny rules -----
def test_user_deny_simple_glob():
    rule = check_user_deny_rule("rm -rf foo", ("rm -rf *",))
    assert rule == "rm -rf *"


def test_user_deny_no_match():
    rule = check_user_deny_rule("ls -la", ("rm -rf *",))
    assert rule is None


def test_user_deny_anchored_at_command_start():
    # Pattern with implicit * matches anywhere.
    rule = check_user_deny_rule("echo hi && rm -rf /tmp", ("rm -rf *",))
    assert rule == "rm -rf *"


def test_preflight_with_user_deny():
    blocked, kind, desc = preflight_block(
        "rm -rf build/", deny_patterns=("rm -rf *",),
    )
    assert blocked
    assert kind == "user_deny"
    assert desc == "rm -rf *"


# ----- block_reason_text -----
def test_block_reason_hardline_text():
    text = block_reason_text("hardline", "rm -rf /")
    assert "hardline" in text
    assert "rm -rf /" in text
    assert "yolo" in text  # Plan 70: explicit mention


def test_block_reason_sudo_text():
    text = block_reason_text("sudo_stdin", None)
    assert "SUDO_PASSWORD" in text
    assert "Sorry, try again" in text  # Plan 74: explicit mention


def test_block_reason_user_deny_text():
    text = block_reason_text("user_deny", "rm -rf *")
    assert "do NOT retry" in text
    assert "rm -rf *" in text
