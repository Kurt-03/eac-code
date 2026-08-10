# eaccode — Iteration N+1 Plan (errno 9 + UX + Hermes/Claude-Code parity)

> **For Hermes:** Use subagent-driven-development for tasks that touch >1 file.
> Use TDD: failing test → implementation → green → commit.
>
> This plan SUPERSEDES the 2026-08-06 plan and the 2026-08-09 first draft.
> Three rounds of digging (code grep, repro, hermes source on GitHub) refined
> the diagnosis. Read §1 carefully — half of what I "knew" in the first draft
> turned out wrong.

**Goal:** Stop crashing on tool calls (errno 9), stop looking like a chatbot,
match Hermes/Claude-Code for the features users actually feel.

**Architecture:** Async-everywhere in the REPL; `subprocess.run` always goes
through one helper that carries Windows `creationflags` (CREATE_NO_WINDOW +
CREATE_BREAKAWAY_FROM_JOB + process-group semantics on POSIX). Tool-call
rendering stays data-only (`ToolCallCard` dataclass + tool_guardrails decision).
Single-writer fence on the stream so a Ctrl+C never desyncs UI and producer.

**Tech Stack:** Python 3.14, Textual 8.x, Rich, LiteLLM, Pydantic v2, Click.

---

## 1. Honest diagnosis (what I got wrong, and what I got right)

### 1.1 errno 9 — what it actually is

**What I claimed in the first draft (wrong):** `asyncio.run()` inside the
Textual loop, in `ui/commands.py:159,170,178`, spawns a second event loop
that tears down the outer Proactor's pipes → next subprocess gets `EBADF`.

**Repro shows this is half-true:**

```
$ .venv/Scripts/python repro_repl_errno9.py
[1] building agent in bypass mode…
[2] first turn (write)…  → ok: 2 turn(s)
[3] simulating /remember via asyncio.run() …
    /remember raised: asyncio.run() cannot be called from a running event loop
[4] second turn (write) — does this fail with errno 9?
    ok: 1 turn(s)             ← NO errno 9
```

Py 3.14 **throws** `RuntimeError` instead of silently breaking the loop. So
the asyncio.run anti-pattern is real (still has to be fixed — it crashes
the slash command silently), but it is **not** the cause of the user's
errno 9.

**What is actually causing the user's errno 9 (verified by reading the
Hermes source):** `bash.py:38-54` runs the subprocess with `subprocess.run`
inside `asyncio.to_thread`, but **without** the Windows `creationflags` that
Hermes ships in `hermes_cli/_subprocess_compat.py` (464 lines, all of which
exist *exactly* for this class of crash). When Textual owns the console, a
naive `subprocess.run` of a console-subsystem child (anything .exe —
`mkdir`, `echo`, even `python` for the MCP server) inherits the console
handle, then closes it on the way out, then the parent's captured pipe
ends up reading from a handle that no longer points at a live process →
EBADF on the next read. Hermes added `_subprocess_compat.py` after exactly
this class of crash (see `bounded_git_probe` docstring, refs
openai/codex#34540 and #36793).

**Concretely, the missing flags on Windows are:**
- `CREATE_NO_WINDOW` (0x08000000) — prevents the inherited console from
  making the child flash + prevents the child's pipes from being tied to a
  console that closes.
- `CREATE_BREAKAWAY_FROM_JOB` (0x01000000) — escapes any job object the
  parent is in (Textual/Electron-wrapped parents, common in dev shells).
- `CREATE_NEW_PROCESS_GROUP` (0x00000200) — Ctrl+C in the parent doesn't
  propagate.
- On POSIX: `start_new_session=True` and `process_group=0` (Py 3.11+).
- Plus process-tree kill via `taskkill /T /F /PID` on Windows / `os.killpg`
  on POSIX when timing out — otherwise a suspended grandchild holds the
  pipe open forever.

**Second contributing factor (Hermes-style fix):** `bash.py` does
`subprocess.run(timeout=…)`. On timeout, Python's `run()` calls an
**unbounded** `communicate()` after killing — which deadlocks if any
descendant holds the pipes. Hermes' `bounded_git_probe` solves this with
explicit `communicate(timeout=…)` + tree-kill + 1 s bounded drain + abandon.

**Also missing on git calls:** `noninteractive_git_env()` — git on a private
remote will otherwise prompt on the inherited stdin and hang forever. eaccode
shells out to git from `orchestrator/worktree.py` and `cli/commands_queue.py`
without this guard.

**Also missing at import time:** `suppress_platform_ver_console()` — every
import that touches `platform.uname()` spawns a visible `cmd /c ver` window.
Cosmetic but jarring in a REPL.

### 1.2 UX-feels-like-a-chatbot — what I claimed vs. what's actually missing

**Claimed in first draft (5 causes). All real, but I undercounted.** The
full list of UX gaps vs. Hermes / Claude Code, after reading both codebases:

| # | Gap | Hermes does | Claude Code does | eaccode does today |
|---|-----|-------------|------------------|---------------------|
| 1 | In-REPL permission prompt with diff | `approvals.py` modal w/ diff | `⎿ Allow once / Always / Deny` | `click.confirm` → returns False silently in REPL (`prompts.py:34`) |
| 2 | Loop guardrails (same tool × N) | `agent/tool_guardrails.py` (632 lines) | v2.1.212 added per-turn caps | **none** |
| 3 | Single-writer stream fence | `agent/stream_single_writer.py` | implicit in Ink TUI | **none** — Ctrl+C during streaming can desync UI |
| 4 | Console window suppression | `_subprocess_compat.suppress_platform_ver_console()` | implicit in their bundling | **none** — `cmd /c ver` flashes per import |
| 5 | Streaming reasoning display | yes, collapsible | yes, collapsible | parsed but **dropped on the floor** (`repl.py:198`) |
| 6 | Spinner while working | kaomoji/emoji/unicode/ascii cycle | yes | static "… working" |
| 7 | Context-window % in status | yes | yes | token count + cost only |
| 8 | Multi-line tool result preview | 6-line preview + collapse | 6-line preview + collapse | 1 line truncated to 90 chars |
| 9 | System messages (`[ ! ]`) instead of red panels | yes | yes | `Panel.fit([red]...)` for every error |
| 10 | Diff render for write/edit before approve | yes | yes | **none** — user sees write after it lands |
| 11 | `/diff [staged\|all\|session]` | yes | yes | **none** |
| 12 | `/status` (session, model, tokens, ctx%, workdir) | yes | yes | **none** |
| 13 | `/compress` | `/compress here N` | `/compact` | exists in `agent/compaction.py`, no slash-cmd |
| 14 | `/skills` (in-REPL) | yes | yes | CLI subcommand only |
| 15 | Cross-platform `/copy` | yes | yes | `clip.exe` only (Windows) |
| 16 | Per-turn runaway-loop caps (web_search, delegate) | yes | yes | **none** |
| 17 | Tool-call-loop hints (different strategies on Nth retry) | yes (`_tool_failure_recovery_hint`) | yes | **none** |
| 18 | `[ctrl+y]` copy last answer | yes | yes | yes (Win only) |
| 19 | Empty-msg recovery from 401/402 with **fallback-also-failed** message | yes | yes | red panel |
| 20 | Approval-mode badge in status bar | yes | yes | yes (mode only, no badge) |

**Things I wrongly thought were fine:**
- **"permission prompts exist, they're just not in REPL."** No — in REPL
  they're denied silently. `prompts.py:23` `if not sys.stdin.isatty(): return False`.
  Every ASK-mode tool call from inside the REPL gets denied. The user
  *never sees a prompt* — that's the worst kind of UX failure.
- **"reasoning display is partial."** Actually **fully missing** — the
  parsed reasoning deltas are never wired into a callback (`repl.py:198`
  only registers `on_text_delta`).
- **"`/clear` resets messages, no confirm."** Correct, but Hermes also
  commits the cleared prefix to the session log so you can `/resume` to
  see it. We don't.

### 1.3 Things I undercounted from the first plan

- **`agent/shell_hooks.py` (39 KB)** in Hermes is a separate pre-/post-
  execution hook layer that wraps every shell tool call. eaccode has
  nothing equivalent — the safety checks are scattered between `safety.py`
  and `prompts.py`. **Worth a refactor**, not a rewrite.
- **Hermes' `_subprocess_compat` is also responsible for `git_probe`** —
  a fail-open git probe used everywhere git is called from non-interactive
  contexts. eaccode's `orchestrator/worktree.py` will block on a private
  remote's credential prompt today.
- **Hermes' `tool_guardrails` distinguish 3 tool classes**: idempotent
  (read-style), mutating (write-style), and runaway-prone (web_search,
  delegate_task). eaccode's `permission_mode` lumps them all into one
  ALLOW/ASK/DENY axis. **Adding a `ToolClass` enum** unlocks both the
  loop detector and per-turn caps in one stroke.

---

## 2. The Plan (TDD, bite-sized, ordered)

> Convention: every task lists a failing test first, then the implementation,
> then the commit. Each task = one commit. Phases can be parallelized across
> two worktrees after Phase B lands.

### Phase 0 — Hygiene (1 commit cycle)

#### Task 0.1 — Archive the obsolete plan + delete the first draft

**Files:**
- `.hermes/plans/archive/2026-08-06_143000-coding-agent-claude-code-clone.md` (move)
- `.hermes/plans/archive/2026-08-09_080000-eaccode-next-iter.md` (move — superseded)
- `.hermes/plans/2026-08-09_100000-eaccode-iteration-n+1.md` (this file)

**Why:** 252 KB of stale plan + my wrong first draft is worse than no plan.

**Steps:**
1. `mkdir -p .hermes/plans/archive`
2. `git mv` both old files.
3. Commit `chore(plans): archive obsolete 2026-08-06 plan and 2026-08-09 first draft`.

#### Task 0.2 — Mark the live integration test as `integration`

**Files:**
- `tests/integration/test_real_provider.py`
- `pyproject.toml`

**Steps:** as in first-draft Task 0.1 — pytest marker, soften assert,
add to default addopts. Commit `chore(tests): mark live-provider tests as integration`.

#### Task 0.3 — Split `llm/client.py` (391 LoC → 3 files)

**Files:**
- `src/eaccode/llm/client.py` (orchestration, < 200 LoC)
- `src/eaccode/llm/_resolve.py` (resolution + kwarg building)
- `src/eaccode/llm/_stream.py` (stream producer + queue)

Same shape as the first draft. Commit per move.

### Phase A — Fix the errno 9 crash (the real fix)

#### Task A.1 — Add `subprocess_compat` helper

**Files (new):**
- `src/eaccode/_subprocess_compat.py` (ported from Hermes, MIT, ~200 LoC, not 464)

**Scope:** minimal viable subset of Hermes' helper:
- `IS_WINDOWS = sys.platform == "win32"`
- `windows_hide_flags()` — `CREATE_NO_WINDOW` (0x08000000) — for short-lived
  helpers (bash, execute_code)
- `windows_detach_flags()` — adds `CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB`
  — for long-lived helpers (MCP server processes)
- `windows_popen_kwargs(detach=False)` — convenience wrapper
- `kill_process_tree(proc)` — `taskkill /T /F /PID` on Windows / `os.killpg`
  on POSIX
- `suppress_platform_ver_console()` — stub `platform._syscmd_ver`
- `noninteractive_git_env(base=None)` — adds `GIT_TERMINAL_PROMPT=0`,
  `GCM_INTERACTIVE=Never`

**Tests (new file):**
- `tests/unit/test_subprocess_compat.py`:
  - `test_windows_hide_flags_constant`
  - `test_windows_popen_kwargs_includes_no_window_on_windows`
  - `test_kill_process_tree_swallows_errors`
  - `test_noninteractive_git_env_sets_expected_vars`
  - `test_suppress_platform_ver_console_idempotent`

**RED:**
```python
def test_windows_popen_kwargs_includes_no_window_on_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    kwargs = windows_popen_kwargs()
    assert kwargs["creationflags"] & 0x08000000  # CREATE_NO_WINDOW
```

**GREEN:** copy the function bodies from Hermes, narrow to ~120 LoC.

**Commit:** `feat(subprocess): windows compat helper (CREATE_NO_WINDOW + tree-kill)`.

#### Task A.2 — `bash.py` uses the new helper

**Files:**
- `src/eaccode/tools/builtin/bash.py`
- `tests/unit/test_tool_bash.py`

**Changes:**
- Import `windows_popen_kwargs`, `kill_process_tree` from `_subprocess_compat`.
- Replace `subprocess.run(..., timeout=…)` with explicit `Popen` +
  bounded `communicate(timeout=timeout-0.5)` + tree-kill on timeout +
  1 s bounded drain + abandon. Mirror Hermes' `bounded_git_probe` flow.
- On Windows, pass `creationflags=windows_hide_flags()`.
- `stdin=DEVNULL` already there — keep.
- Add `env=noninteractive_git_env(env)` for the `git` subset.

**RED:** add a test that runs `bash.py` and asserts the platform-popen-
kwargs are applied (via a monkeypatched `subprocess.Popen` that records
its kwargs). Add a timeout test that asserts tree-kill is called.

**GREEN:** refactor.

**Commit:** `fix(tools): bash subprocess uses CREATE_NO_WINDOW + tree-kill on timeout`.

#### Task A.3 — `execute_code.py` uses the new helper (same fix)

**Files:**
- `src/eaccode/tools/builtin/execute_code.py`
- `tests/unit/test_tools_c.py`

**Commit:** `fix(tools): execute_code uses subprocess compat helper`.

#### Task A.4 — git shells out from `orchestrator/worktree.py` and `cli/commands_queue.py`

**Files:**
- `src/eaccode/orchestrator/worktree.py`
- `src/eaccode/cli/commands_queue.py`
- new: `src/eaccode/tools/git_probe.py` (wraps Hermes' `bounded_git_probe`)

**Changes:** any `subprocess.run(["git", ...])` becomes
`bounded_git_probe(argv, timeout=...)` with `noninteractive_git_env`.

**Commit:** `fix(git): bounded, fail-open git probe + non-interactive env`.

#### Task A.5 — Suppress the `cmd /c ver` console flash at startup

**Files:**
- `src/eaccode/__main__.py` (top of file, before any import that
  touches `platform.uname()`)

**Change:** call `suppress_platform_ver_console()` first thing.

**Commit:** `fix(startup): suppress platform._syscmd_ver console flash`.

#### Task A.6 — Slash commands no longer `asyncio.run` from inside Textual

**Files:**
- `src/eaccode/ui/commands.py`
- `src/eaccode/ui/repl.py` (expose a `run_worker`-based helper)
- `tests/unit/test_repl.py`

**Change:** introduce `_MemoryAdapter` protocol on the App, replace the
three `asyncio.run(...)` calls with `app.run_worker(coro)`.

**RED:**
```python
async def test_remember_does_not_call_asyncio_run_inside_loop(monkeypatch):
    called = []
    monkeypatch.setattr("asyncio.run", lambda coro: called.append(coro))
    handle_command("/remember foo", app)
    assert not called  # must use run_worker instead
```

**GREEN:** wrap each memory call.

**Commit:** `fix(ui): /memory commands use run_worker, not asyncio.run`.

#### Task A.7 — Regression test for errno 9

**Files:**
- `tests/integration/test_repl_errno9.py` (new, marked `integration`)

**Steps:** run a real `BashTool` with a long-running command, kill it
mid-stream, then run another `BashTool` — assert the second one doesn't
raise `EBADF`. (This is the closest we can get to the user's repro
without booting the whole REPL.)

**Commit:** `test(repl): regression for errno-9 after subprocess timeout`.

### Phase B — REPL UX to Hermes/Claude-Code level

#### Task B.1 — In-REPL permission modal (replaces click.confirm)

**Files:**
- `src/eaccode/permissions/prompts.py` (refactor signature)
- `src/eaccode/ui/permission_modal.py` (new, Textual `ModalScreen`)
- `src/eaccode/ui/repl.py` (mount the modal before executing ASK tools)
- `tests/unit/test_prompts.py`
- `tests/unit/test_permission_modal.py`

**Change:**
- `prompt_for_permission` returns `Action` enum (`ALLOW_ONCE | ALLOW_ALWAYS | DENY`)
  + an `asyncio.Future` the caller awaits. Non-TTY default → DENY (same as
  today) but with a logged reason, not silent.
- `PermissionModal` shows: tool name, primary-arg (formatted via
  `build_tool_preview`), and the 3 buttons. `y`/`n`/`a` shortcuts.
- 60 s timeout → DENY with reason "modal timed out".

**RED:**
```python
async def test_permission_modal_allow_once():
    modal = PermissionModal(tool="bash", arguments={"command": "ls"})
    # simulate keypress, assert dismiss("allow-once")
```

**GREEN:** build the modal.

**Commit:** `feat(ui): in-REPL permission modal (allow once/always/deny)`.

#### Task B.2 — Inline diff preview in permission modal

**Files:**
- `src/eaccode/ui/diff_render.py` (new, Rich renderer)
- `src/eaccode/ui/permission_modal.py` (use it for write/edit)
- `tests/unit/test_diff_render.py`

**Change:** `unified_diff` → `rich.text.Text` with `[green]+[/green]` /
`[red]-[/red]` / dim context. Default expanded if file < 200 lines,
collapsed otherwise (toggle with `space`).

**Commit:** `feat(ui): inline diff in permission modal`.

#### Task B.3 — Streamed reasoning displayed above the answer

**Files:**
- `src/eaccode/ui/repl.py` (wire `on_reasoning_delta`)
- `src/eaccode/ui/preview.py` (add `ReasoningBlock` dataclass)
- `src/eaccode/ui/reasoning_widget.py` (new, collapsible)
- `tests/unit/test_repl.py`

**Change:** Reasoning deltas accumulate into a single dim-italic block
above the answer text. Default: collapsed, "thought for 1.2s". `/reasoning on`
expands. Cap display at 2 KB; `/reasoning show-full` shows the rest.

**Commit:** `feat(ui): render streaming reasoning above answer`.

#### Task B.4 — Spinner + animated working indicator

**Files:**
- `src/eaccode/ui/repl.py`
- `tests/unit/test_repl.py`

**Change:** replace static `… working` with a `Spinner` widget
(`rich.spinner.Spinner`). 8 fps. Hide on first text delta or tool card.

**Commit:** `feat(ui): animated spinner while agent works`.

#### Task B.5 — Context-window % in status bar

**Files:**
- `src/eaccode/llm/models.py` (add `ctx_window: int = 128_000` per model)
- `src/eaccode/ui/repl.py` (status bar)
- `tests/unit/test_repl.py`

**Commit:** `feat(ui): context-window % in status bar`.

#### Task B.6 — System messages (`[ i ]`, `[ ! ]`) replace red panels

**Files:**
- `src/eaccode/ui/messages.py` (new, `write_info/write_warn/write_error`)
- `src/eaccode/ui/repl.py` (replace two `Panel.fit([red]...)` calls)
- `tests/unit/test_repl.py`

**Change:** error panel reserved for **fatal** errors (loop crash). All
retryable LLM errors → `write_warn` with the recovery hint. Info → dim
`[ i ]`.

**Commit:** `refactor(ui): system messages replace ad-hoc error panels`.

#### Task B.7 — Multi-line tool-result preview with collapse

**Files:**
- `src/eaccode/ui/preview.py`
- `tests/unit/test_preview.py`

**Change:** extend `build_call_card` with `result_lines=3`. Collapse
beyond 200 chars. Click or `/verbose verbose` expands.

**Commit:** `feat(ui): multi-line tool-result preview with collapse`.

### Phase C — Tool-loop guardrails (Hermes parity)

#### Task C.1 — `ToolClass` enum + per-tool classification

**Files:**
- `src/eaccode/tools/base.py` (add `class Tool(ABC): loop_class: ClassVar[str] = "idempotent"`)
- `src/eaccode/tools/builtin/*.py` (annotate each: bash/execute_code/delegate_task/web_search → `mutating` or `runaway`; read/glob/grep/web_fetch → `idempotent`; write/edit/todo/skill_create → `mutating`)
- `tests/unit/test_tool_registry.py`

**Commit:** `feat(tools): ToolClass enum (idempotent|mutating|runaway)`.

#### Task C.2 — `ToolCallGuardrailController`

**Files (new):**
- `src/eaccode/agent/guardrails.py` (~250 LoC, ported from Hermes)
- `tests/unit/test_guardrails.py`

**Port from Hermes `agent/tool_guardrails.py`:**
- `ToolCallSignature` (tool_name + sha256 of canonical args)
- `ToolGuardrailDecision` (`allow | warn | block | halt`)
- `before_call()` / `after_call(failed=...)`
- Counts: `_exact_failure_counts`, `_same_tool_failure_counts`,
  `_no_progress`, `_turn_web_search_count`, `_turn_subagent_count`
- `_tool_failure_recovery_hint(tool_name, count)` — strategy hints:
  "Bash failed 3×: maybe quote the path / use a here-doc / try with
  smaller scope."

**Commit:** `feat(agent): tool-call guardrail controller (loops + runaway caps)`.

#### Task C.3 — Wire guardrails into `agent/loop.py`

**Files:**
- `src/eaccode/agent/loop.py` (call `guardrails.before_call` /
  `after_call` around `executor.execute`)
- `src/eaccode/agent/factory.py` (build a guardrail instance)
- `tests/unit/test_agent_loop.py` (assert loop stops after Nth failure)

**Change:** on `decision.action == "block"`, return a synthetic
`ToolResult(content=decision.message, is_error=True)` and skip execution.
On `halt`, raise `MaxTurnsExceededError` with the decision message.

**Commit:** `feat(agent): wire guardrails into tool loop`.

#### Task C.4 — Single-writer stream fence

**Files (new):**
- `src/eaccode/llm/stream_fence.py` (~70 LoC, ported from Hermes)
- `src/eaccode/llm/client.py` (claim token before streaming, check on each chunk)
- `tests/unit/test_client.py`

**Change:** on `Ctrl+C` mid-stream, the producer is fenced — a new
turn's chunks are dropped, the UI doesn't get desynced.

**Commit:** `feat(llm): single-writer stream fence (Ctrl+C safe)`.

### Phase D — Slash-command parity

#### Task D.1 — `/status`, `/diff`, `/compress`, `/skills` (in-REPL)

**Files:**
- `src/eaccode/ui/commands.py`
- `src/eaccode/ui/diff_cmd.py` (new)
- `src/eaccode/memory/skills.py` (extend for session toggle)
- `tests/unit/test_commands.py`

**Tasks (bite-sized, one commit each):**
- `feat(ui): /status (session, model, tokens, ctx%, workdir)`
- `feat(ui): /diff staged|all|session`
- `feat(ui): /compress [here N]`
- `feat(ui): /skills (in-REPL browse/enable/disable)`

#### Task D.2 — Cross-platform `/copy` + extended `/cost`

**Files:**
- `src/eaccode/ui/repl.py` (replace `clip.exe` call)
- `src/eaccode/ui/clipboard.py` (new, `pbcopy`/`wl-copy`/`clip.exe`)
- `src/eaccode/ui/commands.py` (`/cost reset`)
- `tests/unit/test_repl.py`
- `tests/unit/test_clipboard.py`

**Commits:**
- `feat(ui): cross-platform /copy (pbcopy/wl-copy/clip.exe)`
- `feat(ui): /cost reset and rate-limit readout`

### Phase E — Verification

#### Task E.1 — Run full suite, manual smoke

**Steps:**
1. `pytest -q` → all green.
2. `eaccode` → run a real "erstelle test.txt auf dem Desktop" prompt:
   - in-REPL permission modal appears with diff
   - no errno 9
   - spinner spins during reasoning
   - reasoning visible (if `/reasoning on`)
   - status bar shows ctx%
   - system message (not red panel) on any non-fatal error
3. Commit nothing (gate).

#### Task E.2 — Update README

**Files:** `README.md`

**Steps:** rewrite the feature list with the truth (Phase B/C/D shipped).
Mention parity with Hermes/Claude Code and what still differs.
Commit `docs: README reflects Phase B/C/D UX`.

---

## 3. Risks & open questions

- **Phase A.2 tree-kill on Windows requires `taskkill` on PATH.** It is, on
  every Windows since Vista — but worth a test.
- **Phase C.2 guardrails use `_subagent_spawn_count(args)`** — Hermes
  walks the args dict for "spawn N agents". We don't have
  `delegate_task(parallelism=…)` yet (current `delegate_task` is 1 task).
  Stub the helper to always return 1 for now; revisit when we add parallel
  spawn.
- **Phase B.3 reasoning cap at 2 KB** — MiniMax-M3 can produce 5 KB of
  reasoning on a hard prompt. `/reasoning show-full` shows the rest, but
  that's a per-turn toggle, not a session-wide policy. Add a session flag
  later if users complain.
- **Phase B.1 modal timeout 60 s** — Hermes uses 120 s. Pick what feels
  right after manual testing; start with 60 s and adjust.
- **Plan scope** — 28 tasks across 5 phases, ~5-7 hours of focused work
  if each task is 10-15 min. Phases A and B can run in parallel
  (independent files). Phase C depends on Phase B.3 / B.7 for the
  guardrail UI integration.
- **Stream-fence interaction with retry/fallback** — `complete()` walks
  fallback chain on 401; `stream()` does not (the bug is "stream is
  half-done, now switch provider"). Phase D task (not in this plan):
  factor `stream()` into `_stream_once(provider, model)` + a fallback
  loop that mirrors `complete()`. Out of scope here; tracked for next
  iteration.

---

## 4. What we explicitly do NOT do this iteration

- New providers (Anthropic OAuth, Bedrock, Vertex).
- GUI / web dashboard.
- Multi-platform gateway (Telegram, Discord) — Hermes has it, eaccode is
  CLI-only by design.
- ACP server for IDE integration.
- Tool marketplace UI.
- Parallel `delegate_task` (Hermes' `_subagent_spawn_count` helper returns
  1 until we add it).
- `stream()` retry/fallback loop (tracked for next iteration).
- Approval queue for non-TTY sessions (Hermes' `hermes_cli/approvals.py`
  is a full sub-system for it; we punt until we have a real second user).

---

### Phase F — Input-UX: slash-command autocomplete + context completions

> **User-reported gap:** typing `/` in the eaccode REPL shows **no command
> suggestions** (no autocomplete/predictive fill). Verified: `grep -rn
> "suggester" src/ tests/` → 0 hits; `repl.py:93` creates a bare
> `Input(placeholder=...)` with no `suggester=`.
>
> **Hermes reference (verified in `hermes_cli/commands.py`, 100 KB):**
> - Single source of truth: `COMMAND_REGISTRY: list[CommandDef]` — each
>   CommandDef carries `name, description, category, aliases, args_hint,
>   subcommands, busy_policy`.
> - `SlashCommandCompleter(Completer)` with `get_completions(document, ...)`:
>   - `/`-prefix → command completions from the registry, with the
>     description as `display_meta` in the dropdown.
>   - base command typed + space → **subcommand completions** (static list
>     from `CommandDef.subcommands`, e.g. `/config show`, `/queue status`).
>   - dynamic completions for `/skin`, `/personality`, `/tools`, `/handoff`
>     (runtime lists, not static).
>   - **`@` context completions** (Claude Code-style): `@diff`, `@staged`,
>     `@file:`, `@folder:`, `@git:N`, `@url:` — with a `_file_cache` for
>     fuzzy project-file matching.
>   - **path completions** for words containing `/` (`./`, `../`, `~/`),
>     excluding URL schemes (`://`); dirs get a trailing `/` and a
>     "dir" meta.
>   - `_PICKER_COMMANDS = {"model", "skin", "personality"}` — no trailing
>     space so Enter executes the picker instead of filling the arg.
> - **Textual 8.2.8 supports this natively** (verified in `.venv`):
>   `textual.suggester.Suggester` (subclass, `get_suggestion(value) -> str | None`)
>   and `SuggestFromList`; `Input(suggester=...)` is a real parameter.
>   The dropdown is built into Textual — we only supply the suggestion
>   strings + meta.

#### Task F.1 — Refactor `ui/commands.py` to a command registry

**Files:**
- `src/eaccode/ui/commands.py` (replace the if-chain with a registry)
- `src/eaccode/ui/command_def.py` (new: `@dataclass(frozen=True) class CommandDef`)
- `tests/unit/test_commands.py`

**Why:** The current `handle_command` if-chain (`commands.py:35-149`) is
data, not logic — the same info lives in `HELP_TEXT` (which drifts from
the code). A registry gives autocomplete, `/help`, and dispatch one source
of truth (Hermes' `COMMAND_REGISTRY` pattern).

**RED:**
```python
def test_registry_covers_all_dispatchable_commands():
    for name, fn in DISPATCH_TABLE.items():
        assert any(c.name == name for c in COMMAND_REGISTRY), name

def test_registry_entries_have_help_text():
    for c in COMMAND_REGISTRY:
        assert c.description, c.name
        assert c.category in {"Session", "Configuration", "Tools & Skills", "Info", "Exit"}
```

**GREEN:** build `CommandDef` (name, description, category, aliases,
args_hint, subcommands, handler) + `COMMAND_REGISTRY` + `dispatch(text, app)`
that looks up by name/alias and calls the handler. Keep `/help` rendering
from the registry (grouped by category, like Hermes' gateway help).

**Commit:** `refactor(ui): slash commands backed by COMMAND_REGISTRY`.

#### Task F.2 — `SlashCommandSuggester` (Textual)

**Files:**
- `src/eaccode/ui/suggester.py` (new: subclass of `textual.suggester.Suggester`)
- `src/eaccode/ui/repl.py` (attach `suggester=SlashCommandSuggester(...)` to `#input`)
- `tests/unit/test_suggester.py`

**RED:**
```python
def test_slash_prefix_returns_matching_commands():
    s = SlashCommandSuggester(COMMAND_REGISTRY)
    out = s.get_suggestion("/m")
    assert out.startswith("/model") or out.startswith("/memory") or out.startswith("/mode")

def test_non_slash_returns_none():
    s = SlashCommandSuggester(COMMAND_REGISTRY)
    assert s.get_suggestion("hello") is None
```

**GREEN:** `get_suggestion(value)`:
- value starts with `/` → find the longest registry entry (name or alias)
  whose prefix matches; return it **with trailing space** (so the user can
  keep typing args), except for picker commands (`/model`, `/mode`).
- subcommand support: if text is `/config s` → suggest `/config show`.
- else → `None`.

**Note:** Textual's `Suggester` is single-suggestion (returns one string),
not a dropdown list like prompt_toolkit. For a richer multi-suggestion
dropdown with descriptions, use Textual's `SuggestFromList` + a custom
populated list, or the `Select`-based command palette. Start with the
Suggester (one best match); iterate to a full palette in F.3 if the
single-suggestion feel is too weak.

**Commit:** `feat(ui): slash-command autocomplete via Suggester`.

#### Task F.3 — Command palette (`Ctrl+K` / `Ctrl+P` style)

**Files:**
- `src/eaccode/ui/command_palette.py` (new: Textual `ModalScreen` with a
  `ListView` of commands, grouped, filterable by typing)
- `src/eaccode/ui/repl.py` (bind `ctrl+k` to open it)
- `tests/unit/test_command_palette.py`

**Why:** Hermes' desktop app has ⌘K; Claude Code has `Tab`-cycle on the
input. A modal palette is the single highest-leverage input feature: every
command + description visible, type to filter, Enter to run. Works even
for commands with long names (`/bypassPermissions`-style).

**RED:**
```python
async def test_palette_filters_by_typed_text():
    palette = CommandPalette(COMMAND_REGISTRY)
    await palette.filter("/ver")  # /verbose
    assert len(palette.visible_commands) >= 1
    assert palette.visible_commands[0].name == "verbose"
```

**GREEN:** build the modal: `Input` (filter) on top, `ListView` below with
`name — description`. Enter runs the command. Esc closes.

**Commit:** `feat(ui): Ctrl+K command palette (filterable)`.

#### Task F.4 — `@` context completions (Claude Code / Hermes parity)

**Files:**
- `src/eaccode/ui/suggester.py` (extend: `@` handling)
- `src/eaccode/ui/context_refs.py` (new: static refs + file matching)
- `tests/unit/test_suggester.py`

**RED:**
```python
def test_at_completions_static():
    s = SlashCommandSuggester(COMMAND_REGISTRY)
    out = s.get_suggestion("@di")
    assert out.startswith("@diff")

def test_at_completions_ignore_urls():
    s = SlashCommandSuggester(COMMAND_REGISTRY)
    assert s.get_suggestion("https://") is None
```

**GREEN:** port Hermes' `_extract_context_word` + `_context_completions` +
`_path_completions` logic (static refs: `@diff`, `@staged`, `@file:`,
`@folder:`, `@git:`, `@url:`), scoped to what eaccode actually supports
today (`@diff` → `/diff all` output; `@file:` → read tool; `@url:` →
web_fetch). Files matched via a cached `os.listdir` walk.

**Commit:** `feat(ui): @ context completions (@diff, @file:, @url:)`.

#### Task F.5 — Path completion in the input

**Files:**
- `src/eaccode/ui/suggester.py` (extend: path-like words)
- `tests/unit/test_suggester.py`

**RED:**
```python
def test_path_completion(tmp_path):
    (tmp_path / "main.py").touch()
    s = SlashCommandSuggester(COMMAND_REGISTRY)
    out = s.get_suggestion(f"./{tmp_path.name}/ma")
    assert out is not None and out.endswith("main.py")
```

**GREEN:** port Hermes' `_extract_path_word` + `_path_completions`
(prefix match in the word's directory; dirs get trailing `/`; skip
`://` tokens). This makes `write ./src/ma<tab>` → `main.py` work.

**Commit:** `feat(ui): path completion in input (dir-aware)`.

### Phase G — High-value features (from the value matrix, §6)

#### Task G.1 — `/status` (session, model, tokens, ctx%, workdir)

**Files:**
- `src/eaccode/ui/commands.py` (registry entry + handler)
- `tests/unit/test_commands.py`

**Steps:** plain multi-line block; assert model, mode, workdir, total
tokens, cost, ctx% (from B.5).

**Commit:** `feat(ui): /status`.

#### Task G.2 — `/diff [staged|all|session]`

**Files:**
- `src/eaccode/ui/commands.py`
- `src/eaccode/ui/diff_cmd.py` (new: `git diff` wrapper, uses
  `bounded_git_probe` from A.4 so it can't hang on credential prompts)
- `src/eaccode/tools/executor.py` (track `_session_touched` on write/edit)
- `tests/unit/test_commands.py`

**Commit:** `feat(ui): /diff staged|all|session`.

#### Task G.3 — `/compress [here N]`

**Files:**
- `src/eaccode/ui/commands.py`
- `src/eaccode/agent/compaction.py` (already exists — expose
  `compact_messages(messages, keep_last_n)`)
- `tests/unit/test_commands.py`

**Commit:** `feat(ui): /compress (manual context compaction)`.

#### Task G.4 — Cross-platform `/copy`

**Files:**
- `src/eaccode/ui/clipboard.py` (new: `pbcopy`/`wl-copy`/`clip.exe`)
- `src/eaccode/ui/repl.py`
- `tests/unit/test_clipboard.py`

**Commit:** `feat(ui): cross-platform /copy`.

#### Task G.5 — `/cost reset` + rate-limit readout

**Files:**
- `src/eaccode/ui/commands.py`
- `tests/unit/test_commands.py`

**Commit:** `feat(ui): /cost reset and rate-limit readout`.

#### Task G.6 — Session titles (auto-name from first prompt)

**Files:**
- `src/eaccode/sessions/store.py` (extend `create_session`)
- `src/eaccode/ui/repl.py` (set title on first message)
- `tests/unit/test_sessions.py`

**Why:** Hermes names sessions from the first user message (`/title [name]`).
eaccode's session list (`eaccode sessions`) shows untitled rows today —
auto-naming makes `--resume` usable.

**Commit:** `feat(sessions): auto-title sessions from first prompt`.

#### Task G.7 — `/help` grouped by category (registry-driven)

**Files:**
- `src/eaccode/ui/commands.py` (replace static HELP_TEXT with registry
  rendering, grouped by `category`)
- `tests/unit/test_commands.py`

**Commit:** `feat(ui): /help grouped by category (registry-driven)`.

---

## 5. Verified references (sources I actually read for this plan)

- `hermes_cli/_subprocess_compat.py` (464 LoC) — full read, lines 1-200 +
  200-464 (Windows flags, `bounded_git_probe`, `noninteractive_git_env`).
- `agent/stream_single_writer.py` (70 LoC) — full read.
- `agent/tool_guardrails.py` (632 LoC) — full read (lines 1-500+).
- `agent/tool_executor.py` — API listing (111 KB), referenced via
  GitHub tree API, not downloaded.
- `agent/shell_hooks.py` — API listing (39 KB), referenced.
- `hermes_cli/commands.py` (100 KB), `hermes_cli/main.py` (509 KB) —
  downloaded but not yet read in detail; out of scope for this iteration
  (commands parity is Phase D, which uses the skill's slash-commands
  reference).
- `agent/file_safety.py` — API listing (28 KB), referenced; eaccode's
  `tools/safety.py` is simpler but covers the same ground.
- Codebase grep of eaccode for `asyncio.run`, `creationflags`, `DEVNULL`,
  `process_group`, `killpg`, `taskkill` — found 0 matches for the last
  four in `src/`. That is the proof we need `subprocess_compat`.
- Repro script: `_write_count["n"]` mock stream with write-only LLM,
  `/remember` simulated via `asyncio.run()` from a long-lived loop. Output
  above (§1.1).

---

## 6. Feature value matrix — what actually pays off

Not everything Hermes has is worth porting. Scored by **value to a
CLI-first BYOK coding agent** (user-reported pain + frequency of use +
implementation cost), not by parity lust:

### 6.1 Input & command UX (highest leverage — user-reported)

| Feature | Value | Cost | Why |
|---|---|---|---|
| Slash-command autocomplete (`/` → suggestions) | ★★★★★ | S | User reported it directly. Hermes: `COMMAND_REGISTRY` + `SlashCommandCompleter`. Textual 8.2.8 has `Suggester` built in. |
| Command palette (`Ctrl+K`, filterable modal) | ★★★★★ | M | Every command discoverable without memorizing; Hermes desktop has ⌘K, Claude Code has Tab-cycle. |
| `/help` grouped by category | ★★★★☆ | S | Registry-driven (F.1), nearly free once the registry exists. |
| `@` context completions (`@diff`, `@file:`) | ★★★★☆ | M | Claude Code signature feature; makes "here's the diff" a keystroke instead of prose. |
| Path completion (`./src/ma<tab>`) | ★★★★☆ | S | Feels native; users type paths constantly in write/bash prompts. |
| Subcommand completions (`/config <tab>` → show…) | ★★★☆☆ | S | Falls out of F.1/F.2 (CommandDef.subcommands). |

### 6.2 Reliability (crash fixes — second-highest)

| Feature | Value | Cost | Why |
|---|---|---|---|
| Subprocess compat (CREATE_NO_WINDOW, tree-kill) | ★★★★★ | S | Directly fixes the reported errno 9. Hermes: `_subprocess_compat.py`. |
| Bounded git probe + non-interactive env | ★★★★☆ | S | Prevents hangs on private remotes (worktree, queue, /diff). |
| Tool-loop guardrails (same-failure×N → hint) | ★★★★☆ | M | Stops the "write → fail → retry forever" spiral (Hermes: `tool_guardrails.py`). |
| Stream single-writer fence | ★★★☆☆ | S | Ctrl+C mid-stream can't desync UI. |
| Suppress `cmd /c ver` flash | ★★☆☆☆ | S | Cosmetic but cheap; every import of `platform.uname()` flashes a window in a REPL. |

### 6.3 Permission UX (correctness of the ASK path)

| Feature | Value | Cost | Why |
|---|---|---|---|
| In-REPL permission modal (y/n/a + diff) | ★★★★★ | M | Today ASK is silently denied in the REPL (verified `prompts.py:23`) — the user never sees prompts. Claude Code's `Allow once/Always/Deny` is table stakes. |
| 60s modal timeout → deny | ★★★☆☆ | S | Hermes uses 120s; prevents a hung agent when the user walks away. |

### 6.4 Session & context

| Feature | Value | Cost | Why |
|---|---|---|---|
| Session auto-titles from first prompt | ★★★★☆ | S | `--resume`/`eaccode sessions` become usable. |
| `/status` | ★★★☆☆ | S | Cheap; model/ctx%/tokens at a glance. |
| `/compress [here N]` | ★★★★☆ | M | Long sessions hit context limits; compaction exists (`agent/compaction.py`) but is unreachable from the REPL. |
| `/diff [staged\|all\|session]` | ★★★★☆ | M | Core coding-agent workflow (see what changed before committing). |
| Cross-platform `/copy` | ★★★☆☆ | S | Only Windows `clip.exe` today. |

### 6.5 Deliberately NOT ported (low value for eaccode)

| Hermes feature | Why not |
|---|---|
| Multi-platform gateway (Telegram/Discord/…) | eaccode is CLI-first by design; a gateway is a whole new product. |
| Desktop app / web dashboard | CLI-first mandate. |
| Pet mascots / skins / TUI widgets | Cosmetic; the user explicitly rejected "buntes Zeugs". |
| Skill bundles (`/<name>` loads several skills) | eaccode has `eaccode skills install`; bundles add indirection without user demand. |
| `/moa` (Mixture-of-Agents), `/kanban`, `/goal` | Sophisticated multi-agent features; YAGNI until the core loop is stable. |
| Plugin system | Extensibility yes, but plugins need a stable core API first — revisit after 0.3. |
| `/snapshot`, `/redraw`, `/indicator`, `/battery`, `/timestamps` | Cosmetic or niche; pollutes the command surface. |
| Memory approval gate (`/memory pending|approve|reject`) | eaccode's auto-memory is simpler and hasn't caused a complaint yet. |
| Provider credential pools (rotation) | eaccode has fallback chain; pools are a per-provider concern. Defer. |

### 6.6 Architecture comparison (what's structurally different)

| Dimension | Hermes | eaccode | Gap severity |
|---|---|---|---|
| CLI input layer | prompt_toolkit (Completer, AutoSuggest) | Textual `Input` (no suggester) | **HIGH** — autocomplete impossible today |
| Command dispatch | `COMMAND_REGISTRY` data-driven | if-chain in `handle_command` | **MEDIUM** — /help drifts from code |
| Tool executor | `agent/tool_executor.py` (111 KB) + guardrails | `tools/executor.py` (69 LoC) | **LOW** — simpler is fine; guardrails are the gap |
| Subprocess layer | `_subprocess_compat.py` (464 LoC) | raw `subprocess.run` in 2 tools | **HIGH** — errno 9 |
| Surfaces | CLI, TUI, desktop, dashboard, gateway, ACP | REPL + headless `run` | **LOW** — by design |
| Loop protection | guardrails + loop caps + stream fence | max_turns only | **MEDIUM** — no same-failure detection |
| Permissions | approval system + smart heuristics | 4 modes + danger heuristics (policy.py) | **LOW-MEDIUM** — modes exist, REPL prompt broken |
| Sessions | state.db + FTS5 + titles | SQLite + FTS5 + search tool | **LOW** — titles missing |
| Memory | memory store + approval gate | store + auto-memory + skill tools | **LOW** |
| System prompt | `prompt_builder.py` (114 KB) + caching | `context.py` + cache (193 LoC) | **LOW** — eaccode's is lean by design |
| Git integration | `bounded_git_probe` everywhere | raw `subprocess.run` in worktree/queue | **MEDIUM** — hang risk |

**The one structural recommendation:** introduce a `src/eaccode/ui/command_def.py`
registry (F.1) before any other UI work. It unblocks autocomplete, /help
grouping, palette, and subcommand completion with a single data model —
the same move Hermes made when `COMMAND_REGISTRY` became its single source
of truth.

---

## 7. Full module-by-module gap analysis (eaccode vs. Hermes source)

Method: downloaded and read 20+ Hermes modules from `agent/` and
`hermes_cli/` (main branch, Aug 2026). Each row = one module, what it
does, whether eaccode has an equivalent, and the concrete port.

### 7.1 Reliability & subprocess (Phase A already covers the top items)

| Hermes module | What it does | eaccode equivalent | Gap |
|---|---|---|---|
| `hermes_cli/_subprocess_compat.py` (464 LoC) | CREATE_NO_WINDOW + tree-kill + bounded git probe + noninteractive git env + suppress `cmd /c ver` | `tools/builtin/bash.py` (raw `subprocess.run`) | **CRITICAL** — errno 9 root cause (Phase A.1-A.5) |
| `agent/bounded_response.py` (148 LoC) | Bounded read of HTTP error bodies on streaming requests (no unbounded `response.read()`) | none | **MEDIUM** — LiteLLM can hang reading a giant error body |
| `agent/reasoning_timeouts.py` (231 LoC) | Per-reasoning-model stale-timeout floor (MiniMax-M3 thinks >180s) | none | **HIGH** — MiniMax-M3 will trip any default stale detector; Hermes raises the floor for known reasoning models |
| `agent/retry_utils.py` (208 LoC) | Jittered backoff + parse Retry-After header + adaptive rate-limit backoff | `llm/client.py` uses tenacity `wait_exponential(min=1,max=10)` | **MEDIUM** — no jitter = thundering herd; no Retry-After respect |
| `agent/rate_limit_tracker.py` (246 LoC) | Parses `x-ratelimit-*` headers into buckets; renders `/usage` bars | none | **MEDIUM** — `/cost` shows $ only, no rate-limit state |
| `agent/error_classifier.py` (1.8k LoC) | Full taxonomy: retry / rotate credential / fallback / compress / abort + per-status extraction | `llm/errors.py` (3-way: STOP/RETRY/FALLBACK) | **MEDIUM** — eaccode lacks "rotate credential" and "compress context" recovery actions |
| `agent/credential_pool.py` (3.2k LoC) | Multi-key rotation per provider, exhausted-TTL, priority | `llm/model_switch.py` (FallbackChain across providers) | **LOW-MEDIUM** — fallback across providers exists; rotation within one provider doesn't |

### 7.2 Tool-call loop (Phase C already covers guardrails)

| Hermes module | What it does | eaccode equivalent | Gap |
|---|---|---|---|
| `agent/tool_executor.py` (2.4k LoC) | Sequential AND concurrent dispatch (`execute_tool_calls_concurrent` with `_ConcurrentToolAuthorizationGate`), batch-timeout, checkpoint-before-mutation, tool search scoping, managed results | `tools/executor.py` (69 LoC, sequential only) | **MEDIUM** — parallel tool calls would speed up read-heavy turns |
| `agent/tool_guardrails.py` (632 LoC) | Loop detection: same-failure×N → warn/halt, idempotent-no-progress, per-turn web_search/subagent caps | none | **HIGH** — Phase C.1-C.4 |
| `agent/tool_result_classification.py` (1.3k LoC... actually 42 LoC) | `file_mutation_result_landed()` — does the tool result actually prove the mutation landed | none | **MEDIUM** — LLM loops on "write succeeded?" otherwise |
| `agent/tool_dispatch_helpers.py` (28 KB) | Argument canonicalization, tool-name resolution, schema prep | `tools/schema.py`, `tools/base.py` | **LOW** — eaccode's simpler registry is fine |

### 7.3 Streaming & display (Phase B covers the user-visible half)

| Hermes module | What it does | eaccode equivalent | Gap |
|---|---|---|---|
| `agent/display.py` (1.5k LoC) | `build_tool_preview` (per-tool arg preview), `build_tool_label` (friendly verbs: "Reading docs/api.md" instead of `⎿ read(path=...)`), `summarize_shell_command` (same function name eaccode has — eaccode's is a *copy* of the original), diff-ANSI colors, `redact_tool_args_for_display` (browser typed text redaction), `LocalEditSnapshot` | `ui/preview.py` (copy of summarize_shell_command + build_call_card) | **MEDIUM** — friendly verbs, arg redaction, LocalEditSnapshot missing |
| `agent/think_scrubber.py` (396 LoC) | **Stateful** StreamingThinkScrubber — handles `<think>` tags split across stream deltas (MiniMax-M2.7/M3 stream `<think>` in 3 deltas; per-delta regex destroys state) | `llm/thinking.py` parses `reasoning_content` field, but **not** `<think>` tags in the text stream | **HIGH** — MiniMax-M3's actual thinking may arrive as `<think>` tags in content, not as `reasoning_content`; eaccode would leak them to the user |
| `agent/stream_single_writer.py` (70 LoC) | Single-writer fence: stale streams dropped, Ctrl+C-safe | none | **MEDIUM** — Phase C.4 |
| `agent/stream_diag.py` (9.9 KB) | Stream diagnostics for debugging provider weirdness | none | **LOW** — nice for `eaccode doctor` later |
| `agent/message_sanitization.py` (865 LoC) | Surrogate-pair repair (crash json.dumps), tool-call-args repair, unique/deterministic tool-call IDs, non-ASCII sanitize, interrupted tool-sequence close | none | **MEDIUM-HIGH** — MiniMax-M3 has been seen emitting malformed tool args; eaccode's `client.py:274` already catches JSON errors but doesn't *repair* them |

### 7.4 Context & system prompt

| Hermes module | What it does | eaccode equivalent | Gap |
|---|---|---|---|
| `agent/coding_context.py` (916 LoC) | **RuntimeMode / ContextProfile**: detects "are we coding?" → injects `build_coding_workspace_block()` into the system prompt: git branch → upstream → ahead/behind, linked-worktree detection, staged/modified/untracked/conflict counts, last 3 commits, project facts (manifest, package manager, **verify commands**, context files) | `memory/project.py` (EACCODE.md discovery only — no git state, no verify commands) | **HIGH** — the agent never knows the git state or how to run tests unless it guesses |
| `agent/context_references.py` (621 LoC) | **@-reference expansion**: `parse_context_references()` + `preprocess_context_references()` — resolves `@file:path`, `@folder:`, `@git:N`, `@url:` into actual content BEFORE the LLM call; `_expand_file_reference` adds metadata + code fence; `_build_folder_listing` via rg | none (only display-side @ completions planned in F.4) | **HIGH** — the *expansion* side (F.4 only plans the *completion* side) is what makes @-refs actually useful |
| `agent/context_compressor.py` (7.4k LoC) | Full auto-compression: head/tail protection, structured summary template (Resolved/Pending questions), skill-marker reinjection, redaction before compaction, auxiliary cheap model | `agent/compaction.py` (exists but minimal) | **MEDIUM** — Phase G.3 exposes `/compress`; full auto-compression is a later iteration |
| `agent/prompt_builder.py` (2.3k LoC) | `_load_agents_md` / `_load_claude_md` / `_load_cursorrules` directory chain (walks parents), `build_context_files_prompt`, skills manifest with **snapshot cache**, soul.md loading, environment hints | `memory/project.py` (EACCODE.md only, no parent chain, no cursorrules, no skills snapshot) | **MEDIUM** — parent-dir AGENTS.md chain + skills snapshot cache are cheap wins |
| `agent/prompt_caching.py` (15 KB) | Provider-aware prompt-cache redecoration (Anthropic cache_control, OpenAI prompt caching) | `agent/factory.py` caches the built string (good) but doesn't emit provider cache-control markers | **MEDIUM** — MiniMax/DeepSeek cache markers would cut cost |
| `agent/system_prompt.py` (32 KB) | The system-prompt template itself | `agent/context.py` (build_system_prompt) | **LOW** — eaccode's is lean by design |

### 7.5 Sessions & titles

| Hermes module | What it does | eaccode equivalent | Gap |
|---|---|---|---|
| `agent/title_generator.py` (653 LoC) | Two-stage titles: **instant deterministic** title from first user message (written before the model call — "session is named the moment it starts"), then **LLM upgrade** on a cheap tier with JSON-constrained response. Provenance `derived < llm < user` enforced by storage | `sessions/store.py` — sessions have no title | **MEDIUM** — Phase G.6 (auto-title) is the cheap 80% |
| `agent/context_breakdown.py` (13 KB) | Per-message context accounting | none | **LOW** — status-bar token count is enough for now |

### 7.6 Memory & skills

| Hermes module | What it does | eaccode equivalent | Gap |
|---|---|---|---|
| `agent/memory_manager.py` (1.2k LoC) | Provider abstraction, streaming context scrubber, memory context block builder | `memory/store.py` + `memory/skills.py` | **LOW** — eaccode's simpler store is fine; the scrubber (`StreamingContextScrubber`) is a nice-to-have |
| `agent/skill_commands.py` (33 KB) | Skills as slash commands (`/skill-name`), stacked skill invocation | `memory/skill_tools.py` (agent tools only) | **LOW-MEDIUM** — Phase G.6 `/skills` is the REPL-side slice |
| `agent/skill_bundles.py` (15 KB) | Bundles: one `/name` loads several skills | none | **LOW** — YAGNI until user asks |
| `agent/curator.py` (87 KB) | Skill curation with pinning, archiving, dedupe | `curator/curator.py` | **LOW** — already comparable |

### 7.7 Permissions & safety

| Hermes module | What it does | eaccode equivalent | Gap |
|---|---|---|---|
| `agent/file_safety.py` (693 LoC) | Write-denied paths/prefixes, **classified** denials (why blocked), cross-profile target warnings, sandbox-mirror warnings | `tools/safety.py` (67 LoC, simpler) | **LOW** — eaccode's is adequate; cross-profile warning is niche for single-profile CLI |
| `hermes_cli/approvals_suggest.py` (487 LoC) | Mines approval history from session DB → proposes allowlist globs (`hermes approvals suggest`) | none | **LOW** — nice; not needed until the permission modal (B.1) ships |
| `agent/shell_hooks.py` (1k LoC) | Pre/post tool-call shell-script hooks with consent + allowlist | none | **LOW-MEDIUM** — genuinely useful for power users (auto-format after write); defer |
| `hermes_cli/clipboard.py` (568 LoC) | Full clipboard: text + **images** via osascript/PowerShell/wayland | `ui/repl.py` (clip.exe text only) | **LOW** — image paste is a future feature; Phase G.4 covers text |

### 7.8 Architecture-level findings

1. **Hermes is a god-file-free codebase by explicit campaign**: `conversation_loop.py` docstring cites `~/.hermes/plans/god-file-decomposition.md`. eaccode's max file is 391 LoC (`llm/client.py`) — already better.
2. **Hermes splits sync/async cleanly**: `_subprocess_compat` helpers are **no-ops on POSIX** by design ("do no damage on non-Windows" guarantee). eaccode should adopt the same pattern rather than sprinkling `if sys.platform == "win32"`.
3. **Hermes' tool executor takes the agent as first arg** (module-level functions, not methods) — enables concurrent dispatch and independent testing. eaccode's `ToolExecutor` class is fine for sequential; parallel dispatch (7.2 row 1) would be the refactor.
4. **Hermes has a `_ra()` indirection** to avoid circular imports when extracted functions need run_agent symbols. eaccode's imports are already clean — no action.

### 7.9 Prioritized port list (beyond Phase A-G)

From the matrix above, the **next-highest-value ports after A-G**:

1. **Stateful think-scrubber** (`think_scrubber.py`) — HIGH, cheap (396 LoC, pure class, no deps). MiniMax-M3 will leak `<think>` blocks otherwise.
2. **Workspace block in system prompt** (`coding_context.py`) — HIGH, medium cost. The agent knowing git branch/status/verify commands transforms code quality.
3. **@-reference expansion** (`context_references.py`) — HIGH, medium cost. Pairs with F.4.
4. **Reasoning-model stale-timeout floor** (`reasoning_timeouts.py`) — HIGH, trivial (a dict of model-prefix → timeout floor).
5. **Tool-result mutation verification** (`tool_result_classification.py`) — MEDIUM, trivial (42 LoC).
6. **Friendly tool verbs** (`display.py` `_TOOL_VERBS`) — MEDIUM, trivial. "Running tests…" beats `⎿ bash(command="pytest")` in the status line.
7. **Jittered backoff + Retry-After** (`retry_utils.py`) — MEDIUM, trivial.
8. **Rate-limit tracker** (`rate_limit_tracker.py`) — MEDIUM, small.
9. **AGENTS.md parent-chain + cursorrules loading** (`prompt_builder.py`) — MEDIUM, small.

These are added as **Phase H** below.

---

## 8. Phase H — Ports from the gap analysis (§7.9)

#### Task H.1 — Stateful streaming think-scrubber

**Files:**
- `src/eaccode/llm/think_scrubber.py` (new, port of Hermes `StreamingThinkScrubber`, ~200 LoC)
- `src/eaccode/llm/client.py` (apply in `_produce` before putting content)
- `tests/unit/test_think_scrubber.py`

**Why:** MiniMax-M3 streams `<think>` split across deltas; eaccode's
`llm/thinking.py` only handles the `reasoning_content` field. Without the
scrubber, thinking leaks to the user as visible text.

**RED:**
```python
def test_think_split_across_deltas_is_scrubbed():
    s = StreamingThinkScrubber()
    assert s.feed("<thi") == ""
    assert s.feed("nk>secret plan") == ""
    assert s.feed("</think>visible") == "visible"
```

**GREEN:** port the state machine (in_block, _buf, partial-tag hold-back,
boundary gating). Reset at turn start.

**Commit:** `feat(llm): stateful streaming think-scrubber`.

#### Task H.2 — Workspace block in the system prompt

**Files:**
- `src/eaccode/agent/workspace.py` (new, port of Hermes `coding_context.py`
  `build_coding_workspace_block` + `detect_project_facts`, ~150 LoC)
- `src/eaccode/agent/context.py` (append workspace block to system prompt)
- `src/eaccode/agent/factory.py` (cache key must include git state; invalidate
  on change or per-session)
- `tests/unit/test_workspace.py`

**Why:** The agent never knows git branch/status or how to run tests unless it
guesses. Hermes injects: branch → upstream → ahead/behind, worktree note,
staged/modified/untracked/conflicts, last 3 commits, verify commands.

**RED:**
```python
def test_workspace_block_shows_git_state(tmp_path):
    init_git(tmp_path, branch="feature/x")
    block = build_coding_workspace_block(tmp_path)
    assert "feature/x" in block
    assert "Status: clean" in block

def test_project_facts_detect_verify_commands(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.pytest]\n")
    facts = detect_project_facts(tmp_path)
    assert "pytest" in facts.verify_commands
```

**GREEN:** port; use `bounded_git_probe` (A.4) for all git calls.

**Commit:** `feat(agent): workspace block (git state + verify commands) in system prompt`.

#### Task H.3 — @-reference expansion (beyond F.4 completion)

**Files:**
- `src/eaccode/ui/context_refs.py` (extend: `parse_context_references` +
  `preprocess_context_references` + `_expand_file_reference` +
  `_build_folder_listing`, ~250 LoC)
- `src/eaccode/agent/loop.py` (preprocess user messages before sending)
- `tests/unit/test_context_refs.py`

**Why:** F.4 only completes `@`-tokens in the input. Expansion resolves them
into actual content before the LLM call — that's what makes `@file:path`
useful.

**RED:**
```python
def test_file_reference_expands_to_fenced_content(tmp_path):
    (tmp_path / "a.py").write_text("x = 1")
    out = preprocess_context_references(f"@file:{tmp_path / 'a.py'} warum?")
    assert "a.py" in out and "x = 1" in out
```

**Commit:** `feat(agent): @-reference expansion (@file:, @folder:, @git:, @url:)`.

#### Task H.4 — Reasoning-model stale-timeout floor

**Files:**
- `src/eaccode/llm/reasoning_timeouts.py` (new, ~50 LoC)
- `src/eaccode/llm/client.py` (use in stream/complete timeout wiring)
- `tests/unit/test_reasoning_timeouts.py`

**Why:** MiniMax-M3 thinks >180s routinely; a default stale detector would
kill legitimate requests.

**RED:**
```python
def test_minimax_m3_gets_floor():
    assert get_reasoning_stale_timeout_floor("MiniMax-M3") is not None
```

**GREEN:** model-prefix → floor dict (`minimax` → 600s, `deepseek-r` → 300s).

**Commit:** `feat(llm): reasoning-model stale-timeout floor`.

#### Task H.5 — Tool-result mutation verification

**Files:**
- `src/eaccode/tools/result_classification.py` (new, ~40 LoC)
- `src/eaccode/agent/guardrails.py` (use in `after_call` failed-detection)
- `tests/unit/test_result_classification.py`

**Why:** An `is_error=False` result that doesn't prove the mutation landed
(`git status` output ≠ file exists) lets the LLM loop on "did it work?".

**RED:**
```python
def test_write_result_lands(tmp_path):
    (tmp_path / "f.txt").write_text("ok")
    assert file_mutation_result_landed("write", f"Wrote 2 bytes to {tmp_path/'f.txt'}")
```

**Commit:** `feat(agent): tool-result mutation verification`.

#### Task H.6 — Friendly tool verbs in status line

**Files:**
- `src/eaccode/ui/preview.py` (add `_TOOL_VERBS` + `build_tool_label`)
- `src/eaccode/ui/repl.py` (use label in tool cards)
- `tests/unit/test_preview.py`

**Why:** `⎿ Running tests…` reads better than `⎿ bash(command="pytest")`.

**Commit:** `feat(ui): friendly tool verbs (Reading/Writing/Running...)`.

#### Task H.7 — Jittered backoff + Retry-After

**Files:**
- `src/eaccode/llm/retry_utils.py` (new, ~80 LoC)
- `src/eaccode/llm/client.py` (replace tenacity wait with jittered)
- `tests/unit/test_retry_utils.py`

**Why:** no jitter = thundering herd on rate-limited providers; Retry-After
respect avoids burning retries.

**Commit:** `feat(llm): jittered backoff + Retry-After respect`.

#### Task H.8 — Rate-limit tracker

**Files:**
- `src/eaccode/llm/rate_limit.py` (new, ~100 LoC)
- `src/eaccode/llm/client.py` (capture x-ratelimit-* headers)
- `src/eaccode/ui/commands.py` (`/usage` shows buckets)
- `tests/unit/test_rate_limit.py`

**Commit:** `feat(llm): rate-limit tracking (x-ratelimit-* headers)`.

#### Task H.9 — AGENTS.md parent-chain + cursorrules

**Files:**
- `src/eaccode/memory/project.py` (extend: walk parent dirs for AGENTS.md,
  load .cursorrules, EACCODE.md)
- `tests/unit/test_project.py`

**Why:** Hermes loads `AGENTS.md`/`CLAUDE.md`/`.cursorrules` from the whole
parent chain; eaccode only reads EACCODE.md in cwd.

**Commit:** `feat(memory): AGENTS.md parent chain + .cursorrules loading`.

---

## 9. Complete task inventory (Phases 0, A-H)

| Phase | Tasks | Status |
|---|---|---|
| 0 — Hygiene | 0.1 archive plans, 0.2 mark integration tests, 0.3 split client.py | pending |
| A — errno 9 | A.1 subprocess_compat, A.2 bash, A.3 execute_code, A.4 git probe, A.5 suppress ver console, A.6 run_worker, A.7 regression | pending |
| B — REPL UX | B.1 permission modal, B.2 diff preview, B.3 reasoning display, B.4 spinner, B.5 ctx%, B.6 system msgs, B.7 multi-line result | pending |
| C — Guardrails | C.1 ToolClass, C.2 controller, C.3 wire loop, C.4 stream fence | pending |
| D — Slash parity | D.1 /status /diff /compress /skills, D.2 /copy /cost | pending |
| F — Input UX | F.1 registry, F.2 suggester, F.3 palette, F.4 @ completions, F.5 path completion | pending |
| G — High-value | G.1-G.7 (/status, /diff, /compress, /copy, /cost, titles, /help) | pending |
| H — Ports | H.1-H.9 (think-scrubber, workspace block, @-expansion, timeout floor, mutation verify, verbs, jitter, rate-limit, AGENTS.md chain) | pending |
| I — Toolset parity | I.0-I.15 (below) | pending |

**Total: 62 tasks.** Recommended execution order:
1. Phase 0 (hygiene, 30 min)
2. Phase A (errno 9 — user is blocked by it, 2 h)
3. Phase F.1 + F.2 (registry + autocomplete — user-visible input pain, 1 h)
4. Phase B (REPL UX — the "looks like a chatbot" complaint, 3 h)
5. Phase C + H.1/H.2/H.4 (loop safety + MiniMax-specific fixes, 2 h)
6. Phase G + D (slash parity, 2 h)
7. Phase H rest (ports, 2 h)
8. Phase I (toolset parity — biggest, 6-10 h, parallelizable in worktrees)
9. Phase E (verification + README)

---
## 10. Phase I — Toolset parity (Hermes' 27 toolsets → eaccode)

> **Policy: full ports, no v1 scoping.** Every tool gets the complete
> Hermes surface — all schema fields implemented, not "documented for
> later". The only exceptions are tools that are *physically impossible*
> without a messaging gateway (discord, yuanbao, stt) — those are
> explicitly marked gateway-dependent, not "deferred for polish".

### 10.1 The full inventory (verified from `hermes_cli/tools_config.py:96-124`)

Hermes ships **27 configurable toolsets**. Column "eaccode" = today.

| # | Toolset | Hermes tools | eaccode today | Plan |
|---|---|---|---|---|
| 1 | web | web_search, web_extract | web_search, web_fetch ✓ | I.6 web_extract (full) |
| 2 | browser | navigate, click, type, scroll, snapshot, back, get_images, console, press, vision, dialog, download | — | I.7 full CDP stack (as Hermes) |
| 3 | terminal | terminal, process | bash ✓ | I.2 process (full ProcessRegistry) |
| 4 | file | read, write, patch, search | read, write, edit, glob, grep ✓ | I.4 search_files (rg) |
| 5 | code_execution | execute_code | execute_code ✓ | done |
| 6 | vision | vision_analyze, video_analyze | — | I.3 full (both tools) |
| 7 | video | video_analyze | — | I.3 (same aux model path) |
| 8 | image_gen | image_generate | — | I.8 full registry (multiple providers) |
| 9 | video_gen | video_generate | — | I.9 opt-in, full provider registry |
| 10 | bfl | bfl_flux3_* | — | I.9 (same video_gen infra) |
| 11 | x_search | x_search | — | I.11 opt-in (xAI OAuth or XAI_API_KEY) |
| 12 | tts | text_to_speech | — | I.10 full (streaming + normalizers) |
| 13 | stt | voice transcription | — | gateway-dependent (voice mode) |
| 14 | skills | list, view, manage | skill tools ✓ | G.6 /skills REPL surface |
| 15 | todo | todo | todo ✓ | done |
| 16 | memory | memory tools | memory store ✓ | done |
| 17 | context_engine | runtime tools | — | I.12 plugin-style engine (full) |
| 18 | session_search | session_search | session_search ✓ | done |
| 19 | clarify | clarify | clarify ✓ | done |
| 20 | delegation | delegate_task | delegate_task ✓ (single-task) | I.13 parallel batch (tasks array) |
| 21 | cronjob | create/list/update/pause/resume/run | — | **I.1 (user-requested, full)** |
| 22 | homeassistant | smart home | — | I.14 opt-in (HASS_TOKEN) |
| 23 | spotify | playback | — | I.15 opt-in (OAuth) |
| 24 | discord | read/participate | — | gateway-dependent (needs channels) |
| 25 | discord_admin | server admin | — | gateway-dependent (needs channels) |
| 26 | yuanbao | group info | — | gateway-dependent (needs channels) |
| 27 | computer_use | capture/click/type/scroll/… via cua-driver | — | **I.5 (user-requested, full schema incl. cua_browser_\*)** |

**Already present (11/27):** web (half), terminal (half), file (most), code_execution, skills, todo, memory, session_search, clarify, delegation.
**Full ports (16):** I.1-I.15 below.
**Gateway-dependent (4):** stt, discord, discord_admin, yuanbao — require a messaging surface that does not exist in a CLI-first tool; they ship when eaccode gains a gateway. Not "deferred for polish" — architecturally impossible today.

### 10.2 Design: toolset infrastructure first (mirrors Hermes' `CONFIGURABLE_TOOLSETS`)

#### Task I.0 — Toolset registry in settings

**Files:**
- `src/eaccode/config/settings.py` (add `enabled_toolsets: list[str]`)
- `src/eaccode/tools/factory.py` (gate registry construction on the list)
- `src/eaccode/cli/commands_config.py` (`eaccode config toolsets` subcommand, checklist UI like Hermes `_prompt_toolset_checklist`)
- `tests/unit/test_settings.py`, `tests/unit/test_tool_registry.py`

**Why:** Hermes' 27 toolsets are a **registry** (`CONFIGURABLE_TOOLSETS`:
key, label, tool list), resolved per-platform, saved to
`platform_toolsets`, with `_DEFAULT_OFF_TOOLSETS` for niche ones.
eaccode's `build_default_registry` hardcodes the list. The registry is
the prerequisite for every I.x below.

**RED:**
```python
def test_toolset_gating():
    reg = build_default_registry(allowed_tools=None, enabled_toolsets=["file", "web"])
    names = {t.name for t in reg.list()}
    assert "read" in names and "web_search" in names
    assert "bash" not in names  # terminal toolset disabled
```

**GREEN:** `TOOLSETS: dict[str, set[str]]` in `tools/factory.py` (key →
tool names), `build_default_registry(enabled_toolsets=...)` filters.
Default-on set mirrors Hermes: everything except
`{homeassistant, spotify, discord, discord_admin, video_gen, x_search}`.

**Commit:** `feat(tools): toolset registry (eaccode toolsets config)`.

### 10.3 Cron jobs — full port

#### Task I.1 — `cronjob` tool + scheduler (complete surface)

**Files (new):**
- `src/eaccode/cron/scheduler.py` (SQLite job table + tick loop)
- `src/eaccode/cron/jobs.py` (full CRUD)
- `src/eaccode/tools/builtin/cronjob.py` (tool wrapper)
- `src/eaccode/cli/commands_cron.py` (`eaccode cron` CLI mirror)
- `tests/unit/test_cron.py`, `tests/unit/test_cronjob_tool.py`

**Hermes reference (verified):** `tools/cronjob_tools.py` (78 KB) — one
tool, `action` discriminator (create/list/update/pause/resume/remove/run),
`schedule` accepts `'30m'`, `'every 2h'`, cron `'0 9 * * *'`, or ISO
timestamp. Scheduler lives in `hermes_cli/cron.py` (24 KB).

**Complete schema — every field implemented (no dead fields):**
- `action`: create, list, update, pause, resume, remove, run — all real.
- `schedule`: `'30m'`, `'every 2h'`, cron, ISO — parser handles all four.
- `prompt`: self-contained job instruction (LLM jobs).
- `name`: human-friendly label.
- `repeat`: repeat count (once for one-shot, forever for recurring).
- `deliver`: `'origin'` (deliver to the REPL/session that created the job
  — the session DB records it and the REPL surfaces it as a system
  message on next launch or live via the worker) or `'local'` (save
  only). `'all'`/platform targets are gateway-era — but the *field* is
  implemented and validated, returning a clear "no gateway connected"
  error, never silently ignored.
- `skills`: ordered skill list loaded before the prompt runs.
- `script`: script path; stdout injected as context (default mode) or
  delivered verbatim with `no_agent=True` (watchdog mode).
- `monitor_script` / `monitor_url`: change-detection — unchanged output
  suppresses the run entirely (no LLM, recorded as `no_change` tick);
  changed output injects a MONITOR CHANGE DETECTED diff block. First
  tick always runs (baseline).
- `no_agent`: pure script watchdog — no LLM. Non-empty stdout delivered
  verbatim; empty stdout = silent; non-zero exit sends an error alert.
- `context_from`: job-chaining — most recent output of listed jobs is
  injected into the prompt.
- `enabled_toolsets`: restrict the job's agent to a subset (lower input
  token overhead).
- `workdir`: absolute path; AGENTS.md/CLAUDE.md/.cursorrules from that
  directory injected; tools run there. Jobs with workdir run
  sequentially.
- `attach_to_session`: the job's delivery becomes a continuable session
  (the user can reply to it in the REPL and the agent has the brief).
- Safety rule in the prompt: cron-run sessions must not recursively
  schedule more cron jobs.

**Scheduler runtime:** tick loop runs inside the REPL's event loop
(Textual `set_interval` worker) and as a background thread in headless
mode. `next_run` computed from schedule; missed ticks catch up; jobs
never double-fire.

**RED:**
```python
def test_cron_create_and_list(tmp_path):
    s = Scheduler(db=tmp_path / "cron.db")
    jid = s.create(schedule="30m", prompt="Run tests", name="nightly")
    assert s.list()[0].id == jid

def test_cron_no_agent_script_stdout_delivered(tmp_path):
    script = tmp_path / "watch.sh"; script.write_text("echo ok")
    s = Scheduler(db=tmp_path / "cron.db")
    jid = s.create(schedule="1h", script=str(script), no_agent=True)
    assert s.run_job(jid) == "ok\n"

def test_cron_monitor_script_suppresses_on_unchanged(tmp_path):
    script = tmp_path / "m.sh"; script.write_text("echo stable")
    s = Scheduler(db=tmp_path / "cron.db")
    jid = s.create(schedule="1h", monitor_script=str(script), prompt="p")
    first = s.run_job(jid)          # baseline: runs agent
    second = s.run_job(jid)         # unchanged: suppressed
    assert second.tick == "no_change" and second.ran_agent is False

def test_cron_deliver_unknown_target_errors_not_silent(tmp_path):
    s = Scheduler(db=tmp_path / "cron.db")
    jid = s.create(schedule="1h", prompt="p", deliver="discord:#x")
    assert "no gateway" in s.validate_deliver(jid).lower()
```

**GREEN:** full port. Cron expression parsing via `croniter` (add to
deps); interval parsing (`30m`, `every 2h`) via a small parser.

**Commit:** `feat(cron): cronjob tool — full surface (watchdog, monitor, chaining, workdir)`.

### 10.4 Computer use — full port

#### Task I.5 — `computer_use` tool (complete cua-driver integration)

**Files (new):**
- `src/eaccode/tools/builtin/computer_use.py` (tool wrapper)
- `src/eaccode/tools/cua.py` (cua-driver client, full action surface)
- `src/eaccode/tools/cua_install.py` (port of `install_cua_driver`:
  Windows-first, PowerShell + autostart repair)
- `src/eaccode/cli/commands_computer.py` (`eaccode computer doctor|install|status`)
- `tests/unit/test_cua.py`, `tests/unit/test_cua_install.py`

**Hermes reference (verified):** `tools/computer_use/tool.py` (56 KB) +
`tools/computer_use/schema.py` (COMPUTER_USE_SCHEMA, 348 lines — read
in full above) + `tools/computer_use/cua_backend.py` (147 KB) +
`tools_config.py` `install_cua_driver` (lines 908-1630, incl. Windows
autostart repair). cua-driver is a separate installed binary speaking
the OS accessibility API; Python side is a client.

**Complete schema — every action implemented:**
- `capture` with modes `som` (numbered element overlays + AX tree),
  `vision` (plain screenshot), `ax` (accessibility tree only).
  `app=`/`pid=`/`window_id=` targeting, `max_elements` cap (default 100,
  max 1000) with `total_elements`/`truncated_elements` surfaced.
- `click`, `double_click`, `right_click`, `middle_click` — by `element`
  index (SOM) or `coordinate` [x,y]; `button`, `modifiers` (cmd/shift/
  option/alt/ctrl/fn/win/super/meta).
- `drag` — from_element/to_element or from_coordinate/to_coordinate.
- `scroll` — direction + amount (wheel ticks, default 3).
- `type` — text (respects layout); `key` — combos ('cmd+s', 'ctrl+alt+t',
  'return', 'escape', 'tab').
- `set_value` — select/popup options by display label, slider values.
- `wait` — seconds (max 30).
- `list_apps`, `list_windows`, `focus_app` (with `raise_window` flag).
- `capture_after` — follow-up capture after an action for verification.
- `delivery_mode`: `background` (default, never steals focus — the
  co-work model) / `foreground` (briefly fronts, acts, restores).
  `bring_to_front` separate approval scope.
- **Typed-browser route (`cua_browser_*`) — full**: `cua_browser_state`
  (semantic_v2 / dom_refs_v1 snapshots, `query`, `scope_ref`,
  `continuation`), `cua_browser_prepare` (profile_mode isolated_new /
  isolated_named / existing_profile, `profile_name`, `allow_launch`),
  `cua_browser_navigate`, `cua_browser_click`, `cua_browser_type`
  (insert_text / keystrokes), `cua_browser_pointer` (hover/right_click/
  double_click/scroll/drag with x/y/to_x/to_y/delta_x/delta_y),
  `cua_browser_dialog` (inspect/accept/dismiss), `cua_browser_set_input_files`,
  `cua_browser_download` (destination_root).
- `input_route`: trusted (default) / dom_event (explicit downgrade).
- Permission: `capture` free; input actions ASK (permission modal B.1);
  `foreground` delivery and `bring_to_front` have their own approval
  scope; `cua_browser_existing_profile` follows cua-driver's immutable
  permission mode.

**RED:**
```python
async def test_cua_capture_parses_som(monkeypatch):
    fake = FakeDriver(stdout='{"elements": [{"n": 1, "role": "button"}]}')
    monkeypatch.setattr("eaccode.tools.cua._run_driver", fake.run)
    out = await cua_capture(mode="som", app="Safari")
    assert out["elements"][0]["n"] == 1

async def test_cua_browser_navigate_uses_tab_capability(monkeypatch):
    fake = FakeDriver(stdout='{"ok": true, "url": "https://example.com"}')
    monkeypatch.setattr("eaccode.tools.cua._run_driver", fake.run)
    out = await cua_browser_navigate(url="https://example.com", tab_id="t1")
    assert out["url"] == "https://example.com"

def test_cua_install_windows_autostart_repair(monkeypatch):
    # port of Hermes _repair_cua_driver_autostart_windows
    ...
```

**GREEN:** port client surface from `cua_backend.py`; port installer
from `tools_config.py` (Windows autostart repair included); wire the
tool gated on `computer_use` toolset + driver present.

**Commit:** `feat(tools): computer_use — full cua-driver integration (desktop + typed browser)`.

### 10.5 The remaining full ports

#### Task I.2 — `process` tool (full ProcessRegistry port)

**Files (new):**
- `src/eaccode/tools/process_registry.py` (full port of Hermes
  `process_registry.py`: ProcessSession, ProcessRegistry, spawn_local,
  spawn_via_env, poll, read_log, wait, kill_process, write_stdin,
  submit_stdin, close_stdin, request_close_terminal, list_sessions,
  count_running, has_active_processes, snapshot_running_ids,
  kill_started_since, kill_all, recover_from_checkpoint,
  format_process_notification)
- `src/eaccode/tools/builtin/process.py` (tool wrapper, schema from
  `process_registry.py:2816`)
- `tests/unit/test_process_registry.py`

**Why:** `bash` is fire-and-forget; `process` is the persistent
background session (long builds, dev servers, interactive `eaccode
review` jobs). Full port = checkpoint recovery + notification drain +
stdin interactivity, not just spawn/poll/kill. Uses
`windows_detach_flags` from A.1.

**Commit:** `feat(tools): process — full background session registry (checkpoints, stdin, notifications)`.

#### Task I.3 — `vision_analyze` + `video_analyze` (full aux-model routing)

**Files (new):**
- `src/eaccode/tools/builtin/vision.py` (vision_analyze + video_analyze)
- `src/eaccode/llm/aux_vision.py` (aux vision model client, provider-gated)
- `tests/unit/test_vision_tool.py`

**Why:** Hermes routes vision through an auxiliary model
(`auxiliary_client.py`, 452 KB). eaccode: `vision_model:` key in
providers.yaml; absent → tool returns a clear "no vision model
configured — set providers.yaml vision_model" error and the schema is
withheld. `video_analyze` uses the same path (video-capable model
required, documented in the schema).

**Commit:** `feat(tools): vision_analyze + video_analyze via aux vision model`.

#### Task I.4 — `search_files` tool (rg)

**Files:**
- `src/eaccode/tools/builtin/search_files.py` (rg wrapper; extract
  shared runner from `grep.py`)
- `tests/unit/test_tool_search_files.py`

**Commit:** `feat(tools): search_files (rg-powered)`.

#### Task I.6 — `web_extract` (full readable-page extraction)

**Files:**
- `src/eaccode/tools/builtin/web_extract.py` (fetch + readability via
  `trafilatura` or `readability-lxml`; link extraction; base64-image
  handling like Hermes `convert_base64_images_to_links`)
- `tests/unit/test_tool_web_extract.py`

**Commit:** `feat(tools): web_extract (readable-page extraction + links + images)`.

#### Task I.7 — `browser` toolset (full CDP stack, as Hermes)

**Files (new):**
- `src/eaccode/tools/browser/session.py` (CDP session: connect, navigate,
  snapshot via accessibility tree, click, type, press, scroll, back)
- `src/eaccode/tools/browser/actions.py` (get_images, console, vision,
  dialog handling, download)
- `src/eaccode/tools/builtin/browser.py` (tool wrapper, schema mirrors
  Hermes `browser_tool.py`)
- `tests/unit/test_browser_session.py` (mock CDP)

**Why:** Hermes' `browser_tool.py` is 219 KB (CDP + supervisors +
camofox). Full port means the same tool surface: navigate, snapshot
(accessibility tree), click by ref, type, press, scroll, back,
get_images, console (JS errors), vision (screenshot), dialog,
download. CDP via `pychrome`/websocket-client (add to deps) — not a
Playwright shortcut. Stealth/anti-bot (camofox) is a separate
`browser_camofox` layer — port it too when a user reports bot
detection; the base CDP stack ships complete.

**Commit:** `feat(tools): browser — full CDP stack (navigate/click/type/snapshot/console/vision)`.

#### Task I.8 — `image_gen` (full provider registry)

**Files (new):**
- `src/eaccode/tools/builtin/image_gen.py`
- `src/eaccode/tools/image_gen_registry.py` (provider registry:
  fal/flux, openai-compatible images endpoints)
- `providers.yaml` key `image_model:`
- `tests/unit/test_image_gen.py`

**Hermes reference:** `tools/image_generation_tool.py` (78 KB) +
`agent/image_gen_registry.py`. Full surface: prompt, size, provider
selection, image-source handling (URL/path/data-URL output).

**Commit:** `feat(tools): image_generate — provider registry (fal, openai-compatible)`.

#### Task I.9 — `video_gen` + `bfl_flux3` (full provider registry, opt-in)

**Files (new):**
- `src/eaccode/tools/builtin/video_gen.py`
- `src/eaccode/tools/video_gen_registry.py`
- `src/eaccode/tools/builtin/bfl_flux3.py` (BFL FLUX 3 video)
- `tests/unit/test_video_gen.py`

**Why:** Hermes ships video_gen + bfl as separate toolsets, both OFF by
default (`_DEFAULT_OFF_TOOLSETS`). eaccode ports both fully, default-off,
provider-gated (fal/BFL credentials).

**Commit:** `feat(tools): video_generate + bfl_flux3 (opt-in, provider registry)`.

#### Task I.10 — `tts` (full: streaming + normalizers)

**Files (new):**
- `src/eaccode/tools/builtin/tts.py`
- `src/eaccode/tools/tts_normalize.py` (text normalizer, port of Hermes
  `tts_text_normalize.py`)
- `src/eaccode/tools/tts_streaming.py` (streaming playback)
- `tests/unit/test_tts.py`

**Hermes reference:** `tools/tts_tool.py` (178 KB) — full surface:
voice selection, speed, output path, streaming, text normalization.
Providers: edge-tts default (no key), provider TTS option.

**Commit:** `feat(tools): text_to_speech — full (voices, streaming, normalization)`.

#### Task I.11 — `x_search` (X/Twitter search, opt-in)

**Files (new):**
- `src/eaccode/tools/builtin/x_search.py`
- `providers.yaml` key `xai_api_key:` / OAuth flow (port of Hermes
  `tools/x_search_tool.py` 21 KB)
- `tests/unit/test_x_search.py`

**Why:** needs xAI OAuth or XAI_API_KEY. Auto-enables when the key is
present (Hermes behavior), schema withheld otherwise.

**Commit:** `feat(tools): x_search (opt-in, xAI credentials)`.

#### Task I.12 — `context_engine` (plugin-style runtime tools)

**Files (new):**
- `src/eaccode/context/engine.py` (plugin registry: tools registered at
  runtime by loaded plugins)
- `src/eaccode/context/plugin_api.py` (minimal plugin API: register_tool,
  register_slash_command)
- `tests/unit/test_context_engine.py`

**Why:** Hermes' context_engine ships "runtime tools from the active
context engine". A minimal plugin API (tool + slash-command
registration) gives eaccode the same extension seam without a full
plugin system. Plugins live in `~/.eaccode/plugins/` (a directory
eaccode already owns).

**Commit:** `feat(context): context engine — plugin tool/slash registration`.

#### Task I.13 — `delegate_task` parallel batch (tasks array)

**Files:**
- `src/eaccode/tools/builtin/delegate.py` (add `tasks` array support:
  `[{"goal": ..., "context": ..., "role": ...}]` spawns up to N
  parallel subagents)
- `src/eaccode/agent/factory.py` (subagent builder reuse)
- `tests/unit/test_delegate_batch.py`

**Why:** Hermes' `delegate_tool.py` (192 KB) supports a `tasks` batch
array with per-task context — eaccode's is single-goal only. Parallel
batch is the difference between "review these 6 files" and "review file
by file, sequentially, in one turn". Port the batch semantics; the
per-task results consolidate into one return.

**Commit:** `feat(tools): delegate_task parallel batch (tasks array)`.

#### Task I.14 — `homeassistant` (opt-in)

**Files (new):**
- `src/eaccode/tools/builtin/homeassistant.py` (port of Hermes
  `homeassistant_tool.py` 18 KB: list devices, get state, call service)
- `providers.yaml` key `hass_token:`
- `tests/unit/test_homeassistant.py`

**Commit:** `feat(tools): homeassistant (opt-in, HASS_TOKEN)`.

#### Task I.15 — `spotify` (opt-in)

**Files (new):**
- `src/eaccode/tools/builtin/spotify.py` (port of Hermes: playback,
  search, playlists, library; OAuth flow)
- `tests/unit/test_spotify.py`

**Commit:** `feat(tools): spotify (opt-in, OAuth)`.

### 10.6 Gateway-dependent toolsets (explicitly out of CLI scope)

`stt` (voice transcription), `discord`, `discord_admin`, `yuanbao` —
these tools operate on a *messaging surface* (channels, voice messages,
groups). eaccode is CLI-first by design; there is no channel to read or
post to. They are **not** deferred for polish — they are architecturally
impossible without a gateway. The plan for them is a single line: when
eaccode gains a gateway (a later product decision), port
`tools/discord_tool.py`, `tools/transcription_tools.py`, and
`tools/yuanbao_tools.py` behind the existing `CONFIGURABLE_TOOLSETS`
registry entries — the registry already accepts their keys.

### 10.7 Toolset parity summary

| After Phase I | Count |
|---|---|
| Fully present | 23/27 (11 already + 12 full ports + I.13 batch) |
| Gateway-dependent (explicit) | 4/27 (stt, discord, discord_admin, yuanbao) |
