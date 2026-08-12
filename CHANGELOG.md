# Changelog

## v0.1.0 (2026-08-12) — Hermes / Claude-Code parity in Look & Feel

Builds on v0.0.1 with the fully-realized TUI redesign. The TUI now looks
and behaves like Hermes / Claude Code.

### Streaming
- In-place stream rendering inside the transcript (no separate static widget).
- `StreamingMarkdownRenderer` (new) — incremental, O(1)-per-delta; the
  renderer buffers only the partial markers (`**`, `*`, `` ` ``, ` ``` `)
  until they close, never re-parsing the accumulated text.
- Maximum renderer feed size = delta size (verified: the 50-delta repro
  reports `max feed size: 4`, not 200).
- No duplicate render at turn end (the stream is committed via
  `renderer.finalize()` once, not re-emitted via `log.write`).

### Permission
- Inline prompt in the transcript (no ModalScreen).
- **Color-coded unified diff** — file headers `---/+++` in bold blue,
  hunk markers `@@` in bold cyan, removals in red, additions in green,
  context in dim.
- Tool-specific header subtitle: `bash` → command, `write` → path +
  bytes, `edit` → path + replace hint, `read` → path.
- Quick-Pick legend with all five keys: `y` once · `s` session ·
  `a` always · `n` deny · `p` pause · `Esc` deny.
- **New `PermissionChoice.ALLOW_SESSION`** — session-only remember;
  no `allowlist.json` write. Press `s` to grant + remember-for-session.

### Layout
- Thin rule between transcript and composer (no boxes, no headers).
- Single-column prompt glyph `❯` (was 2 columns).
- Hermes-style status rule: busy indicator · model · git branch ·
  context window · cost · cwd/session.
- Slash-Overlay (filterable, ranked) and Cmd-K palette retained.

### Cleanup
- Removed the legacy `PermissionModal` class (Dead Code since v0.5.0).
- Renamed `permission_diff.py` → `diff_renderer.py` (only the diff
  helpers remain).
- Added a regression test that pins the REPL never pushes a Modal.

### Tests
- `tests/integration/test_stream_50_deltas.py` — 50-delta streaming
  reproducer (no LLM required).
- `tests/integration/test_tui_screenshot.py` — SVG snapshot of three
  scenarios (empty, streaming, permission prompt) under the
  `integration` marker.
- `tools/repro_stream_50_deltas.py` — manual probe.

### Documentation
- `docs/manual-test.md` — guided end-to-end probe (8 sections) to
  verify the Herme parity in look and feel.
- `README.md` rewritten with v0.0.1 → v0.1.0 highlights.

## v0.0.1 (2026-08-12) — Redesign-Start (Hermes/Claude-Code-Parity)

First release of the redesigned TUI. The repository reverts to v0.0.1 as
the canonical start version; the prior v0.5.x source remains in git history
as the foundation this work was built on.

Focus of v0.0.1 → v0.1.0: the TUI must look and behave like Hermes / Claude Code.

- Hermes-style transcript (single RichLog, no separate stream widget)
- Inline permission prompt with a colored unified diff (red `-`, green `+`, cyan `@@`)
- New `ALLOW_SESSION` choice (Quick-Pick `s`) — session-only allowlist
- Quick-Pick legend (`y` once · `s` session · `a` always · `n` deny · `p` pause)
- In-place live streaming (no duplicate render, no full re-parse)
- 1-column prompt glyph + thin rule between transcript and composer
- Status rule with tokens, cost, and current git branch

## v0.3.0 (2026-08-11) — PLAN-4 Masterplan, Phasen A–K

### Phase A — Skill-System
- Frontmatter-Parser (name/description/triggers/platform, robust gegen kaputtes YAML)
- Provenance (bundled/user/pinned) + Usage-Sidecars, Skill-Manager 5+ Actions
- Skill-Linter (12 Regeln), Preprocessing ({{cwd}}, inline-shell), Trigger-Injektion pro Turn
- skills-Config, SOUL.md-Template, Memory-Nudge, Markdown-Memory-Provider
- Lokale Skill-Bundles (`eaccode skills bundle`), 5 Paket-Bundles, `/memory trim`

### Phase B — safeAuto
- Aux-LLM-Classifier (Provider-Flag `classifier`), Key-Pattern-Heuristik, Fail-Open zu ASK
- `/mode safeAuto` (ersetzt `smart`, Migration beim Laden), `/approve` + `/deny` mit Registry
- Rule-Scopes (session/always) + fnmatch-Kategorien

### Phase C — Background-Review + Curator
- Review-Scheduler (settings.review_every_turns), Whitelist-Review-Agent (memory_*/skill_*)
- Proposals als Pending-Approvals (nichts wird automatisch geschrieben)
- Async-Delegation (`delegate_task background=true`), Ergebnis-Collection im Loop
- Curator-Lifecycle (paused/archived/pinned), Backups (zip), Learning-Graph

### Phase D — Sessions
- Two-Stage-Titles (derived < llm < user), Provenance-Persistenz
- REPL-Persistenz: Session-ID + SQLite-Save nach jedem Lauf, `/title`
- Leases (Cross-Prozess-Locks, Stale-Cleanup), Export (md/html), Recap, `--since/--query`-Filter

### Phase E — CLI
- `init/setup/env/version/manifest/recipes/backup/update/deps/dump/hooks/plugins`
- Fallback-Config (kaputte YAML → `.broken` + Defaults), Env-Loader, Migrationen
- Doctor um Deps/Allowlist/Sessions-DB/Keys erweitert, `/status`-Ausbau

### Phase F — Agent-Runtime
- EACCODE_CONFIG_DIR-Profile, Turn-Finalizer, IterationBudget/RetryState, runtime_cwd
- `/compress` mit Token-Feedback, `/context`-Grid, Reasoning-Summary, Context-Guidance
- Tool-Result-Sanitization, Error-Evidenz-Marker, verify_on_stop, Estop (Esc)
- Thread-Silence, Error-Classifier (transient/permanent/needs_input), Timeouts, Budget-Config

### Phase G — Cron/Process/Web
- **web_search neu** (keyless DuckDuckGo-Registry — Tool fehlte vorher komplett)
- POSIX-PTY-Spawn (Windows-Hinweis), Process-Registry + Exit-Kill, Daemon-Pool
- Cron no_agent-Watchdog (Skript direkt, DB-Migration), execute_parallel, Heartbeat

### Phase H — Tools-Detail & Safety
- URL-Guard, Prompt-Injection-Detection, Credential-File-Block, Selbst-Schutz (Paketpfad)
- Redigierte Modal-Argumente, Schema-Sanitizer, tool_search, Result-Spill (>50K)
- V4A-Multi-File-Patch-Parser, markdown_table/sizefmt/timefmt

### Phase J — P1-Rest (ausgewählt)
- `/debug` (Stream-Fence-Stats), `/tips`, `/focus`, `/clear --yes`-Confirm
- Per-Model-Cost (`/cost`), Onboarding-Hints, Input-Sanitize
- ssl_verify-Setting, Recipes-Verzeichnis, Provider-Katalog

### Fixes & Funde
- `test_policy_smart` auf SAFE_AUTO migriert (B.3-Umbenennung)
- web_search-Tool war im Toolset gelistet, existierte aber nicht — gebaut (G.6)
- Turn-Finalizer-Doppelzählung von Usage behoben (F.7)
- Test-Heartbeat auf Windows-Timer-Granularität kalibriert
