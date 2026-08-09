"""Coding-context awareness — workspace snapshot for the system prompt (H.2).

Ported from Hermes' ``agent/coding_context.py`` (``build_coding_workspace_block``
+ ``detect_project_facts``). When eaccode runs inside a git repo, the
system prompt gets a stable snapshot: branch → upstream → ahead/behind,
worktree note, staged/modified/untracked/conflict counts, last 3 commits,
and detected project facts (manifests, package manager, verify commands,
context files).

The agent therefore knows the git state and how to run tests WITHOUT
guessing. All git calls go through ``bounded_git_probe`` (Phase A.4), so
a private remote can never hang the prompt build on a credential prompt.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from eaccode._subprocess_compat import bounded_git_probe

_PROJECT_MARKERS = (
    "pyproject.toml", "package.json", "Cargo.toml", "go.mod", "pom.xml",
    "build.gradle", "Gemfile", "composer.json", "mix.exs", "Makefile",
)
_CONTEXT_FILES = ("AGENTS.md", "CLAUDE.md", ".cursorrules", "EACCODE.md")
_PY_LOCKFILES = (("uv.lock", "uv"), ("poetry.lock", "poetry"), ("Pipfile.lock", "pipenv"))
_JS_LOCKFILES = (("package-lock.json", "npm"), ("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"))
_VERIFY_TARGETS = ("test", "tests", "check", "lint", "verify")
_MAX_VERIFY_COMMANDS = 6


@dataclass
class ProjectFacts:
    """Structured project facts — detected once, consumed everywhere."""

    manifests: list[str]
    package_managers: list[str]
    verify_commands: list[str]
    context_files: list[str]


def _read_small(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:200_000]
    except OSError:
        return ""


def _git_root(cwd: Path) -> Path | None:
    """Find the git root of cwd, or None (fail-open)."""
    cur = cwd.resolve()
    while True:
        if (cur / ".git").exists():
            return cur
        if cur.parent == cur:
            return None
        cur = cur.parent


def detect_project_facts(root: Path) -> ProjectFacts:
    """Detect manifests, package manager(s), verify commands, context files."""
    manifests = [
        m for m in _PROJECT_MARKERS
        if m not in _CONTEXT_FILES and (root / m).is_file()
    ]
    package_managers = list(
        dict.fromkeys(
            pm for lock, pm in (*_PY_LOCKFILES, *_JS_LOCKFILES)
            if (root / lock).is_file()
        )
    )

    verify: list[str] = []
    if (root / "scripts" / "run_tests.sh").is_file():
        verify.append("scripts/run_tests.sh")
    if (root / "package.json").is_file():
        try:
            scripts = json.loads(_read_small(root / "package.json") or "{}").get("scripts") or {}
        except (json.JSONDecodeError, AttributeError):
            scripts = {}
        js_pm = next((pm for lock, pm in _JS_LOCKFILES if (root / lock).is_file()), "npm")
        verify.extend(f"{js_pm} run {name}" for name in _VERIFY_TARGETS if name in scripts)
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        text = _read_small(pyproject)
        if "[tool.pytest" in text or "pytest" in text:
            verify.append("pytest")
    if (root / "pytest.ini").is_file():
        verify.append("pytest")
    makefile = _read_small(root / "Makefile")
    if makefile:
        verify.extend(
            f"make {name}" for name in _VERIFY_TARGETS
            if re.search(rf"^{re.escape(name)}\s*:", makefile, re.MULTILINE)
        )

    return ProjectFacts(
        manifests=manifests,
        package_managers=package_managers,
        verify_commands=list(dict.fromkeys(verify))[:_MAX_VERIFY_COMMANDS],
        context_files=[c for c in _CONTEXT_FILES if (root / c).is_file()],
    )


def _project_facts_lines(root: Path) -> list[str]:
    """Render project facts as workspace-snapshot lines."""
    f = detect_project_facts(root)
    facts: list[str] = []
    if f.manifests:
        line = f"- Project: {', '.join(f.manifests[:6])}"
        if f.package_managers:
            line += f" ({'/'.join(f.package_managers)})"
        facts.append(line)
    if f.verify_commands:
        facts.append(f"- Verify: {'; '.join(f.verify_commands)}")
    if f.context_files:
        facts.append(f"- Context files: {', '.join(f.context_files)}")
    return facts


def _parse_status(porcelain: str) -> tuple[dict[str, str], dict[str, int]]:
    """Parse `git status --porcelain=2 --branch` into (branch, counts).

    Branch headers look like `# branch.head feature/x`,
    `# branch.upstream origin/main`, `# branch.ab +1 -2`.
    """
    branch: dict[str, str] = {}
    counts = {"staged": 0, "modified": 0, "untracked": 0, "conflicts": 0}
    for line in porcelain.splitlines():
        if line.startswith("# branch."):
            # "# branch.head feature/x" → key="head", value="feature/x"
            # (strip the 7-char "branch." prefix)
            parts = line.split()
            if len(parts) >= 3:
                branch[parts[1][7:]] = parts[2]
            continue
        if line.startswith("1 ") or line.startswith("2 "):
            counts["staged"] += 1
        elif line.startswith("u "):
            counts["conflicts"] += 1
        elif line.startswith("?"):
            counts["untracked"] += 1
        elif line.startswith("."):
            counts["modified"] += 1
    return branch, counts


def build_coding_workspace_block(cwd: Path | str | None = None) -> str:
    """Workspace snapshot for the system prompt ("" outside a workspace).

    Git state (branch/status/commits) when cwd is in a repo, plus
    detected project facts — so marker-only (non-git) projects still get
    a snapshot. Byte-stable per session so the prompt cache stays valid.
    """
    resolved = Path(cwd or Path.cwd()).resolve()
    root = _git_root(resolved)
    if root is None:
        return ""

    lines = ["Workspace (snapshot at session start — re-check with `git` before acting on it):"]
    lines.append(f"- Root: {root}")

    porcelain = bounded_git_probe(
        ["git", "-C", str(root), "status", "--porcelain=2", "--branch"], timeout=15
    )
    if porcelain:
        branch, counts = _parse_status(porcelain)
        head = branch.get("head", "")
        if head and head != "(detached)":
            line = f"- Branch: {head}"
            if branch.get("upstream"):
                line += f" → {branch['upstream']}"
                ahead, behind = branch.get("ahead", "0"), branch.get("behind", "0")
                if ahead != "0" or behind != "0":
                    line += f" (ahead {ahead}, behind {behind})"
            lines.append(line)
        elif head == "(detached)":
            lines.append("- Branch: (detached HEAD)")

        # Linked worktree detection (state shared with primary tree).
        git_dir = bounded_git_probe(
            ["git", "-C", str(root), "rev-parse", "--git-dir"], timeout=10
        )
        common_dir = bounded_git_probe(
            ["git", "-C", str(root), "rev-parse", "--git-common-dir"], timeout=10
        )
        if git_dir and common_dir and Path(git_dir).resolve() != Path(common_dir).resolve():
            lines.append("- Worktree: linked (git state shared with primary tree)")

        dirty = [f"{n} {label}" for label, n in (
            ("staged", counts["staged"]), ("modified", counts["modified"]),
            ("untracked", counts["untracked"]), ("conflicts", counts["conflicts"]),
        ) if n]
        lines.append(f"- Status: {', '.join(dirty) if dirty else 'clean'}")

        recent = bounded_git_probe(
            ["git", "-C", str(root), "log", "-3", "--pretty=%h %s"], timeout=10
        )
        if recent:
            lines.append("- Recent commits:")
            lines.extend(f"    {c}" for c in recent.splitlines())

    lines.extend(_project_facts_lines(root))
    return "\n".join(lines)
