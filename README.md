# eaccode v0.0.1

A Claude Code / Hermes-style autonomous coding agent CLI. Reads and writes
files, runs shell commands, works autonomously over many turns, reviews code
in parallel, and learns from every session. **BYOK**: bring your own API keys
for any provider (MiniMax, opencode-go, Anthropic, OpenAI, ...).

> **v0.0.1 → v0.1.0** is the "Hermes/Claude-Code parity" release. The TUI
> has been rebuilt to look and behave like Hermes: in-place streaming,
> inline permission prompt with colored diff, ASCII spinner, status rule,
> slash overlay. See [docs/manual-test.md](docs/manual-test.md) for the
> guided tour.

## Quickstart

```bash
pip install -e ".[all]"

# Add your providers (keys are stored hidden, file chmod 600)
eaccode providers add --provider minimax --model MiniMax-M3
eaccode providers add --provider opencode-go --model deepseek-v4-flash \
  --base-url https://opencode.ai/zen/go/v1

# Interactive REPL (project context + memory + skills auto-loaded)
eaccode

# Headless one-shot (for CI / scripts)
eaccode run "Refactor src/auth.py to use async/await" --print --output-format json

# Parallel code reviews of the current diff (max 6 concurrent agents)
eaccode review --aspects bugs,security,tests
eaccode queue status          # watch the pool from any terminal
```

## What's in v0.0.1 → v0.1.0

The TUI is the focus of this release. It now behaves like Hermes / Claude
Code:

- **In-place streaming** — the stream renders inside the transcript, not
  in a separate static widget. The transcript scrolls as the answer
  arrives; no staircase duplication.
- **Incremental markdown renderer** — `StreamingMarkdownRenderer` keeps
  a small lookahead buffer and only completes tokens it can finish
  (*bold*, `*italic*`, `` `code` ``, fenced blocks). No O(N²) re-parse
  on 50 deltas; `tools/repro_stream_50_deltas.py` shows `max feed size:
  4` (the delta size, not the accumulated text).
- **Inline permission prompt** — appears in the transcript with a tool
  subtitle and a colored unified diff:
  - `--- a/foo.py` / `+++ b/foo.py` → **bold blue**
  - `@@ -1,1 +1,1 @@` → **bold cyan**
  - `-old line` → **red**
  - `+new line` → **green**
  - ` context` → dim
- **Quick-pick keys** — `y` once, `s` session, `a` always, `n` deny,
  `p` pause, `Esc` deny. The `s` key is the new **ALLOW_SESSION** choice
  (session-only remember, no `allowlist.json` write).
- **Hermes-style status rule** — busy indicator · model · git branch ·
  context window · cost · cwd/session.
- **Thin rule between transcript and composer** — no headers, no footers,
  no boxes.
- **Single-column prompt glyph** — `❯` followed by a clean input line.

## Features

- **BYOK** — provider-agnostic via LiteLLM: native providers (minimax,
  anthropic, openai, ...) and custom OpenAI-compatible endpoints
  (opencode-go) with per-request credentials.
- **4 permission modes** — `default`, `acceptEdits`, `plan`, `safeAuto`
  (auto-approves classified-safe bash via key patterns + optional aux
  LLM), `bypassPermissions`. Switchable in the REPL with `/mode`.
  `/approve <id>` and `/deny <id>` resolve pending asks; persistent
  allowlist via `/allow`.
- **Built-in tools** — read, write, edit, bash (timeout + exit codes),
  glob, grep (ripgrep + fallback), web_fetch, web_search (keyless,
  DuckDuckGo), web_extract, todo_write, process, vision, delegate
  (batch + background), cronjob, tool_search, execute_code, MCP.
- **Provider-specific thinking** — `effort: low|medium|high` mapped per
  model (Anthropic `budget_tokens`, OpenAI `reasoning_effort`, Gemini
  `thinkingBudget`, DeepSeek/Qwen `reasoning_content` in stream).
- **Model aliases + fallback chain** — `/model sonnet`, user aliases
  shadow built-ins, automatic provider failover.
- **Project memory** — `EACCODE.md`/`AGENTS.md` auto-discovery (parent
  walk to git root, 20K cap, prompt-injection scanner), auto-learned
  facts per project (`/remember`, `/forget`), markdown memory
  (MEMORY.md/USER.md/SOUL.md), background reviews that propose facts
  (approved via `/approve`).
- **Parallel review queue** — persistent SQLite job queue + worker pool,
  hard cap of 6 concurrent agents, jobs can be appended from any terminal.
- **Sessions** — SQLite persistence + FTS search, two-stage titles
  (derived < llm < user), export (md/html), recap, leases, `/title`.
- **Self-improvement** — skills (frontmatter/triggers/linter/bundles),
  curator lifecycle (paused/archived/pinned) with backups, learning
  graph, behavior rules in the system prompt.
- **Safety** — credential files unreadable by tools, prompt-injection
  warnings, self-repo guard, redacted tool output, result spill >50K.

## Architecture

```
src/eaccode/
├── agent/       agent loop, context builder, compaction, factory
├── config/      paths (XDG), settings, BYOK providers
├── llm/         LiteLLM client, models, tokens, thinking, aliases
├── memory/      skills, project context, auto-memory, scanner
├── orchestrator/ job queue, worker pool
├── permissions/ policy engine (4 modes + allow/ask/deny rules)
├── sessions/    SQLite session store
├── tools/       tool protocol, registry, executor, built-ins
├── tui/         Textual REPL (Hermes-style), slash overlay, status rule
└── ui/          slash commands, palette, diff renderer
```

## Development

```bash
# Run unit tests
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider

# Run integration tests (real streamed live provider, screenshot tests)
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider -m integration

# 50-delta streaming reproducer (manual probe)
.venv/Scripts/python.exe tools/repro_stream_50_deltas.py

# Lint
.venv/Scripts/python.exe -m ruff check src/ tests/
```

## Documentation

- [docs/manual-test.md](docs/manual-test.md) — guided end-to-end probe
  to verify Hermes parity in look and feel.

## License

MIT — see [LICENSE](LICENSE).

**Design attribution:** the v0.0.1 TUI is modeled on the [Hermes Agent
TUI](https://github.com/NousResearch/hermes-agent) (`ui-tui/`, MIT
license, © Nous Research): fuzzy slash scoring (`fuzzyScore.ts`), the
role-gutter message layout (`roles.ts`), the status rule
(`appChrome.tsx`), and the color role system (`theme.ts`) were ported
and adapted for eaccode. The original MIT copyright notice applies to
those design elements.
