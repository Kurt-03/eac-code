"""Skill discovery (Task 6.1 / A.1) — markdown files with YAML frontmatter.

A.1 adds the full frontmatter surface (name/description/triggers/platform),
robust parsing for broken frontmatter, and a platform filter. A.3 adds
provenance (bundled/user/curator/pinned): the provenance is derived from
the directory layout (``bundled/`` subdir) unless the frontmatter
overrides it; ``pinned`` lives in the usage sidecar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

from eaccode.memory.skill_usage import last_used_ts

PROVENANCES = ("bundled", "user", "curator", "pinned")


@dataclass
class Skill:
    name: str
    description: str
    content: str
    source: Path
    last_used: datetime | None = field(default=None)  # file mtime = last touched
    triggers: list[str] = field(default_factory=list)
    platform: str | None = None  # windows | linux | darwin | null = any
    provenance: str = "user"  # bundled | user | curator | pinned


def parse_skill_frontmatter(text: str) -> tuple[dict, str]:
    """Split YAML frontmatter (--- delimited) from the markdown body.

    Broken frontmatter never raises: on YAML errors the whole text is
    treated as body and the meta is empty (the skill still loads).
    """
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            try:
                meta = yaml.safe_load(text[3:end]) or {}
            except yaml.YAMLError:
                return {}, text
            if not isinstance(meta, dict):
                return {}, text
            return meta, text[end + 4 :].lstrip("\n")
    return {}, text


def platform_matches(meta: dict, current: str | None = None) -> bool:
    """True when the skill's `platform` allows the current OS.

    ``platform`` may be a single name or a list. Unset/missing means any.
    """
    import sys

    wanted = meta.get("platform")
    if not wanted:
        return True
    if isinstance(wanted, str):
        wanted = [wanted]
    current = current or sys.platform
    current = "windows" if current == "win32" else current
    return current in wanted


def _provenance_for(path: Path, meta: dict) -> str:
    override = meta.get("provenance")
    if override in PROVENANCES:
        return override
    parts = path.parts
    if "bundled" in parts:
        return "bundled"
    return "user"


def discover_skills(paths: list[Path]) -> list[Skill]:
    skills: list[Skill] = []
    for p in paths:
        if not p.exists():
            continue
        for f in sorted(p.rglob("*.md")):
            try:
                text = f.read_text(encoding="utf-8")
            except OSError:
                continue
            meta, body = parse_skill_frontmatter(text)
            if not platform_matches(meta):
                continue
            # Real usage signal (P0.4) beats the mtime fallback: mtime is
            # the last *edit*, not the last *use*.
            ts = last_used_ts(f)
            last_used = (
                datetime.fromtimestamp(ts)
                if ts is not None
                else datetime.fromtimestamp(f.stat().st_mtime)
            )
            triggers = meta.get("triggers") or []
            if isinstance(triggers, str):
                triggers = [triggers]
            skills.append(
                Skill(
                    name=meta.get("name") or f.stem,
                    description=meta.get("description", ""),
                    content=body,
                    source=f,
                    last_used=last_used,
                    triggers=[str(t) for t in triggers],
                    platform=str(meta["platform"]) if meta.get("platform") else None,
                    provenance=_provenance_for(f, meta),
                )
            )
    return skills


def skills_to_system_prompt_section(skills: list[Skill]) -> str:
    if not skills:
        return ""
    sections = ["# Available Skills\n"]
    for s in skills:
        header = f"## {s.name}"
        if s.description:
            header += f" — {s.description}"
        sections.append(f"{header}\n\n{s.content}\n---\n")
    return "\n".join(sections)
