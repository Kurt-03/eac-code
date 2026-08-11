"""Skill preprocessing (A.5) — template vars + inline shell blocks.

Two Hermes-style conveniences applied right before a skill's content is
injected into the prompt:

- ``{{cwd}}`` (and ``{{workdir}}``) are replaced with the session workdir.
- fenced ``shell`` blocks are executed and their stdout is spliced into
  the content (errors become a visible comment — never a crash). This is
  for *local* skills the user installed; the timeout keeps runaway
  scripts in check.

Pure functions; the shell execution runs synchronously with a timeout.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from eaccode.memory.skills import Skill

SHELL_TIMEOUT_S = 10.0
_SHELL_BLOCK = re.compile(
    r"```shell\n(.*?)```", re.DOTALL
)


def substitute_template_vars(content: str, workdir: Path) -> str:
    """Replace {{cwd}} / {{workdir}} with the resolved workdir."""
    return (
        content.replace("{{cwd}}", str(workdir))
        .replace("{{workdir}}", str(workdir))
    )


def _run_shell(script: str, workdir: Path) -> str:
    """Run one shell block; returns a markdown-fenced result."""
    try:
        proc = subprocess.run(
            script,
            shell=True,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=SHELL_TIMEOUT_S,
        )
        if proc.returncode == 0:
            return "```text\n" + proc.stdout.rstrip() + "\n```\n"
        return (
            f"```text\n[inline shell exited {proc.returncode}]\n"
            + proc.stderr.rstrip()[:500]
            + "\n```\n"
        )
    except subprocess.TimeoutExpired:
        return f"```text\n[inline shell timed out after {SHELL_TIMEOUT_S}s]\n```\n"
    except OSError as e:
        return f"```text\n[inline shell error: {e}]\n```\n"


def run_inline_shell(content: str, workdir: Path) -> str:
    """Execute every fenced shell block and splice stdout into the content."""
    def _replace(m: re.Match) -> str:
        return _run_shell(m.group(1), workdir)

    return _SHELL_BLOCK.sub(_replace, content)


def preprocess_skill(skill: Skill, workdir: Path) -> Skill:
    """Return a copy of *skill* with template vars and inline shell applied."""
    content = substitute_template_vars(skill.content, workdir)
    content = run_inline_shell(content, workdir)
    if content == skill.content:
        return skill
    return Skill(
        name=skill.name,
        description=skill.description,
        content=content,
        source=skill.source,
        last_used=skill.last_used,
        triggers=skill.triggers,
        platform=skill.platform,
        provenance=skill.provenance,
    )
