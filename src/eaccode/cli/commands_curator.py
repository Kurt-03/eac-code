"""CLI sub-commands — registered onto the main click group on import."""
from __future__ import annotations

from eaccode.cli import main
from eaccode.cli._output import print_info
from eaccode.config.paths import EaccodePaths
from eaccode.config.settings import Settings

# ------------------------------------------------------------------ curator

@main.group()
def curator() -> None:
    """Self-maintenance: stale skills, memory dedupe."""


@curator.command("run")
def curator_run() -> None:
    """Scan skills + memory and write a maintenance report."""

    from eaccode.curator.curator import dedupe_memory, find_stale_skills
    from eaccode.memory.skills import discover_skills

    paths = EaccodePaths()
    settings = Settings.load(paths.settings_file)
    report: list[str] = [
        "# Curator report",
        f"generated: {__import__('datetime').datetime.now().isoformat()}",
    ]

    # 1. stale skills (proposal only — never delete automatically)
    skills = discover_skills([paths.skills_dir])
    stale = find_stale_skills(skills, stale_after_days=settings.curator.stale_after_days)
    if stale:
        report.append(f"\n## Stale skills (> {settings.curator.stale_after_days} days untouched)")
        for s in stale:
            report.append(f"- {s.name} ({s.source.name}, last used {s.last_used:%Y-%m-%d})")
        report.append("  → delete manually or patch them to keep them fresh")
    else:
        report.append("\n## Stale skills\nNone — all skills are fresh.")

    # 2. memory dedupe (automatic, safe)
    deduped_total = 0
    for mem_file in paths.memory_dir.glob("*.jsonl"):
        import json as jsonlib

        lines = mem_file.read_text(encoding="utf-8").splitlines()
        if not lines:
            continue
        entries = []
        for ln in lines:
            try:
                entries.append(jsonlib.loads(ln))
            except Exception:
                continue
        texts = [e.get("text", "") for e in entries]
        cleaned = dedupe_memory(texts)
        if len(cleaned) < len(texts):
            deduped_total += len(texts) - len(cleaned)
            deduped_entries = []
            seen = set()
            for e in entries:
                key = " ".join(e.get("text", "").lower().split())
                if key not in seen:
                    seen.add(key)
                    deduped_entries.append(e)
            mem_file.write_text(
                "".join(jsonlib.dumps(e, ensure_ascii=False) + "\n" for e in deduped_entries),
                encoding="utf-8",
            )
    report.append(f"\n## Memory\n{deduped_total} duplicate facts removed.")

    report_path = paths.data_dir / "curator_report.md"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print_info("\n".join(report))
    print_info(f"\nReport saved: {report_path}")


@curator.command("report")
def curator_report() -> None:
    """Show the last curator report."""
    paths = EaccodePaths()
    report = paths.data_dir / "curator_report.md"
    if not report.exists():
        print_info("No report yet. Run `eaccode curator run` first.")
        return
    print_info(report.read_text(encoding="utf-8"))


