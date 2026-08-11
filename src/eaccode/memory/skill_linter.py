"""Skill linter (A.4) — convention enforcement for SKILL.md files.

Every skill must follow the same shape so discovery, prompt injection
and the curator can rely on it. Rules (12):

    R1  frontmatter exists (--- delimited block)
    R2  frontmatter has a `name`
    R3  frontmatter has a `description`
    R4  description <= 57 chars (the system-prompt index truncates)
    R5  name is a slug (lowercase, hyphens)
    R6  triggers, when present, is a YAML list
    R7  platform, when present, is windows|linux|darwin
    R8  body is non-empty
    R9  file <= 600 lines (maintainability cap)
    R10 no [SKILL_PRUNED] markers (ghost residue)
    R11 file is valid UTF-8 (no binary garbage)
    R12 provenance, when present, is bundled|user|curator|pinned

Pure functions — no IO beyond reading the given path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from eaccode.memory.skills import parse_skill_frontmatter

MAX_DESCRIPTION_CHARS = 57
MAX_LINES = 600
VALID_PLATFORMS = ("windows", "linux", "darwin")
VALID_PROVENANCES = ("bundled", "user", "curator", "pinned")


@dataclass(frozen=True)
class LintIssue:
    rule: str
    message: str


def lint_skill(path: Path) -> list[LintIssue]:
    """Lint one skill file; returns [] when everything is fine."""
    issues: list[LintIssue] = []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [LintIssue("R11", "file is not valid UTF-8 (binary garbage?)")]

    if not text.startswith("---"):
        issues.append(LintIssue("R1", "missing YAML frontmatter (--- block)"))
        return issues  # nothing else to check without meta

    meta, body = parse_skill_frontmatter(text)

    if not meta.get("name"):
        issues.append(LintIssue("R2", "frontmatter has no `name`"))
    else:
        name = str(meta["name"])
        if name != name.lower() or " " in name or "_" in name:
            issues.append(
                LintIssue("R5", f"name {name!r} is not a slug "
                                "(lowercase, hyphens only)")
            )

    if "description" not in meta:
        issues.append(LintIssue("R3", "frontmatter has no `description`"))
    else:
        desc = str(meta["description"])
        if len(desc) > MAX_DESCRIPTION_CHARS:
            issues.append(
                LintIssue("R4", f"description is {len(desc)} chars "
                                f"(max {MAX_DESCRIPTION_CHARS})")
            )

    if "triggers" in meta and not isinstance(meta["triggers"], (list, tuple)):
        issues.append(LintIssue("R6", "`triggers` must be a YAML list"))

    platform = meta.get("platform")
    if platform and str(platform) not in VALID_PLATFORMS:
        issues.append(
            LintIssue("R7", f"platform {platform!r} not in "
                            f"{'/'.join(VALID_PLATFORMS)}")
        )

    provenance = meta.get("provenance")
    if provenance and str(provenance) not in VALID_PROVENANCES:
        issues.append(
            LintIssue("R12", f"provenance {provenance!r} not in "
                             f"{'/'.join(VALID_PROVENANCES)}")
        )

    if not body.strip():
        issues.append(LintIssue("R8", "body is empty"))

    if len(text.splitlines()) > MAX_LINES:
        issues.append(
            LintIssue("R9", f"file has {len(text.splitlines())} lines "
                            f"(max {MAX_LINES})")
        )

    if "[SKILL_PRUNED]" in text:
        issues.append(LintIssue("R10", "contains [SKILL_PRUNED] ghost marker"))

    return issues


def lint_skills_dir(skills_dir: Path) -> dict[str, list[LintIssue]]:
    """Lint every markdown file under *skills_dir* (path -> issues)."""
    if not skills_dir.is_dir():
        return {}
    result: dict[str, list[LintIssue]] = {}
    for f in sorted(skills_dir.rglob("*.md")):
        issues = lint_skill(f)
        if issues:
            result[str(f)] = issues
    return result
