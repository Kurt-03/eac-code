# eac-code v0.2.0 — Hermes-Gap-Plan (konsolidiert)

> **Single source of truth.** Alles was in v0.2.0 reinkommt. Operativ + Audit-Referenz + Tech-Entscheidungen in **einem** File.
>
> **Stand:** 2026-08-10 · Hermes v0.20.0 vs. eac-code (50 Commits, 91 Files, ~12k LOC)
>
> **Begleit-Files (Referenz, NICHT-Plan):**
> - `HERMES-FULL-ANALYSIS.md` (60 KB) — 500+ Hermes-Files mit eac-code-Gap-Markierung
> - `HERMES-GAP-ANALYSIS-v2.md` (45 KB) — eac-code-File-by-File-Audit

---

## 0. Executive Summary

| | Hermes | eac-code 0.1.0 | Faktor |
|---|---|---|---|
| Files | 1133 | 91 | **12x** |
| LOC | ~628.000 | ~12.000 | **52x** |

**Ziel v0.2.0:** Auf **Hermes-Pattern-Niveau in den 5 kritischen Selbst-Improvement-Mechaniken** kommen, ohne 1:1-Ports. Konzeptionelle Parität ja, eigene Mechanik wo begründet.

**5 Big-Gaps (P0, alle lokal umsetzbar):**

1. **Background-Review-Fork** — Post-Turn-Daemon-Thread der Memory/Skills selbst verbessert (Hermes: `agent/background_review.py` 1144 LOC, eac-code: 0)
2. **Smart-Compaction** — Soft-Tail-Budget, Ghost-Skill-Defense, Pre-LLM-Feasibility-Skip (Hermes: `context_compressor.py` 7386 LOC, eac-code: 30)
3. **Memory-Rewrite MEMORY.md/USER.md/SOUL.md** — Memory-Tool mit Approve-Gate, Batch-Operations, Char-Budgets (Hermes: `memory_tool.py` 1248 LOC, eac-code: ~30)
4. **Skill-Usage-Telemetrie** — `.usage.json` mit `use_count`/`view_count`/`last_used` für Curator-Signals (Hermes: `skill_usage.py` 1340 LOC, eac-code: 0)
5. **File-State-Coordination** — Per-Path-Locks, Stale-Detection für Subagent-Schreib-Konflikte (Hermes: `file_state.py` 469 LOC, eac-code: 0)

**5 eac-code-stärken (BLEIBEN so, nicht "verbessern"):**

- Permission-Modal mit Edit-Diff (besser als Hermes, die nur Hash-Check haben)
- Context-Engine-Plugin (eac-code hat Hermes-Pattern bereits)
- Worktree-Manager (Hermes hat das nicht)
- `_subprocess_compat.py` (eigener Port, sauberer als Hermes' Original)
- Streaming-Mixin-Split (eac-code ist hier strukturierter)

**Scope-Limits (hart):**

- ❌ Keine Cloud-Features: Browser, Discord, Slack, Telegram, fal, OpenAI-Codex, TTS/STT, Image/Video-Gen, OAuth, daytona, Web-UI
- ❌ Keine neuen Python-Deps (nur stdlib + LiteLLM + Tiktoken + Git + Textual + Rich + Pydantic)
- ❌ Kein 1:1-Code-Port von Hermes (Konzepte ja, Mechanik eigen)
- ❌ Kein Docker/Container-Runtime
- ❌ Keine `tui_gateway/`-Portierung (1-2 Wochen Aufwand, out-of-scope)

---

## 1. Tech-Entscheidungen (verbindlich, vor Sprint 1)

### 1.1 Approval-Mode-Umbenennung (Hermes-konform, aber ehrlich)

| Alt (eac-code 0.1.0) | Neu (v0.2.0) | Was ändert sich |
|---|---|---|
| `interactive` | `manual` | User bestätigt jeden Write-Tool-Call |
| `smart` | `safeAuto` | Auxiliary-LLM klassifiziert Risk; nur safe = bypass |
| `bypassPermissions` | `bypass` | Alle Tools ohne Nachfrage |

**Hermes-Referenz:** `hermes_cli/approval_mode.py:10` `VALID_APPROVAL_MODES = ("manual", "smart", "off")`. eac-code verwendet andere Namen, aber das Konzept ist Hermes-konform. **Wichtig:** eac-code's aktuelle `smart`-Logik lügt — sie behauptet "smart" zu sein, ist aber deterministisch (nur `bash` wird klassifiziert, alle anderen fallen auf `interactive` durch).

**Konsequenz:** `safeAuto` MUSS Auxiliary-LLM nutzen. Wenn keine LLM-Verbindung: Fail-Open zu `manual`, **nicht** silent-bypass.

### 1.2 Approve-Stufen (3, nicht 4 — Hermes-konform)

- `Y` = **Yes** (einmal, diese Aktion)
- `N` = **No** (einmal, ablehnen)
- `A` = **Always** (Session-Scope, gleicher Befehl/Pfad)
- `P` = **Pause** (Session-Pause, kein Tool-Call mehr)

**Hermes-Referenz:** `tools/approval.py:2858-2871` bestätigt `once`/`session`/`always`. eac-code's aktuelle 4. Stufe "Don't ask again this session for this category" wird zu `A` zusammengefasst.

### 1.3 Memory-Layout (3 Files, nicht 1 JSONL)

| File | Scope | Größe | Inhalt |
|---|---|---|---|
| `MEMORY.md` | project | ≤2200 char | Was über das Projekt wichtig ist |
| `USER.md` | user-global | ≤1375 char | Was über den User wichtig ist |
| `SOUL.md` | user-global | ≤800 char | Personality, Tone, Working-Style |

**Hermes-Referenz:** `hermes_cli/memory_setup.py` + `agent/memory_manager.py:1241`. eac-code's aktuelles `memory/store.py` (JSONL) wird ersetzt.

### 1.4 REPL-Style (schlicht, Hermes-Format)

```
> Describe the bug you saw
⎿  read(path="src/auth.py")
  ⎿ 42 lines read
  ⎿ Done · 0.3s

The auth flow on line 15 calls the wrong helper. Should be...
```

**Verbote:**
- ❌ `Panel.fit` Boxes ("you" / "eac-code" Boxes)
- ❌ Cyan-Präfixe wie `[cyan]eaccode[/cyan]`
- ❌ 2-Space-Indent für Tool-Results
- ❌ Stream-Doppel-Render (live + final)

**Pflicht:**
- ✓ User-Input plain, monospace
- ✓ Tool-Calls mit `⎿  tool_name(args)` (call-expression, nicht nur verb)
- ✓ Tool-Results mit `  ⎿ ...`
- ✓ Assistant-Response plain, kein Prefix

### 1.5 Skills-Layout (Hermes-Pattern, ohne Org-Mirror)

```
~/.eaccode/skills/
├── user/                  # User-authored
│   ├── my-skill/
│   │   ├── SKILL.md       # Frontmatter + Body
│   │   └── .usage.json    # use_count, view_count, last_used
├── bundled/               # Mit dem Tool ausgeliefert
│   ├── python-debug/
│   └── git-workflow/
├── pinned/                # Read-only, nicht-editierbar
│   └── safety-checklist/
└── curator/               # Auto-managed durch Background-Review
    └── learned-pattern-1/
```

**Hermes-Referenz:** `tools/skill_provenance.py` (78 LOC). eac-code hat aktuell **0** Skills — das ändert sich in v0.2.0.

### 1.6 Subagent-Interface (eigenes Pattern, Hermes-Spiritus)

```python
# eac-code's delegate tool:
async def delegate(
    agent: str,        # "explore" | "code" | "review" | custom
    prompt: str,       # Aufgabe
    files: list[str],  # Read-only-Whitelist
    worktree: bool,    # Optional: eigener Worktree
    background: bool,  # Optional: async, return task_id
) -> DelegateResult
```

**Hermes:** `tools/delegate_tool.py:4356` LOC. eac-code: 100 LOC. eac-code's Pattern ist **bereits gut** (Lighter-Tool-Concept + Worktree-Support) — bleibt, wird erweitert.

---

## 2. Backlog (Top-50, priorisiert)

### P0 (5 Big-Gaps, ~30-32 Tage, 6-7 Wochen)

#### P0.1 — Background-Review-Fork (4 Tage)
**Hermes-Ref:** `agent/background_review.py` 1144 LOC
**eac-code:** 0

- [ ] `src/eaccode/agent/background_review.py` — Daemon-Thread-Fork
- [ ] `should_review_memory(turn_count, last_review_turn)` + `should_review_skills(...)`
- [ ] `_spawn_background_review(messages_snapshot, review_memory, review_skills)`
- [ ] Neue AIAgent-Instanz mit Tool-Whitelist `["memory", "skills"]`
- [ ] Inheritance: provider/model/api_key/prefix-cache
- [ ] Cancel-pending-Logik bei neuem Turn
- [ ] Result-Stream in nächste User-Message als `Background-Review-Complete` System-Msg

**Eigene Mechanik statt Hermes' 1144 LOC:** eac-code's `agent/loop.py` ist 135 LOC und nutzt schon eine klare Hook-Pattern. Background-Review klinkt sich in `on_turn_end()` ein, kein eigenes AIAgent-Lifecycle nötig. **Geschätzt: 250-300 LOC.**

#### P0.2 — Smart-Compaction (4 Tage)
**Hermes-Ref:** `agent/context_compressor.py` 7386 LOC
**eac-code:** `agent/compaction.py` 30 LOC

- [ ] `compaction.py` erweitern: Soft-Tail-Budget (demote statt drop)
- [ ] Ghost-Skill-Defense: `[SKILL_PRUNED]`-Marker statt echtes Löschen
- [ ] Pre-LLM-Feasibility-Skip: wenn middle < 10% von threshold → kein LLM-Call
- [ ] Small-Context-Window-Floor: <512K-Modelle → 50% Floor
- [ ] Cross-Session-Boundary-Redaction (strict mode, default ON)

**Eigene Mechanik:** Hermes' Compaction ist 7386 LOC weil sie 12+ Provider-spezifische Edge-Cases hat. eac-code's LiteLLM-Layer abstrahiert das weg. **Geschätzt: 400-500 LOC.**

#### P0.3 — Memory-Rewrite MEMORY.md/USER.md/SOUL.md (3 Tage)
**Hermes-Ref:** `tools/memory_tool.py` 1248 LOC, `agent/memory_manager.py` 1241 LOC
**eac-code:** `memory/store.py` ~30 LOC (JSONL, unzureichend)

- [ ] `memory/markdown_store.py` — File-Backend mit 3 Files (MEMORY/USER/SOUL)
- [ ] Char-Budget-Enforcement (2200/1375/800)
- [ ] Atomic-Write (write-temp + rename)
- [ ] Memory-Approval-Gate: alle Writes durch Permission-System
- [ ] Auto-Memory-Nudge: alle N Turns Reminder "consider writing to memory"
- [ ] Memory-Tool: `add` / `replace` / `remove` / `view` Actions
- [ ] First-Run-Setup (`memory_setup.py` analog Hermes)

**Eigene Mechanik:** Hermes' 1248 LOC inkludiert 6+ Memory-Provider (Notion, etc.). eac-code: nur File-Backend. **Geschätzt: 350-400 LOC.**

#### P0.4 — Skill-Usage-Telemetrie (2 Tage)
**Hermes-Ref:** `tools/skill_usage.py` 1340 LOC
**eac-code:** 0

- [ ] `memory/skill_usage.py` — `.usage.json` Reader/Writer
- [ ] Per-Skill: `use_count`, `view_count`, `last_used`, `created_at`
- [ ] Atomic-Write mit File-Lock
- [ ] Track-View: jedes `skill_view`-Tool-Call
- [ ] Track-Use: jedes Skill-Loading vor System-Prompt-Inject
- [ ] Aggregat-Stats: `get_skill_stats(skill_name, since_ts)`

**Eigene Mechanik:** Hermes' 1340 LOC inkludiert DB-Backend, eac-code nutzt JSON-only. **Geschätzt: 150-200 LOC.**

#### P0.5 — File-State-Coordination (2 Tage)
**Hermes-Ref:** `tools/file_state.py` 469 LOC
**eac-code:** 0

- [ ] `tools/file_state.py` — Per-Path-Lock-Registry
- [ ] `lock_path(path)` Context-Manager
- [ ] `check_stale(task_id, path)` vor jedem Write
- [ ] `writes_since(task_id, since_ts, paths)` für Subagent-Konflikterkennung
- [ ] Per-Agent-Read-Stamps (`threading.Lock` pro resolved path)

**Eigene Mechanik:** Hermes' 469 LOC inkludiert Cross-Process-Locks (DBus/Unix-Sockets). eac-code: nur Thread-Scope. **Geschätzt: 200-250 LOC.**

### P0.6 — Bug-Fix Sprint (Audit 17 Findings) (2 Tage)
**Ref:** `HERMES-GAP-ANALYSIS-v2.md` § "Audit Bugs"

- [ ] Bug 1: `stream_fence.py:23-32` — `claim_stream_writer` doesn't store token on owner
- [ ] Bug 2: `permission_modal.py:120-130` — Edit diff args reversed
- [ ] Bug 3: `aux_vision.py:38-44` — Full video in RAM
- [ ] Bug 4: `providers.py:43-46` — Plaintext keys in YAML
- [ ] Bug 5: `llm/client.py:88-90` — API keys via `os.environ.setdefault` (kein Fallback)
- [ ] Bugs 6-17: Subtle Issues in `process.py`, `queue.py`, `edit.py`, `safety.py`, `scanner.py`, `checkpoints.py`, `retry_utils.py`, `result_classification.py`, `delegate.py`, `context/engine.py`, `repl.py`

### P0.7 — Stream-Fence-Fix (0.5 Tage)
**Inkludiert in P0.6 Bug 1** — separat wegen User-Sichtbarkeit

- [ ] `_subprocess_compat.py` Refactor: `stream_owner_token` durchreichen
- [ ] `process.py:claim_stream_writer` akzeptiert token
- [ ] Test: doppelte Stream-Render ausschließen

### P0.8 — 3. Approve-Stufe `P` für Pause (1 Tag)
**Hermes-Ref:** `tools/approval.py:2858-2871`

- [ ] `permissions/policy.py` — `A`/Always-Button von Session-Scope auf Category-Scope
- [ ] Neue Aktion: `P`/Pause → session-paused Flag, alle Tool-Calls werden abgelehnt mit Hint
- [ ] UI: `permission_modal.py` — 4 Buttons statt 3

### P0.9 — Permanent-Command-Allowlist (1 Tag)
**Hermes-Ref:** `hermes_cli/approvals_suggest.py`

- [ ] `permissions/allowlist.py` — `~/.eaccode/allowlist.json` mit command→scope-Map
- [ ] `policy.py` prüft Allowlist VOR Decision
- [ ] Suggest-Mode: nach 3x Approval → "Add to allowlist?" Prompt
- [ ] Scope-Levels: `session` / `always`

### P0.10 — Hooks-System Basis (2 Tage)
**Hermes-Ref:** `agent/shell_hooks.py` 1067 LOC, `tools/hook_output_spill.py`

- [ ] `hooks/registry.py` — Hook-Discovery aus `~/.eaccode/hooks/*.sh`
- [ ] `hooks/runner.py` — Subprocess-Executor mit Timeout
- [ ] Events: `PreToolUse`, `PostToolUse`, `SessionStart`, `SessionEnd`
- [ ] `~/.eaccode/config.yaml` Hook-Config-Block
- [ ] Output-Spill: Hook-Output landet im nächsten User-Message-Stream

**Eigene Mechanik:** Hermes' 1067 LOC inkludiert 12+ Event-Types, Async-Queue, Cross-Process. eac-code-Variante: 5 Events, sync. **Geschätzt: 250-300 LOC.**

### P0.11 — Memory/Skill-Auto-Nudge (1 Tag)
**Hermes-Ref:** `agent/learning_graph.py` 328 LOC

- [ ] `agent/nudge.py` — `should_nudge_memory(turn_count)` / `should_nudge_skills(...)`
- [ ] Nudge-Injection in System-Prompt-Builder
- [ ] Frequency: alle 5 Turns bei low-skill-count

### P0.12 — Skill-Manager-Tool erweitern (2 Tage)
**Hermes-Ref:** `tools/skill_manager_tool.py`

- [ ] `memory/skill_tools.py` — Actions: `create` / `edit` / `patch` / `delete` / `write_file` / `remove_file`
- [ ] `skill_create(name, body, frontmatter)` mit Validation
- [ ] `skill_patch(name, ops)` für id-based edits
- [ ] `skill_delete(name)` mit Soft-Delete (curator/)
- [ ] Tool-Approval-Gate: Skill-Edits brauchen User-Bestätigung

### P0.13 — Skill-Linter (1 Tag)
**Hermes-Ref:** `tools/skill_linter.py` 462 LOC

- [ ] `memory/skill_linter.py` — 8+ Convention-Rules
- [ ] Rules: frontmatter-required, name-format, max-body-length, no-todo-marker, no-credentials, etc.
- [ ] `skill_lint(name)` Returncode 0/1 mit Violations-List
- [ ] Integration in `skill_create` Auto-Lint

### P0.14 — Skill-Provenance + Protected (0.5 Tage)
**Hermes-Ref:** `tools/skill_provenance.py` 78 LOC

- [ ] `memory/skill_provenance.py` — 5 Sources: `bundled` / `user` / `curator` / `pinned` / `hub`
- [ ] `pinned` Skills sind read-only
- [ ] `curator` Skills werden vom Background-Review gemanaged
- [ ] Lint-Warning wenn user `curator/` editiert

### P0.15 — Triggers + Pre-Filter (1 Tag)
**Hermes-Ref:** `agent/skill_preprocessing.py` 144 LOC, `agent/skill_commands.py` 840 LOC

- [ ] `memory/skill_triggers.py` — Frontmatter-Trigger-Parser
- [ ] `prefilter_skills(user_message)` → Top-N relevant Skills
- [ ] Trigger-Match: keywords, file-patterns, command-patterns
- [ ] Integration in System-Prompt-Builder

### P0.16 — skill_view Tool (0.5 Tage)
**Hermes-Ref:** `agent/skill_utils.py` 934 LOC

- [ ] `memory/skill_tools.py:skill_view(name)` — lädt Skill-Body, tracked `view_count`
- [ ] Output-Format: Frontmatter als Tabelle, Body als Markdown
- [ ] Tool-Gate: read-only, no-approval-needed

### P0.17 — Subagent-Steering + Interrupt (2 Tage)
**Hermes-Ref:** `agent/subagent_lifecycle.py` 540 LOC, `tools/async_delegation.py` 1515 LOC

- [ ] `tools/builtin/delegate.py` — `steer(task_id, new_prompt)` für Background-Tasks
- [ ] `interrupt(task_id)` für Cancel
- [ ] Live-Log: `tools/delegation_live_log.py` Hermes-Pattern (424 LOC → eac-code 80 LOC)
- [ ] Subagent-Context-Tracking: `delegated_child_context` flag

### P0.18 — CLI-Output-Konsolidierung (1 Tag)

- [ ] `cli/_output.py` neu (Hermes-Ref: `hermes_cli/cli_output.py` 77 LOC)
- [ ] `print_info`, `print_warn`, `print_error`, `print_table` Helpers
- [ ] Alle `commands_*.py` umstellen

### P0.19 — CLI-Subcommands: backup/hooks/memory/status/verify/dump (2 Tage)
**Hermes-Ref:** `hermes_cli/subcommands/` 46 Files

- [ ] `commands_backup.py` — `~/.eaccode` zip-archive mit Timestamp
- [ ] `commands_hooks.py` — list/install/remove Hooks
- [ ] `commands_memory.py` — view/edit MEMORY.md/USER.md/SOUL.md
- [ ] `commands_status.py` — system-status (model, skills, memory, hooks)
- [ ] `commands_verify.py` — verify-hooks + safety-checks
- [ ] `commands_dump.py` — debug-dump (config, skills, recent-sessions)

### P0.20 — Permanent-Approve-List-Import (0.5 Tage)
**Hermes-Ref:** `hermes_cli/approvals_suggest.py`

- [ ] `permissions/allowlist.py:import_from_history(session_id)` 
- [ ] Suggest: nach 3x Approval eines Patterns → Allowlist-Add

**P0 Total: ~30-32 Tage, 6-7 Wochen**

---

### P1 (Nice-to-Have, lokal-tauglich, ~20-25 Tage)

#### P1.1 — Skill-Hub-Lite (3 Tage)
**Hermes-Ref:** `hermes_cli/skills_hub.py` 4607 LOC
**eac-code:** 0 (lokaler Mini-Hub, kein Cloud-Sync)

- [ ] `memory/skill_hub.py` — lokales Skill-Repo (git-clone in `~/.eaccode/hub/`)
- [ ] `commands_hub.py` — `install <name>`, `update`, `list`
- [ ] Lockfile: `~/.eaccode/hub.lock` mit gepinnten Versionen

#### P1.2 — Fuzzy-Match für Skill-Trigger (1 Tag)
**Hermes-Ref:** `tools/fuzzy_match.py` 1108 LOC

- [ ] `memory/fuzzy_match.py` — minimaler Subsequence-Matcher
- [ ] Score-Function: ordered + weighted
- [ ] Use: Skill-Trigger-Matching bei Tippfehlern

#### P1.3 — Checkpoint-Manager-Erweiterung (2 Tage)
**Hermes-Ref:** `tools/checkpoint_manager.py` 1953 LOC
**eac-code:** `tools/builtin/checkpoints.py` (Basic)

- [ ] Tree-Checkpoints (statt nur lineare)
- [ ] Auto-Checkpoint vor `safeAuto`-Approved-Write
- [ ] Diff-Viewer für Checkpoints
- [ ] `commands_undo.py` Integration

#### P1.4 — Session-Export HTML/MD (2 Tage)
**Hermes-Ref:** `hermes_cli/session_export*.py` 3 Files

- [ ] `sessions/export_html.py` — Syntax-highlighted HTML mit Tool-Call-Blocks
- [ ] `sessions/export_md.py` — Markdown mit collapsible Tool-Calls
- [ ] `commands_sessions.py:export --format html|md`

#### P1.5 — Session-Recap (1 Tag)
**Hermes-Ref:** `hermes_cli/session_recap.py`

- [ ] `sessions/recap.py` — "Was haben wir gemacht?" Summary
- [ ] Token-Stats, Tool-Usage, Errors
- [ ] `commands_sessions.py:recap [session_id]`

#### P1.6 — Title-Generator (1 Tag)
**Hermes-Ref:** `agent/title_generator.py` 739 LOC
**eac-code:** 20 LOC

- [ ] `agent/title_generator.py` erweitern: Strip-Control-Wrappers, Titleable-Message-Detection
- [ ] Heuristic: erste 60 Zeichen oder LLM-Summary
- [ ] Async-Title-Generation (non-blocking)

#### P1.7 — Profile-System (2 Tage)
**Hermes-Ref:** `hermes_cli/profiles.py`

- [ ] `config/profiles.py` — Multi-Profile-Support
- [ ] `~/.eaccode/profiles/<name>/` — eigene Settings/Allowlist/Memory
- [ ] `--profile <name>` CLI-Flag
- [ ] Profile-Switch ohne Restart

#### P1.8 — Redact-Engine (2 Tage)
**Hermes-Ref:** `agent/redact.py` 1197 LOC
**eac-code:** `security/redact.py` 24 LOC

- [ ] Pattern-Library: API-Keys, JWTs, AWS-Keys, Private-Keys, IP-Adressen
- [ ] Tool-Output-Scrubbing (post-tool, pre-context)
- [ ] `security/redact.py:scrub_tool_output(tool, content)`

#### P1.9 — Error-Classifier (1 Tag)
**Hermes-Ref:** `agent/error_classifier.py` 1842 LOC
**eac-code:** `llm/errors.py` 84 LOC

- [ ] LiteLLM-Error-Code-Mapping: Rate-Limit / Auth / Context-Overflow / Network
- [ ] User-Friendly-Messages
- [ ] Retry-Strategie pro Class

#### P1.10 — Context-Breakdown-UI (1 Tag)
**Hermes-Ref:** `agent/context_breakdown.py` 360 LOC

- [ ] `ui/context_breakdown.py` — Visualisierung: System/Memory/Skills/Tools/History
- [ ] `/context` Command: zeigt Breakdown
- [ ] Warn bei >80% von Model-Context

#### P1.11 — Markdown-Tables-Parser (0.5 Tage)
**Hermes-Ref:** `agent/markdown_tables.py` 309 LOC

- [ ] `llm/markdown_tables.py` — Tabellen-Parser für Tool-Output
- [ ] Round-Trip: Markdown → DataFrame → Markdown

#### P1.12 — Message-Sanitization (1 Tag)
**Hermes-Ref:** `agent/message_sanitization.py` 865 LOC

- [ ] `llm/message_sanitize.py` — close_interrupted_tool_sequence, coalesce_tool_call_id
- [ ] Replay-Protection: Strip dangling tool_call_tail
- [ ] Deterministic-Call-IDs

#### P1.13 — i18n-Skelett (1 Tag, optional)
**Hermes-Ref:** `agent/i18n.py` 282 LOC

- [ ] `i18n/__init__.py` — `t(key, lang)` mit Fallback en
- [ ] `locales/en.json`, `locales/de.json`
- [ ] **Default: en-only**, de optional

#### P1.14 — Doctor-Live (1 Tag)
**Hermes-Ref:** `hermes_cli/doctor_live.py`

- [ ] `commands_utility.py:doctor_live` — Interactive-Checks
- [ ] "Press Enter to run: [test-llm-connection]"
- [ ] Auto-Fix-Optionen für simple Issues

#### P1.15 — Learning-Graph-View (2 Tage)
**Hermes-Ref:** `agent/learning_graph*.py` 986 LOC

- [ ] `memory/learning_graph.py` — Skills + Memory als Graph
- [ ] `commands_journey.py` — Visualisierung im Terminal
- [ ] Recency-basiertes Coloring

**P1 Total: ~20-25 Tage, 4-5 Wochen**

---

### P2 (Optional, später, ~30-40 Tage)

Diese sind **nice-to-have**, kein Hermes-P0-Pattern. Kann später kommen wenn P0+P1 durch sind:

- `commands_insights.py` (Usage-Stats, 2 Tage)
- `commands_logs.py` (Session-Logs-Viewer, 1 Tag)
- `commands_debug.py` (Debug-CLI, 1 Tag)
- `commands_dump.py` (Config-Dump, 0.5 Tage)
- `kanban.py` (Kanban-System, 1-2 Wochen) — Hermes hat 11320 LOC Kanban-DB, das ist **eigenes Feature, nicht Hermes-P0**
- `pty_session.py` (echte PTY-Unterstützung, 1-2 Tage)
- `outbound_webhooks.py` (lokale HTTP-Hooks, 1-2 Tage)
- `verification_evidence.py` (Verify-Nudges, 1-2 Tage)
- `cost_tracking.py` (Per-Session-Cost-Anzeige, 1 Tag)
- `turn_summary.py` (Token-Flow-Stats, 1 Tag)
- `security_audit.py` (Security-Audit-CLI, 1-2 Tage)
- `model_search.py` (Provider-Suche, 1 Tag)
- `image_source.py` (Local-Image-Source, 0.5 Tag)
- `feishu_*`, `telegram_*`, `discord_*`, `slack_*` — **ALLE OUT OF SCOPE (Cloud)**
- `tui_gateway/` Port — **OUT OF SCOPE (Aufwand zu hoch, 1-2 Wochen)**
- `auth.py` OAuth-Teile — **OUT OF SCOPE (lokal nur)**

**P2 Total: ~30-40 Tage, 6-8 Wochen (nur wenn wirklich gewünscht)**

---

## 3. Sprint-Plan (P0 in 6-7 Wochen)

### Sprint 1: Stabilisierung (5 Tage)
- P0.6 Bug-Fix Sprint Audit 17
- P0.7 Stream-Fence-Fix
- P0.8 3. Approve-Stufe `P`
- P0.9 Permanent-Command-Allowlist
- P0.18 CLI-Output-Konsolidierung

**Deliverable:** eac-code 0.1.1 mit allen 17 Audit-Bugs gefixt + 3 Approve-Stufen + Allowlist.

### Sprint 2: Smart-Compaction + Memory (5 Tage)
- P0.2 Smart-Compaction (Soft-Tail-Budget, Ghost-Skill-Defense, Pre-LLM-Feasibility-Skip)
- P0.3 Memory-Rewrite MEMORY.md/USER.md/SOUL.md (Basis)
- P0.11 Memory/Skill-Auto-Nudge

**Deliverable:** Compaction, die Skills nicht löscht; Memory-Layer mit Approve-Gate.

### Sprint 3: Skill-System (5 Tage)
- P0.4 Skill-Usage-Telemetrie
- P0.12 Skill-Manager-Tool erweitern
- P0.13 Skill-Linter
- P0.14 Skill-Provenance + Protected
- P0.15 Triggers + Pre-Filter
- P0.16 skill_view Tool

**Deliverable:** Vollständiges Skill-System mit Telemetrie, Linter, Provenance.

### Sprint 4: Self-Improvement-Loop (5 Tage)
- P0.1 Background-Review-Fork
- P0.5 File-State-Coordination
- P0.17 Subagent-Steering + Interrupt

**Deliverable:** Background-Review-Daemon, der nach jedem Turn Skills/Memory verbessert; Subagent-Lifecycle vollständig.

### Sprint 5: Hooks + CLI-Parität (5 Tage)
- P0.10 Hooks-System Basis
- P0.19 CLI-Subcommands: backup/hooks/memory/status/verify/dump
- P0.20 Permanent-Approve-List-Import

**Deliverable:** Hooks funktionieren; 6 neue CLI-Subcommands; Allowlist mit History-Import.

### Sprint 6: Polish + eac-code-Spezifisch (5 Tage)
- Title-Generator-Verbesserung
- Redact-Engine
- Error-Classifier
- Context-Breakdown-UI
- Session-Export HTML/MD (P1.4)
- Session-Recap (P1.5)

**Deliverable:** eac-code 0.2.0-RC mit allen P0 + ersten P1-Features.

### Sprint 7 (Optional, 3-5 Tage): P1-Items
- Profile-System (P1.7)
- Fuzzy-Match (P1.2)
- Doctor-Live (P1.14)
- i18n-Skelett (P1.13)

**Deliverable:** eac-code 0.2.0 stabil.

---

## 4. Was eac-code BEHÄLT (nicht "verbessern")

Diese eac-code-Mechaniken sind **besser oder gleichwertig** zu Hermes — kein Refactor:

1. **Permission-Modal mit Edit-Diff** — Hermes zeigt nur Hash-Check bei Edits, eac-code zeigt unified-diff. **Bleibt.**
2. **Context-Engine-Plugin-Pattern** — eac-code's `context/engine.py` macht was Hermes' 200 Plugin-Files macht, nur mit klarer Plugin-API. **Bleibt.**
3. **Worktree-Manager** — Hermes hat keinen Worktree-Support. eac-code's `tools/builtin/worktree.py` ist unique feature. **Bleibt.**
4. **`_subprocess_compat.py`** — eac-code's Port ist sauberer als Hermes' Original (`subprocess_compat.py` über 200 LOC verstreut). **Bleibt, nur Stream-Fence-Fix (P0.7).**
5. **Streaming-Mixin-Split** — eac-code's `ui/streaming.py` + `ui/stream_box.py` Split ist sauberer als Hermes' monolithisches `display.py`. **Bleibt.**
6. **LiteLLM-Only** — Hermes hat 7 Provider-Adapter (Anthropic-native, Bedrock, Vertex, Gemini-Native, OpenAI-Native, etc.). eac-code's LiteLLM ist **bewusste Vereinfachung**. **Bleibt.**
7. **`safeAuto` statt `smart`** — Hermes nennt es `smart`, aber das ist **misnomer** (deterministisch, nicht LLM-driven). eac-code's neue Benennung `safeAuto` ist ehrlich. **Neu (war ja die Entscheidung in 1.1).**

---

## 5. Was OUT OF SCOPE ist (klar, nicht in v0.2.0)

**Cloud (alle RAUS):**
- ❌ Browser-Provider / -Tools
- ❌ Discord / Slack / Telegram / WhatsApp / Feishu
- ❌ OpenAI-Codex-Runtime
- ❌ Anthropic-Copilot / GitHub-Copilot
- ❌ fal / OpenAI-Image / OpenAI-Video
- ❌ TTS (Neutts, OpenAI-TTS, ElevenLabs)
- ❌ STT (Whisper, etc.)
- ❌ Daytone-Container
- ❌ OAuth-Flows (alle: Nous, GitHub, Google, Microsoft, etc.)
- ❌ Vercel-Auth, DingTalk-Auth
- ❌ Web-UI (`web_server.py` 17951 LOC)
- ❌ Dashboard (TUI-Web-Frontend)
- ❌ ACP-Adapter (`acp_adapter/` 11 Files, proprietär)
- ❌ Cross-Platform-Gateway (`gateway/` 88 Files, 70% Cloud)

**OS-Bound (RAUS):**
- ❌ Computer-Use (OS-Automation)
- ❌ Electron-Desktop-UI
- ❌ Windows-PTY-Bridge (eac-code ist Linux-only)
- ❌ Container-Runtime (Docker)

**Aufwand-zu-hoch (RAUS für 0.2.0, P3+):**
- ❌ TUI-Gateway (`tui_gateway/` 26422 LOC, 1-2 Wochen Port-Aufwand)
- ❌ MoA-Loop (`agent/moa_loop.py` 2384 LOC, 1 Woche)
- ❌ Kanban (`kanban_db.py` 11320 LOC, 1-2 Wochen)
- ❌ Learning-Graph-Full (`learning_graph*.py` 986 LOC, 1 Woche)
- ❌ Auth-Monster (`auth.py` 9274 LOC, 1-2 Wochen auch nur lokal)
- ❌ Web-Server (`web_server.py` 17951 LOC, 2-3 Wochen)

**Eigene Hermes-Interna (RAUS):**
- ❌ Relay-LLM / Relay-Runtime (Hermes-Internal, nicht User-Facing)
- ❌ Models-Dev-Sync (`models_dev.py` 903 LOC, OpenRouter-spezifisch)
- ❌ Nous-Account / Subscription / Billing (Nous-spezifisch)

---

## 6. Open Questions (vor Sprint 1 klären)

1. **Skill-Hub:** Eigenes Git-Repo lokal, oder weglassen? Hermes' Hub ist 4607 LOC, Mini-Lite wäre 1-2 Tage. **Entscheidung: P1, kann warten.**
2. **`safeAuto` Fail-Behavior:** Wenn keine LLM-Verbindung → `manual` (sicher) oder `bypass` (nützlich)? **Entscheidung: `manual` (sicher, in 1.1 so festgelegt).**
3. **Memory-File-Format:** Plain-Markdown oder Markdown + Frontmatter? **Hermes: Plain-MD, eac-code: gleiche Entscheidung.**
4. **`A` (Always) Scope:** Category-Scope (Hermes) oder Path-Scope? **Hermes: category. eac-code: gleiche Entscheidung.**
5. **Background-Review-Frequency:** Jeder Turn, oder alle 5 Turns? **Hermes: alle 5. eac-code: gleiche Entscheidung (P0.11 Nudge-Frequency).**
6. **PTY-Support:** Echte PTY oder Subprocess-Pseudo-Terminal? **Subprocess für v0.2.0, PTY später.**
7. **P1-Selection:** Welche P1-Items willst du in v0.2.0? (Default: P1.4 + P1.5 + P1.7 + P1.14)
8. **Woche 7:** Sprint 7 weglassen oder rein?

---

## 7. Aufwands-Statistik

| Stufe | Items | Tage | Wochen |
|---|---|---|---|
| P0 (20 Items) | 20 | ~30-32 | 6-7 |
| P1 (15 Items) | 15 | ~20-25 | 4-5 |
| P2 (optional) | ~20 | ~30-40 | 6-8 |
| **P0+P1 (Realistisch)** | **35** | **~50-57** | **10-12** |
| **P0+P1+P2 (Full-Parity)** | **~55** | **~80-97** | **16-20** |

**Für 0.2.0 empfohlen:** P0 komplett + ausgewählte P1-Items. **~35-45 Tage, 7-9 Wochen.**

---

## 8. Referenz-Map (zu Begleit-Files)

| Frage | Datei | Sektion |
|---|---|---|
| Was fehlt konkret pro Hermes-File? | `HERMES-FULL-ANALYSIS.md` | 500+ Einträge |
| Was ist pro eac-code-File kaputt? | `HERMES-GAP-ANALYSIS-v2.md` | Audit-Bugs § |
| Welche Hermes-Mechanik ist warum P0? | `HERMES-GAP-ANALYSIS-v2.md` | 5 Big-Gaps § |
| Was macht Hermes-Konzept X? | `HERMES-FULL-ANALYSIS.md` | entsprechende Hermes-File-Sektion |
| Welche Hermes-Features sind out-of-scope? | `HERMES-FULL-ANALYSIS.md` | "Was NICHT in dieser Analyse steht" § |

---

**Letzte Entscheidung steht aus:** Sprint 7 rein/raus, P1-Selection, und: fängst du mit Sprint 1 an oder erst Memory-Layout-Refactor vorziehen?
