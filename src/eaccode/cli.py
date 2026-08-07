"""CLI entry point (Task 1.4).

Command hierarchy (see plan, section "CLI Command Tree"):
    eaccode                     → REPL (Phase 7, currently a hint)
    eaccode paths               → show XDG paths
    eaccode providers add/list/remove/set-default
    eaccode config show/set     → show/change settings
"""
from __future__ import annotations

import sys
from pathlib import Path

import click

from eaccode.config.paths import EaccodePaths
from eaccode.config.providers import ProviderConfig, load_providers, save_providers
from eaccode.config.settings import PermissionMode, Settings


def _configure_windows_asyncio() -> None:
    """Windows: subprocess + asyncio needs the selector policy.

    The default ProactorEventLoop is known to break
    ``asyncio.create_subprocess_*`` + ``communicate()`` (errno 9 / invalid
    handle) on Windows. The selector policy fixes it; must run before any
    event loop is created (Textual creates its own loop at startup).
    """
    if sys.platform == "win32":
        import asyncio

        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


_configure_windows_asyncio()


@click.group(invoke_without_command=True)
@click.version_option(version="0.1.0", prog_name="eaccode")
@click.pass_context
def main(ctx: click.Context) -> None:
    """eaccode — autonomous coding agent (BYOK)."""
    if ctx.invoked_subcommand is None:
        if not sys.stdin.isatty():
            click.echo(
                "REPL requires an interactive terminal. "
                "Use: eaccode run <prompt> (headless)"
            )
            return
        from eaccode.ui.repl import run_repl

        run_repl()


@main.command()
def paths() -> None:
    """Show resolved config/data paths."""
    p = EaccodePaths()
    click.echo(f"config:    {p.config_dir}")
    click.echo(f"data:      {p.data_dir}")
    click.echo(f"cache:     {p.cache_dir}")
    click.echo(f"sessions:  {p.sessions_dir}")
    click.echo(f"memory:    {p.memory_dir}")
    click.echo(f"skills:    {p.skills_dir}")


# ---------------------------------------------------------------- providers

@main.group()
def providers() -> None:
    """Manage BYOK providers."""


@providers.command("add")
@click.option("--provider", required=True,
              help="Provider name (minimax, anthropic, opencode-go, ...)")
@click.option("--model", required=True, help="Default model for this provider")
@click.option("--api-key", prompt=True, hide_input=True, help="API key (prompted hidden)")
@click.option("--base-url", default=None, help="Custom API base URL (OpenAI-compatible endpoints)")
def providers_add(provider: str, model: str, api_key: str, base_url: str | None) -> None:
    """Add a provider + API key (BYOK)."""
    paths = EaccodePaths()
    existing = load_providers(paths.providers_file)
    for p in existing:
        if p.name == provider:
            click.echo(
                f"✗ Provider '{provider}' already exists — remove it first "
                f"or edit {paths.providers_file} directly."
            )
            raise SystemExit(1)
    existing.append(
        ProviderConfig(name=provider, api_key=api_key, model=model, base_url=base_url)  # type: ignore[arg-type]
    )
    save_providers(existing, paths.providers_file)
    paths.providers_file.chmod(0o600)
    click.echo(f"✓ {provider} → {model} saved ({paths.providers_file})")


@providers.command("list")
def providers_list() -> None:
    """List configured providers (keys masked)."""
    paths = EaccodePaths()
    providers_list = load_providers(paths.providers_file)
    if not providers_list:
        click.echo("No providers configured. Add one with: eaccode providers add")
        return
    for p in providers_list:
        key = p.api_key.get_secret_value()
        masked = f"{key[:4]}…{key[-2:]}" if len(key) > 6 else "***"
        suffix = f" (base_url: {p.base_url})" if p.base_url else ""
        click.echo(f"  {p.name:14s} {p.model:30s} key={masked}{suffix}")


@providers.command("remove")
@click.argument("name")
def providers_remove(name: str) -> None:
    """Remove a provider."""
    paths = EaccodePaths()
    existing = load_providers(paths.providers_file)
    remaining = [p for p in existing if p.name != name]
    if len(remaining) == len(existing):
        click.echo(f"✗ Provider '{name}' not found.")
        raise SystemExit(1)
    save_providers(remaining, paths.providers_file)
    click.echo(f"✓ {name} removed")


@providers.command("set-default")
@click.argument("name")
def providers_set_default(name: str) -> None:
    """Set the default provider for new sessions."""
    paths = EaccodePaths()
    if not any(p.name == name for p in load_providers(paths.providers_file)):
        click.echo(f"✗ Provider '{name}' not configured.")
        raise SystemExit(1)
    settings = Settings.load(paths.settings_file)
    settings.default_provider = name
    settings.save(paths.settings_file)
    click.echo(f"✓ Default provider: {name}")


# ------------------------------------------------------------------ config

@main.group()
def config() -> None:
    """Show and change settings."""


@config.command("show")
def config_show() -> None:
    """Show current settings."""
    paths = EaccodePaths()
    settings = Settings.load(paths.settings_file)
    for k, v in settings.model_dump(mode="json").items():
        click.echo(f"  {k:24s} {v}")


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str) -> None:
    """Set a setting, e.g. `eaccode config set permission_mode acceptEdits`."""
    paths = EaccodePaths()
    settings = Settings.load(paths.settings_file)
    if key not in Settings.model_fields:
        click.echo(f"✗ Unknown setting: {key}. Known: {', '.join(Settings.model_fields)}")
        raise SystemExit(1) from None
    # Pydantic validates itself (enum, int, bool, float, constraints like ge=1)
    try:
        updated = Settings.model_validate({**settings.model_dump(), key: value})
    except Exception as e:
        click.echo(f"✗ Invalid value for {key}: {value} ({e})")
        raise SystemExit(1) from None
    updated.save(paths.settings_file)
    value_out = getattr(updated, key)
    click.echo(f"✓ {key} = {value_out.value if hasattr(value_out, 'value') else value_out}")


@main.command("run")
@click.argument("prompt")
@click.option("--print", "print_mode", is_flag=True, help="Headless: result to stdout, no TUI")
@click.option("--output-format", default="text", type=click.Choice(["text", "json"]),
              help="Output format (headless)")
@click.option("--max-turns", default=None, type=int, help="Override max turns")
@click.option("--allowed-tools", default=None, help="Comma-separated tool whitelist")
@click.option("--mode", "mode_name", default=None,
              type=click.Choice([m.value for m in PermissionMode]),
              help="Permission mode override (default for headless runs: bypassPermissions)")
@click.option("--model", default=None, help="Model alias or provider/model")
def run_cmd(prompt: str, print_mode: bool, output_format: str, max_turns: int | None,
            allowed_tools: str | None, mode_name: str | None, model: str | None) -> None:
    """Run one task headlessly (for CI, the queue, and the future GUI)."""
    import asyncio
    import json as jsonlib

    from eaccode.agent.factory import build_agent
    from eaccode.agent.loop import MaxTurnsExceededError
    from eaccode.config.providers import load_providers
    from eaccode.llm.models import Message

    paths = EaccodePaths()
    settings = Settings.load(paths.settings_file)
    if not load_providers(paths.providers_file):
        click.echo(
            "No providers configured. Add one first:\n"
            "  eaccode providers add --provider minimax --model MiniMax-M3"
        )
        raise SystemExit(1)

    # Headless runs are non-interactive: permission prompts would hang or
    # auto-deny. Default to bypassPermissions (like `claude -p` in CI);
    # an explicit --mode override wins. The --allowed-tools whitelist
    # remains the safety net.
    mode = (
        PermissionMode(mode_name)
        if mode_name
        else PermissionMode.BYPASS_PERMISSIONS
    )
    # Load MCP servers (optional; failures degrade to a warning)
    mcp_tools: list = []
    try:
        import asyncio as _asyncio

        from eaccode.tools.mcp.client import connect_mcp_tools

        mcp_tools, _ = _asyncio.run(connect_mcp_tools(paths.config_dir / "mcp.yaml"))
    except Exception as e:
        click.echo(f"Warning: MCP servers failed to load: {e}", err=True)

    agent, _, _ = build_agent(
        Path.cwd(),
        mode=mode,
        max_turns=max_turns,
        allowed_tools=allowed_tools.split(",") if allowed_tools else None,
        model=model,
        settings=settings,
        paths=paths,
        mcp_tools=mcp_tools,
    )

    try:
        result = asyncio.run(agent.run([Message.user(prompt)]))
    except MaxTurnsExceededError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from None

    if output_format == "json":
        click.echo(jsonlib.dumps({
            "result": result.final_text,
            "turns": result.turns,
            "cost_usd": round(result.cost_usd, 4),
            "usage": {
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
            },
        }))
    else:
        click.echo(result.final_text)


# ------------------------------------------------------------------ sessions

@main.group()
def sessions() -> None:
    """Manage sessions (list, resume, search, delete)."""


@sessions.command("list")
@click.option("--limit", default=20, help="Max sessions to show")
def sessions_list(limit: int) -> None:
    """List recent sessions."""
    import asyncio

    from eaccode.sessions.store import SessionStore

    paths = EaccodePaths()
    store = SessionStore(paths.sessions_dir / "sessions.db")
    for s in asyncio.run(store.list_sessions(limit=limit)):
        cwd = s.metadata.get("cwd", "")
        click.echo(f"  {s.id[:12]}  {s.title:40s} {s.updated_at[:19]}  {cwd}")


@sessions.command("search")
@click.argument("query")
def sessions_search(query: str) -> None:
    """Full-text search across all sessions."""
    import asyncio

    from eaccode.sessions.search import search_sessions
    from eaccode.sessions.store import SessionStore

    paths = EaccodePaths()
    store = SessionStore(paths.sessions_dir / "sessions.db")
    for h in asyncio.run(search_sessions(store, query)):
        click.echo(f"  [{h.title}] {h.session_id}")
        click.echo(f"    {h.snippet}")


@sessions.command("delete")
@click.argument("session_id")
def sessions_delete(session_id: str) -> None:
    """Delete a session."""
    import asyncio

    from eaccode.sessions.store import SessionStore

    paths = EaccodePaths()
    store = SessionStore(paths.sessions_dir / "sessions.db")
    ok = asyncio.run(store.delete(session_id))
    click.echo("✓ deleted" if ok else "✗ session not found")


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
    click.echo("\n".join(report))
    click.echo(f"\nReport saved: {report_path}")


@curator.command("report")
def curator_report() -> None:
    """Show the last curator report."""
    paths = EaccodePaths()
    report = paths.data_dir / "curator_report.md"
    if not report.exists():
        click.echo("No report yet. Run `eaccode curator run` first.")
        return
    click.echo(report.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------- mcp

@main.group()
def mcp() -> None:
    """Manage MCP servers (external tool servers)."""


@mcp.command("list")
def mcp_list() -> None:
    """List configured MCP servers."""
    from eaccode.tools.mcp.client import load_mcp_configs

    paths = EaccodePaths()
    configs = load_mcp_configs(paths.config_dir / "mcp.yaml")
    if not configs:
        click.echo(
            "No MCP servers configured. Add one with: "
            "eaccode mcp add <name> -- <command> [args...]"
        )
        return
    for c in configs:
        click.echo(f"  {c.name:20s} {c.command} {' '.join(c.args)}")


@mcp.command("add")
@click.argument("name")
@click.argument("command_args", nargs=-1, required=True)
def mcp_add(name: str, command_args: tuple[str, ...]) -> None:
    """Add an MCP server: eaccode mcp add <name> -- <command> [args...]"""
    from eaccode.tools.mcp.client import (
        MCPServerConfig,
        load_mcp_configs,
        save_mcp_configs,
    )

    paths = EaccodePaths()
    if "--" in command_args:
        idx = command_args.index("--")
        command = command_args[idx + 1]
        args = list(command_args[idx + 2 :])
    else:
        command = command_args[0]
        args = list(command_args[1:])
    configs = load_mcp_configs(paths.config_dir / "mcp.yaml")
    configs = [c for c in configs if c.name != name]
    configs.append(MCPServerConfig(name=name, command=command, args=args))
    save_mcp_configs(paths.config_dir / "mcp.yaml", configs)
    click.echo(f"✓ MCP server '{name}' added ({command} {' '.join(args)})")


@mcp.command("remove")
@click.argument("name")
def mcp_remove(name: str) -> None:
    """Remove an MCP server."""
    from eaccode.tools.mcp.client import load_mcp_configs, save_mcp_configs

    paths = EaccodePaths()
    configs = load_mcp_configs(paths.config_dir / "mcp.yaml")
    remaining = [c for c in configs if c.name != name]
    if len(remaining) == len(configs):
        click.echo(f"✗ MCP server '{name}' not found.")
        raise SystemExit(1)
    save_mcp_configs(paths.config_dir / "mcp.yaml", remaining)
    click.echo(f"✓ MCP server '{name}' removed")


# ------------------------------------------------------------------- doctor

@main.command("doctor")
def doctor() -> None:
    """Diagnose the installation: providers, settings, git, skills, MCP."""
    paths = EaccodePaths()
    problems = 0

    def check(ok: bool, msg: str) -> None:
        nonlocal problems
        click.echo(f"  {'✓' if ok else '✗'} {msg}")
        if not ok:
            problems += 1

    click.echo("eaccode doctor")
    providers = load_providers(paths.providers_file)
    check(bool(providers), f"providers configured ({len(providers)})")
    for p in providers:
        click.echo(f"      {p.name:14s} {p.model}")
    settings = Settings.load(paths.settings_file)
    check(settings.permission_mode.value in ("default", "acceptEdits", "plan", "bypassPermissions"),
          f"settings loadable (mode={settings.permission_mode.value})")
    check(paths.skills_dir.exists(), f"skills dir exists ({paths.skills_dir})")
    try:
        subprocess_run = __import__("subprocess").run(
            ["git", "--version"], capture_output=True, timeout=10
        )
        check(subprocess_run.returncode == 0, "git available")
    except Exception:
        check(False, "git available")
    from eaccode.tools.mcp.client import load_mcp_configs

    mcp_configs = load_mcp_configs(paths.config_dir / "mcp.yaml")
    check(len(mcp_configs) >= 0, f"mcp.yaml ({len(mcp_configs)} server(s) configured)")

    if problems:
        click.echo(f"\n{problems} issue(s) found.")
        raise SystemExit(1)
    click.echo("\nAll checks passed.")


# ------------------------------------------------------------------ models

@main.group()
def models_cmd() -> None:
    """Show configured models and their capabilities."""


@models_cmd.command("list")
def models_list() -> None:
    """List configured providers/models with thinking capabilities."""
    from eaccode.llm.thinking import ThinkingMapper

    paths = EaccodePaths()
    mapper = ThinkingMapper()
    providers_list = load_providers(paths.providers_file)
    if not providers_list:
        click.echo("No providers configured.")
        return
    for p in providers_list:
        litellm_id = p.litellm_model(p.model)
        thinking = mapper.supports_thinking(litellm_id)
        click.echo(
            f"  {p.name:14s} {p.model:30s} thinking={'✓' if thinking else '✗'}  "
            f"({litellm_id})"
        )


# ------------------------------------------------------------------ skills

@main.group()
def skills() -> None:
    """Manage skills (markdown instructions the agent loads)."""


@skills.command("list")
def skills_list() -> None:
    """List installed skills."""
    from eaccode.memory.skills import discover_skills

    paths = EaccodePaths()
    installed = discover_skills([paths.skills_dir])
    if not installed:
        click.echo(f"No skills installed. Put .md files in {paths.skills_dir}")
        return
    for s in installed:
        click.echo(f"  {s.name:25s} {s.description}")


@skills.command("add")
@click.argument("path")
def skills_add(path: str) -> None:
    """Import a skill markdown file into the skills directory."""
    import shutil

    from eaccode.memory.skills import _parse_frontmatter

    paths = EaccodePaths()
    src = Path(path)
    if not src.exists():
        click.echo(f"✗ File not found: {src}")
        raise SystemExit(1)
    meta, _ = _parse_frontmatter(src.read_text(encoding="utf-8"))
    name = meta.get("name") or src.stem
    paths.skills_dir.mkdir(parents=True, exist_ok=True)
    dest = paths.skills_dir / f"{name}.md"
    shutil.copy2(src, dest)
    click.echo(f"✓ Skill '{name}' installed at {dest}")


# --------------------------------------------------------------- config init

@config.command("init")
def config_init() -> None:
    """Create .eaccode/ with an EACCODE.md template in the current project."""
    project_dir = Path.cwd()
    dot_dir = project_dir / ".eaccode"
    dot_dir.mkdir(exist_ok=True)
    ctx_file = project_dir / "EACCODE.md"
    if not ctx_file.exists():
        ctx_file.write_text(
            "# EACCODE.md — project rules for eaccode\n\n"
            "## Build\n- (add your build/test commands here)\n\n"
            "## Conventions\n- (add style/code conventions here)\n",
            encoding="utf-8",
        )
    click.echo(f"✓ Created {ctx_file}")
    click.echo(f"✓ Created {dot_dir} (put project skills here)")


# ------------------------------------------------------------------- queue

@main.group()
def queue_cmd() -> None:
    """Manage the background job queue (parallel reviews, agents)."""


@queue_cmd.command("status")
def queue_status() -> None:
    """Show queue state: queued / running / done / failed."""
    import asyncio

    from eaccode.orchestrator.queue import JobQueue

    paths = EaccodePaths()
    settings = Settings.load(paths.settings_file)
    queue = JobQueue(paths.data_dir / "queue.db", max_running=settings.max_parallel_agents)
    jobs = asyncio.run(queue.list_jobs(limit=30))
    counts: dict[str, int] = {}
    for j in jobs:
        counts[j.status.value] = counts.get(j.status.value, 0) + 1
    click.echo(
        f"pool: max {settings.max_parallel_agents} concurrent  |  "
        + "  ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
    )
    icons = {"queued": "⏳", "running": "▶", "done": "✓", "failed": "✗"}
    for j in jobs[:15]:
        click.echo(
            f"  {icons.get(j.status.value, '?')} {j.id[:8]}  {j.name:22s} "
            f"{j.status.value:7s} ${j.cost_usd:.3f}  {j.created_at[:19]}"
        )


@queue_cmd.command("show")
@click.argument("job_id")
def queue_show(job_id: str) -> None:
    """Show a job's full report."""
    import asyncio

    from eaccode.orchestrator.queue import JobQueue

    paths = EaccodePaths()
    queue = JobQueue(paths.data_dir / "queue.db")
    job = asyncio.run(queue.get(job_id))
    click.echo(f"# {job.name} ({job.status.value})\n")
    if job.report:
        click.echo(job.report)
    if job.error:
        click.echo(f"[error] {job.error}")


@queue_cmd.command("add")
@click.argument("prompt")
@click.option("--name", default="custom-job", help="Job name")
def queue_add(prompt: str, name: str) -> None:
    """Append an arbitrary agent job to the queue (runs when a slot frees)."""
    import asyncio

    from eaccode.orchestrator.queue import JobQueue

    paths = EaccodePaths()
    queue = JobQueue(paths.data_dir / "queue.db")
    job_id = asyncio.run(queue.enqueue(name=name, prompt=prompt, workdir=str(Path.cwd())))
    click.echo(f"✓ enqueued {job_id} ({name}) — runs when a pool slot frees")


@queue_cmd.command("cancel")
@click.argument("job_id")
def queue_cancel(job_id: str) -> None:
    """Cancel a queued (not yet running) job."""
    import asyncio

    from eaccode.orchestrator.queue import JobQueue

    paths = EaccodePaths()
    queue = JobQueue(paths.data_dir / "queue.db")
    ok = asyncio.run(queue.cancel(job_id))
    click.echo("✓ cancelled" if ok else "✗ job not found or already running")


@queue_cmd.command("prune")
def queue_prune() -> None:
    """Remove old done/failed jobs."""
    import asyncio

    from eaccode.orchestrator.queue import JobQueue

    paths = EaccodePaths()
    queue = JobQueue(paths.data_dir / "queue.db")
    jobs = asyncio.run(queue.list_jobs(limit=1000))
    removed = 0
    for j in jobs:
        if j.status.value in ("done", "failed"):
            import sqlite3

            with sqlite3.connect(queue.db_path) as conn:
                conn.execute("DELETE FROM jobs WHERE id=?", (j.id,))
            removed += 1
    click.echo(f"✓ pruned {removed} finished jobs")


# ------------------------------------------------------------------ review

@main.command("review")
@click.option("--diff", "diff_ref", default="HEAD", help="Diff ref (e.g. 'main...feature')")
@click.option("--aspects", default=None, help="Comma-separated: bugs,security,tests,style,perf")
@click.option("--detach", is_flag=True, help="Enqueue and return immediately")
def review_cmd(diff_ref: str, aspects: str | None, detach: bool) -> None:
    """Enqueue parallel code reviews of the current diff (one job per aspect).

    Jobs run in the shared pool (max `max_parallel_agents`, default 6).
    Watch progress with `eaccode queue status`; append more with --detach.
    """
    import asyncio
    import subprocess

    from eaccode.orchestrator.queue import JobQueue

    paths = EaccodePaths()
    settings = Settings.load(paths.settings_file)
    try:
        diff = subprocess.run(
            ["git", "diff", diff_ref], capture_output=True, text=True, cwd=Path.cwd()
        ).stdout
    except FileNotFoundError:
        click.echo("Error: git is not installed or not a git repository.")
        return
    if not diff.strip():
        click.echo("No diff to review.")
        return

    default_aspects = ["bugs", "security", "tests"]
    chosen = (aspects or ",".join(default_aspects)).split(",")
    aspect_prompts = {
        "bugs": "Review this diff for logic errors, race conditions, and edge cases. "
                "Report concrete issues with line references.",
        "security": "Review this diff for security issues: injection, secrets, "
                    "authz flaws, unsafe deserialization.",
        "tests": "Review this diff for missing test coverage and suggest specific test cases.",
        "style": "Review this diff for style/consistency issues.",
        "perf": "Review this diff for performance problems (N+1, hot loops, allocations).",
    }

    queue = JobQueue(paths.data_dir / "queue.db", max_running=settings.max_parallel_agents)
    enqueued: list[str] = []
    for aspect in chosen:
        job_id = asyncio.run(queue.enqueue(
            name=f"review-{aspect}",
            prompt=(
                f"{aspect_prompts.get(aspect, 'Review this diff.').strip()}\n\n"
                f"DIFF TO REVIEW:\n```diff\n{diff[:50000]}\n```"
            ),
            workdir=str(Path.cwd()),
            tools=["read", "grep", "glob", "bash"],
            max_turns=15,
        ))
        enqueued.append(job_id)
        click.echo(f"✓ enqueued {job_id[:8]} review-{aspect}")

    if detach:
        click.echo(
            f"Jobs will run in the background pool (max {settings.max_parallel_agents} "
            f"concurrent). Watch with `eaccode queue status`."
        )
        return

    # Blocking mode: process the queue (including jobs from other terminals)
    # until all jobs we enqueued are finished. Each job runs in its own
    # isolated git worktree (Task 11.1).
    from eaccode.orchestrator.pool import WorkerPool, agent_runner, make_worktree_runner
    from eaccode.orchestrator.worktree import WorktreeManager

    async def _wait() -> None:
        runner = make_worktree_runner(WorktreeManager(Path.cwd()), agent_runner)
        pool = WorkerPool(queue, runner)
        while True:
            await pool.run_until_idle(wait_for_new=False)
            remaining = [
                j for j in await queue.list_jobs()
                if j.id in enqueued and j.status.value in ("queued", "running")
            ]
            if not remaining:
                return
            await asyncio.sleep(2)

    asyncio.run(_wait())
    click.echo("\nDone. Full reports: `eaccode queue show <job-id>`")


if __name__ == "__main__":
    main()
