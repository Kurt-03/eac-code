# eaccode — Next Iteration Plan

> **For Hermes:** Use subagent-driven-development for tasks that touch >1 file.
> Use TDD: failing test → implementation → green → commit.

**Goal:** Stop looking like a chatbot. Fix the errno-9 crash on tool calls, raise the
REPL UX to Claude Code / Hermes quality, close the gap in slash-commands, permission
prompts, and reasoning display. One pass, no scope creep.

**Architecture:** Async-everywhere in the REPL; sync wrappers for CLI only.
System-prompt cache stays (Phase D.2). Tool-call rendering is data-only
(`ToolCallCard` dataclass) — UI consumes data, never builds strings.

**Tech Stack:** Python 3.14, Textual 8.x, Rich, LiteLLM, Pydantic v2, Click, SQLite.

---

## 0. Where we actually are (code-truth, not plan-aspiration)

- **73 src files, 53 test files, 5.384 src-LoC, 71 commits.**
- All unit tests green; only red is `test_real_opencode_go_completion` (live
  integration, `deepseek-v4-flash` returns `stop_reason='length'` on the strict
  test prompt — see Task 0.1).
- One source file on the watchlist: `src/eaccode/llm/client.py` (391 LoC,
  hard cap 600) — split **before** the next feature lands there.
- The old `2026-08-06_143000-coding-agent-claude-code-clone.md` (252 KB)
  becomes a historical artifact and is **moved to `archive/`**.

---

## 1. Three concrete bugs the user reported

### Bug A — errno 9 / "Bad file descriptor" on tool calls

**Symptom:** When the agent makes a tool call inside the Textual REPL, the
process dies with `OSError: [Errno 9] Bad file descriptor`.

**Root cause (found via grep, confirmed in code):** `src/eaccode/ui/commands.py`
calls `asyncio.run(store.recall/remember/forget(...))` from inside slash-command
handlers — and Textual is already running its own asyncio loop. `asyncio.run()`
creates a **second** event loop in the same thread; when that loop closes,
its `ProactorEventLoop` tears down the I/O proactors that were inherited from
the outer loop. The next subprocess call (e.g. via `asyncio.to_thread` in
`BashTool`) gets an OS handle pointing at a closed proactor pipe → errno 9.

The same anti-pattern exists at:
- `src/eaccode/ui/commands.py:159, 170, 178`
- `src/eaccode/cli/__init__.py:47, 49, 51`

**Fix:** All memory operations from inside the running REPL go through
`app.run_worker(...)` with an async coroutine — never `asyncio.run`. For CLI
subcommands outside the REPL the existing `asyncio.run` is fine (no outer loop).

### Bug B — UX feels like a chatbot

**Symptom:** Even with the `⎿` chevron and one-line tool cards, the chat still
reads as "bot talking to me" instead of "coding agent at work".

**Root causes (all in code):**
1. **Permission prompt is `click.confirm`** (`permissions/prompts.py:34`) — it
   blocks on stdin, prints nothing in the REPL, and returns `False` (deny)
   whenever stdin is not a TTY. So inside the Textual REPL **every** ASK-mode
   tool call is denied silently. Users never see prompts like Claude Code's
   `⎿ Run command?  Allow once / Always allow / Deny  [y/n/a]`.
2. **No diff before write/edit.** The user sees `⎿ write(path="foo.py")` and
   later a green `✓ write 0.8s`, but the diff of what changed is hidden.
   Claude Code shows the diff inline before approving.
3. **No streaming reasoning.** `llm/thinking.py` parses `reasoning_content`
   from the stream but `ui/repl.py:198` only wires `on_text_delta` — reasoning
   is dropped on the floor. With MiniMax-M3 (reasoning model) the user sees a
   blank "… working" for seconds, then a sudden answer drop.
4. **User prompt uses `❯` + Panel.border** (`repl.py:148`) — that's the
   chatbot look. Claude Code uses a bare `❯` on its own line, no panel, no
   "you" title.
5. **Tool result preview is one line truncated to 90 chars.** For multi-line
   output (test runs, file dumps, command results) that's unreadable. Claude
   Code expands to a 6-line preview with a `…` collapse.
6. **No header that names the project / branch / tokens-per-minute.** Hermes
   shows `model · mode · ctx% · 12k tok · $0.04` in the sub-title; eaccode
   shows `model · mode · 1234 tok · $0.0400` — close, but no `ctx%` and no
   spinner while working.
7. **No `[ ! ]` system messages for failures.** When the LLM hits a 401, the
   REPL shows the raw exception in a red panel (`repl.py:174`) — looks like
   a crash. Should be a yellow system message with the recovery suggestion
   ("Tried fallback provider → OpenAI — also failed").

### Bug C — Missing UX vs. Hermes / Claude Code

Gap table (verified against the live Hermes skill docs and the Claude Code
public docs that the hermes-agent skill cites):

| Feature | Hermes | Claude Code | eaccode today | Plan |
|---|---|---|---|---|
| `⎿ tool(args)` one-liner | ✓ | ✓ | ✓ | already there |
| Live tool cards (chevron + duration) | ✓ | ✓ | ✓ | already there |
| `/verbose` cycle (off → new → all → verbose) | ✓ | ✓ | ✓ | already there |
| `/model [name]` mid-session switch | ✓ | ✓ | ✓ | already there |
| `/reasoning [on\|off]` | ✓ | ✓ | partial (state stored, never rendered) | Task B.3 |
| `/clear` | ✓ | ✓ | ✓ (resets messages, no confirm) | already there |
| `/undo [N]` | ✓ | ✓ | ✓ | already there |
| `/retry` | ✓ | ✓ | ✓ | already there |
| `/cost` / `/usage` | ✓ | ✓ | ✓ (`/cost` only, no reset, no rate-limit readout) | Task C.1 |
| `/copy` (last answer to clipboard) | ✓ | ✓ | ✓ (`clip.exe`, only Win) | Task C.2 |
| `/status` (session/model/tokens/ctx%) | ✓ | ✓ | ✗ | Task C.3 |
| `/diff [mode]` (staged\|all\|session) | ✓ | ✓ | ✗ | Task C.4 |
| `/compress [/compact]` (context-window mgmt) | ✓ | ✓ | partial (`agent/compaction.py` exists, no slash-cmd) | Task C.5 |
| `/skills` (browse / enable / disable) | ✓ | ✓ | ✗ (CLI subcommand exists, no in-REPL) | Task C.6 |
| Permission prompt in-REPL (`Allow once / Always / Deny`) | ✓ | ✓ | ✗ (click.confirm returns False) | Task B.1 |
| Diff preview for write/edit before approve | ✓ | ✓ | ✗ | Task B.2 |
| Streaming reasoning display | ✓ | ✓ | ✗ (parsed, dropped) | Task B.3 |
| Spinner while working | ✓ | ✓ | partial (static "… working") | Task B.4 |
| `ctx%` in status bar | ✓ | ✓ | ✗ | Task B.5 |
| System messages (`[ ! ]`) instead of red panels for non-fatal errors | ✓ | ✓ | ✗ | Task B.6 |
| Per-tool-result multi-line preview with `…` collapse | ✓ | ✓ | ✗ | Task B.7 |
| `--continue` / `--resume` | ✓ | ✓ | ✓ | already there |
| `--worktree / -w` (parallel agent isolation) | ✓ | ✓ | ✓ (`orchestrator/worktree.py`) | already there |

**Already-strong differentiators we should advertise (not "missing"):**
- Filesystem checkpoints (`/rollback`) with stable IDs — Hermes has it too,
  most agents don't.
- Job queue with parallel review (`eaccode review`, max 6) — Hermes has cron,
  not a review-pool primitive.
- Profile-isolated config (`HERMES_HOME`-style paths).

---

## 2. Implementation Tasks (TDD, bite-sized, ordered)

> Convention: every task lists a failing test first, then the implementation,
> then the commit. Each task = one commit.

### Phase 0 — Hygiene (do first, blocks everything else)

#### Task 0.1 — Mark and fix the live integration test

**Files:**
- `tests/integration/test_real_provider.py`
- `pyproject.toml`

**Why:** CI is "red" today because one live test asserts a string on a
real provider; the provider returns `stop_reason='length'` (token budget
exhausted) and an empty string. That's not a bug in eaccode.

**Steps:**
1. Add `pytest.mark.integration` to both live tests.
2. Add to `pyproject.toml`:
   ```toml
   [tool.pytest.ini_options]
   markers = ["integration: live network calls — skipped by default"]
   addopts = "-q -m 'not integration'"
   ```
3. Soften the assertion: accept empty text if `tool_calls` non-empty OR
   `usage.output_tokens > 0` (provider spent tokens, just no plain text).
4. Run `pytest -q` — must be green.
5. Commit `chore(tests): mark live-provider tests as integration`.

#### Task 0.2 — Archive the obsolete plan

**Files:**
- `.hermes/plans/archive/2026-08-06_143000-coding-agent-claude-code-clone.md`

**Why:** A 252-KB plan that contradicts the code is worse than no plan.

**Steps:**
1. `mkdir -p .hermes/plans/archive`
2. `git mv .hermes/plans/2026-08-06_143000-coding-agent-claude-code-clone.md .hermes/plans/archive/`
3. Commit `chore(plans): archive obsolete 2026-08-06 master plan`.

#### Task 0.3 — Split `llm/client.py` (391 LoC → 3 files)

**Files:**
- `src/eaccode/llm/client.py` (orchestration, < 200 LoC)
- `src/eaccode/llm/_resolve.py` (`_resolve_model`, `_base_kwargs`, `_to_litellm_*`, < 150 LoC)
- `src/eaccode/llm/_stream.py` (`stream()`, `_produce`, queue, < 150 LoC)

**Why:** Hard cap 600 LoC, we're at 391, next feature (reasoning-budget
plumbing for MiniMax-M3) will tip us over.

**Steps (per file, RED→GREEN→commit):**
1. Test that `LLMClient(...).complete(req)` still works after moving
   `_resolve_model` to a new module and importing it back.
2. Move the function, re-export from `client.py` for back-compat.
3. Same for `_stream.py`.
4. Run full suite, must stay green.
5. Commit per move: `refactor(llm): extract _resolve helpers`,
   `refactor(llm): extract _stream helpers`.

### Phase A — Fix the errno 9 crash

#### Task A.1 — Memory operations from REPL go through `run_worker`

**Files:**
- `src/eaccode/ui/commands.py`
- `tests/unit/test_repl.py`

**Failing test:**
```python
async def test_memory_command_uses_running_loop():
    """Memory ops inside REPL must NOT call asyncio.run (would crash tools)."""
    # assert: _save_memory / _get_memory call app.run_worker or app.call_from_thread,
    # not asyncio.run
```

**Steps:**
1. Replace the three `asyncio.run(...)` calls in `commands.py:159,170,178`
   with helpers that go through `app.run_worker(coro)` (Textual) for the
   REPL case and `asyncio.run` for non-REPL callers.
2. Add a small `MemoryAdapter` protocol so the helper doesn't reach into
   the App class for state.
3. Run `pytest tests/unit/test_repl.py -v` → green.
4. Commit `fix(ui): memory ops from REPL no longer spawn second event loop`.

#### Task A.2 — Same fix in `cli/__init__.py` (session resume path)

**Files:**
- `src/eaccode/cli/__init__.py`
- `tests/unit/test_cli.py`

**Note:** This one is outside the REPL — `asyncio.run` is technically fine
here. But the call is hidden inside a Click callback; safer to extract a
`_load_session_async` and unify the path. Skip if `tests/unit/test_cli.py`
doesn't cover this case.

#### Task A.3 — Repro the crash with a script, then verify the fix

**Files:**
- `tests/integration/test_repl_errno9.py` (new, marked `integration`)

**Steps:**
1. Write a script that: builds an agent, runs the REPL loop, issues a
   prompt that triggers a `bash` tool call, then issues `/remember foo`,
   then issues another `bash` tool call. Assert the second bash succeeds.
2. Run it manually (or as integration) — before fix it fails, after fix it
   passes.
3. Commit `test(repl): regression for errno-9 after /remember`.

### Phase B — REPL UX to Claude-Code / Hermes level

#### Task B.1 — In-REPL permission prompt widget

**Files:**
- `src/eaccode/permissions/prompts.py` (refactor signature)
- `src/eaccode/ui/permission_modal.py` (new, Textual ModalScreen)
- `src/eaccode/ui/repl.py` (mount the modal)
- `tests/unit/test_prompts.py`

**Failing test:**
```python
async def test_permission_modal_returns_action():
    modal = PermissionModal(tool="bash", arguments={"command": "ls"})
    # simulate keypress "a" (allow once), assert modal.dismiss("allow-once")
```

**Steps:**
1. Refactor `prompt_for_permission` to return an `Action` enum
   (`ALLOW_ONCE | ALLOW_ALWAYS | DENY`), not a bool.
2. Build `PermissionModal` (Textual `ModalScreen`) with three buttons /
   shortcuts: `y` / `n` / `a`. Show the tool, the args (formatted like
   the existing `_describe`), and — for write/edit — the diff (Task B.2).
3. Wire `repl.py._run_agent_streaming` to push the modal before
   `_execute_with_permission` whenever policy says ASK.
4. Tests: assert three paths.
5. Commit `feat(ui): in-REPL permission prompt (allow once/always/deny)`.

#### Task B.2 — Inline diff preview for write/edit in the permission modal

**Files:**
- `src/eaccode/ui/diff_render.py` (new, Rich renderer for unified diff)
- `src/eaccode/ui/permission_modal.py` (use it)
- `tests/unit/test_diff_render.py`

**Failing test:** render a unified diff between two strings, assert
3 chunks of colorized output (added/removed/context).

**Steps:**
1. Use `difflib.unified_diff`, render via `rich.syntax.Syntax` or a
   hand-rolled `Text` with `[green]+[/green]` / `[red]-[/red]`.
2. Modal layout: tool+args line, then a collapsible diff box (default
   expanded for files < 200 lines, collapsed otherwise).
3. Commit `feat(ui): inline diff in permission modal`.

#### Task B.3 — Render streaming reasoning above the answer

**Files:**
- `src/eaccode/ui/repl.py` (wire `on_reasoning_delta`)
- `src/eaccode/ui/preview.py` (add `ReasoningBlock` widget data)
- `tests/unit/test_repl.py`

**Failing test:**
```python
async def test_reasoning_deltas_render_collapsed():
    # feed three reasoning deltas; assert they accumulate and render as
    # a single collapsible block above the streaming text
```

**Steps:**
1. In `_run_agent_streaming`, register `on_reasoning_delta` that writes to
   a `ReasoningBlock` (collapsed, expandable via `/reasoning on`).
2. Default: collapsed, dimmed italic. `/reasoning on` expands live and
   keeps it expanded for future turns.
3. Commit `feat(ui): render streaming reasoning above answer`.

#### Task B.4 — Animated spinner while the agent works

**Files:**
- `src/eaccode/ui/repl.py`
- `tests/unit/test_repl.py`

**Steps:**
1. Replace static `… working` with a Rich `Spinner` widget in the stream
   area. Update at 8 fps via `self.set_interval(0.125, ...)`.
2. Hide on first token / first tool card.
3. Commit `feat(ui): animated spinner while agent works`.

#### Task B.5 — Context-window percentage in status bar

**Files:**
- `src/eaccode/llm/models.py` (add `ctx_window` field per model)
- `src/eaccode/llm/client.py` (expose `last_ctx_used`)
- `src/eaccode/ui/repl.py` (status bar)
- `tests/unit/test_repl.py`

**Steps:**
1. Add `ctx_window: int = 128_000` to the model catalog (one source of
   truth, in `llm/models.py`).
2. After each streaming turn, compute `used / window` and update
   `sub_title` to include `12 %` or `87 %`.
3. Commit `feat(ui): context-window % in status bar`.

#### Task B.6 — System messages for non-fatal failures (no red panels)

**Files:**
- `src/eaccode/ui/repl.py`
- `src/eaccode/ui/messages.py` (new, three message kinds: `info|warn|error`)
- `tests/unit/test_repl.py`

**Steps:**
1. Introduce `write_system(level, text)` helper:
   - `info` → dim `[ i ] text`
   - `warn` → yellow `[ ! ] text`
   - `error` → red only for **truly fatal** errors (loop crashed, agent
     raised); for retryable LLM errors use `warn`.
2. Replace the two `Panel.fit(...red...)` calls in `repl.py` with the
   appropriate level.
3. Commit `refactor(ui): system messages replace ad-hoc error panels`.

#### Task B.7 — Multi-line result preview with `…` collapse

**Files:**
- `src/eaccode/ui/preview.py`
- `tests/unit/test_preview.py`

**Steps:**
1. Extend `build_call_card` with `result_lines=3` and a `collapsed: bool`
   derived from `len(result) > 200`.
2. Render the result as up to N lines, then `… (12 more lines)` if
   collapsed; expand on click (Textual `on_click`) or `/verbose verbose`.
3. Commit `feat(ui): multi-line tool-result preview with collapse`.

### Phase C — Slash-command parity with Hermes / Claude Code

#### Task C.1 — `/cost` shows reset + rate limits

**Files:**
- `src/eaccode/ui/commands.py`
- `tests/unit/test_commands.py`

**Steps:**
1. Extend the `/cost` message with the model's RPM/TPM if the catalog
   has them; add `/cost reset` that zeroes `_total_usage`.
2. Tests for both paths.
3. Commit `feat(ui): /cost reset and rate-limit readout`.

#### Task C.2 — `/copy` cross-platform clipboard

**Files:**
- `src/eaccode/ui/repl.py`
- `tests/unit/test_repl.py`

**Steps:**
1. Detect platform. On Linux/macOS use `wl-copy` / `pbcopy`; on Windows
   keep `clip.exe`. Wrap in a `clipboard.copy(text)` helper.
2. `/copy` accepts an optional N (last N lines) like Hermes.
3. Commit `feat(ui): cross-platform /copy (Linux, macOS, Windows)`.

#### Task C.3 — `/status` (session, model, tokens, ctx%, workdir)

**Files:**
- `src/eaccode/ui/commands.py`
- `tests/unit/test_commands.py`

**Steps:**
1. Format a multi-line status block (plain text, no panel).
2. Tests: assert model, mode, workdir, total tokens, cost, ctx%.
3. Commit `feat(ui): /status`.

#### Task C.4 — `/diff [staged|all|session]`

**Files:**
- `src/eaccode/ui/commands.py`
- `src/eaccode/ui/diff_cmd.py` (new, thin wrapper over `subprocess.run(["git", ...])`)
- `tests/unit/test_commands.py`

**Steps:**
1. `staged` (default) = `git diff --staged`.
2. `all` = `git diff HEAD`.
3. `session` = diff between the files the agent touched this session
   (track in `_session_touched: set[Path]` populated by `write`/`edit`).
4. Render via `diff_render` (Task B.2).
5. Commit `feat(ui): /diff staged|all|session`.

#### Task C.5 — `/compress [here N]` (manual compaction)

**Files:**
- `src/eaccode/ui/commands.py`
- `src/eaccode/agent/compaction.py` (already exists, expose)
- `tests/unit/test_commands.py`

**Steps:**
1. `agent/compaction.py` already does it; expose a public
   `compact_messages(messages, keep_last_n=N)`.
2. Wire `/compress` to call it; `/compress here N` keeps last N user
   turns, the rest get a one-line summary.
3. Commit `feat(ui): /compress (manual context compaction)`.

#### Task C.6 — `/skills` (in-REPL browse/enable/disable)

**Files:**
- `src/eaccode/ui/commands.py`
- `src/eaccode/memory/skills.py` (already exists, extend)
- `tests/unit/test_commands.py`

**Steps:**
1. `/skills` lists loaded skills (name + one-line summary).
2. `/skills disable <name>` / `enable <name>` toggles a session flag,
   the next agent rebuild picks it up.
3. Commit `feat(ui): /skills browse/enable/disable`.

### Phase D — Verification & docs

#### Task D.1 — Update README

**Files:** `README.md`

**Steps:**
1. Replace the feature list with the truth (Phase B features now shipped).
2. Add a "UX parity" section listing what we ship that matches Hermes /
   Claude Code.
3. Commit `docs: README reflects Phase B UX`.

#### Task D.2 — Run full suite, smoke-test live

**Steps:**
1. `pytest -q` → all green (including A.3 regression).
2. `eaccode` → start REPL → run a real prompt that uses 3 tool calls →
   inspect: no errno-9, reasoning visible if `/reasoning on`, permission
   prompts are in-REPL modals with diff, status bar shows ctx%, spinner
   spins.
3. Commit nothing (this is the gate, not a task).

---

## 3. Risks & open questions

- **B.2 diff render** — `difflib.unified_diff` is OK for show, but for
  long files a structural diff (Patience, Myer's) would read better. Defer
  to v0.3 — current scope is "show the diff", not "show the best diff".
- **B.3 reasoning rendering** — reasoning_content can be **very** long
  (MiniMax-M3 burns 1k-3k tokens thinking on simple prompts). Need to cap
  display at 2 KB by default with `/reasoning show-full` to expand. Watch
  the context budget — rendering shouldn't cost us tokens on the next turn.
- **C.4 session diff** — "files the agent touched" requires us to track
  write/edit at the executor level. Hook point is `tools/executor.py:53`
  (after `tool.run` succeeds). Low risk, one-liner.
- **B.1 modal** — Textual modals are well-documented; risk is the
  permission prompt blocking forever if the user walks away. Add a 60s
  timeout → default deny (matches current non-TTY behavior).
- **Plan scope** — 18 tasks total, ~3 hours of focused work if each task
  is 5-10 min. Phases 0+A are blockers; B and C are independent and can
  be parallelized across two worktrees.

---

## 4. What we explicitly do NOT do this iteration

- New providers (Anthropic OAuth, Bedrock, Vertex) — current providers cover
  the user's two needs (MiniMax-M3 + opencode-go).
- GUI / web dashboard — CLI-first mandate, no scope creep.
- Multi-platform gateway (Telegram, Discord) — Hermes has it, eaccode is
  CLI-only by design.
- AGENTS.md / .cursorrules auto-injection — already shipped
  (`memory/project.py:discover_project_context`); no change.
- Tool marketplace / tool registry UI — `eaccode skills install` already
  exists; not user-reported as missing.
