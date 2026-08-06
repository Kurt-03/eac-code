"""Skill discovery (Task 6.1) — markdown files with YAML frontmatter."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml


@dataclass
class Skill:
    name: str
    description: str
    content: str
    source: Path
    last_used: datetime | None = field(default=None)  # file mtime = last touched


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split YAML frontmatter (--- delimited) from the markdown body."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            try:
                meta = yaml.safe_load(text[3:end]) or {}
            except yaml.YAMLError:
                meta = {}
            return meta, text[end + 4 :].lstrip("\n")
    return {}, text


def discover_skills(paths: list[Path]) -> list[Skill]:
    skills: list[Skill] = []
    for p in paths:
        if not p.exists():
            continue
        for f in sorted(p.glob("*.md")):
            try:
                meta, body = _parse_frontmatter(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            skills.append(
                Skill(
                    name=meta.get("name") or f.stem,
                    description=meta.get("description", ""),
                    content=body,
                    source=f,
                    last_used=datetime.fromtimestamp(f.stat().st_mtime),
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
