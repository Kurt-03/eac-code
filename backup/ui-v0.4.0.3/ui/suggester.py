"""Input suggestions for the REPL — Textual ``Suggester`` subclass.

Ported from Hermes' ``SlashCommandCompleter`` (``hermes_cli/commands.py``),
adapted to Textual's single-suggestion API (``get_suggestion(value) -> str | None``).

Suggestion sources, in priority order:
1. ``/``-prefix  → command (or alias) whose name starts with the typed
   text; subcommand completion after ``/cmd <prefix>``. Picker commands
   (``/model``, ``/mode``, ...) get NO trailing space so Enter executes
   them instead of filling an argument (Hermes ``_PICKER_COMMANDS``).
2. ``@``-prefix  → Claude Code-style context references (``@diff``,
   ``@staged``, ``@file:``, ``@folder:``, ``@git:``, ``@url:``) plus
   project-file fuzzy matching.
3. path-like word (``./``, ``../``, ``~/``, contains ``/``, not a URL
   scheme) → file/directory completion in the word's directory.
"""

from __future__ import annotations

import os
from pathlib import Path

from textual.suggester import Suggester

from eaccode.ui.command_def import COMMAND_REGISTRY, get_command

# Commands that open pickers when run without arguments — no trailing
# space in completions (Hermes _PICKER_COMMANDS semantics).
_PICKER_COMMANDS = frozenset(
    cmd.name for cmd in COMMAND_REGISTRY if cmd.picker
)

_STATIC_CONTEXT_REFS = (
    ("@diff", "Git working tree diff"),
    ("@staged", "Git staged diff"),
    ("@file:", "Attach a file"),
    ("@folder:", "Attach a folder"),
    ("@git:", "Git log with diffs (e.g. @git:5)"),
    ("@url:", "Fetch web content"),
)

# Delimiters that end the current "word" when scanning backwards.
_WHITESPACE = " \t\n"


class SlashCommandSuggester(Suggester):
    """Suggest slash commands, subcommands, @-refs, and paths."""

    def __init__(self, cwd: Path | None = None) -> None:
        super().__init__()
        self._cwd = Path(cwd or Path.cwd())
        self._file_cache: list[str] = []
        self._file_cache_time = 0.0

    # ------------------------------------------------------------ commands

    async def get_suggestion(self, value: str) -> str | None:
        """Textual calls this on every keystroke; return one suggestion.

        Textual's Suggester API is async — the base class awaits the
        result on every keystroke.
        """
        if not value:
            return None
        if value.startswith("/"):
            return self._slash_completion(value)
        ctx_word = self._extract_word(value)
        if ctx_word and ctx_word.startswith("@"):
            return self._context_completion(ctx_word)
        path_word = self._extract_path_word(value)
        if path_word is not None:
            return self._path_completion(path_word)
        return None

    def _slash_completion(self, text: str) -> str | None:
        """Complete `/cmd ...` with subcommand or command-name support."""
        parts = text.split(maxsplit=1)
        base = parts[0].lower()

        # Subcommand completion: /cmd <prefix>
        if len(parts) > 1:
            entry = get_command(base)
            if entry and entry.subcommands:
                sub_prefix = parts[1].lower()
                for sub in entry.subcommands:
                    if sub.startswith(sub_prefix) and sub != sub_prefix:
                        return f"{base} {sub}"
            return None  # args are free text (paths, names)

        # Command-name completion: /prefix
        word = base[1:]
        best: str | None = None
        for cmd in COMMAND_REGISTRY:
            for candidate in (cmd.name, *cmd.aliases):
                if candidate.startswith(word) and candidate != word:
                    if best is None or len(candidate) < len(best):
                        best = candidate
                    break
        if best is None:
            return None
        if best in _PICKER_COMMANDS:
            return f"/{best}"
        return f"/{best} "

    # ------------------------------------------------------------- context

    @staticmethod
    def _extract_word(text: str) -> str | None:
        """The whitespace-delimited word under the cursor."""
        i = len(text) - 1
        while i >= 0 and text[i] not in _WHITESPACE:
            i -= 1
        return text[i + 1 :] or None

    def _context_completion(self, word: str) -> str | None:
        lowered = word.lower()
        for candidate, _meta in _STATIC_CONTEXT_REFS:
            if candidate.lower().startswith(lowered) and candidate.lower() != lowered:
                return candidate
        # @file: / @folder: with a path prefix → path completion
        for prefix in ("@file:", "@folder:"):
            if lowered.startswith(prefix):
                rest = word[len(prefix) :]
                if not rest:
                    return f"{prefix}"
                return prefix + (self._path_completion(rest) or rest)
        # @git:N
        if lowered.startswith("@git:"):
            return word  # already complete enough; leave the number to the user
        return None

    # ---------------------------------------------------------------- paths

    @staticmethod
    def _extract_path_word(text: str) -> str | None:
        """Return the current word if it looks like a file path."""
        if not text:
            return None
        i = len(text) - 1
        while i >= 0 and text[i] != " ":
            i -= 1
        word = text[i + 1 :]
        if not word:
            return None
        # URLs contain "/" but are not local paths — never listdir("https:").
        if "://" in word:
            return None
        if word.startswith(("./", "../", "~/", "/", "@file:", "@folder:")) or "/" in word:
            return word
        return None

    def _path_completion(self, word: str) -> str | None:
        """Complete a path prefix to the first matching entry (dirs get '/').
        Falls back to the typed word when nothing matches."""
        expanded = os.path.expanduser(word)
        if expanded.endswith("/"):
            search_dir, prefix = expanded, ""
        else:
            search_dir = os.path.dirname(expanded) or "."
            prefix = os.path.basename(expanded)
        try:
            entries = sorted(os.listdir(search_dir))
        except OSError:
            return None
        prefix_lower = prefix.lower()
        for entry in entries:
            if prefix and not entry.lower().startswith(prefix_lower):
                continue
            full = os.path.join(search_dir, entry)
            suffix = "/" if os.path.isdir(full) else ""
            display = self._display_path(word, full)
            return display + suffix
        return None

    @staticmethod
    def _display_path(typed: str, full: str) -> str:
        """Render the completion the way the user typed the prefix.

        Windows: os.path.relpath returns backslashes; the user typed
        forward slashes — normalize to '/' so the completion matches
        what they're typing.  Relative prefixes (./) are preserved so
        the completion stays consistent with the typed word.
        """
        if typed.startswith("~"):
            display = "~/" + os.path.relpath(full, os.path.expanduser("~"))
        elif os.path.isabs(typed):
            display = full
        else:
            prefix = ""
            for p in ("./", "../"):
                if typed.startswith(p):
                    prefix = p
                    break
            display = prefix + os.path.relpath(full)
        return display.replace("\\", "/")
