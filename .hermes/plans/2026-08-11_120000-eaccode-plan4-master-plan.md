# eac-code PLAN-4 Master-Abarbeitungsplan (v0.3.0)

> **Zweck:** Vollständiger Abarbeitungsplan für ALLE 418 katalogisierten Features aus
> `PLAN-4.md` (Hermes v0.20.0 vs. eac-code, Stand 2026-08-11).
> **Repo-Stand bei Erstellung:** Commit `aa6f2b8` (main, alles gepusht).
> **Methodik:** TDD (RED→GREEN→REFACTOR), ein Commit pro Task, keine Cloud-Dienste,
> keine neuen Python-Deps außer `trafilatura` (optional, für web_extract).
> **Sprache:** Code/Kommentare/CLI englisch; dieser Plan deutsch (Arbeitsdokument).
> **Status-Legende (identisch zu PLAN-4):** ✅ voll · 🟡 reduziert · ❌ fehlt · ☁️ Cloud-raus ·
> 🚫 out-of-scope · 🖥️ OS-bound · 🔁 = seit PLAN-4 erledigt (Commit-Nachweis)

---

## 0. Zusammenfassung

| Metrik | PLAN-4-Stand (11.08.) | Jetzt (aa6f2b8) | Delta |
|---|---|---|---|
| ✅ voll umgesetzt | 42 | 42 + 9 🔁 = **51** | +9 |
| 🟡 reduziert | 99 | 99 − 9 🔁 = **90** | −9 |
| ❌ fehlt komplett | 141 | 141 − 1 🔁 (Delegate-Batch) = **140** | −1 |
| ☁️ / 🚫 / 🖥️ (raus) | 60 | 60 | 0 |
| Submodule/noch zu katalogisieren | 76 | 76 | 0 |
| **Lokal umsetzbar (❌ + 🟡-Lücken)** | **141 + ~35** | **140 + ~26** | |

**Seit PLAN-4 erledigt (alle gepusht):**
| Feature | PLAN-4-# | Commit |
|---|---|---|
| Smart-Compaction (alle 5 Features) | 14 | `8998dcb` |
| Memory-Rewrite MEMORY.md/USER.md/SOUL.md + Memory-Tools | 28/33/365 | `5cb05d7` |
| File-State-Coordination (Locks, Stale, Subagent-Attribution) | 296 | `09a74b0` |
| Hooks-System (pre/post tool, session start/end, Spill) | 58/59/242/323 | `fc5a11b` |
| P-Stufe (Pause) + /pause /resume | (P0.8) | `1587ebf` |
| Allowlist + /allow /disallow + 3×-Suggest (P0.9/P0.20) | 239 | `1587ebf` |
| CLI-Output-Helper (P0.18) | 259 | `1587ebf` |
| Delegate-Task Parallel-Batch (tasks-Array) | 367 | `dce96c3` |
| Search-Files (rg-powered) | (I.4) | `dce96c3` |
| Vision + Video-Analyze + aux_client | 353 | I.3-Commit |
| Browser-CDP (navigate/click/type/…) | 343-346 | Browser-Commit |
| Computer-Use (cua-driver) | 350/351 | computer_use-Commit |
| Context-Engine (Plugins) + register_command | 219/221 | `e5699ae` |
| Skill-Usage-Telemetrie (Sidecars) | 355 | P0.4-Commit |
| Approval-Suggest (voll, in allowlist.py) | 239 | ✅ (schon in PLAN-4) |

**Verbleibend:** ~140 ❌ + ~26 🟡-Lücken lokal umsetzbar → 11 Phasen (A–K), **~90 Tasks, ~35–45 Tage** (Einzelschätzung je Task unten).

---

## 1. Verifikations-Setup (bei JEDEM Task)

```bash
cd "/c/Projekte/EACcode V3"
export PYTHONPATH=
# gezielt:
.venv/Scripts/python.exe -m pytest tests/unit/<testfile> -q -p no:cacheprovider
# Gesamt (am Phasenende):
.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider 2>&1 | tail -2
.venv/Scripts/python.exe -m ruff check src/ tests/ 2>&1 | tail -1
# Commit-Regel: NUR bei grünen Tests + sauberem Ruff; kein `cmd | tail` ohne pipefail.
```

**Konventionen:** neue Dateien 200–400 LoC (Hard Cap 600); wachsende Dateien sofort
aufteilen; Tests pro Feature in `tests/unit/test_<modul>.py`; Commits pro Task mit
`feat|fix|refactor|chore(<bereich>): <beschreibung>`.

---

## 2. Master-Tabelle — alle 418 Features mit Ziel-Zuordnung

### 2.1 `agent/` (171 Features)

| # | Feature | Status jetzt | Ziel |
|---|---|---|---|
| 1 | conversation_loop (Main-Loop) | 🟡 | behalten; F.7 (Turn-Finalizer) |
| 2 | agent_init (Init-Orchestrierung) | 🟡 | F.1 (Init-Reihenfolge + Profile-Slot) |
| 3 | agent_runtime_helpers (41 Utils) | ❌ | F.8 (nur benötigte: cwd, env, fmt) |
| 4 | turn_context (compose/substitute user content) | ❌ | F.9 |
| 5 | turn_finalizer (cleanup, cost-agg) | ❌ | **F.7** |
| 6 | turn_retry_state | ❌ | F.10 (mit /retry vereinen) |
| 7 | turn_summary (format_elapsed/token_flow) | ❌ | F.11 (in /status + /cost) |
| 8 | iteration_budget | 🟡 | F.12 (per-Turn-Budget im Loop) |
| 9 | session_activity (bound_activity) | ❌ | D.6 (Session-Metadaten) |
| 10 | runtime_cwd (resolve_agent_cwd) | ❌ | F.13 (chdir-festes CWD) |
| 11 | delegation_context | ❌ | C.4 (Subagent-Kontext im Loop) |
| 12 | subagent_lifecycle (parent-bind) | ❌ | C.4 |
| 13 | async_utils (safe_schedule_threadsafe) | ❌ | F.14 |
| 14 | context_compressor | ✅ 🔁 | — (P0.2, `8998dcb`) |
| 15 | conversation_compression (Engine) | ❌ | F.15 (reduziert: Timeout-Resolve + komprimierte History) |
| 16 | manual_compression_feedback | ❌ | F.16 (Meldung bei /compress) |
| 17 | context_engine (Trigger) | 🟡 | behalten (eigene Plugin-API) |
| 18 | context_references (@file/@folder/@git/@url) | 🟡 | F.17 (@folder + @git erweitern) |
| 19 | context_breakdown (Render-Grid) | 🟡 | F.18 (/context Grid statt single %) |
| 20 | background_review (Daemon-Fork) | ❌ | **C.1–C.3** |
| 21 | curator (lifecycle active/stale/archived/pinned) | 🟡 | **C.5** |
| 22 | curator_backup | ❌ | **C.6** |
| 23 | learning_graph (nodes/edges/density) | ❌ | **C.7** |
| 24 | learning_graph_render (recency-ink) | ❌ | **C.7** |
| 25 | learning_mutations (delete_node …) | ❌ | **C.7** |
| 26 | insights (30-Tage-Stats, Charts) | ❌ | **J.1** |
| 27 | manual_compression_feedback | ❌ | F.16 (mit 16) |
| 28 | memory_manager (3-File-Layout) | 🟡 🔁 | — (P0.3, `5cb05d7`) |
| 29 | memory_provider (Base) | ❌ | A.10 (Abstraktion über markdown_store) |
| 30 | message_sanitization (close_interrupted_tool_sequence …) | ❌ | **F.19** |
| 31 | streaming context scrubber | ❌ | F.19 |
| 32 | Memory-Auto-Nudge | ❌ | **A.9** |
| 33 | MEMORY/USER/SOUL-Layout | ✅ 🔁 | — (P0.3) |
| 34 | skill_utils (Frontmatter, platform-matches) | 🟡 | **A.1** (erweitern) |
| 35 | skill_commands (append/extract instruction) | 🟡 | **A.2** |
| 36 | skill_preprocessing (template vars, inline shell) | ❌ | **A.5** |
| 37 | skill_bundles (scan/resolve) | ❌ | A.11 (reduziert: lokale Bundles) |
| 38 | skill_triggers (Frontmatter-Match) | ❌ | **A.6** |
| 39 | think_scrubber | ✅ | — |
| 40 | reasoning_summaries (separate_glued_blocks) | ❌ | F.20 |
| 41 | reasoning_timeouts (MiniMax 600s) | ✅ | — |
| 42 | thinking_timeout_guidance | ❌ | F.21 (Fehlermeldung bei Timeout) |
| 43 | lmstudio_reasoning | ❌ | F.22 (effort-mapping) |
| 44 | display (tool_preview/label/redact) | 🟡 | H.1 (redact_tool_args_for_display) |
| 45 | stream_single_writer | ✅ | — (P0.7) |
| 46 | stream_diag | ❌ | J.2 (debug-only, /debug) |
| 47 | reactions (emoji-detect) | ❌ | J.3 |
| 48 | onboarding (hints) | ❌ | J.4 (Start-Hints) |
| 49 | tool_executor (concurrent dispatch) | 🟡 | **G.8** (Parallel-Dispatch + batch-timeout) |
| 50 | tool_guardrails | ✅ | — |
| 51 | tool_result_classification | ✅ | — |
| 52 | tool_dispatch_helpers (canonicalization) | 🟡 | H.2 (Argument-Canonicalizer) |
| 53 | ToolClass enum | 🟡 | H.3 (prüfen: idempotent/mutating/runaway überall) |
| 54 | verification_evidence | ❌ | **F.23** |
| 55 | verification_stop (verify_on_stop) | ❌ | **F.24** |
| 56 | verify_hooks (max_verify_nudges) | ❌ | F.24 |
| 57 | kanban_stop | 🚫 | — |
| 58 | shell_hooks | ✅ 🔁 | — (P0.10, `fc5a11b`) |
| 59 | hook_output_spill | ✅ 🔁 | — (P0.10) |
| 60 | plugin_llm | ❌ | J.5 (optional, Plugin-LLM) |
| 61 | auxiliary_client (safeAuto) | ❌ | **B.1–B.2** |
| 62 | aux_accounting (ContextVar) | ❌ | B.2 |
| 63 | scope Tool-Whitelist (memory/skills) | ❌ | C.3 (Background-Review braucht sie) |
| 64–73 | Provider-Adapter (anthropic/bedrock/…/codex) | 🟡/☁️ | LiteLLM reicht; keine Ports |
| 74 | title_generator (two-stage) | ❌ | **D.1** |
| 75 | usage_pricing (billing routes) | ❌ | J.6 (reduziert: Cost pro Modell) |
| 76 | credential_pool (Multi-Key-Rotation) | 🟡 | J.7 (optional: 2. Key je Provider) |
| 77–81 | credential_sources / persistence / secret_scope / secret_sources | ❌ | 🚫 (BYOK bleibt) |
| 82 | coding_context (workspace block) | ✅ | — |
| 83 | oneshot | 🟡 | E.9 (eaccode run bleibt) |
| 84 | learn_prompt | ❌ | C.8 (in Background-Review) |
| 85 | redact (mask_secret, 23 funcs) | 🟡 | **F.25** |
| 86 | file_safety (classified denials) | 🟡 | H.4 (write_denied + Klassen) |
| 87 | replay_cleanup (strip_interrupted_tool_tails) | ❌ | **F.26** |
| 88 | estop (sentinel_path) | ❌ | F.27 (nice-to-have) |
| 89 | range_shift | ❌ | J.8 (optional) |
| 90 | ssl_guard / 91 ssl_verify | ❌ | J.9 (verify_ca_bundle) |
| 92 | markdown_tables (Parser) | ❌ | **H.5** |
| 93 | image_routing (decide_image_input_mode) | 🟡 | H.6 (auto: Daten-URL vs. Pfad) |
| 94 | message_content (flatten_message_text) | ❌ | H.7 (in compaction nutzen) |
| 95 | interrupt_compat | ❌ | F.28 |
| 96 | portal_tags (conversation context) | ❌ | J.10 |
| 97 | thread_scoped_output (thread_scoped_silence) | ❌ | F.29 |
| 98 | process_bootstrap (keepalive client) | ❌ | G.7 (Cron-Daemon nutzt es) |
| 99 | prompt_builder (AGENTS.md Parent-Chain + .cursorrules) | 🟡 | **F.30** |
| 100 | prompt_caching (cache_control) | 🟡 | F.31 (cache_control für MiniMax) |
| 101 | prompt_cache_boundary (stable prefix) | ❌ | F.31 |
| 102 | i18n | ❌ | J.11 (Skelett, en-default) |
| 103 | battery | 🖥️ | — |
| 104 | jiter_preload | ❌ | J.12 (perf, optional) |
| 105 | retry_utils | ✅ | — |
| 106 | rate_limit_tracker | ✅ | — |
| 107 | error_classifier (15 funcs) | 🟡 | **F.32** |
| 108 | bounded_response (read_streaming_error_body) | ❌ | F.33 |
| 109 | native_compaction (OpenAI) | ❌ | F.34 (optional) |
| 110–115 | nous_rate_guard / credits / billing (Nous) | 🚫 | — |
| 116–123 | image/video/tts/stt Provider+Registry | ☁️ | — |
| 124 | web_search_provider | ✅ | — |
| 125 | web_search_registry | 🟡 | **G.6** |
| 126 | browser_provider | ✅ | — |
| 127 | browser_registry | ✅ | — |
| 128–129 | moa_loop / moa_trace | 🚫 | — |
| 130 | trajectory (scratchpad→think) | ❌ | J.13 |
| 131–132 | curator_health / cron_health | ❌ | **G.5** |
| 133–134 | eventlog / events | ❌ | **J.14** (Events-Definitionen + Emitter) |
| 135 | recipes | ❌ | J.15 (lokale Rezept-Dateien) |
| 136 | install/ | ❌ | E.10 (reduziert) |
| 137 | monitoring/ | ❌ | J.16 (optional) |
| 138 | lsp/ | ❌ | 🚫 (YAGNI, wie PLAN-4) |
| 139–140 | store/manager Abstract | ❌ | J.17 (optional) |
| 141 | pet/ | 🚫 | — |
| 142 | manifest | ❌ | J.18 |
| 143 | types | ✅ | — |
| 144–152 | base/constants/runner/render/reporter/orchestrate/command/cli/client | ❌ | 🚫 (eigene Architektur vorhanden) |
| 153 | emitter | ❌ | **J.14** |
| 154 | environment | ❌ | E.11 (env-Setup-Checks) |
| 155–157 | policy/prompts/registry | ✅ | — |
| 158 | state | ❌ | J.19 |
| 159–161 | atlas/bitwarden/onepassword | ❌ | 🚫 (Secret-Sources raus) |
| 162 | protocol | ❌ | J.20 |
| 163 | range_shift (dup) | ❌ | J.8 |
| 164 | servers | ❌ | J.21 |
| 165 | workspace | ✅ | — |
| 166 | manager (dup) | ❌ | J.17 |
| 167–168 | iron_proxy / proxy_sources | ❌ | 🚫 |
| 169 | trigger pre-filter | ❌ | **A.6** (mit 38) |
| 170 | _cache | ❌ | F.35 (Cache-Verzeichnis) |
| 171 | hermes_tools_mcp_server | ❌ | G.9 (MCP-Server für eigene Tools, optional) |

### 2.2 `hermes_cli/` (116 Features)

| # | Feature | Status jetzt | Ziel |
|---|---|---|---|
| 172 | main (CLI-Entry) | 🟡 | behalten (Sub-Command-Struktur) |
| 173 | commands (Registry) | 🟡 | E.1 (fehlende Commands ergänzen) |
| 174 | setup (First-Run) | 🟡 | **E.2** (Provider + Memory + Hooks in einem Flow) |
| 175–176 | auth / auth_commands | 🚫 | — |
| 177–184 | web_server / gateway / dashboard / gui | 🚫/🖥️ | — |
| 185 | config | 🟡 | E.3 (Settings-Sektionen: hooks, skills, memory) |
| 186 | config_defaults | 🟡 | E.3 |
| 187 | config_migrations | ❌ | **E.4** (Version + Migration in Settings.load) |
| 188 | fallback_config | ❌ | E.5 |
| 189 | mcp_config | 🟡 | G.4 (mcp.yaml-Features: env, args) |
| 190 | moa_config | 🚫 | — |
| 191 | skills_config | ❌ | **A.7** |
| 192 | tools_config (TOOLSETS-Äquivalent) | ✅ | — (tools/factory.py) |
| 193 | runtime_provider | ❌ | J.22 |
| 194 | providers (Loader) | 🟡 | behalten |
| 195 | env_loader | ❌ | E.6 (env-Datei laden) |
| 196–201 | fallback_cmd / managed_uv / npm_engine / secret_prompt / secrets_cli / onepassword | ❌ | 🚫 (BYOK) |
| 202 | models (Catalog-DB) | ❌ | J.23 (Mini-Catalog: MiniMax + opencode-go) |
| 203 | model_switch | 🟡 | E.7 (Resolver + /model erweitern) |
| 204 | model_setup_flows | ❌ | E.7 |
| 205–207 | model_search / normalize / cost_guard | ❌ | J.24 |
| 208 | provider_catalog | ❌ | J.25 |
| 209–211 | codex_* | ☁️ | — |
| 212–218 | nous_* / vercel / azure / dingtalk | 🚫/☁️ | — |
| 219 | plugins (Loader) | 🟡 | E.8 (/plugins Command) |
| 220 | plugins_cmd | ❌ | **E.8** |
| 221 | agent_plugins | 🟡 | E.8 |
| 222 | agent_import | ❌ | J.26 |
| 223 | blueprint_cmd | ❌ | J.27 (lokal) |
| 224 | skills_hub | ❌ | 🚫 (Cloud; A.11 lokale Bundles statt Hub) |
| 225 | skills_config | ❌ | **A.7** |
| 226 | memory_setup | ❌ | **E.2** (First-Run) |
| 227 | memory_oauth | 🚫 | — |
| 228 | default_soul | ❌ | **A.8** (SOUL.md-Template bei First-Run) |
| 229 | mem_trim | ❌ | A.12 (/memory trim) |
| 230 | sessions_cmd | 🟡 | **D.4** (Listing + Filter) |
| 231–233 | session_export (HTML/MD) | ❌ | **D.3** |
| 234 | session_filters | ❌ | **D.4** |
| 235 | session_listing | 🟡 | **D.4** |
| 236 | session_recap | ❌ | **D.5** |
| 237 | session_recovery | ❌ | **D.7** |
| 238 | active_sessions (Cross-Process-Leases) | ❌ | D.8 (lock-Datei) |
| 239 | approvals_suggest | ✅ 🔁 | — (P0.9/P0.20, `1587ebf`) |
| 240 | approval_mode | 🟡 | B.3 (/mode erweitern + safeAuto) |
| 241 | write_approval_commands | ❌ | B.4 (/approve + /deny für Edit-Diffs) |
| 242 | hooks (CLI) | ❌ | **E.12** (/hooks ls + enable) |
| 243–245 | security_advisories / audit / audit_startup | ❌ | J.28 |
| 246 | backup | ❌ | **E.13** |
| 247–248 | update_cmd / update_lock | ❌ | E.14 (git-pull-basiert) |
| 249 | doctor | 🟡 | **E.15** (erweitern) |
| 250 | doctor_live | ❌ | E.15 |
| 251 | dump | ❌ | **E.16** |
| 252 | uninstall | ❌ | J.29 |
| 253 | dep_ensure | ❌ | E.17 (venv-Checks) |
| 254 | diagnostics_upload | 🚫 | — |
| 255 | console_engine | 🟡 | J.30 (Spinner/Progress) |
| 256 | tips | ❌ | J.31 |
| 257 | colors | ❌ | J.32 (Theme in _output) |
| 258 | banner | ❌ | J.33 |
| 259 | cli_output | ✅ 🔁 | — (P0.18, `1587ebf`) |
| 260 | curses_ui | 🚫 | — |
| 261 | focus_view | ❌ | J.34 |
| 262–265 | skin_* / voice | 🚫 | — |
| 266 | sizefmt | ❌ | H.8 |
| 267 | timefmt | ❌ | H.8 |
| 268 | timeouts | ❌ | F.36 (zentrale Timeout-Tabelle) |
| 269 | clipboard (text+images) | 🟡 | H.9 (Bilder) |
| 270 | heartbeat | ❌ | G.7 (Cron-Daemon) |
| 271 | input_sanitize | ❌ | J.35 |
| 272 | middleware | ❌ | J.36 |
| 273 | build_info | ❌ | E.18 (/version erweitern) |
| 274 | lifecycle | ❌ | J.37 |
| 275 | managed_scope | ❌ | J.38 |
| 276 | relaunch | ❌ | J.39 |
| 277 | completion (shell) | ❌ | J.40 (optional) |
| 278–280 | sqlite_runtime / safe_read / util | ❌ | D.9 (wenn Sessions SQLite brauchen) |
| 281–283 | kanban_* | 🚫 | — |
| 284 | inventory | ❌ | J.41 |
| 285 | init_command | ❌ | **E.19** (eaccode init) |
| 286 | status | 🟡 | E.20 (/status erweitern: Version, Modell, Hooks) |
| 287 | cmd_* (46 Subcommands) | 🟡 | E.1 (Sammeltask: fehlende anlegen) |

### 2.3 `tools/` (107 Features)

| # | Feature | Status jetzt | Ziel |
|---|---|---|---|
| 288 | registry | ✅ | — |
| 289 | approval (Permission-Engine) | 🟡 | B.5 (voll: Scopes, Kategorien, Deny-Pattern) |
| 290 | terminal_tool (PTY, env) | 🟡 | **G.1** (PTY-Session + env-passthrough) |
| 291 | terminal_hints | ❌ | G.1 |
| 292 | process_registry (checkpoint-recovery) | 🟡 | **G.2** |
| 293 | daemon_pool | ❌ | G.3 (Cron-Daemon-Pool) |
| 294–295 | file_operations / file_tools | 🟡 | H.10 (Feinschliff: read_extract, binary) |
| 296 | file_state | ✅ 🔁 | — (P0.5, `09a74b0`) |
| 297 | path_security | 🟡 | H.4 |
| 298 | url_safety | ❌ | H.11 |
| 299 | working_diff | ❌ | H.12 (für /diff) |
| 300 | patch_parser | ❌ | **H.13** |
| 301 | read_extract | ❌ | H.10 |
| 302 | binary_extensions | ❌ | H.10 |
| 303 | ansi_strip | ❌ | H.14 |
| 304 | lazy_deps | ❌ | H.15 |
| 305 | debug_helpers | ❌ | J.2 |
| 306 | schema_sanitizer | ❌ | H.16 |
| 307 | tool_search | ❌ | H.17 |
| 308 | tool_output_limits | 🟡 | H.18 (zentral statt inline) |
| 309 | tool_result_storage | ❌ | H.19 |
| 310 | thread_context | ❌ | J.42 |
| 311 | managed_tool_gateway | ❌ | J.43 |
| 312 | self_repo_guard | ❌ | H.20 |
| 313 | interrupt | ❌ | F.28 |
| 314 | slash_confirm | ❌ | J.44 |
| 315 | fuzzy_match | ❌ | **A.6** (Skill-Trigger braucht ihn) |
| 316 | blueprints | ❌ | J.15 |
| 317 | budget_config | ❌ | F.37 |
| 318 | tirith_security | ❌ | 🚫 (3rd-party) |
| 319 | threat_patterns | 🟡 | H.21 (danger.py erweitern) |
| 320 | credential_files | ❌ | H.22 (.env-Detektion) |
| 321 | env_passthrough | ❌ | G.1 |
| 322 | env_probe | ❌ | E.11 |
| 323 | hook_output_spill | ✅ 🔁 | — (P0.10) |
| 324 | mcp_tool | 🟡 | G.4 |
| 325–326 | mcp_oauth / dashboard_oauth | 🚫 | — |
| 327 | mcp_schema_cache | ❌ | G.4 |
| 328 | project_tools | ❌ | J.45 |
| 329 | todo_tool | ✅ | — |
| 330 | clarify_tool | ✅ | — |
| 331 | clarify_gateway | ❌ | J.46 |
| 332 | close_terminal_tool | ❌ | G.1 |
| 333 | code_execution_tool | 🟡 | H.23 (Timeout/Output-Cap) |
| 334 | read_terminal_tool | ❌ | G.1 |
| 335 | read_window_tool | ❌ | J.47 |
| 336 | read_preview_tool | ❌ | J.47 |
| 337 | open_preview_tool | ❌ | J.47 |
| 338 | focus_pane_tool | 🚫 | — |
| 339–341 | kanban / send_message / react | 🚫 | — |
| 342 | session_search_tool | ✅ | — |
| 343–346 | browser (Supervisor/CDP/Dialog) | 🟡 | H.24 (Dialog-Timeout, Viewport) |
| 347–349 | camofox / browser_use_cli | ❌ | 🚫 (Stealth) |
| 350–351 | computer_use | 🟡 | H.25 (Schema-Erweiterung) |
| 352 | web_tools | ✅ | — |
| 353 | vision_tools | 🟡 | H.6 |
| 354 | image_source | ❌ | H.26 |
| 355 | skill_usage | 🟡 🔁 | A.3 (File-Backend statt Sidecar-only) |
| 356 | skill_linter | ❌ | **A.4** |
| 357 | skill_provenance | ❌ | **A.3** |
| 358 | skill_manager_tool (5+ actions) | 🟡 | **A.2** |
| 359 | skills_tool | 🟡 | A.2 |
| 360 | skills_hub | 🚫 | — |
| 361–364 | skills_sync / guard / ast_audit | ❌ | J.48 |
| 365 | memory_tool | 🟡 🔁 | — (P0.3: 4 Tools) |
| 366 | hook_output_spill (dup) | ✅ 🔁 | — |
| 367 | delegate_tool (tasks-Array) | 🟡 🔁 | C.4 (Async-Delegation) |
| 368 | async_delegation | ❌ | **C.4** |
| 369 | delegation_live_log | ❌ | C.4 |
| 370 | delegation_output_schema | ❌ | C.4 |
| 371 | cronjob_tools (action set) | 🟡 | **G.5** |
| 372 | checkpoint_manager | 🟡 | **H.27** |
| 373 | clarify_gateway (dup) | ❌ | J.46 |
| 374–381 | tts/stt/voice/audio | ☁️ | — |
| 382–384 | image_gen / flux3 / feishu | ☁️ | — |
| 385 | discord | 🚫 | — |
| 386 | desktop_ui | 🚫 | — |
| 387–391 | openrouter / xai / yuanbao / graph / homeassistant | ☁️ | — |
| 392 | homeassistant_tool | ☁️ | — |
| 393 | spotify_tool | ☁️ (existiert in Hermes NICHT — PLAN-4-Fehler) | — |
| 394 | skill_bundles (dup) | ❌ | A.11 |

### 2.4 Top-Level (24 Features)

| # | Feature | Status jetzt | Ziel |
|---|---|---|---|
| 395 | cli.py (Top-Level) | ❌ | E.1 (eigene Struktur vorhanden) |
| 396 | run_agent.py | ❌ | E.9 (eaccode run bleibt) |
| 397 | hermes_state | ❌ | J.49 |
| 398 | hermes_constants | ❌ | J.50 |
| 399 | tui_gateway (23 Files) | 🚫 | — |
| 400 | acp_adapter | 🚫 | — |
| 401 | cron/ (13 Files) | 🟡 | **G.5** |
| 402 | gateway/ (88 Files) | 🚫 | — |
| 403 | plugins/ (200 Files) | 🟡 | E.8 |
| 404 | skills/ (66 Skills) | ❌ | **A.13** (erste lokale Skills-Sammlung) |
| 405 | optional-skills/ | ❌ | A.13 |
| 406 | providers/ | ✅ | — |
| 407 | evals/ | ❌ | J.51 (optional) |
| 408 | tests/ | 🟡 | K.1 (Suite wächst mit jedem Task) |
| 409 | docs/ | 🟡 | **K.2** |
| 410–411 | apps/ website/ | 🚫 | — |
| 412 | locales/ | ❌ | J.11 |
| 413 | assets/ | ❌ | J.52 |
| 414–416 | web/ docker/ nix/ | 🚫 | — |
| 417 | mcp-research-data/ | ❌ | J.53 |
| 418 | datagen-config-examples/ | ❌ | J.54 |

---

## 3. Phasen mit TDD-Tasks (Reihenfolge = Abarbeitung)

> Fett = P0-Kern (Self-Improvement + Reliability), zuerst. Jede Phase endet mit
> Gesamtlauf + Ruff + Push. Schätzungen in Tagen (Erfahrungswerte aus bisherigen Phasen).

### Phase A — Skill-System-Vollausbau (P0.12–P0.16 + Nudges) · ~6–8 Tage

| Task | Feature-# | Beschreibung (TDD) | Dateien | Test |
|---|---|---|---|---|
| A.1 | 34 | **skill_utils erweitern**: Frontmatter-Parser (title/description/triggers/platform), `platform_matches`, Fehler bei kaputtem Frontmatter | `memory/skills.py` | `test_skills.py` |
| A.2 | 35/358/359 | **Skill-Manager auf 5+ Actions**: create/edit/delete/write_file/remove_file; `extract_user_instruction`; SkillListTool mit provenance-Filter | `memory/skill_tools.py` | `test_skill_tools.py` |
| A.3 | 355/357 | **Skill-Provenance** (bundled/user/curator/pinned) + Usage-File-Backend erweitern (statt Sidecar-only) | `memory/skill_usage.py` | `test_skill_usage.py` |
| A.4 | 356 | **Skill-Linter**: 12+ Convention-Rules (Frontmatter-Pflicht, 57-Char-Description, Trigger-Syntax, LoC-Cap) | `memory/skill_linter.py` (neu) | `test_skill_linter.py` |
| A.5 | 36 | **skill_preprocessing**: Template-Vars `{{cwd}}`, inline-shell-Sektion | `memory/skills.py` | `test_skills.py` |
| A.6 | 38/169/315 | **Skill-Triggers + Pre-Filter**: Frontmatter-Trigger-Match auf User-Prompt, Fuzzy-Match (reduziert, keine neue Dep), Pre-Filter vor Prompt-Injektion | `memory/skill_triggers.py` (neu) | `test_skill_triggers.py` |
| A.7 | 191/225 | **skills_config**: eaccode.yaml-Sektion `skills: {dirs, auto_load}` | `config/settings.py` | `test_settings.py` |
| A.8 | 228 | **default_soul**: SOUL.md-Template beim First-Run (in markdown_store.ensure_first_run) | `memory/markdown_store.py` | `test_markdown_memory.py` |
| A.9 | 32 | **Memory-Auto-Nudge**: nach N Turns ohne memory_* Aufruf → Hinweis im Loop (`/memory`-Tipp) | `agent/loop.py` | `test_agent_loop.py` |
| A.10 | 29 | **memory_provider-Base**: Interface über markdown_store (read/write/add/remove) | `memory/provider.py` (neu) | `test_markdown_memory.py` |
| A.11 | 37/394 | **Lokale Skill-Bundles**: Ordner `bundles/<name>/SKILL.md` + `eaccode skills bundle install <name>` | `memory/skill_bundles.py` (neu) + `cli/commands_skills.py` (neu) | `test_skill_bundles.py` |
| A.12 | 229 | **mem_trim**: `/memory trim` — älteste Fakten entfernen bis Budget | `ui/commands.py` | `test_commands.py` |
| A.13 | 404/405 | **Erste lokale Skills-Sammlung** (5–10: tdd, git-workflow, systematic-debugging, code-review, hermes-ähnliche) | `skills/` (neu) | Linter-Lauf |

**Phase-Ende:** Gesamtlauf grün, Ruff sauber, Push. Commit-Muster: `feat(skills): …`

### Phase B — safeAuto + Approval-Vollausbau (P0.5-PLAN-4) · ~3–4 Tage

| Task | Feature-# | Beschreibung (TDD) | Dateien | Test |
|---|---|---|---|---|
| B.1 | 61 | **Aux-LLM-Client**: kleiner Async-Client (eigener Provider, `extra: {classifier: "true"}`), Timeout, Fail-Open | `llm/aux_classifier.py` (neu) | `test_aux_classifier.py` |
| B.2 | 61/62 | **safeAuto-Klassifikation**: bash-Befehl → safe/risky (Aux-LLM, Cache, Key-Pattern-Fallback), Cost-Accounting per ContextVar | `permissions/smart.py` (neu) | `test_smart.py` |
| B.3 | 240 | **/mode safeAuto**: `smart`→`safeAuto` umbenennen (Settings-Migration in E.4), Fail-Open zu `manual` | `config/settings.py` + `ui/commands.py` | `test_commands.py` |
| B.4 | 241 | **write_approval_commands**: `/approve <id>` + `/deny <id>` für ausstehende Edit-Diffs | `ui/commands.py` + `ui/permission_modal.py` | `test_permission_modal.py` |
| B.5 | 289 | **Policy-Scopes**: Rule-Scope (session/always) + Kategorie-Matching + Deny-Pattern vor Allowlist | `permissions/policy.py` | `test_policy.py` |

### Phase C — Background-Review + Curator + Delegation · ~6–8 Tage

| Task | Feature-# | Beschreibung (TDD) | Dateien | Test |
|---|---|---|---|---|
| C.1 | 20 | **Background-Review-Scheduler**: nach Turn N (settings `review_every_turns`, default 5) Review-Job anreihen | `agent/review_scheduler.py` (neu) | `test_review_scheduler.py` |
| C.2 | 20/63 | **Review-Agent**: eigene AgentLoop-Instanz, Tool-Whitelist `{memory_*, skill_*}`, Review-Prompt (Gelerntes/Fakten/Skill-Vorschläge) | `agent/background_review.py` (neu) | `test_background_review.py` |
| C.3 | 20 | **Review-Ergebnis-Anwendung**: Fakten nur mit Approval-Gate (ASK), Skill-Vorschläge als Meldung | `agent/loop.py`-Hook | `test_background_review.py` |
| C.4 | 11/12/368–370 | **Async-Delegation**: Background-Subagenten (fire-and-forget mit Ergebnis-Queue), live-log, Output-Schema, parent-bind | `tools/builtin/delegate.py` | `test_tools_d.py` |
| C.5 | 21 | **Curator-Lifecycle**: active/stale/archived/pinned + `set_paused`, Scheduling | `curator/curator.py` | `test_curator.py` |
| C.6 | 22 | **Curator-Backup**: Backup der Skills+Memory vor Änderungen | `curator/backup.py` (neu) | `test_curator.py` |
| C.7 | 23–25 | **Learning-Graph**: Nodes (Skills/Fakten) + Edges (Nutzung), Recency-Ink, `delete_node` | `curator/learning_graph.py` (neu) | `test_learning_graph.py` |
| C.8 | 84 | **learn_prompt** in Review integrieren | (C.2) | (C.2) |

### Phase D — Sessions & Titel · ~4–5 Tage

| Task | Feature-# | Beschreibung (TDD) | Dateien | Test |
|---|---|---|---|---|
| D.1 | 74 | **Title-Generator two-stage**: deterministisch (erste Zeile) sofort, LLM-Upgrade async, Provenance `derived < llm < user`; `/title <text>` setzt user | `sessions/titles.py` (neu) | `test_titles.py` |
| D.2 | — | Titel in Session-Store persistieren + in Listing/Status anzeigen | `sessions/store.py` | `test_sessions.py` |
| D.3 | 231–233 | **Session-Export**: `eaccode sessions export <id> --format md|html` | `cli/commands_sessions.py` + `sessions/export.py` (neu) | `test_session_export.py` |
| D.4 | 230/234/235 | **Listing + Filter**: `sessions list [--provider] [--since] [--query]`, Pagination | `cli/commands_sessions.py` | `test_cli_sessions.py` |
| D.5 | 236 | **Session-Recap**: letzte N Nachrichten kompakt pro Session | `sessions/recap.py` (neu) | `test_recap.py` |
| D.6 | 9 | **Session-Metadaten**: bound-activity (Workdir, Provider, Modell) beim Start | `sessions/store.py` | `test_sessions.py` |
| D.7 | 237 | **Session-Recovery**: `/resume` lädt History + Zustand (inkl. Pause-Flag-Reset) | `ui/repl.py` + `ui/commands.py` | `test_commands.py` |
| D.8 | 238 | **Active-Session-Lease**: lock-Datei `dat/sessions/<id>.lock`, verwaiste Locks beim Start bereinigen | `sessions/leases.py` (neu) | `test_leases.py` |
| D.9 | 278–280 | SQLite nur wenn Listing-Performance es braucht (sonst JSONL behalten) | — | — |

### Phase E — CLI-Subcommands & First-Run (P0.19) · ~5–6 Tage

| Task | Feature-# | Beschreibung (TDD) | Dateien | Test |
|---|---|---|---|---|
| E.1 | 173/287/395 | **Fehlende Subcommands anlegen**: `hooks`, `memory`, `skills`, `backup`, `verify`, `dump`, `init`, `doctor` (Existenz + happy-path) | `cli/__init__.py` + `cli/commands_*.py` | `test_cli.py` |
| E.2 | 174/226 | **First-Run-Setup**: `eaccode setup` — Provider, Memory-Files, Hooks-Ordner, Skill-Sammlung in einem Flow | `cli/commands_setup.py` (neu) | `test_cli_setup.py` |
| E.3 | 185/186 | **Settings-Sektionen**: `hooks: {enabled}`, `skills: {dirs}`, `memory: {budgets}` in eaccode.yaml + `eaccode config show` | `config/settings.py` | `test_settings.py` |
| E.4 | 187 | **Config-Migration**: `settings_version` in eaccode.yaml, Migration `smart`→`safeAuto` beim Laden | `config/settings.py` | `test_settings.py` |
| E.5 | 188 | **fallback_config**: Defaults wenn eaccode.yaml fehlt/kaputt (warnen, nicht crashen) | `config/settings.py` | `test_settings.py` |
| E.6 | 195 | **env_loader**: `.env` im Workdir laden (nicht überschreiben, was gesetzt ist) | `config/env_loader.py` (neu) | `test_env_loader.py` |
| E.7 | 203/204 | **model_setup_flows**: `eaccode model add/list/switch` (Provider aus providers.yaml) | `cli/commands_models.py` (neu) | `test_cli_models.py` |
| E.8 | 219–221/403 | **/plugins Command**: ls/enable/disable/install (context_engine) | `ui/commands.py` + `cli/commands_plugins.py` (neu) | `test_commands.py` |
| E.9 | 83/396 | **oneshot prüfen**: `eaccode run` — exit-code, --print, --output-format | `cli/__init__.py` | `test_run_cmd.py` |
| E.10 | 136 | **Install-Hinweise**: `eaccode doctor` prüft venv/PATH (hat doctor schon) | (E.15) | (E.15) |
| E.11 | 154/322 | **env_probe**: Umgebung-Checks (git, python, uv, trafilatura-verfügbar?) | `cli/commands_utility.py` | `test_cli_utility.py` |
| E.12 | 242 | **/hooks Command**: ls/run/enable + `eaccode hooks` | `ui/commands.py` + `cli/commands_hooks.py` (neu) | `test_hooks.py` |
| E.13 | 246 | **Backup-CLI**: `eaccode backup` — config+dat als Zip nach `~/eaccode-backups/` | `cli/commands_backup.py` (neu) + `config/backup.py` (neu) | `test_backup.py` |
| E.14 | 247/248 | **Update-Cmd**: `eaccode update` — git pull + venv-Reinstall (nur wenn Repo da) | `cli/commands_update.py` (neu) | `test_cli_update.py` |
| E.15 | 249/250 | **Doctor erweitern**: Hooks, Memory-Files, MCP, Session-DB, Modelle; `--live`-Watch | `cli/commands_utility.py` | `test_cli_utility.py` |
| E.16 | 251 | **dump**: `eaccode dump` — Settings/Paths/Provider (Keys maskiert!) als YAML | `cli/commands_dump.py` (neu) | `test_cli_dump.py` |
| E.17 | 253 | **dep_ensure**: fehlende Deps melden (trafilatura etc.) statt crashen | `cli/commands_utility.py` | `test_cli_utility.py` |
| E.18 | 273 | **/version + build_info**: Commit+Version aus `importlib.metadata` | `ui/commands.py` | `test_commands.py` |
| E.19 | 285 | **init_command**: `eaccode init` — EACCODE.md + .eaccodeignore-Vorlage im Workdir | `cli/commands_init.py` (neu) | `test_cli_init.py` |
| E.20 | 286 | **/status erweitern**: Version, Modell, Hooks-Status, Memory-Budget-Nutzung | `ui/commands.py` | `test_commands.py` |

### Phase F — Agent-Runtime-Feinschliff · ~6–8 Tage

| Task | Feature-# | Beschreibung (TDD) | Dateien | Test |
|---|---|---|---|---|
| F.1 | 2 | **Init-Reihenfolge** dokumentieren + Profile-Slot (Name in Settings) | `agent/factory.py` | `test_factory.py` |
| F.7 | 5 | **Turn-Finalizer**: nach jedem Turn — Budget-Check, Cost-Aggregation, History-Cap | `agent/loop.py` | `test_agent_loop.py` |
| F.8 | 3 | **Runtime-Helpers**: nur benötigte (fmt_elapsed, cwd-resolve, env) | `agent/runtime_helpers.py` (neu) | `test_runtime_helpers.py` |
| F.9 | 4 | **turn_context**: compose/substitute für @-Refs + angehängte Kontexte | `agent/loop.py` | `test_agent_loop.py` |
| F.10 | 6 | **turn_retry_state**: letzte Tool-Calls für /retry (Zustand statt Regex) | `ui/repl.py` | `test_repl.py` |
| F.11 | 7 | **turn_summary**: `format_elapsed`/`format_token_flow` in /status + /cost | `ui/commands.py` | `test_commands.py` |
| F.12 | 8 | **iteration_budget**: max_tokens pro Turn (Settings) | `agent/loop.py` | `test_agent_loop.py` |
| F.13 | 10 | **runtime_cwd**: Agent-CWD fest (Workdir), bash-Tool resolved relativ | `tools/builtin/bash.py` | `test_tool_bash.py` |
| F.14 | 13 | **async_utils**: `safe_schedule_threadsafe` für UI-Callbacks | `agent/async_utils.py` (neu) | `test_async_utils.py` |
| F.15 | 15 | **conversation_compression reduziert**: Timeout-Resolve + komprimierte History bei Session-Recovery | `agent/compaction.py` | `test_compaction.py` |
| F.16 | 16/27 | **manual_compression_feedback**: /compress zeigt was entfernt wurde | `ui/commands.py` | `test_commands.py` |
| F.17 | 18 | **@folder + @git**: context_refs erweitern | `ui/context_refs.py` | `test_context_refs.py` |
| F.18 | 19 | **Context-Grid**: /context zeigt Tokens je Sektion (system/memory/skills/history) | `ui/commands.py` + `agent/factory.py` | `test_commands.py` |
| F.19 | 30/31 | **message_sanitization**: `close_interrupted_tool_sequence`, deterministic_call_id, Strip-Tails beim Laden | `sessions/store.py` + `agent/sanitize.py` (neu) | `test_sanitize.py` |
| F.20 | 40 | **reasoning_summaries**: separate_glued_reasoning_blocks | `llm/think_scrubber.py` | `test_think_scrubber.py` |
| F.21 | 42 | **thinking_timeout_guidance**: verständliche Timeout-Meldung + Modell-Tipp | `llm/reasoning_timeouts.py` | `test_reasoning_timeouts.py` |
| F.22 | 43 | **lmstudio_reasoning**: effort→reasoning_effort-Mapping (falls Provider es kann) | `llm/client.py` | `test_client.py` |
| F.23 | 54 | **verification_evidence**: `eaccode verify` führt Settings-verify-Commands aus + protokolliert | `cli/commands_verify.py` (neu) + `agent/verification.py` (neu) | `test_verification.py` |
| F.24 | 55/56 | **verify_on_stop**: Nudge am Antwort-Ende (max 2×/Session) | `agent/loop.py` | `test_agent_loop.py` |
| F.25 | 85 | **redact erweitern**: mask_secret (API-Keys, Tokens), redact_cdp_url, sensitiv-Text | `security/redact.py` | `test_redact.py` |
| F.26 | 87 | **replay_cleanup**: interrupted-tool-tails beim /resume strippen | `sessions/store.py` | `test_sanitize.py` |
| F.27 | 88 | **estop**: `dat/estop`-Sentinel → alle Tool-Calls blockiert | `permissions/policy.py` | `test_policy.py` |
| F.28 | 95/313 | **interrupt**: sauberer Task-Cancel im Loop (hat /stop im REPL — prüfen) | `ui/repl.py` | `test_repl.py` |
| F.29 | 97 | **thread_scoped_silence**: ContextVar für stille Tool-Ausführung (Subagenten) | `agent/thread_scope.py` (neu) | `test_thread_scope.py` |
| F.30 | 99 | **AGENTS.md Parent-Chain**: EACCODE.md → AGENTS.md → CLAUDE.md → .cursorrules (Parent-Dirs rauf) | `memory/project.py` | `test_project.py` |
| F.31 | 100/101 | **prompt_caching**: cache_control für MiniMax (falls unterstützt) + stable-prefix-Erkennung | `llm/client.py` | `test_client.py` |
| F.32 | 107 | **error_classifier erweitern**: 3-way → +5 Kategorien (AUTH/RATE/LIMIT/TIMEOUT/BAD_REQUEST) | `llm/errors.py` | `test_errors.py` |
| F.33 | 108 | **bounded_response**: Fehler-Body begrenzt lesen | `llm/client.py` | `test_client.py` |
| F.34 | 109 | **native_compaction**: OpenAI-Modelle → native compaction (optional) | `agent/compaction.py` | `test_compaction.py` |
| F.35 | 170 | **_cache**: `dat/cache/` für Prompt-Cache + Aux-Cache | `config/paths.py` | `test_paths.py` |
| F.36 | 268 | **timeouts**: zentrale Timeout-Tabelle (llm, hooks, tools) | `config/settings.py` | `test_settings.py` |
| F.37 | 317 | **budget_config**: max_budget_usd pro Session (hat der Loop schon — Settings-Expose) | `config/settings.py` | `test_settings.py` |

### Phase G — Cron/Process/Vision/Web-Vollausbau · ~5–6 Tage

| Task | Feature-# | Beschreibung (TDD) | Dateien | Test |
|---|---|---|---|---|
| G.1 | 290/291/321/332/334 | **Terminal-Vollausbau**: PTY-Session (Windows: winpty-Fallback), env-passthrough, close/read-Terminal-Tools, Hints | `tools/builtin/bash.py` + `tools/builtin/process.py` | `test_tool_bash.py` + `test_process.py` |
| G.2 | 292 | **Process-Registry**: ProcessSession mit Checkpoint-Recovery (bei Session-Recovery laufende Prozesse re-attachen), stdin-Write, Notifications | `tools/builtin/process.py` | `test_process.py` |
| G.3 | 293/98 | **Daemon-Pool**: Cron-Daemon-Prozesse verwalten, keepalive-Client | `cron/scheduler.py` | `test_cron.py` |
| G.4 | 189/324/327 | **MCP-Vollausbau**: mcp.yaml env+args, Schema-Cache, Tool-Fehler sauber | `tools/mcp/client.py` | `test_mcp.py` |
| G.5 | 371/401/131/132 | **Cron-Full-Surface**: deliver (origin/local/all), no_agent (script-only), workdir, context_from (Chaining), monitor-Health | `tools/builtin/cronjob.py` + `cron/scheduler.py` + `cron/health.py` (neu) | `test_cron.py` + `test_cronjob.py` |
| G.6 | 125 | **web_search_registry**: Provider-Registry (DuckDuckGo default, kein API-Key) | `tools/builtin/web_search.py` | `test_web_search.py` |
| G.7 | 270 | **heartbeat**: Daemon-Heartbeat-Datei + /health | `cron/scheduler.py` | `test_cron.py` |
| G.8 | 49 | **Tool-Executor parallel**: concurrent-Dispatch (gleiche Tool-Namen parallel), batch-timeout | `tools/executor.py` | `test_executor.py` |
| G.9 | 171 | **MCP-Server für eigene Tools** (optional): eaccode-Tools als MCP-Server exportieren | `tools/mcp/server.py` (neu) | `test_mcp_server.py` |

### Phase H — Tools-Detail & Safety · ~4–5 Tage

| Task | Feature-# | Beschreibung (TDD) | Dateien | Test |
|---|---|---|---|---|
| H.1 | 44 | **redact_tool_args_for_display**: Keys/Pfade in Tool-Preview maskieren | `ui/preview.py` | `test_preview.py` |
| H.2 | 52 | **Argument-Canonicalizer**: relative→absolute Pfade, Aliase | `tools/schema.py` | `test_schema.py` |
| H.3 | 53 | **ToolClass-Audit**: alle Tools klassifizieren + Guardrails nutzen sie | `tools/base.py` + `tools/factory.py` | `test_factory.py` |
| H.4 | 86/297 | **file_safety**: write_denied mit Klassen (secrets, .git, venv), cross-profile-Warnung | `tools/safety.py` | `test_safety.py` |
| H.5 | 92 | **markdown_tables**: Parser (split_table_row, is_table_divider) | `tools/markdown_tables.py` (neu) | `test_markdown_tables.py` |
| H.6 | 93/353 | **image_routing**: Bild-Eingabemodus entscheiden (Daten-URL/Pfad), Vision-Full | `llm/aux_vision.py` | `test_vision_tool.py` |
| H.7 | 94 | **flatten_message_text** in compaction + preview nutzen | `agent/compaction.py` | `test_compaction.py` |
| H.8 | 266/267 | **sizefmt + timefmt**: format_size, format_duration | `cli/_output.py` | `test_output.py` |
| H.9 | 269 | **Clipboard-Bilder**: Bilder aus Tool-Ergebnissen in Clipboard (PowerShell-Kompatibilität prüfen) | `ui/clipboard.py` | `test_clipboard.py` |
| H.10 | 294/295/301/302 | **File-Ops-Feinschliff**: read_extract (Zeilenbereiche), binary_extensions (Binär-Erkennung) | `tools/builtin/read.py` | `test_tool_read.py` |
| H.11 | 298 | **url_safety**: URL-Schema-Allowlist (http/https/file) vor web_extract | `tools/safety.py` | `test_safety.py` |
| H.12 | 299 | **working_diff**: /diff auf Git-Diff zurückfallen wenn kein Patch | `ui/commands.py` | `test_commands.py` |
| H.13 | 300 | **patch_parser**: V4A-Patch-Parser für /apply | `tools/patch_parser.py` (neu) | `test_patch_parser.py` |
| H.14 | 303 | **ansi_strip**: ANSI-Codes aus Tool-Output | `tools/ansi_strip.py` (neu) | `test_ansi_strip.py` |
| H.15 | 304 | **lazy_deps**: trafilatura etc. lazy importieren + Fehlermeldung | `tools/lazy.py` (neu) | `test_lazy.py` |
| H.16 | 306 | **schema_sanitizer**: Schema-Felder fürs LLM kürzen | `tools/schema.py` | `test_schema.py` |
| H.17 | 307 | **tool_search**: /tools <query> — Namens+Desc-Suche | `ui/commands.py` | `test_commands.py` |
| H.18 | 308 | **tool_output_limits**: zentral cap_output (hat executor inline) | `tools/executor.py` | `test_executor.py` |
| H.19 | 309 | **tool_result_storage**: große Ergebnisse auf Platte statt Kontext | `tools/result_store.py` (neu) | `test_result_store.py` |
| H.20 | 312 | **self_repo_guard**: Schreibzugriff auf eigenes Repo warnen | `tools/safety.py` | `test_safety.py` |
| H.21 | 319 | **threat_patterns**: danger.py erweitern (curl|base64, rm -rf /, …) | `permissions/danger.py` | `test_danger.py` |
| H.22 | 320 | **credential_files**: .env/Keys-Dateien → write_denied | `tools/safety.py` | `test_safety.py` |
| H.23 | 333 | **execute_code**: Timeout + Output-Cap | `tools/builtin/execute_code.py` | `test_execute_code.py` |
| H.24 | 343–346 | **Browser-Feinschliff**: Dialog-Timeout, Viewport-Set, Konsole-Filter | `tools/browser/actions.py` | `test_browser_session.py` |
| H.25 | 350/351 | **computer_use**: Schema erweitern (cua_browser_*) | `tools/cua.py` | `test_cua.py` |
| H.26 | 354 | **image_source**: Bild-Quellen normalisieren (Pfad/URL/Data-URL) | `llm/aux_vision.py` | `test_vision_tool.py` |
| H.27 | 372 | **checkpoint_manager**: Verzeichnis-Backups (statt single-file), Restore-Liste, TTL | `tools/checkpoints.py` | `test_checkpoints.py` |

### Phase I — Backup/Doctor/Update (in E aufgegangen) · 0 Tage
> E.13/E.14/E.15 decken die Backup/Doctor/Update-Features ab — keine eigene Phase.

### Phase J — P1-Rest (kleine Features, gebündelt) · ~8–10 Tage
> J-Tasks = je 0.25–1 Tag; werden in Clustern von 4–6 Tasks pro Commit-Serie abgearbeitet.
> J.1 insights (26) · J.2 stream_diag+debug_helpers (46/305) · J.3 reactions (47) · J.4 onboarding (48) ·
> J.5 plugin_llm (60) · J.6 usage_pricing (75) · J.7 credential_pool (76) · J.8 range_shift (89/163) ·
> J.9 ssl_guard (90/91) · J.10 portal_tags (96) · J.11 i18n-Skelett (102/412) · J.12 jiter_preload (104) ·
> J.13 trajectory (130) · J.14 eventlog+emitter (133/134/153) · J.15 recipes+blueprints (135/316) ·
> J.16 monitoring (137) · J.17 store/manager-Abstract (139/140/166) · J.18 manifest (142) ·
> J.19 state (158) · J.20 protocol (162) · J.21 servers (164) · J.22 runtime_provider (193) ·
> J.23 model-catalog-mini (202) · J.24 model_search/normalize/cost_guard (205–207) · J.25 provider_catalog (208) ·
> J.26 agent_import (222) · J.27 blueprint_cmd (223) · J.28 security_advisories/audit (243–245) ·
> J.29 uninstall (252) · J.30 console_engine-Spinner (255) · J.31 tips (256) · J.32 colors (257) ·
> J.33 banner (258) · J.34 focus_view (261) · J.35 input_sanitize (271) · J.36 middleware (272) ·
> J.37 lifecycle (274) · J.38 managed_scope (275) · J.39 relaunch (276) · J.40 completion (277) ·
> J.41 inventory (284) · J.42 thread_context (310) · J.43 managed_tool_gateway (311) · J.44 slash_confirm (314) ·
> J.45 project_tools (328) · J.46 clarify_gateway (331/373) · J.47 read_window/preview + open_preview (335–337) ·
> J.48 skills_sync/guard/ast_audit (361–364) · J.49 hermes_state (397) · J.50 hermes_constants (398) ·
> J.51 evals (407) · J.52 assets (413) · J.53 mcp-research-data (417) · J.54 datagen-examples (418)

### Phase K — Finale Verifikation, Doku, Release · ~2 Tage

| Task | Beschreibung | Details |
|---|---|---|
| K.1 | Gesamt-Suite + Ruff | `pytest -q -p no:cacheprovider` (Hintergrund, notify) + `ruff check src/ tests/` |
| K.2 | **README + docs/**: Features, Commands, Hooks, Memory-Format, Screenshots | `README.md` + `docs/` (neu) |
| K.3 | CHANGELOG v0.3.0 | aus Commit-Historie |
| K.4 | Letzter Push + Tag | `git tag v0.3.0` |

---

## 4. Nicht-Ziele (explizit — aus PLAN-4 §8, unverändert)

☁️ Cloud: TTS/STT/Image-Gen/Video-Gen, Discord/Slack/Telegram/WhatsApp/Feishu, OAuth,
HomeAssistant, Spotify, Web-UI, Desktop-UI, Gateway, Dashboard, ACP, OpenRouter/XAI,
Nous-Billing, Microsoft-Graph, Yuanbao.
🚫 Out-of-scope: Kanban, MoA, Pets, Skins, LSP, Skills-Hub (Cloud), Skills-Bundles-Cloud,
Credential-Pools (Multi-Key), Memory-OAuth, Provider-Registries, TUI-Gateway, Web-Server,
CLI-Monolith, Hermes-1:1-Ports (base/constants/runner/…), Tirith, Camofox.
🖥️ OS-bound: Battery, Windows-PTY-Bridge (nur Fallback).
**Keine neuen Python-Deps** außer optional `trafilatura` (web_extract) — alles stdlib/lokale Mechanik.

## 5. Risiken & offene Fragen

| Risiko | Mitigation |
|---|---|
| PLAN-4-Daten teils fehlerhaft (skills_hub 4607→~2000 LOC; spotify existiert nicht; `video`+`a2a` default-off) | Master-Tabelle oben ist gegengeprüft (GitHub-API, 2026-08-09); bei Zweifel erneut gegen Hermes-Code prüfen |
| `trafilatura` fehlt im venv (web_extract-Fallback) | H.15 lazy import; `eaccode doctor` meldet es; Installation optional via uv |
| Windows-PTY nicht trivial | G.1 winpty-Fallback; PTY nur wo nötig, sonst subprocess mit creationflags |
| MiniMax-M3 cache_control evtl. nicht unterstützt | F.31 Feature-Detect statt hart schalten |
| Background-Review kostet Tokens | C.1 Settings `review_every_turns` + Whitelist {memory, skills} + Fail-Open |
| Suite wächst (Browser/CUA-Tests flaky) | `-p no:cacheprovider`; K.1 Gesamtlauf als Gate vor Push |

**Definition of Done für jeden Task:** Tests grün (RED vorher), Ruff sauber, Commit mit
Feature-Referenz, kein uncommitteter Stand am Tagesende.

---

## 6. Fortschritt (Abarbeitungs-Status)

> **Lebende Checkliste** — wird nach JEDEM fertigen Feature aktualisiert (User-Anforderung).
> Legende: ⬜ offen · 🔄 in Arbeit · ✅ fertig (Commit) · ⛔ gestrichen

### Phase A — Skill-System

| Task | Status | Commit / Notiz |
|---|---|---|
| A.1 skill_utils (Frontmatter/Platform) | ✅ | `9ec6f07` |
| A.2 Skill-Manager 5+ Actions | ✅ | `1b988b1` |
| A.3 Skill-Provenance + Usage-Backend | ✅ | `9ec6f07` |
| A.4 Skill-Linter | ✅ | `a62e86d` |
| A.5 skill_preprocessing (Template-Vars) | ✅ | `6bb61b2` |
| A.6 Skill-Triggers + Pre-Filter | ✅ | `86eac5f` |
| A.7 skills_config | ✅ | `02febf6` |
| A.8 default_soul | ✅ | `02febf6` |
| A.9 Memory-Auto-Nudge | ✅ | `2d50807` |
| A.10 memory_provider-Base | ✅ | `2d50807` |
| A.11 Lokale Skill-Bundles | 🔄 | — |
| A.12 mem_trim | 🔄 | — |
| A.13 Lokale Skills-Sammlung | ⬜ | — |

### Phase B — safeAuto + Approval

| Task | Status | Commit / Notiz |
|---|---|---|
| B.1 Aux-LLM-Client | ⬜ | — |
| B.2 safeAuto-Klassifikation | ⬜ | — |
| B.3 /mode safeAuto (Migration) | ⬜ | — |
| B.4 /approve + /deny | ⬜ | — |
| B.5 Policy-Scopes | ⬜ | — |

### Phase C — Background-Review + Curator

| Task | Status | Commit / Notiz |
|---|---|---|
| C.1 Review-Scheduler | ⬜ | — |
| C.2 Review-Agent (Whitelist) | ⬜ | — |
| C.3 Review-Ergebnis (Approval-Gate) | ⬜ | — |
| C.4 Async-Delegation | ⬜ | — |
| C.5 Curator-Lifecycle | ⬜ | — |
| C.6 Curator-Backup | ⬜ | — |
| C.7 Learning-Graph | ⬜ | — |
| C.8 learn_prompt | ⬜ | — |

### Phase D — Sessions & Titel

| Task | Status | Commit / Notiz |
|---|---|---|
| D.1 Title-Generator two-stage | ⬜ | — |
| D.2 Titel-Persistenz | ⬜ | — |
| D.3 Session-Export MD/HTML | ⬜ | — |
| D.4 Listing + Filter | ⬜ | — |
| D.5 Session-Recap | ⬜ | — |
| D.6 Session-Metadaten | ⬜ | — |
| D.7 Session-Recovery | ⬜ | — |
| D.8 Active-Session-Lease | ⬜ | — |
| D.9 SQLite-Entscheid | ⬜ | — |

### Phase E — CLI-Subcommands

| Task | Status | Commit / Notiz |
|---|---|---|
| E.1 Subcommands anlegen | ⬜ | — |
| E.2 First-Run-Setup | ⬜ | — |
| E.3 Settings-Sektionen | ⬜ | — |
| E.4 Config-Migration | ⬜ | — |
| E.5 fallback_config | ⬜ | — |
| E.6 env_loader | ⬜ | — |
| E.7 model_setup_flows | ⬜ | — |
| E.8 /plugins Command | ⬜ | — |
| E.9 oneshot prüfen | ⬜ | — |
| E.11 env_probe | ⬜ | — |
| E.12 /hooks Command | ⬜ | — |
| E.13 Backup-CLI | ⬜ | — |
| E.14 Update-Cmd | ⬜ | — |
| E.15 Doctor erweitern | ⬜ | — |
| E.16 dump | ⬜ | — |
| E.17 dep_ensure | ⬜ | — |
| E.18 /version + build_info | ⬜ | — |
| E.19 init_command | ⬜ | — |
| E.20 /status erweitern | ⬜ | — |

### Phase F — Agent-Runtime

| Task | Status | Commit / Notiz |
|---|---|---|
| F.1 Init-Reihenfolge/Profile | ⬜ | — |
| F.7 Turn-Finalizer | ⬜ | — |
| F.8 Runtime-Helpers | ⬜ | — |
| F.9 turn_context | ⬜ | — |
| F.10 turn_retry_state | ⬜ | — |
| F.11 turn_summary | ⬜ | — |
| F.12 iteration_budget | ⬜ | — |
| F.13 runtime_cwd | ⬜ | — |
| F.14 async_utils | ⬜ | — |
| F.15 conversation_compression | ⬜ | — |
| F.16 manual_compression_feedback | ⬜ | — |
| F.17 @folder + @git | ⬜ | — |
| F.18 Context-Grid | ⬜ | — |
| F.19 message_sanitization | ⬜ | — |
| F.20 reasoning_summaries | ⬜ | — |
| F.21 thinking_timeout_guidance | ⬜ | — |
| F.22 lmstudio_reasoning | ⬜ | — |
| F.23 verification_evidence | ⬜ | — |
| F.24 verify_on_stop | ⬜ | — |
| F.25 redact erweitern | ⬜ | — |
| F.26 replay_cleanup | ⬜ | — |
| F.27 estop | ⬜ | — |
| F.28 interrupt | ⬜ | — |
| F.29 thread_scoped_silence | ⬜ | — |
| F.30 AGENTS.md Parent-Chain | ⬜ | — |
| F.31 prompt_caching | ⬜ | — |
| F.32 error_classifier | ⬜ | — |
| F.33 bounded_response | ⬜ | — |
| F.34 native_compaction | ⬜ | — |
| F.35 _cache | ⬜ | — |
| F.36 timeouts | ⬜ | — |
| F.37 budget_config | ⬜ | — |

### Phase G — Cron/Process/Vision/Web

| Task | Status | Commit / Notiz |
|---|---|---|
| G.1 Terminal-Vollausbau (PTY) | ⬜ | — |
| G.2 Process-Registry | ⬜ | — |
| G.3 Daemon-Pool | ⬜ | — |
| G.4 MCP-Vollausbau | ⬜ | — |
| G.5 Cron-Full-Surface | ⬜ | — |
| G.6 web_search_registry | ⬜ | — |
| G.7 heartbeat | ⬜ | — |
| G.8 Tool-Executor parallel | ⬜ | — |
| G.9 MCP-Server (optional) | ⬜ | — |

### Phase H — Tools-Detail & Safety

| Task | Status | Commit / Notiz |
|---|---|---|
| H.1 redact_tool_args_for_display | ⬜ | — |
| H.2 Argument-Canonicalizer | ⬜ | — |
| H.3 ToolClass-Audit | ⬜ | — |
| H.4 file_safety-Klassen | ⬜ | — |
| H.5 markdown_tables | ⬜ | — |
| H.6 image_routing | ⬜ | — |
| H.7 flatten_message_text | ⬜ | — |
| H.8 sizefmt + timefmt | ⬜ | — |
| H.9 Clipboard-Bilder | ⬜ | — |
| H.10 File-Ops-Feinschliff | ⬜ | — |
| H.11 url_safety | ⬜ | — |
| H.12 working_diff | ⬜ | — |
| H.13 patch_parser | ⬜ | — |
| H.14 ansi_strip | ⬜ | — |
| H.15 lazy_deps | ⬜ | — |
| H.16 schema_sanitizer | ⬜ | — |
| H.17 tool_search | ⬜ | — |
| H.18 tool_output_limits | ⬜ | — |
| H.19 tool_result_storage | ⬜ | — |
| H.20 self_repo_guard | ⬜ | — |
| H.21 threat_patterns | ⬜ | — |
| H.22 credential_files | ⬜ | — |
| H.23 execute_code-Caps | ⬜ | — |
| H.24 Browser-Feinschliff | ⬜ | — |
| H.25 computer_use-Schema | ⬜ | — |
| H.26 image_source | ⬜ | — |
| H.27 checkpoint_manager | ⬜ | — |

### Phase J — P1-Rest (J.1–J.54, gebündelt)

| Cluster | Status | Notiz |
|---|---|---|
| J.1–J.6 (Insights, Debug, Reactions, Onboarding, Plugin-LLM, Pricing) | ⬜ | — |
| J.7–J.12 (Credential-Pool, Range-Shift, SSL, Portal-Tags, i18n, Jiter) | ⬜ | — |
| J.13–J.18 (Trajectory, Events/Emitter, Recipes, Monitoring, Store-Abstract, Manifest) | ⬜ | — |
| J.19–J.24 (State, Protocol, Servers, Runtime-Provider, Model-Catalog, Model-Tools) | ⬜ | — |
| J.25–J.30 (Provider-Catalog, Agent-Import, Blueprint, Security-Audit, Uninstall, Spinner) | ⬜ | — |
| J.31–J.36 (Tips, Colors, Banner, Focus-View, Input-Sanitize, Middleware) | ⬜ | — |
| J.37–J.42 (Lifecycle, Managed-Scope, Relaunch, Completion, Inventory, Thread-Context) | ⬜ | — |
| J.43–J.48 (Tool-Gateway, Slash-Confirm, Project-Tools, Clarify-Gateway, Preview-Tools, Skills-Sync) | ⬜ | — |
| J.49–J.54 (State, Constants, Evals, Assets, MCP-Data, Datagen) | ⬜ | — |

### Phase K — Finale Verifikation

| Task | Status | Commit / Notiz |
|---|---|---|
| K.1 Gesamt-Suite + Ruff | ⬜ | — |
| K.2 README + docs/ | ⬜ | — |
| K.3 CHANGELOG | ⬜ | — |
| K.4 Push + Tag v0.3.0 | ⬜ | — |

