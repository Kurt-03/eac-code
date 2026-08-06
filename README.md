# eaccode

An autonomous coding agent CLI — Claude Code / Hermes-style. Reads and writes
files, runs shell commands, browses the web, works autonomously over many turns.
**BYOK**: bring your own API keys for any provider (MiniMax, opencode-go,
Anthropic, OpenAI, ...).

## Status

🚧 Early development — Phase 1 (config & providers) in progress.

## Quickstart (soon)

```bash
uv pip install -e ".[dev]"
eaccode providers add --provider minimax --model MiniMax-M2
eaccode
```

## Features (planned)

- BYOK provider config with LiteLLM
- 4 permission modes: `default`, `acceptEdits`, `plan`, `bypassPermissions`
- Built-in tools: read, write, edit, bash, glob, grep, web
- Parallel review queue (max 6 concurrent agents)
- Persistent sessions + auto-memory per project
- Self-improvement loop: skills, curator, session search
- TUI (Textual) + headless `run --print` mode

## License

MIT
