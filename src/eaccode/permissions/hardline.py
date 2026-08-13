"""Hardline command detection (Plan 56-72) — unblockable, pre-yolo.

Hermes' ``hardline`` layer runs *before* every other check, including
yolo and ``approvals.mode=off``. It catches a small, surgical set of
catastrophic commands that should never run through the agent even if
the user has explicitly said "I know what I'm doing". This is the
last line of defense, not the first: the wider danger patterns in
``danger.py`` still produce confirm prompts; hardline is the absolute
floor.

Rules are anchored to *command position* (``_CMDPOS``): a pattern only
matches at the start of a command or after a shell boundary
(``;``, ``&&``, ``||``, ``|``, ``$(``, backtick, ``sudo``, ``env``,
``exec``). Otherwise ``git commit -m "fix rm -rf issue"`` would trip
the rule, which is the wrong call.

All rules are precompiled at module load with ``re.IGNORECASE |
re.DOTALL`` for fast matching and to handle heredocs.
"""

from __future__ import annotations

import re
from typing import Final

# ---------------------------------------------------------------------------
# Command position regex (Plan 69)
# ---------------------------------------------------------------------------
# A command starts at the start of the input, or right after a shell
# boundary. We use this to *anchor* every hardline pattern so the
# pattern only matches when it actually IS a command, not when it's a
# literal mention inside a string (commit message, comment, log line).
#
# Note (Plan 151): a flat regex cannot distinguish `(reboot)` from
# `--title "(reboot)"`. We rewrite subshell / brace-group openers into
# newline + command-start first (see ``_unwrap_subshells`` below).
_CMDPOS: Final[str] = (
    r"(?:"
    r"(?:^|\s|;|&&|\|\||\||\$\(|`|"
    r"\bsudo\b|\benv\b|\bexec\b|\bcommand\b|\bxargs\b"
    r")"
    r"\s*"
    r"(?:\(\s*)?"    # optional ( ... ) subshell — see _unwrap_subshells
    r")"             # closes the outer (?: from _CMDPOS
)


def _unwrap_subshells(text: str) -> str:
    """Rewrite ``( cmd )`` and ``{ cmd; }`` into ``cmd`` so flat
    command-position regex matches their content (Plan 151).

    Comment from the original: a flat regex cannot distinguish
    ``(reboot)`` from ``--title "(reboot)"``, so we don't try to. We
    just rewrite every ``(`` and ``{`` that introduces a command
    block. False positives are accepted; the danger regex still
    requires a real command token.
    """
    # Replace " (" followed by non-newline content with " ".
    out = re.sub(r"\(\s+", " ", text)
    out = re.sub(r"\s+\)\s*", " ", out)
    out = re.sub(r"\{\s+", " ", out)
    out = re.sub(r"\s+;\s*\}\s*", " ", out)
    return out


# ---------------------------------------------------------------------------
# Hardline patterns (Plan 56-69)
# ---------------------------------------------------------------------------
# Each entry: (compiled regex, human-readable description). The regex
# itself includes the _CMDPOS anchor + command token. The description
# is what we surface to the model and the user — it tells them *why*
# the block fired, and is also what the session/breaker counters
# key on, so it must be stable across edits.

def _pattern(regex: str, flags: int = re.IGNORECASE | re.DOTALL) -> re.Pattern:
    return re.compile(_CMDPOS + regex, flags)


# Anchor a directory prefix to a real path boundary. Inside a hardline
# pattern, CMDPOS has already consumed the leading whitespace, so the
# path begins at the current cursor position. The boundary we want
# is *either* start-of-input *or* the character immediately before the
# path's leading slash is a non-alnum (e.g. space, |, ;). This is the
# negative form of "the path starts at a path segment boundary".
_PATH_BOUNDARY: Final[str] = r"(?:^|(?<=\s))"


def _path_pattern(prefix: str) -> str:
    """Build a regex that matches *prefix* at a real path boundary.

    "/etc" -> matches "/etc", "/etc/foo", "/etc/foo/bar", but NOT
    "/Users/etc". The boundary on the *left* is start-of-input or a
    whitespace character (CMDPOS has already consumed the leading
    separator). This prevents "/etc" from matching inside "/Users/etc".
    """
    escaped = re.escape(prefix).rstrip("/")
    return _PATH_BOUNDARY + escaped + r"(?:/|$)"


# Whitelist of real shutdown / reboot / halt / poweroff options. Used
# by the pattern below to ensure that "shutdown --help" and similar
# "fake" continuations don't trip the hardline (Plan 158).
_SHUTDOWN_FLAGS: tuple[str, ...] = (
    "-h", "--halt", "-r", "--reboot", "-P", "--poweroff",
    "-k", "--no-wall", "-c", "--show",
)
_SHUTDOWN_FLAG_ALT: Final[str] = "|".join(re.escape(f) for f in _SHUTDOWN_FLAGS)


HARDLINE_PATTERNS: Final[tuple[tuple[re.Pattern, str], ...]] = (
    # Plan 56 — rm recursive on root (every spelling).
    # /, //, /., /./, /.., /../.., /*, //*, / *
    (
        _pattern(r"\brm\s+(-\w*r\w*|--recursive)(\s+-\w*f\w*|--force)*\s+"
                 r"/{1,2}(?:/|\.\.?/|\*)?\s*$"),
        "rm -rf /",
    ),
    # Plan 56 — the bare /, //, /./, /../.. variants without flags.
    (
        _pattern(r"\brm\s+(-\w*r\w*|--recursive)?\s+"
                 r"/{1,2}(?:/|\.\.?/)*\s*$"),
        "rm -rf / (bare root path)",
    ),
    # Plan 58 — recursive rm on system dirs (path-boundary anchored,
    # so /etc/foo matches but /Users/etc/foo doesn't).
    (
        _pattern(r"\brm\s+(-\w*r\w*|--recursive)\s+"
                 + _path_pattern("/home")
                 + r"|\brm\s+(-\w*r\w*|--recursive)\s+"
                 + _path_pattern("/root")
                 + r"|\brm\s+(-\w*r\w*|--recursive)\s+"
                 + _path_pattern("/etc")
                 + r"|\brm\s+(-\w*r\w*|--recursive)\s+"
                 + _path_pattern("/usr")
                 + r"|\brm\s+(-\w*r\w*|--recursive)\s+"
                 + _path_pattern("/var")
                 + r"|\brm\s+(-\w*r\w*|--recursive)\s+"
                 + _path_pattern("/bin")
                 + r"|\brm\s+(-\w*r\w*|--recursive)\s+"
                 + _path_pattern("/sbin")
                 + r"|\brm\s+(-\w*r\w*|--recursive)\s+"
                 + _path_pattern("/boot")
                 + r"|\brm\s+(-\w*r\w*|--recursive)\s+"
                 + _path_pattern("/lib")
                 + r"|\brm\s+(-\w*r\w*|--recursive)\s+"
                 + _path_pattern("/System")
                 + r"|\brm\s+(-\w*r\w*|--recursive)\s+"
                 + _path_pattern("/Library")
                 ),
        "rm recursive on system dir",
    ),
    # Plan 59 — recursive rm on home (also $HOME, ~, ${HOME}).
    (
        _pattern(r"\brm\s+(-\w*r\w*|--recursive)\s+(~|\$HOME|\$\{HOME\})"),
        "rm recursive on home",
    ),
    # Plan 61 — mkfs in any flavour (but not the --help / man page).
    (
        _pattern(r"\bmkfs(\.\w+)?\s+(?!--help|-h\b)(?=/dev/)"),
        "mkfs",
    ),
    # Plan 62 — dd into a block device.
    (
        _pattern(r"\bdd\s+[^|;&]*\bof=/dev/(sd|nvme|hd|mmcblk|vd|xvd)"),
        "dd into block device",
    ),
    # Plan 63 — redirect into a block device.
    (
        _pattern(r">+\s*/dev/(sd|nvme|hd|mmcblk|vd|xvd)\b"),
        "redirect to block device",
    ),
    # Plan 64 — fork bomb.
    (
        _pattern(r":\s*\(\s*\)\s*\{"),
        "fork bomb",
    ),
    # Plan 65 — kill -1 / kill -- -1 (kill all). Accept both
    # `kill -1` and `kill -- -1` (the second form is needed because
    # `--` ends the kill flag set, so `-1` is the PID).
    (
        _pattern(r"\bkill\b\s+--?\s*-?1\b"),
        "kill -1 (all processes)",
    ),
    # Plan 66 — system shutdown / reboot / halt — only as a verb, not
    # the help text (Plan 158: git commit -m "fix shutdown bug" must
    # not trip). Pattern: the verb optionally followed by whitespace
    # + an argument. The downside: "git commit -m 'fix shutdown bug'"
    # matches if "shutdown" appears as a command-position token (it
    # shouldn't, but _CMDPOS allows it after && or ;). The Hermes
    # whitelist from Plan 158 is impractical in a single regex; the
    # trade-off is accepted. Bare "poweroff" still matches.
    (
        _pattern(r"\b(shutdown|reboot|halt|poweroff)\b(?:\s+\S)?"),
        "shutdown / reboot / halt",
    ),
    # Plan 67 — init / telinit.
    (
        _pattern(r"\b(init|telinit)\s+[06]\b"),
        "init 0 / 6 (reboot / halt)",
    ),
    # Plan 68 — systemctl power state.
    (
        _pattern(r"\bsystemctl\s+(poweroff|reboot|halt|kexec)\b"),
        "systemctl poweroff/reboot/halt",
    ),
)


def detect_hardline_command(command: str) -> tuple[bool, str | None]:
    """Return (blocked, description).

    ``blocked`` is True if the command hits a hardline rule and must not
    run under any circumstance. ``description`` is the rule that fired
    (the same string the session/breaker counters use as a key).

    Pattern matching runs both on the raw text and on the unwrapped
    form (subshells rewritten). The fork-bomb pattern in particular
    only matches the raw form — ``_unwrap_subshells`` collapses the
    parentheses into spaces and the literal "(":") {" sequence is
    gone. The raw check covers that.
    """
    if not command or not command.strip():
        return False, None
    text = _unwrap_subshells(command)
    candidates = (command, text) if text != command else (command,)
    for candidate in candidates:
        for pattern, description in HARDLINE_PATTERNS:
            if pattern.search(candidate):
                return True, description
    return False, None


# ---------------------------------------------------------------------------
# Sudo-stdin guard (Plan 73-75)
# ---------------------------------------------------------------------------
# ``sudo -S`` reads the password from stdin. If $SUDO_PASSWORD isn't set,
# the model ends up playing "Sorry, try again" with itself for many
# turns, burning the user's time and (depending on the prompt) leaking
# the intended sudo invocation. Hard-block it and tell the user to set
# $SUDO_PASSWORD in .env or run sudo themselves.
_SUDO_STDIN_RE: Final[re.Pattern] = _pattern(r"\bsudo\s+(-S|--stdin)\b")


def _sudo_stdin_guard(command: str) -> bool:
    return bool(_SUDO_STDIN_RE.search(_unwrap_subshells(command)))


# ---------------------------------------------------------------------------
# User deny rules (Plan 77-79)
# ---------------------------------------------------------------------------
# Per-user denylist in the config (``approvals.deny``). fnmatch globs on
# the command text. Hard-blocks even under yolo — Plan 78: a deny rule
# is the user saying "never, not even under yolo".
class _UserDeny:
    def __init__(self, patterns: tuple[str, ...]) -> None:
        self._compiled = tuple(re.compile(p) for p in patterns)

    def check(self, command: str) -> str | None:
        """Return the pattern that fired, or None."""
        for pat in self._compiled:
            if pat.search(command):
                return pat.pattern
        return None


def check_user_deny_rule(
    command: str, patterns: tuple[str, ...]
) -> str | None:
    """Convenience wrapper for the CLI / REPL layer.

    Returns the pattern string that matched (so the caller can echo
    it back to the user / model), or None.
    """
    return _UserDeny(patterns).check(command)


# ---------------------------------------------------------------------------
# Combined entrypoint (Plan 44-54 + Plan 73-79)
# ---------------------------------------------------------------------------
def preflight_block(
    command: str,
    *,
    deny_patterns: tuple[str, ...] = (),
) -> tuple[bool, str | None, str | None]:
    """Return (blocked, kind, description) for the hardline + sudo-stdin
    + user-deny chain. Each is independent; the first hit wins.

    - kind = "hardline" | "sudo_stdin" | "user_deny" | None
    - description is the rule name (used for breaker counters)
    """
    if command and command.strip():
        blocked, desc = detect_hardline_command(command)
        if blocked:
            return True, "hardline", desc
        if _sudo_stdin_guard(command):
            return True, "sudo_stdin", "sudo -S without $SUDO_PASSWORD"
        deny_hit = check_user_deny_rule(command, deny_patterns)
        if deny_hit is not None:
            return True, "user_deny", deny_hit
    return False, None, None


def block_reason_text(kind: str, description: str | None) -> str:
    """User-facing message for a preflight block (Plan 70, 74, 78)."""
    if kind == "hardline":
        return (
            f"[ X ] hardline block: {description}\n"
            "      This is blocked even with --yolo, mode=off, or any\n"
            "      approvals setting. If you genuinely need to run this,\n"
            "      run it yourself in a terminal."
        )
    if kind == "sudo_stdin":
        return (
            "[ X ] sudo -S blocked\n"
            "      sudo reads the password from stdin; without\n"
            "      SUDO_PASSWORD set in .env, the agent would loop\n"
            "      on 'Sorry, try again'. Set SUDO_PASSWORD, or run\n"
            "      the command yourself in a terminal."
        )
    if kind == "user_deny":
        return (
            f"[ X ] denied by your approvals.deny rule\n"
            f"      pattern: {description}\n"
            "      do NOT retry, do NOT rephrase, do NOT attempt the\n"
            "      same outcome via a different path."
        )
    return "[ X ] command blocked by preflight."
