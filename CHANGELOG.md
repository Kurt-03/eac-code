# Changelog

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
