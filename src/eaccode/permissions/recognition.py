"""Command-verb detection helpers (Plan P3.4, Punkte 147-160).

Variants of recognition the policy layer needs to know about:

  - short-flag alias expansion (eaccode aliases ``-rf`` -> ``-r -f``,
    ``-fr`` -> ``-r -f``)
  - compound verb expansion (``rm -rf`` -> ``rm -r -f``)
  - per-token argument classification (path / url / pattern / etc.)
  - argument shape normalization (``--foo=bar`` vs ``--foo bar``)

Hermes covers 5 lex variants (Plan 151-160). We implement the four
that actually matter for the danger table:

  1. expand_short_flags("rm -rf")   -> "rm -r -f"
  2. expand_short_flags("ls -la")   -> "ls -l -a"
  3. normalize_eq_form("--foo=bar")-> "--foo bar"
  4. normalize_eq_form("--foo bar")-> "--foo bar"  (no-op)
"""

from __future__ import annotations

import re
from typing import Final

# Recognized short aliases for the verbs that the danger table cares
# about. Mirrors GNU getopt(1) behaviour — see eaccode's
# tools/builtin/bash.py for the runtime interpreter's view of the
# same flags. We extend the table conservatively; users can add more.
_SHORT_ALIASES: Final[dict[str, dict[str, str]]] = {
    "rm": {
        "r": "recursive",
        "f": "force",
        "i": "interactive",
        "v": "verbose",
    },
    "ls": {
        "l": "long",
        "a": "all",
        "h": "human-readable",
        "R": "recursive",
        "1": "one-column",
    },
    "cp": {
        "r": "recursive",
        "f": "force",
        "i": "interactive",
        "v": "verbose",
    },
    "mv": {
        "f": "force",
        "i": "interactive",
        "v": "verbose",
    },
    "chmod": {
        "R": "recursive",
        "v": "verbose",
        "f": "silent",
    },
    "kill": {
        "9": "sigkill",
        "1": "sighup",
    },
    "find": {
        "L": "follow",
    },
}


def expand_short_flags(command: str) -> str:
    """Plan 151: explode short-flag clusters like ``-rf`` -> ``-r -f``.

    Only expansions listed in ``_SHORT_ALIASES`` are honoured — unknown
    verbs are left untouched so a custom command with ``-rf`` semantics
    doesn't get clobbered. A cluster is expanded atomically: if any
    character in it has no alias, the entire cluster is kept as a
    single token (some tools use ``-xyz`` as a single named flag).
    """
    parts = command.split()
    if not parts:
        return command
    verb = parts[0]
    aliases = _SHORT_ALIASES.get(verb, {})

    out: list[str] = [verb]
    cluster_re = re.compile(r"^-([A-Za-z0-9]{2,})$")
    for token in parts[1:]:
        m = cluster_re.match(token)
        if m and all(ch in aliases for ch in m.group(1)):
            out.extend("-" + ch for ch in m.group(1))
            continue
        # Either not a cluster (single flag or single arg) or has unknown
        # char — keep as-is.
        out.append(token)
    return " ".join(out)


# Argument-shape normalization: --foo=bar -> --foo bar
_EQ_FORM_RE: Final[re.Pattern] = re.compile(
    r"--?([A-Za-z][A-Za-z0-9_-]*)=(\S+)"
)


def normalize_eq_form(command: str) -> str:
    """Plan 157: rewrite ``--foo=bar`` -> ``--foo bar``.

    This matters because the danger-table predicates scan the command
    string with regexes like ``\brm\b``. Without normalization, a
    command line like ``command -rf=path`` would survive the alias
    expand but the rm-regex wouldn't match because the verb itself
    wasn't present. (Pretty unlikely in practice, but Plan 157 calls
    it out.)
    """
    return _EQ_FORM_RE.sub(r"--\1 \2", command)


def first_verb(command: str) -> str | None:
    """Plan 149: extract the first verb token, ignoring sudo/doas/etc.

    Strips leading wrappers (sudo, doas, pkexec, run0, env, nice).
    For ``env FOO=bar bash`` we strip ``env`` then skip the FOO=bar
    assignment so the verb comes back as ``bash``.
    """
    if not command:
        return None
    # Wrapper prefixes that take either no extra arg or one --user flag.
    no_arg_prefixes = {"sudo", "doas", "pkexec", "run0", "nice"}
    prefixes_with_arg = {"env"}

    parts = command.split()
    while parts and parts[0] in no_arg_prefixes:
        parts.pop(0)
        # ``sudo -u user`` / ``sudo -k`` — skip the flag (and optionally value)
        if parts and parts[0].startswith("-"):
            parts.pop(0)
            # ``sudo -u user`` — skip the user arg that follows -u
            if parts and len(parts) and not parts[0].startswith("-"):
                # Heuristic: this is a value for the flag, skip too.
                # But be conservative — only skip when next looks like a flag value
                pass
    if parts and parts[0] in prefixes_with_arg:
        parts.pop(0)
        # env followed by FOO=bar assignments — skip them
        while parts and "=" in parts[0] and not parts[0].startswith("-"):
            parts.pop(0)
    return parts[0] if parts else None


def is_absolute_path(token: str) -> bool:
    """Plan 159: True if *token* is an absolute path (Unix or Windows)."""
    if not token:
        return False
    return token.startswith(("/", "~", "$HOME", "${HOME}")) or (
        len(token) >= 3 and token[1] == ":" and token[2] in ("/", "\\")
    )


def classify_arg(token: str) -> str:
    """Plan 154: classify a single argument token.

    Returns one of:
      ``path``     — absolute or relative file path
      ``url``      — http(s) URL
      ``flag``     — anything starting with ``-``
      ``keyword``  — otherwise
    """
    if not token:
        return "keyword"
    if token.startswith("-"):
        return "flag"
    if re.match(r"^https?://", token, re.IGNORECASE):
        return "url"
    if is_absolute_path(token):
        return "path"
    if "/" in token or "\\" in token:
        return "path"
    return "keyword"


def normalize_command(command: str) -> str:
    """Apply expansion + normalization in the right order."""
    if not command:
        return command
    cmd = normalize_eq_form(command)
    cmd = expand_short_flags(cmd)
    return cmd
