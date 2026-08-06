# eaccode

An autonomous coding agent CLI — Claude Code / Hermes-style. Reads and writes
files, runs shell commands, works autonomously over many turns, reviews code
in parallel, and learns from every session. **BYOK**: bring your own API keys
for any provider (MiniMax, opencode-go, Anthropic, OpenAI, ...).

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

## Features

- **BYOK** — provider-agnostic via LiteLLM: native providers (minimax, anthropic,
  openai, ...) and custom OpenAI-compatible endpoints (opencode-go) with
  per-request credentials
- **4 permission modes** — `default`, `acceptEdits`, `plan`, `bypassPermissions`
  (switchable in the REPL with `/mode`)
- **Built-in tools** — read, write, edit, bash (timeout + exit codes), glob,
  grep (ripgrep + fallback), web_fetch, todo_write
- **Provider-specific thinking** — `effort: low|medium|high` mapped per model
  (Anthropic budget_tokens, OpenAI reasoning_effort, Gemini thinkingBudget,
  DeepSeek/Qwen reasoning_content in stream)
- **Model aliases + fallback chain** — `/model sonnet`, user aliases shadow
  built-ins, automatic provider failover
- **Project memory** — `EACCODE.md`/`AGENTS.md` auto-discovery (parent walk to
  git root, 20K cap, prompt-injection scanner), auto-learned facts per project
  (`/remember`, `/forget`), skills that the agent creates and patches itself
- **Parallel review queue** — persistent SQLite job queue + worker pool,
  hard cap of 6 concurrent agents, jobs can be appended from any terminal
- **Sessions** — SQLite persistence, context compaction, FTS search (planned)
- **Self-improvement** — skills, auto-memory, curator (stale detection,
  dedupe), behavior rules in the system prompt

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
└── ui/          Textual REPL, slash commands
```

## License

MIT
