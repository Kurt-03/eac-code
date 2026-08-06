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
    agent, _, _ = build_agent(
        Path.cwd(),
        mode=mode,
        max_turns=max_turns,
        allowed_tools=allowed_tools.split(",") if allowed_tools else None,
        model=model,
        settings=settings,
        paths=paths,
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
