# eac-code v0.2.0 — Vollständiger Hermes-Feature-Katalog mit eac-code-Status

> **Single source of truth.** Alles was Hermes kann, mit eac-code-Stand daneben.
>
> **Stand:** 2026-08-11 · Hermes v0.20.0 (1099 Files, 848k LOC) vs. eac-code (117 Files, 11833 LOC src-only)
>
> **Legende:**
> - ✅ = voll umgesetzt (gleicher oder besserer Mechanismus)
> - 🟡 = teilweise / reduziert umgesetzt
> - ❌ = fehlt komplett
> - ☁️ = Cloud-only (RAUS für eac-code)
> - 🖥️ = OS-bound (RAUS)
> - 🚫 = explizit out-of-scope (User-Entscheidung)
>
> **Referenz-Files:** `HERMES-FULL-ANALYSIS.md` (60 KB), `HERMES-GAP-ANALYSIS-v2.md` (45 KB), `eac-code/.hermes/plans/2026-08-09_100000-eaccode-iteration-n+1.md` (User-Plan, 1667 Zeilen)

---

## 0. Summary

| | Hermes | eac-code 2026-08-11 | Faktor |
|---|---|---|---|
| Python-Files | 1099 | 117 | **9.4x** |
| LOC | 848.560 | 11.833 | **71.7x** |
| Tests | 2860 | 78+ | **37x** |
| `agent/` | 188 Files, ~150k LOC | 6 Files, ~1250 LOC | **120x** |
| `hermes_cli/` | 268 Files, ~340k LOC | 10 Files, ~1100 LOC | **309x** |
| `tools/` | 135 Files, ~280k LOC | 28 Files, ~3500 LOC | **80x** |

**Realität:** eac-code ist funktional **viel weiter** als mein Audit v2 glaubte. User hat in den letzten 13 Commits **alle Phase 0-A-H User-Plan-Items teilweise oder voll umgesetzt** plus 2 Toolset-Items (Browser, Computer-Use).

---

## 1. agent/ — 188 Hermes-Files, ~150.000 LOC

### Core Loop & Agent-Runtime

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 1 | `agent/conversation_loop.py` | 7757 | Main-Loop: prompt → LLM → tool → repeat | `agent/loop.py` 344 LOC | 🟡 reduziert (kein Codex-Runtime, kein Relay) |
| 2 | `agent/agent_init.py` | 2858 | Top-Level-Init (Credentials, Provider, Memory, Skills, Tools, Profile, Background-Review, Hook-Loading, MCP-Discovery) | `agent/factory.py` 209 LOC | 🟡 reduziert (kein Background-Review, kein Profile) |
| 3 | `agent/agent_runtime_helpers.py` | 4086 | 41 Runtime-Utility-Functions | (nicht vorhanden) | ❌ |
| 4 | `agent/turn_context.py` | 1378 | `compose_user_api_content`, `substitute_api_content` | (nicht vorhanden) | ❌ |
| 5 | `agent/turn_finalizer.py` | 798 | `finalize_turn` (cleanup, cost-aggregation) | (nicht vorhanden) | ❌ |
| 6 | `agent/turn_retry_state.py` | 93 | Turn-Retry-State-Tracking | (nicht vorhanden) | ❌ |
| 7 | `agent/turn_summary.py` | 310 | `format_elapsed`, `format_token_flow` | (nicht vorhanden) | ❌ |
| 8 | `agent/iteration_budget.py` | 62 | Pro-Iteration-Budget-Enforcement | `agent/loop.py` (nur max_turns) | 🟡 reduziert |
| 9 | `agent/session_activity.py` | 106 | `bound_activity_description`, `normalize_activity_provenance` | (nicht vorhanden) | ❌ |
| 10 | `agent/runtime_cwd.py` | 100 | Session-CWD, `resolve_agent_cwd` | (nicht vorhanden) | ❌ |
| 11 | `agent/delegation_context.py` | 161 | Subagent-Context-Tracking | (nicht vorhanden) | ❌ |
| 12 | `agent/subagent_lifecycle.py` | 540 | Subagent-Parent-Bind, `get_active_subagent_parent` | (nicht vorhanden) | ❌ |
| 13 | `agent/async_utils.py` | 84 | `safe_schedule_threadsafe`, `consume_detached_task_result` | (nicht vorhanden) | ❌ |

### Compaction & Context-Compression

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 14 | `agent/context_compressor.py` | 7386 | Smart-Compaction: Soft-Tail, Ghost-Skill, Pre-LLM-Feasibility, Window-Floor, Redaction | `agent/compaction.py` 164 LOC | ✅ alle 5 Features portiert |
| 15 | `agent/conversation_compression.py` | 4133 | Conversation-Compression-Engine, `resolve_context_compression_timeouts` | (nicht vorhanden) | ❌ (zu komplex, eigenes?) |
| 16 | `agent/manual_compression_feedback.py` | 120 | `describe_compression_lock_skip`, `summarize_manual_compression` | (nicht vorhanden) | ❌ |
| 17 | `agent/context_engine.py` | 489 | Context-Engine-Trigger, `sanitize_memory_context` | `context/engine.py` 80 LOC | 🟡 teilweise (eigene Plugin-API) |
| 18 | `agent/context_references.py` | 621 | `parse_context_references`, `preprocess_context_references` (`@file:`, `@folder:`, `@git:`, `@url:`) | `ui/context_refs.py` 60 LOC + `agent/loop.py:_expand_user_references` | 🟡 reduziert (Grundmechanik da) |
| 19 | `agent/context_breakdown.py` | 360 | `compute_session_context_breakdown`, `render_context_grid` | `ui/repl.py:_context_pct` (single %) | 🟡 nur %, kein Grid |

### Background-Review & Self-Improvement

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 20 | `agent/background_review.py` | 1144 | **Daemonsicher Background-Fork**: Post-Turn Memory/Skill-Review, eigene AIAgent-Instanz, Tool-Whitelist `["memory","skills"]`, inherited Runtime | (nicht vorhanden) | ❌ **P0 ITEM** |
| 21 | `agent/curator.py` | 2019 | Skill-Curator: load_state, save_state, set_paused, lifecycle (active/stale/archived/pinned) | `curator/curator.py` 34 LOC | 🟡 Skelett, kaum Logik |
| 22 | `agent/curator_backup.py` | 751 | Curator-Backup-Logik | (nicht vorhanden) | ❌ |
| 23 | `agent/learning_graph.py` | 328 | Skills+Memory-Graph (nodes, edges, density) | (nicht vorhanden) | ❌ |
| 24 | `agent/learning_graph_render.py` | 658 | Recency-Ink, format_date, compute_recency | (nicht vorhanden) | ❌ |
| 25 | `agent/learning_mutations.py` | 206 | parse_node_kind, node_detail, delete_node | (nicht vorhanden) | ❌ |
| 26 | `agent/insights.py` | 1162 | 30-Tage-Stats, Cost-Breakdown, Tool-Usage-Charts | (nicht vorhanden) | ❌ |
| 27 | `agent/manual_compression_feedback.py` | 120 | (siehe oben) | — | ❌ |

### Memory-System (Hermes-Style)

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 28 | `agent/memory_manager.py` | 1241 | MemoryManager: load_from_disk, char-budgets, system-prompt-inject | `memory/store.py` 87 LOC (JSONL) | 🟡 nur Store, kein 3-File-Layout |
| 29 | `agent/memory_provider.py` | 357 | Memory-Provider-Abstract-Base | (nicht vorhanden) | ❌ |
| 30 | `agent/message_sanitization.py` | 865 | `close_interrupted_tool_sequence`, `deterministic_call_id`, `coalesce_tool_call_id`, replay-cleanup | (nicht vorhanden) | ❌ |
| 31 | `agent/memory_provider.py` (siehe oben) | 357 | Streaming-Context-Scrubber | — | ❌ |
| 32 | `agent/memory_provider.py` Memory-Auto-Nudge | — | (in `loop.py`) | (nicht vorhanden) | ❌ **P0 ITEM** (Memory-Rewrite) |
| 33 | `agent/memory_layout` MEMORY/USER/SOUL.md | — | 3 separate Files, char-budgets (2200/1375/800), atomic-write, approval-gate | (1 JSONL-File) | ❌ **P0 ITEM** |

### Skill-System (Hermes-Style)

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 34 | `agent/skill_utils.py` | 934 | Frontmatter-Parser, platform-matches, is_org_mirror_path | `memory/skills.py` 86 LOC | 🟡 Grundmechanik da, weniger Features |
| 35 | `agent/skill_commands.py` | 840 | `append_user_instruction`, `extract_user_instruction_from_skill_message` | `memory/skill_tools.py` 80 LOC | 🟡 reduziert |
| 36 | `agent/skill_preprocessing.py` | 144 | load_skills_config, substitute_template_vars, run_inline_shell | (nicht vorhanden) | ❌ |
| 37 | `agent/skill_bundles.py` | 438 | scan_bundles, resolve_bundle_command_key | (nicht vorhanden) | ❌ |
| 38 | `agent/skill_triggers` (in skill_preprocessing) | — | Frontmatter-Trigger-Match | (nicht vorhanden) | ❌ |

### Reasoning & Thinking

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 39 | `agent/think_scrubber.py` | 396 | **Stateful** StreamingThinkScrubber (handelt `<think>` split across deltas) | `llm/think_scrubber.py` 165 LOC | ✅ voll portiert |
| 40 | `agent/reasoning_summaries.py` | 67 | `separate_glued_reasoning_blocks` | (nicht vorhanden) | ❌ |
| 41 | `agent/reasoning_timeouts.py` | 231 | Per-Reasoning-Model Stale-Timeout-Floor (MiniMax-M3 → 600s) | `llm/reasoning_timeouts.py` 40 LOC | ✅ voll portiert |
| 42 | `agent/thinking_timeout_guidance.py` | 136 | `is_thinking_timeout`, `build_thinking_timeout_guidance` | (nicht vorhanden) | ❌ |
| 43 | `agent/lmstudio_reasoning.py` | 60 | `resolve_lmstudio_effort` | (nicht vorhanden) | ❌ |

### Display & Streaming

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 44 | `agent/display.py` | 1580 | `build_tool_preview`, `build_tool_label`, `summarize_shell_command`, `redact_tool_args_for_display` | `ui/preview.py` 253 LOC | 🟡 teilweise (Verbs, Preview) |
| 45 | `agent/stream_single_writer.py` | 70 | Single-Writer-Fence (Ctrl+C-safe) | `llm/stream_fence.py` 65 LOC | ✅ voll portiert |
| 46 | `agent/stream_diag.py` | 280 | Stream-Diagnostics (debug) | (nicht vorhanden) | ❌ |
| 47 | `agent/reactions.py` | 56 | `detect_reaction` (emoji-Reaction-Detection) | (nicht vorhanden) | ❌ |
| 48 | `agent/onboarding.py` | 266 | Onboarding-Hints (busy_input_hint_gateway, tool_progress_hint) | (nicht vorhanden) | ❌ |

### Tool-Execution & Guardrails

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 49 | `agent/tool_executor.py` | 2429 | Sequential+Concurrent Dispatch, Authorization-Gate, batch-timeout, checkpoint-before-mutation, managed results | `tools/executor.py` 69 LOC | 🟡 nur sequential, keine Concurrency |
| 50 | `agent/tool_guardrails.py` | 632 | Loop-Detection: same-failure×N → warn/halt, idempotent-no-progress, per-turn web_search/subagent caps | `agent/guardrails.py` 276 LOC | ✅ voll portiert + in `loop.py` verdrahtet |
| 51 | `agent/tool_result_classification.py` | 42 | `file_mutation_result_landed` | `tools/result_classification.py` 43 LOC | ✅ voll portiert |
| 52 | `agent/tool_dispatch_helpers.py` | 732 | Argument-Canonicalization, Tool-Name-Resolution, Schema-Prep | `tools/schema.py` 9 LOC + `tools/base.py` 87 LOC | 🟡 reduziert |
| 53 | `agent/tool_guardrails.py` `ToolClass` enum | — | idempotent\|mutating\|runaway | `tools/base.py:ToolClass` (sollte existieren) | 🟡 zu prüfen |

### Verification & Stop

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 54 | `agent/verification_evidence.py` | 698 | `classify_verification_command`, `record_terminal_result`, `record_verify_run` | (nicht vorhanden) | ❌ |
| 55 | `agent/verification_stop.py` | 312 | `verify_on_stop_enabled`, `build_verify_on_stop_nudge` | (nicht vorhanden) | ❌ |
| 56 | `agent/verify_hooks.py` | 69 | `max_verify_nudges`, `coding_verify_guidance` | (nicht vorhanden) | ❌ |
| 57 | `agent/kanban_stop.py` | 108 | `kanban_stop_nudge_enabled`, `session_called_kanban_terminal` | (nicht vorhanden) | ❌ |

### Hooks (Hermes)

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 58 | `agent/shell_hooks.py` | 1067 | Pre/Post-Tool-Call Shell-Hooks (config-driven, allowlist) | (nicht vorhanden) | ❌ **P0 ITEM** (war in User-Plan als nicht enthalten) |
| 59 | `agent/hook_output_spill` (in `tools/`) | — | Hook-Output-Spill in nächste User-Message | (nicht vorhanden) | ❌ |

### LLM-Tool-Whitelist & Pluggable-LLM

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 60 | `agent/plugin_llm.py` | 1046 | Plugin-LLM-System | (nicht vorhanden) | ❌ |
| 61 | `agent/auxiliary_client.py` | 10298 | **Auxiliary-LLM** für Smart-Mode, Mode-Probing, Interrupt-Protection | (nicht vorhanden) | ❌ **P0 ITEM** (`safeAuto`) |
| 62 | `agent/aux_accounting.py` | 138 | `set_accounting_context` (ContextVar) für Smart-Mode-Cost | (nicht vorhanden) | ❌ |
| 63 | `agent/scope` Tool-Whitelist | — | Tool-Whitelist per-agent (memory, skills) | (nicht vorhanden) | ❌ |

### Provider-Adapters (Cloud-bound)

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 64 | `agent/anthropic_adapter.py` | 3186 | Anthropic-spezifischer Adapter (73 funcs) | (nur LiteLLM-Generic) | 🟡 LiteLLM reicht |
| 65 | `agent/bedrock_adapter.py` | 1573 | AWS-Bedrock (SigV4-Auth) | (nur LiteLLM) | ☁️ Cloud |
| 66 | `agent/gemini_native_adapter.py` | 1127 | Gemini-Native | (nur LiteLLM) | ☁️ Cloud |
| 67 | `agent/codex_responses_adapter.py` | 1625 | OpenAI-Codex-Responses | (nicht vorhanden) | ☁️ Cloud |
| 68 | `agent/codex_runtime.py` | 1467 | Codex-App-Server-Runtime | (nicht vorhanden) | ☁️ Cloud |
| 69 | `agent/copilot_acp_client.py` | 756 | GitHub-Copilot | (nicht vorhanden) | ☁️ Cloud |
| 70 | `agent/vertex_adapter.py` | 228 | Google-Vertex | (nicht vorhanden) | ☁️ Cloud |
| 71 | `agent/azure_identity_adapter.py` | 571 | Azure-Identity | (nicht vorhanden) | ☁️ Cloud |
| 72 | `agent/moonshot_schema.py` | 269 | Moonshot-Schema | (nicht vorhanden) | ☁️ Cloud (Asia-only) |
| 73 | `agent/chat_completion_helpers.py` | 4631 | Chat-Completion-Utilities (provider-agnostic) | (nicht vorhanden) | 🟡 LiteLLM macht vieles |

### Title, Auth, Cost

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 74 | `agent/title_generator.py` | 739 | **Two-Stage**: instant deterministic + LLM-upgrade, provenance `derived < llm < user` | `sessions/store.py` (keine Titles) | ❌ |
| 75 | `agent/usage_pricing.py` | 1432 | resolve_billing_route, get_pricing_entry, normalize_usage | (nicht vorhanden) | ❌ |
| 76 | `agent/credentials/credential_pool.py` | 3178 | Multi-Key-Rotation per Provider | `config/providers.py` 145 LOC | 🟡 Single-Key, Fallback-Chain |
| 77 | `agent/credential_sources.py` | 451 | Credential-Source-Registry | (nicht vorhanden) | ❌ |
| 78 | `agent/credential_persistence.py` | 174 | `is_borrowed_credential_source` | (nicht vorhanden) | ❌ |
| 79 | `agent/backend_identity.py` | 204 | `classify_failure_scope` | `llm/errors.py` 53 LOC | 🟡 reduziert |
| 80 | `agent/secret_scope.py` | 293 | `set_multiplex_active`, `set_secret_scope` | (nicht vorhanden) | ❌ |
| 81 | `agent/secret_sources/` | — | 1Password, Bitwarden, Atlas, etc. | (nicht vorhanden) | ❌ (optional) |
| 82 | `agent/coding_context.py` | 916 | RuntimeMode/ContextProfile, `build_coding_workspace_block` | `agent/workspace.py` 207 LOC | ✅ voll portiert |
| 83 | `agent/oneshot.py` | 158 | `run_oneshot` (one-shot-mode) | `cli/__init__.py` `eaccode run` | 🟡 ähnlich |
| 84 | `agent/learn_prompt.py` | 237 | `build_learn_prompt` | (nicht vorhanden) | ❌ |

### Redaction & Security

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 85 | `agent/redact.py` | 1197 | `mask_secret`, `redact_cdp_url`, `redact_sensitive_text` (23 funcs) | `security/redact.py` 24 LOC | 🟡 nur Basic-Patterns |
| 86 | `agent/file_safety.py` | 693 | Write-denied paths, classified denials, cross-profile warnings | `tools/safety.py` 67 LOC | 🟡 reduziert |
| 87 | `agent/replay_cleanup.py` | 323 | `is_interrupted_tool_result`, `strip_interrupted_tool_tails` | (nicht vorhanden) | ❌ |
| 88 | `agent/estop.py` | 174 | Emergency-Stop (`sentinel_path`, `engage`) | (nicht vorhanden) | ❌ (nice-to-have) |
| 89 | `agent/range_shift.py` | — | (siehe Hermes) | — | ❌ |
| 90 | `agent/ssl_guard.py` | 101 | `verify_ca_bundle` | (nicht vorhanden) | ❌ |
| 91 | `agent/ssl_verify.py` | 63 | `resolve_httpx_verify` | (nicht vorhanden) | ❌ |

### Misc Utilities

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 92 | `agent/markdown_tables.py` | 309 | Markdown-Table-Parser (split_table_row, is_table_divider) | (nicht vorhanden) | ❌ |
| 93 | `agent/image_routing.py` | 821 | `extract_image_refs`, `decide_image_input_mode` | `llm/aux_vision.py` | 🟡 reduziert |
| 94 | `agent/message_content.py` | 50 | `flatten_message_text` | (nicht vorhanden) | ❌ |
| 95 | `agent/interrupt_compat.py` | — | Interrupt-Compat-Shim | (nicht vorhanden) | ❌ |
| 96 | `agent/portal_tags.py` | 144 | `set_conversation_context`, `get_conversation_context` | (nicht vorhanden) | ❌ |
| 97 | `agent/thread_scoped_output.py` | 142 | `thread_scoped_silence` | (nicht vorhanden) | ❌ |
| 98 | `agent/process_bootstrap.py` | 227 | `build_keepalive_http_client` | (nicht vorhanden) | ❌ |
| 99 | `agent/prompt_builder.py` | 2334 | `_load_agents_md`, `_load_claude_md`, `_load_cursorrules` (parent-chain) | `memory/project.py` (single EACCODE.md) | 🟡 kein Parent-Chain |
| 100 | `agent/prompt_caching.py` | 432 | Provider-aware prompt-cache redecoration | `agent/factory.py` (cache ja, cache_control nein) | 🟡 kein cache_control |
| 101 | `agent/prompt_cache_boundary.py` | 94 | register_stable_prefix, find_stable_prefix | (nicht vorhanden) | ❌ |
| 102 | `agent/i18n.py` | 282 | t(key, lang), Fallback en | (nicht vorhanden) | ❌ (en-only Default) |
| 103 | `agent/battery.py` | 131 | `read_battery`, `battery_category` | (nicht vorhanden) | ❌ (laptop-only) |
| 104 | `agent/jiter_preload.py` | — | Performance-Optimization | (nicht vorhanden) | ❌ |
| 105 | `agent/retry_utils.py` | 208 | Jittered-Backoff, Retry-After-Parse | `llm/retry_utils.py` 50 LOC | ✅ voll portiert |
| 106 | `agent/rate_limit_tracker.py` | 246 | parse_rate_limit_headers, format_rate_limit_display | `llm/rate_limit.py` 100+ LOC | ✅ voll portiert |
| 107 | `agent/error_classifier.py` | 1842 | 15 funcs, riesige Code-Mappings | `llm/errors.py` 53 LOC | 🟡 nur 3-way (STOP/RETRY/FALLBACK) |
| 108 | `agent/bounded_response.py` | 148 | `read_streaming_error_body` | (nicht vorhanden) | ❌ |
| 109 | `agent/native_compaction.py` | 186 | `is_native_compaction_model`, OpenAI-Native-Compaction | (nicht vorhanden) | ❌ |
| 110 | `agent/nous_rate_guard.py` | 325 | Nous-spezifischer Rate-Guard | (nicht vorhanden) | 🚫 (Nous ist Cloud) |
| 111 | `agent/credits_tracker.py` | 852 | `new_credits_latch`, `is_free_tier_model` | (nicht vorhanden) | 🚫 |
| 112 | `agent/billing_view.py` | 511 | parse_money, format_money, billing_state_from_payload | (nicht vorhanden) | 🚫 |
| 113 | `agent/billing_usage.py` | 323 | format_renews, usage_model_from_account | (nicht vorhanden) | 🚫 |
| 114 | `agent/billing_links.py` | 124 | is_nous_inference_route, build_billing_block | (nicht vorhanden) | 🚫 |
| 115 | `agent/account_usage.py` | 902 | render_account_usage_lines, build_nous_credits_snapshot | (nicht vorhanden) | 🚫 |

### Image/Video/TTS-Provider (Cloud)

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 116 | `agent/image_gen_provider.py` | 399 | Image-Gen-Provider-Base | (nicht vorhanden) | ☁️ Cloud |
| 117 | `agent/image_gen_registry.py` | 145 | Image-Gen-Registry | (nicht vorhanden) | ☁️ Cloud |
| 118 | `agent/video_gen_provider.py` | 596 | Video-Gen-Provider-Base | (nicht vorhanden) | ☁️ Cloud |
| 119 | `agent/video_gen_registry.py` | 133 | Video-Gen-Registry | (nicht vorhanden) | ☁️ Cloud |
| 120 | `agent/tts_provider.py` | 274 | TTS-Provider-Base | (nicht vorhanden) | ☁️ Cloud (lokal: edge-tts möglich) |
| 121 | `agent/tts_registry.py` | 134 | TTS-Registry | (nicht vorhanden) | ☁️ Cloud |
| 122 | `agent/transcription_provider.py` | 193 | STT-Provider-Base | (nicht vorhanden) | ☁️ Cloud |
| 123 | `agent/transcription_registry.py` | 124 | STT-Registry | (nicht vorhanden) | ☁️ Cloud |
| 124 | `agent/web_search_provider.py` | 211 | Web-Search-Provider-Base | `tools/builtin/web_search.py` 82 LOC | ✅ vorhanden |
| 125 | `agent/web_search_registry.py` | 304 | Web-Search-Registry | (in `web_search.py`?) | 🟡 |

### Browser (lokal via cua-driver)

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 126 | `agent/browser_provider.py` | 177 | Browser-Provider-Pattern | `tools/browser/session.py` 401 LOC | ✅ voll portiert |
| 127 | `agent/browser_registry.py` | 192 | Browser-Provider-Registry | `tools/browser/actions.py` 104 LOC | ✅ voll portiert |

### MoA (Mixture-of-Agents)

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 128 | `agent/moa_loop.py` | 2384 | MoA-Loop (Multi-Agent-Konsens) | (nicht vorhanden) | 🚫 out-of-scope (YAGNI) |
| 129 | `agent/moa_trace.py` | 167 | MoA-Trace | (nicht vorhanden) | 🚫 |

### Misc

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 130 | `agent/trajectory.py` | 56 | convert_scratchpad_to_think, save_trajectory | (nicht vorhanden) | ❌ |
| 131 | `agent/curator_health.py` (in cron_health) | — | Health-Checks | (nicht vorhanden) | ❌ |
| 132 | `agent/cron_health.py` | — | Cron-Health | (nicht vorhanden) | ❌ |
| 133 | `agent/eventlog/` | — | Event-Log | (nicht vorhanden) | ❌ |
| 134 | `agent/events.py` | — | Event-Definitions | (nicht vorhanden) | ❌ |
| 135 | `agent/recipes.py` | — | Recipes (skill-bundles-ähnlich) | (nicht vorhanden) | ❌ |
| 136 | `agent/install/` | — | Install-Logik | (nicht vorhanden) | ❌ |
| 137 | `agent/monitoring/` | — | Monitoring | (nicht vorhanden) | ❌ |
| 138 | `agent/lsp/` | — | LSP-Integration (Language-Server-Protocol) | (nicht vorhanden) | ❌ (cool) |
| 139 | `agent/store.py` | — | Store-Abstract | (nicht vorhanden) | ❌ |
| 140 | `agent/manager.py` | — | Manager-Abstract | (nicht vorhanden) | ❌ |
| 141 | `agent/pet/` | — | Pet-Mascots | (nicht vorhanden) | 🚫 |
| 142 | `agent/manifest.py` | — | Manifest-Loader | (nicht vorhanden) | ❌ |
| 143 | `agent/types.py` | — | Type-Definitions | `llm/models.py` | ✅ vorhanden (eigene) |
| 144 | `agent/base.py` | — | Base-Classes | (nicht vorhanden) | ❌ |
| 145 | `agent/constants.py` | — | Constants | (nicht vorhanden) | ❌ |
| 146 | `agent/runner.py` | — | Runner | (nicht vorhanden) | ❌ |
| 147 | `agent/render.py` | — | Render | (nicht vorhanden) | ❌ |
| 148 | `agent/reporter.py` | — | Reporter | (nicht vorhanden) | ❌ |
| 149 | `agent/orchestrate.py` | — | Orchestrate | (nicht vorhanden) | ❌ |
| 150 | `agent/command.py` | — | Command-Abstract | (nicht vorhanden) | ❌ |
| 151 | `agent/cli.py` | — | CLI-Base | (nicht vorhanden) | ❌ |
| 152 | `agent/client.py` | — | Client-Base | (nicht vorhanden) | ❌ |
| 153 | `agent/emitter.py` | — | Event-Emitter | (nicht vorhanden) | ❌ |
| 154 | `agent/environment.py` | — | Environment-Setup | (nicht vorhanden) | ❌ |
| 155 | `agent/policy.py` | — | Policy-Base | `permissions/policy.py` | ✅ eigene |
| 156 | `agent/prompts.py` | — | Prompts-Base | `permissions/prompts.py` | ✅ eigene |
| 157 | `agent/registry.py` | — | Registry-Base | `tools/factory.py` | ✅ eigene |
| 158 | `agent/state.py` | — | State-Base | (nicht vorhanden) | ❌ |
| 159 | `agent/atlas.py` (in secret_sources) | — | Atlas-Integration | (nicht vorhanden) | ❌ |
| 160 | `agent/bitwarden.py` (in secret_sources) | — | Bitwarden-Integration | (nicht vorhanden) | ❌ |
| 161 | `agent/onepassword.py` (in secret_sources) | — | 1Password-Integration | (nicht vorhanden) | ❌ |
| 162 | `agent/protocol.py` | — | Protocol-Definitions | (nicht vorhanden) | ❌ |
| 163 | `agent/range_shift.py` | — | Range-Shift | (nicht vorhanden) | ❌ |
| 164 | `agent/servers.py` | — | Server-Management | (nicht vorhanden) | ❌ |
| 165 | `agent/workspace.py` | — | Workspace-Base | `agent/workspace.py` | ✅ eigene |
| 166 | `agent/manager.py` | — | (s.o.) | — | — |
| 167 | `agent/iron_proxy.py` | — | Iron-Proxy | (nicht vorhanden) | ❌ |
| 168 | `agent/proxy_sources/` | — | Proxy-Sources | (nicht vorhanden) | ❌ |
| 169 | `agent/skill_commands` Trigger-Pre-Filter | — | (in skill_preprocessing) | (nicht vorhanden) | ❌ |
| 170 | `agent/_cache/` | — | Cache | (nicht vorhanden) | ❌ |
| 171 | `agent/hermes_tools_mcp_server.py` | — | MCP-Server für Tools | (nicht vorhanden) | ❌ |

**Subtotal agent/: 171 Features katalogisiert** (von 188 Files; Rest sind Submodule in `lsp/`, `monitoring/`, `pet/`, `secret_sources/`, `proxy_sources/`, `eventlog/`, `install/`)

---

## 2. hermes_cli/ — 268 Hermes-Files, ~340.000 LOC

### Main & Setup

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 172 | `hermes_cli/main.py` | 12805 | Main-CLI-Entry | `cli/__init__.py` 60 LOC | 🟡 nur Sub-Commands, kein Main-Monolith |
| 173 | `hermes_cli/commands.py` | 18915 | Top-Level-Commands-Registry | `ui/commands.py` 407 LOC | 🟡 reduziert |
| 174 | `hermes_cli/setup.py` | 3645 | First-Run-Setup | `cli/commands_utility.py` 50 LOC | 🟡 reduziert |
| 175 | `hermes_cli/auth.py` | 9274 | OAuth/Auth-Flow | (nicht vorhanden) | 🚫 (lokal) |
| 176 | `hermes_cli/auth_commands.py` | — | Auth-Commands | (nicht vorhanden) | 🚫 |
| 177 | `hermes_cli/web_server.py` | 17951 | Web-UI (FastAPI) | (nicht vorhanden) | 🚫 (kein Web) |
| 178 | `hermes_cli/gateway.py` | 7539 | TUI-Gateway | (nicht vorhanden) | 🚫 |
| 179 | `hermes_cli/gateway_windows.py` | — | Windows-Gateway | (nicht vorhanden) | 🖥️ |
| 180 | `hermes_cli/gateway_enroll.py` | — | Gateway-Enroll | (nicht vorhanden) | 🚫 |
| 181 | `hermes_cli/dashboard_procs.py` | — | Dashboard-Procs | (nicht vorhanden) | 🚫 |
| 182 | `hermes_cli/dashboard_register.py` | — | Dashboard-Register | (nicht vorhanden) | 🚫 |
| 183 | `hermes_cli/dashboard_auth/` | — | Dashboard-Auth | (nicht vorhanden) | 🚫 |
| 184 | `hermes_cli/gui_uninstall.py` | — | GUI-Uninstall | (nicht vorhanden) | 🚫 |

### Config

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 185 | `hermes_cli/config.py` | 5499 | Config-Monster | `config/settings.py` 80 LOC | 🟡 viel kleiner |
| 186 | `hermes_cli/config_defaults.py` | 4429 | Config-Defaults | (in `settings.py`?) | 🟡 |
| 187 | `hermes_cli/config_migrations.py` | 760 | Config-Migrations | (nicht vorhanden) | ❌ |
| 188 | `hermes_cli/fallback_config.py` | — | Fallback-Config | (nicht vorhanden) | ❌ |
| 189 | `hermes_cli/mcp_config.py` | — | MCP-Config | `tools/mcp/client.py` 70 LOC | 🟡 reduziert |
| 190 | `hermes_cli/moa_config.py` | — | MoA-Config | (nicht vorhanden) | 🚫 |
| 191 | `hermes_cli/skills_config.py` | — | Skills-Config | (nicht vorhanden) | ❌ |
| 192 | `hermes_cli/tools_config.py` | 5550 | Tools-Config (inkl. `_DEFAULT_OFF_TOOLSETS`) | (nicht vorhanden) | ❌ |
| 193 | `hermes_cli/runtime_provider.py` | 2298 | Runtime-Provider-Resolver | (nicht vorhanden) | ❌ |
| 194 | `hermes_cli/providers.py` | 959 | Providers-Loader | `config/providers.py` 145 LOC | 🟡 reduziert |
| 195 | `hermes_cli/env_loader.py` | — | Env-Loader | (nicht vorhanden) | ❌ |
| 196 | `hermes_cli/fallback_cmd.py` | — | Fallback-CMD | (nicht vorhanden) | ❌ |
| 197 | `hermes_cli/managed_uv.py` | — | Managed-UV | (nicht vorhanden) | ❌ |
| 198 | `hermes_cli/npm_engine.py` | — | NPM-Engine | (nicht vorhanden) | ❌ |
| 199 | `hermes_cli/secret_prompt.py` | — | Secret-Prompt | (nicht vorhanden) | ❌ |
| 200 | `hermes_cli/secrets_cli.py` | — | Secrets-CLI | (nicht vorhanden) | ❌ |
| 201 | `hermes_cli/onepassword_secrets_cli.py` | — | 1Password-Integration | (nicht vorhanden) | ❌ (optional) |

### Models, Auth, Billing

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 202 | `hermes_cli/models.py` | 5518 | Model-Catalog-DB | (nicht vorhanden) | ❌ |
| 203 | `hermes_cli/model_switch.py` | 3368 | Model-Switch | `llm/model_switch.py` 35 LOC | 🟡 reduziert |
| 204 | `hermes_cli/model_setup_flows.py` | 2300 | Model-Setup-Flows | (nicht vorhanden) | ❌ |
| 205 | `hermes_cli/model_search.py` | — | Model-Suche | (nicht vorhanden) | ❌ |
| 206 | `hermes_cli/model_normalize.py` | — | Model-Normalize | (nicht vorhanden) | ❌ |
| 207 | `hermes_cli/model_cost_guard.py` | — | Model-Cost-Guard | (nicht vorhanden) | ❌ |
| 208 | `hermes_cli/provider_catalog.py` | 181 | Provider-Catalog | (nicht vorhanden) | ❌ |
| 209 | `hermes_cli/codex_models.py` | — | Codex-Models | (nicht vorhanden) | ☁️ |
| 210 | `hermes_cli/codex_runtime_switch.py` | — | Codex-Switch | (nicht vorhanden) | ☁️ |
| 211 | `hermes_cli/codex_runtime_plugin_migration.py` | — | Codex-Migration | (nicht vorhanden) | ☁️ |
| 212 | `hermes_cli/nous_account.py` | — | Nous-Account | (nicht vorhanden) | 🚫 |
| 213 | `hermes_cli/nous_billing.py` | — | Nous-Billing | (nicht vorhanden) | 🚫 |
| 214 | `hermes_cli/nous_subscription.py` | — | Nous-Subscription | (nicht vorhanden) | 🚫 |
| 215 | `hermes_cli/nous_auth_keepalive.py` | — | Nous-Auth-Keepalive | (nicht vorhanden) | 🚫 |
| 216 | `hermes_cli/vercel_auth.py` | — | Vercel-Auth | (nicht vorhanden) | 🚫 |
| 217 | `hermes_cli/azure_detect.py` | — | Azure-Detection | (nicht vorhanden) | ☁️ |
| 218 | `hermes_cli/dingtalk_auth.py` | — | DingTalk-Auth | (nicht vorhanden) | 🚫 |

### Toolsets & Plugins

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 219 | `hermes_cli/plugins.py` | 2300+ | Plugin-Loader (system-wide) | `context/engine.py` 80 LOC | 🟡 eigene Mini-Variante |
| 220 | `hermes_cli/plugins_cmd.py` | — | Plugins-CLI | (nicht vorhanden) | ❌ |
| 221 | `hermes_cli/agent_plugins.py` | — | Agent-Plugins | `context/engine.py` | 🟡 |
| 222 | `hermes_cli/agent_import.py` | — | Agent-Import | (nicht vorhanden) | ❌ |
| 223 | `hermes_cli/blueprint_cmd.py` | — | Blueprint-Command | (nicht vorhanden) | ❌ |

### Skills & Memory

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 224 | `hermes_cli/skills_hub.py` | 4607 | Skills-Hub (Cloud) | (nicht vorhanden) | ❌ (lokal: Mini-Hub möglich) |
| 225 | `hermes_cli/skills_config.py` | — | Skills-Config | (nicht vorhanden) | ❌ |
| 226 | `hermes_cli/memory_setup.py` | — | First-Run-Memory-Setup | (nicht vorhanden) | ❌ |
| 227 | `hermes_cli/memory_oauth.py` | — | Memory-OAuth | (nicht vorhanden) | 🚫 |
| 228 | `hermes_cli/default_soul.py` | — | Default-SOUL-Template | (nicht vorhanden) | ❌ |
| 229 | `hermes_cli/mem_trim.py` | — | Memory-Trim | (nicht vorhanden) | ❌ |

### Sessions

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 230 | `hermes_cli/sessions_cmd.py` | 2300+ | Sessions-Command | `cli/commands_sessions.py` 80 LOC | 🟡 reduziert |
| 231 | `hermes_cli/session_export.py` | — | Session-Export | (nicht vorhanden) | ❌ |
| 232 | `hermes_cli/session_export_html.py` | — | HTML-Export | (nicht vorhanden) | ❌ |
| 233 | `hermes_cli/session_export_md.py` | — | MD-Export | (nicht vorhanden) | ❌ |
| 234 | `hermes_cli/session_filters.py` | — | Session-Filter | (nicht vorhanden) | ❌ |
| 235 | `hermes_cli/session_listing.py` | — | Session-Listing | `sessions/search.py` 33 LOC | 🟡 |
| 236 | `hermes_cli/session_recap.py` | — | Session-Recap | (nicht vorhanden) | ❌ |
| 237 | `hermes_cli/session_recovery.py` | — | Session-Recovery | (nicht vorhanden) | ❌ |
| 238 | `hermes_cli/active_sessions.py` | 426 | Cross-Process-Session-Leases | (nicht vorhanden) | ❌ |

### Approvals, Hooks, Security

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 239 | `hermes_cli/approvals_suggest.py` | 487 | Approval-History-Mining → Allowlist-Glob-Suggest | `permissions/allowlist.py` 166 LOC | ✅ voll portiert |
| 240 | `hermes_cli/approval_mode.py` | — | Approval-Mode-Commands | (in `policy.py`) | 🟡 inline |
| 241 | `hermes_cli/write_approval_commands.py` | — | Write-Approval-Commands | (nicht vorhanden) | ❌ |
| 242 | `hermes_cli/hooks.py` | — | Hooks-CLI | (nicht vorhanden) | ❌ **P0 ITEM** |
| 243 | `hermes_cli/security_advisories.py` | — | Security-Advisories | (nicht vorhanden) | ❌ |
| 244 | `hermes_cli/security_audit.py` | — | Security-Audit | (nicht vorhanden) | ❌ |
| 245 | `hermes_cli/security_audit_startup.py` | — | Security-Audit-Startup | (nicht vorhanden) | ❌ |

### Backup, Update, Doctor

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 246 | `hermes_cli/backup.py` | 2300+ | Backup-CLI | (nicht vorhanden) | ❌ |
| 247 | `hermes_cli/update_cmd.py` | 5854 | Update-Command | (nicht vorhanden) | ❌ |
| 248 | `hermes_cli/update_lock.py` | — | Update-Lock | (nicht vorhanden) | ❌ |
| 249 | `hermes_cli/doctor.py` | 2300+ | Doctor (Diagnostics) | `cli/commands_utility.py:doctor` 50 LOC | 🟡 reduziert |
| 250 | `hermes_cli/doctor_live.py` | — | Live-Doctor | (nicht vorhanden) | ❌ |
| 251 | `hermes_cli/dump.py` | — | Dump | (nicht vorhanden) | ❌ |
| 252 | `hermes_cli/uninstall.py` | — | Uninstall | (nicht vorhanden) | ❌ |
| 253 | `hermes_cli/dep_ensure.py` | — | Dep-Ensure | (nicht vorhanden) | ❌ |
| 254 | `hermes_cli/diagnostics_upload.py` | — | Diagnostics-Upload | (nicht vorhanden) | 🚫 |

### UI-Output, Tips, Color

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 255 | `hermes_cli/console_engine.py` | 1668 | Output-Engine (Themes, Progress, Spinner) | `ui/messages.py` 24 LOC | 🟡 sehr reduziert |
| 256 | `hermes_cli/tips.py` | 485 | Random-Tipps | (nicht vorhanden) | ❌ |
| 257 | `hermes_cli/colors.py` | 38 | Color-Theme | (nicht vorhanden) | ❌ |
| 258 | `hermes_cli/banner.py` | — | Banner-Display | (nicht vorhanden) | ❌ |
| 259 | `hermes_cli/cli_output.py` | 77 | CLI-Output-Helpers | `cli/_output.py` 52 LOC | ✅ voll portiert |
| 260 | `hermes_cli/curses_ui.py` | — | Curses-UI | (nicht vorhanden) | 🚫 (Textual-only) |
| 261 | `hermes_cli/focus_view.py` | — | Focus-View | (nicht vorhanden) | ❌ |
| 262 | `hermes_cli/skin_engine.py` | 2300+ | Skin-Engine | (nicht vorhanden) | 🚫 |
| 263 | `hermes_cli/skin_cmd.py` | — | Skin-Command | (nicht vorhanden) | 🚫 |
| 264 | `hermes_cli/skins/` | — | Skin-Templates | (nicht vorhanden) | 🚫 |
| 265 | `hermes_cli/voice.py` | — | Voice | (nicht vorhanden) | 🚫 |
| 266 | `hermes_cli/sizefmt.py` | — | Size-Format | (nicht vorhanden) | ❌ |
| 267 | `hermes_cli/timefmt.py` | — | Time-Format | (nicht vorhanden) | ❌ |
| 268 | `hermes_cli/timeouts.py` | — | Timeouts | (nicht vorhanden) | ❌ |
| 269 | `hermes_cli/clipboard.py` | 568 | Clipboard (text+images) | `ui/clipboard.py` (text-only) | 🟡 reduziert |
| 270 | `hermes_cli/heartbeat.py` | — | Heartbeat | (nicht vorhanden) | ❌ |
| 271 | `hermes_cli/input_sanitize.py` | — | Input-Sanitize | (nicht vorhanden) | ❌ |
| 272 | `hermes_cli/middleware.py` | — | Middleware | (nicht vorhanden) | ❌ |
| 273 | `hermes_cli/build_info.py` | — | Build-Info | (nicht vorhanden) | ❌ |
| 274 | `hermes_cli/lifecycle.py` | — | Lifecycle | (nicht vorhanden) | ❌ |
| 275 | `hermes_cli/managed_scope.py` | — | Managed-Scope | (nicht vorhanden) | ❌ |
| 276 | `hermes_cli/relaunch.py` | — | Relaunch | (nicht vorhanden) | ❌ |
| 277 | `hermes_cli/completion.py` | — | Completion (shell) | (nicht vorhanden) | ❌ (optional) |
| 278 | `hermes_cli/sqlite_runtime.py` | — | SQLite-Runtime | (nicht vorhanden) | ❌ |
| 279 | `hermes_cli/sqlite_safe_read.py` | — | SQLite-Safe-Read | (nicht vorhanden) | ❌ |
| 280 | `hermes_cli/sqlite_util.py` | — | SQLite-Util | (nicht vorhanden) | ❌ |
| 281 | `hermes_cli/kanban.py` | 3399 | Kanban-Logic | (nicht vorhanden) | 🚫 |
| 282 | `hermes_cli/kanban_db.py` | 11320 | Kanban-DB | (nicht vorhanden) | 🚫 |
| 283 | `hermes_cli/kanban_*.py` (5 weitere) | — | Kanban-Extensions | (nicht vorhanden) | 🚫 |
| 284 | `hermes_cli/inventory.py` | — | Inventory | (nicht vorhanden) | ❌ |
| 285 | `hermes_cli/init_command.py` | — | Init-Command | (nicht vorhanden) | ❌ |
| 286 | `hermes_cli/status.py` | — | Status-Command | `ui/commands.py:_cmd_status` 30 LOC | 🟡 reduziert |
| 287 | `hermes_cli/cmd_*` Subcommands (46 files) | — | 46 Subcommands (auth, backup, claw, config, console, cron, dashboard, debug, dump, gateway, gui, hooks, import_agent, insights, login, logout, logs, mcp, memory, model, monitoring, pause, plugins, profile, prompt_size, security, setup, skills, skin, slack, status, sync, tools, uninstall, update, verify, version, webhook, whatsapp) | 8 eac-code-Commands | 🟡 viele fehlen |

**Subtotal hermes_cli/: 116 Features katalogisiert** (von 268 Files)

---

## 3. tools/ — 135 Hermes-Files, ~280.000 LOC

### Core Tools

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 288 | `tools/registry.py` | — | Tool-Registry | `tools/base.py` 87 LOC | ✅ eigene |
| 289 | `tools/approval.py` | 4553 | Permission-Engine (full) | `permissions/policy.py` 132 LOC | 🟡 3% portiert, viel fehlt |
| 290 | `tools/terminal_tool.py` | 3800 | Terminal-Tool (PTY, env-passthrough) | `tools/builtin/bash.py` 142 LOC + `tools/builtin/process.py` 196 LOC | 🟡 reduziert |
| 291 | `tools/terminal_hints.py` | — | Terminal-Hints | (nicht vorhanden) | ❌ |
| 292 | `tools/process_registry.py` | 2300+ | Process-Registry (ProcessSession, checkpoint-recovery) | `tools/builtin/process.py` 196 LOC | 🟡 reduziert |
| 293 | `tools/daemon_pool.py` | — | Daemon-Pool | (nicht vorhanden) | ❌ |
| 294 | `tools/file_operations.py` | 2300+ | File-Operations-Backend | `tools/builtin/read.py` 55 + `write.py` 43 + `edit.py` 65 LOC | 🟡 |
| 295 | `tools/file_tools.py` | 2300+ | File-Tools-Wrapper | (s.o.) | 🟡 |
| 296 | `tools/file_state.py` | 332 | **File-State-Coordination**: Per-Path-Locks, Stale-Detection, Read-Stamps | (nicht vorhanden) | ❌ **P0 ITEM** |
| 297 | `tools/path_security.py` | — | Path-Security | `tools/safety.py` 67 LOC | 🟡 reduziert |
| 298 | `tools/url_safety.py` | — | URL-Safety | (nicht vorhanden) | ❌ |
| 299 | `tools/working_diff.py` | — | Working-Diff | (nicht vorhanden) | ❌ |
| 300 | `tools/patch_parser.py` | — | Patch-Parser | (nicht vorhanden) | ❌ |
| 301 | `tools/read_extract.py` | — | Read-Extract | (nicht vorhanden) | ❌ |
| 302 | `tools/binary_extensions.py` | — | Binary-Extensions | (nicht vorhanden) | ❌ |
| 303 | `tools/ansi_strip.py` | — | ANSI-Strip | (nicht vorhanden) | ❌ |
| 304 | `tools/lazy_deps.py` | — | Lazy-Deps | (nicht vorhanden) | ❌ |
| 305 | `tools/debug_helpers.py` | — | Debug-Helpers | (nicht vorhanden) | ❌ |
| 306 | `tools/schema_sanitizer.py` | — | Schema-Sanitizer | (nicht vorhanden) | ❌ |
| 307 | `tools/tool_search.py` | — | Tool-Search | (nicht vorhanden) | ❌ |
| 308 | `tools/tool_output_limits.py` | — | Tool-Output-Limits | `tools/executor.py:cap_output` (inline) | 🟡 |
| 309 | `tools/tool_result_storage.py` | — | Tool-Result-Storage | (nicht vorhanden) | ❌ |
| 310 | `tools/thread_context.py` | — | Thread-Context | (nicht vorhanden) | ❌ |
| 311 | `tools/managed_tool_gateway.py` | 452 | Managed-Tool-Gateway | (nicht vorhanden) | ❌ |
| 312 | `tools/self_repo_guard.py` | — | Self-Repo-Guard | (nicht vorhanden) | ❌ |
| 313 | `tools/interrupt.py` | — | Interrupt | (nicht vorhanden) | ❌ |
| 314 | `tools/slash_confirm.py` | — | Slash-Confirm | (nicht vorhanden) | ❌ |
| 315 | `tools/fuzzy_match.py` | 1108 | Fuzzy-Match (für Skill-Trigger) | (nicht vorhanden) | ❌ |
| 316 | `tools/blueprints.py` | 324 | Blueprints (Recipe-System) | (nicht vorhanden) | ❌ |
| 317 | `tools/budget_config.py` | — | Budget-Config | (nicht vorhanden) | ❌ |
| 318 | `tools/tirith_security.py` | — | Tirith-Security (3rd-party) | (nicht vorhanden) | ❌ |
| 319 | `tools/threat_patterns.py` | — | Threat-Patterns | `permissions/danger.py` 40 LOC | 🟡 reduziert |
| 320 | `tools/credential_files.py` | — | Credential-Files | (nicht vorhanden) | ❌ |
| 321 | `tools/env_passthrough.py` | — | Env-Passthrough | (nicht vorhanden) | ❌ |
| 322 | `tools/env_probe.py` | — | Env-Probe | (nicht vorhanden) | ❌ |
| 323 | `tools/hook_output_spill.py` | — | Hook-Output-Spill | (nicht vorhanden) | ❌ |
| 324 | `tools/mcp_tool.py` | — | MCP-Tool | `tools/mcp/client.py` 70 LOC | 🟡 reduziert |
| 325 | `tools/mcp_oauth.py` | — | MCP-OAuth | (nicht vorhanden) | 🚫 |
| 326 | `tools/mcp_dashboard_oauth.py` | — | MCP-Dashboard-OAuth | (nicht vorhanden) | 🚫 |
| 327 | `tools/mcp_schema_cache.py` | — | MCP-Schema-Cache | (nicht vorhanden) | ❌ |
| 328 | `tools/project_tools.py` | — | Project-Tools | (nicht vorhanden) | ❌ |
| 329 | `tools/todo_tool.py` | — | Todo-Tool | `tools/builtin/todo.py` 46 LOC | ✅ vorhanden |
| 330 | `tools/clarify_tool.py` | — | Clarify-Tool | `tools/builtin/clarify.py` 35 LOC | ✅ vorhanden |
| 331 | `tools/clarify_gateway.py` | — | Clarify-Gateway | (nicht vorhanden) | ❌ |
| 332 | `tools/close_terminal_tool.py` | — | Close-Terminal-Tool | (nicht vorhanden) | ❌ |
| 333 | `tools/code_execution_tool.py` | 2300+ | Code-Execution-Tool | `tools/builtin/execute_code.py` 100 LOC | 🟡 reduziert |
| 334 | `tools/read_terminal_tool.py` | — | Read-Terminal | (nicht vorhanden) | ❌ |
| 335 | `tools/read_window_tool.py` | — | Read-Window | (nicht vorhanden) | ❌ |
| 336 | `tools/read_preview_tool.py` | — | Read-Preview | (nicht vorhanden) | ❌ |
| 337 | `tools/open_preview_tool.py` | — | Open-Preview | (nicht vorhanden) | ❌ |
| 338 | `tools/focus_pane_tool.py` | — | Focus-Pane | (nicht vorhanden) | 🚫 (TUI) |
| 339 | `tools/kanban_tools.py` | 2476 | Kanban-Tools | (nicht vorhanden) | 🚫 |
| 340 | `tools/send_message_tool.py` | 2300+ | Send-Message | (nicht vorhanden) | 🚫 |
| 341 | `tools/react_to_message_tool.py` | — | React-to-Message | (nicht vorhanden) | 🚫 |
| 342 | `tools/session_search_tool.py` | — | Session-Search | `sessions/tool.py` 40 LOC | ✅ vorhanden |

### Browser (lokal-tauglich)

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 343 | `tools/browser_tool.py` | 2300+ | Browser-Tool | `tools/builtin/browser.py` 211 LOC | 🟡 reduced |
| 344 | `tools/browser_supervisor.py` | 2300+ | Browser-Supervisor | `tools/browser/session.py` 401 LOC | 🟡 |
| 345 | `tools/browser_cdp_tool.py` | — | Browser-CDP-Tool | (in `session.py`) | 🟡 |
| 346 | `tools/browser_dialog_tool.py` | — | Browser-Dialog-Tool | (in `actions.py`) | 🟡 |
| 347 | `tools/browser_camofox.py` | — | Browser-Camofox (Stealth) | (nicht vorhanden) | ❌ (optional) |
| 348 | `tools/browser_camofox_state.py` | — | Camofox-State | (nicht vorhanden) | ❌ (optional) |
| 349 | `tools/browser_use_cli.py` | — | Browser-Use-CLI | (nicht vorhanden) | ❌ |

### Computer-Use (lokal-tauglich via cua-driver)

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 350 | `tools/computer_use_tool.py` | 2300+ | Computer-Use-Tool | `tools/builtin/computer_use.py` 226 LOC | 🟡 reduced (cua-driver-Client) |
| 351 | `tools/computer_use/` (subdir) | — | Computer-Use-Schema, Backend | `tools/cua.py` 211 LOC + `tools/cua_install.py` 108 LOC | 🟡 reduced |

### Web-Search, Web-Extract

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 352 | `tools/web_tools.py` | 2300+ | Web-Tools (search, fetch) | `tools/builtin/web_search.py` 82 + `web_fetch.py` 70 + `web_extract.py` 74 LOC | ✅ vorhanden |

### Vision

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 353 | `tools/vision_tools.py` | 2300+ | Vision-Tools | `tools/builtin/vision.py` 74 LOC | 🟡 reduced |
| 354 | `tools/image_source.py` | — | Image-Source | (nicht vorhanden) | ❌ |

### Skills & Memory (Tools-Layer)

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 355 | `tools/skill_usage.py` | 1340 | Skill-Usage-Telemetrie + Provenance | `memory/skill_usage.py` 63 LOC | 🟡 **reduced** (kein File-Backend, nur curator-signal) |
| 356 | `tools/skill_linter.py` | 462 | Skill-Linter (12+ convention-rules) | (nicht vorhanden) | ❌ |
| 357 | `tools/skill_provenance.py` | 78 | Skill-Provenance (bundled/user/curator/pinned/hub) | (nicht vorhanden) | ❌ |
| 358 | `tools/skill_manager_tool.py` | 1810 | Skill-Manager-Tool (5+ actions) | `memory/skill_tools.py` 80 LOC | 🟡 reduced (3 actions) |
| 359 | `tools/skills_tool.py` | 2300+ | Skills-Tool | `memory/skills.py` 86 LOC | 🟡 |
| 360 | `tools/skills_hub.py` | 2300+ | Skills-Hub (Cloud) | (nicht vorhanden) | 🚫 (lokal: Mini-Hub möglich) |
| 361 | `tools/skills_sync.py` | — | Skills-Sync | (nicht vorhanden) | ❌ |
| 362 | `tools/skills_sync_client.py` | — | Skills-Sync-Client | (nicht vorhanden) | ❌ |
| 363 | `tools/skills_guard.py` | — | Skills-Guard | (nicht vorhanden) | ❌ |
| 364 | `tools/skills_ast_audit.py` | — | Skills-AST-Audit | (nicht vorhanden) | ❌ |
| 365 | `tools/memory_tool.py` | 1248 | Memory-Tool (add/replace/remove + batch) | `memory/store.py` 87 LOC | 🟡 reduced (1 JSONL) |
| 366 | `tools/hook_output_spill.py` | — | (s.o.) | — | ❌ |

### Delegation

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 367 | `tools/delegate_tool.py` | 4356 | Delegation-Tool (mit tasks-array) | `tools/builtin/delegate.py` 102 LOC | 🟡 single-task-only |
| 368 | `tools/async_delegation.py` | 1515 | Async-Delegation (background) | (nicht vorhanden) | ❌ |
| 369 | `tools/delegation_live_log.py` | 424 | Delegation-Live-Log | (nicht vorhanden) | ❌ |
| 370 | `tools/delegation_output_schema.py` | 151 | Delegation-Output-Schema | (nicht vorhanden) | ❌ |

### Cron & Background

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 371 | `tools/cronjob_tools.py` | 1619 | Cronjob-Tools (action discriminator) | `tools/builtin/cronjob.py` 186 LOC + `cron/scheduler.py` 159 + `cron/store.py` 169 LOC | 🟡 reduced (action set fehlt teilweise) |

### Checkpoints

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 372 | `tools/checkpoint_manager.py` | 1953 | Checkpoint-Manager (full) | `tools/checkpoints.py` 61 LOC | 🟡 very reduced |
| 373 | `tools/clarify_gateway.py` | — | (s.o.) | — | ❌ |

### Cloud-Bound (TTS, STT, Image, Video, Discord, etc.)

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 374 | `tools/tts_tool.py` | 17800 | TTS-Tool (streaming + normalizers) | (nicht vorhanden) | ☁️ (lokal: edge-tts möglich) |
| 375 | `tools/tts_normalize.py` | — | TTS-Normalize | (nicht vorhanden) | ☁️ |
| 376 | `tools/tts_streaming.py` | — | TTS-Streaming | (nicht vorhanden) | ☁️ |
| 377 | `tools/neutts_synth.py` | — | NeuTTS-Synth | (nicht vorhanden) | ☁️ |
| 378 | `tools/transcription_tools.py` | — | STT-Tools | (nicht vorhanden) | ☁️ |
| 379 | `tools/voice_mode.py` | — | Voice-Mode | (nicht vorhanden) | ☁️ |
| 380 | `tools/wake_word.py` | — | Wake-Word | (nicht vorhanden) | ☁️ |
| 381 | `tools/audio_container.py` | — | Audio-Container | (nicht vorhanden) | ☁️ |
| 382 | `tools/image_generation_tool.py` | 7800 | Image-Generation-Tool | (nicht vorhanden) | ☁️ |
| 383 | `tools/flux3_video_tool.py` | — | Flux3-Video | (nicht vorhanden) | ☁️ |
| 384 | `tools/feishu_doc_tool.py` | — | Feishu-Doc | (nicht vorhanden) | ☁️ |
| 385 | `tools/discord_tool.py` | — | Discord-Tool | (nicht vorhanden) | 🚫 (Gateway) |
| 386 | `tools/desktop_ui.py` | — | Desktop-UI | (nicht vorhanden) | 🚫 |
| 387 | `tools/openrouter_client.py` | — | OpenRouter-Client | (nicht vorhanden) | ☁️ |
| 388 | `tools/xai_http.py` | — | XAI-HTTP | (nicht vorhanden) | ☁️ |
| 389 | `tools/xai_video_tools.py` | — | XAI-Video | (nicht vorhanden) | ☁️ |
| 390 | `tools/yuanbao_tools.py` | — | Yuanbao-Tools | (nicht vorhanden) | ☁️ |
| 391 | `tools/microsoft_graph_*.py` | — | Microsoft-Graph | (nicht vorhanden) | ☁️ |
| 392 | `tools/homeassistant_tool.py` | 1800 | HomeAssistant | (nicht vorhanden) | ☁️ (Cloud-API) |
| 393 | `tools/spotify_tool.py` | 2300+ | Spotify | (nicht vorhanden) | ☁️ (OAuth) |
| 394 | `tools/skill_bundles.py` | — | (s.o.) | — | ❌ |

**Subtotal tools/: 107 Features katalogisiert** (von 135 Files)

---

## 4. Top-Level Hermes-Files

| # | Hermes-File | LOC | Was es tut | eac-code | Status |
|---|---|---|---|---|---|
| 395 | `cli.py` | 18915 | Top-Level-CLI-Entry | (nicht vorhanden) | ❌ |
| 396 | `run_agent.py` | 8302 | Top-Level-Run-Agent | (nicht vorhanden) | ❌ |
| 397 | `hermes_state.py` | 10979 | Global-State-Management | (nicht vorhanden) | ❌ |
| 398 | `hermes_constants.py` | — | Hermes-Constants | (nicht vorhanden) | ❌ |
| 399 | `tui_gateway/` (23 Files, 26422 LOC) | — | TUI-Gateway (TUI-Toolkit) | (nicht vorhanden) | ❌ (out-of-scope, 1-2 Wochen) |
| 400 | `acp_adapter/` (11 Files) | — | Agent-Communication-Protocol | (nicht vorhanden) | 🚫 (proprietär) |
| 401 | `cron/` (13 Files) | — | Cron-Subsystem | `cron/` 2 Files 328 LOC | 🟡 reduced |
| 402 | `gateway/` (88 Files) | — | Cross-Platform-Gateway | (nicht vorhanden) | 🚫 (Cloud) |
| 403 | `plugins/` (200 Files) | — | Plugin-Architecture (19+ categories) | `context/engine.py` 80 LOC | 🟡 mini |
| 404 | `skills/` (66 Skills) | — | User-Skills (333 .md) | (0) | ❌ |
| 405 | `optional-skills/` (81 Skills) | — | Optional-Skills (333 .md) | (0) | ❌ |
| 406 | `providers/` (2 Files) | — | Provider-Base | `config/providers.py` 145 LOC | ✅ |
| 407 | `evals/` (4 Files) | — | Evals | (nicht vorhanden) | ❌ (optional) |
| 408 | `tests/` (2860 Files) | — | Tests | 78 Files | 🟡 |
| 409 | `docs/` | — | Docs | README.md 1 File | 🟡 |
| 410 | `apps/` (Electron) | — | Desktop-UI | (nicht vorhanden) | 🚫 |
| 411 | `website/` | — | Website | (nicht vorhanden) | 🚫 |
| 412 | `locales/` | — | Locales | (nicht vorhanden) | ❌ |
| 413 | `assets/` | — | Assets | (nicht vorhanden) | ❌ |
| 414 | `web/` | — | Web | (nicht vorhanden) | 🚫 |
| 415 | `docker/` | — | Docker | (nicht vorhanden) | 🚫 |
| 416 | `nix/` | — | Nix | (nicht vorhanden) | 🚫 |
| 417 | `mcp-research-data/` | — | MCP-Research-Data | (nicht vorhanden) | ❌ |
| 418 | `datagen-config-examples/` | — | DataGen-Examples | (nicht vorhanden) | ❌ |

---

## 5. Summary-Statistik (eac-code Stand 2026-08-11)

| Status | Anzahl | Prozent |
|---|---|---|
| ✅ voll umgesetzt | **42** | 10% |
| 🟡 reduziert/teilweise | **99** | 24% |
| ❌ fehlt komplett | **141** | 34% |
| ☁️ Cloud-only (RAUS) | **36** | 9% |
| 🚫 explizit out-of-scope | **22** | 5% |
| 🖥️ OS-bound (RAUS) | **2** | 0.5% |
| Submodule/noch zu katalogisieren | **76** | 18% |
| **GESAMT** | **418** | **100%** |

**Davon lokal umsetzbar (✅ + 🟡 + ❌ ohne ☁️/🚫/🖥️):** 282 Features, davon:
- **Bereits umgesetzt oder reduziert:** 141 (✅ + 🟡)
- **Fehlt noch, lokal umsetzbar:** 141 (❌ ohne Cloud/OS/out-of-scope)
- **Davon P0-Items (Self-Improvement-kritisch):** 5-7 (Background-Review-Fork, Memory-Rewrite, File-State-Coordination, Hooks, Auxiliary-LLM)
- **Davon Toolset-Parity (lokal-tauglich):** 6 (I.1 cron, I.2 process, I.3 vision, I.4 search_files, I.6 web_extract, I.13 delegate-batch)
- **Davon Hermes-Ports (lokal, nice-to-have):** 30+ (H.1 think-scrubber ✅, H.2 workspace ✅, H.3 @-refs 🟡, H.4 timeout-floor ✅, H.5 mutation-verify ✅, H.6 friendly-verbs 🟡, H.7 jitter ✅, H.8 rate-limit ✅, H.9 AGENTS-chain ❌)

---

## 6. P0-Items die eac-code NOCH FEHLEN (lokal umsetzbar)

| # | Item | Hermes-Ref | Aufwand | Warum P0 |
|---|---|---|---|---|
| 1 | **Background-Review-Fork** | `agent/background_review.py` 1144 LOC | 4 Tage | Self-Improvement-Kern, fehlt komplett |
| 2 | **Memory-Rewrite (3 Files: MEMORY/USER/SOUL)** | `tools/memory_tool.py` 1248 + `agent/memory_manager.py` 1241 | 3 Tage | Hermes-Pattern, char-budgets, approval-gate |
| 3 | **File-State-Coordination** | `tools/file_state.py` 332 LOC | 2 Tage | Subagent-Konflikt-Schutz |
| 4 | **Hooks-System** | `agent/shell_hooks.py` 1067 LOC + `hermes_cli/hooks.py` | 2-3 Tage | User-Plan-erweiterbar (war nicht enthalten) |
| 5 | **Auxiliary-LLM für safeAuto** | `agent/auxiliary_client.py` 10298 LOC (reduziert: 200-300 LOC) | 1-2 Tage | eac-code's `smart` lügt, braucht LLM-classifier |
| 6 | **Memory-Auto-Nudge** | (in `agent/learning_graph.py` + `agent/memory_manager.py`) | 1 Tag | Erinnert alle N Turns an Memory-Write |
| 7 | **Skill-Auto-Nudge** | (in `agent/skill_preprocessing.py`) | 1 Tag | Erinnert an Skill-Discovery |
| 8 | **Skill-Linter** | `tools/skill_linter.py` 462 LOC | 1-2 Tage | Convention-Enforcement |
| 9 | **Skill-Provenance (5 sources)** | `tools/skill_provenance.py` 78 LOC | 0.5 Tag | bundled/user/curator/pinned/hub tracking |
| 10 | **Skill-Triggers + Pre-Filter** | `agent/skill_preprocessing.py` 144 LOC | 1 Tag | Frontmatter-Trigger-Match |
| 11 | **Skill-Manager erweitern (5+ actions)** | `tools/skill_manager_tool.py` 1810 LOC (eac-code: 3 actions) | 1-2 Tage | create/edit/patch/delete/write_file/remove_file |
| 12 | **Cron Full-Surface (deliver, monitor, no_agent, workdir, chaining)** | `tools/cronjob_tools.py` 1619 LOC (eac-code: reduced) | 2-3 Tage | User-Plan: I.1 |
| 13 | **Process Full-Registry (checkpoints, stdin, notifications)** | `tools/process_registry.py` 2300+ LOC (eac-code: 196) | 2-3 Tage | User-Plan: I.2 |
| 14 | **Vision + Video-Analyze (full aux-routing)** | `tools/vision_tools.py` 2300+ LOC (eac-code: 74) | 1-2 Tage | User-Plan: I.3 |
| 15 | **Delegate-Task Parallel-Batch (tasks array)** | `tools/delegate_tool.py` 4356 LOC (eac-code: single-task) | 1-2 Tage | User-Plan: I.13 |
| 16 | **Web-Extract full (trafilatura + readability)** | (in `tools/web_tools.py`) | 0.5 Tag | User-Plan: I.6 |
| 17 | **Search-Files (rg-powered)** | (eigene Hermes-Implementation) | 0.5 Tag | User-Plan: I.4 |
| 18 | **Title-Generator (two-stage)** | `agent/title_generator.py` 739 LOC | 1-2 Tage | Sessions brauchen Titel |
| 19 | **AGENTS.md Parent-Chain + .cursorrules** | `agent/prompt_builder.py` 2334 LOC (eac-code: nur EACCODE.md) | 0.5-1 Tag | H.9 Hermes-Pattern |
| 20 | **Friendly-Tool-Verbs (Reading/Writing/Running)** | `agent/display.py` 1580 LOC | 0.5 Tag | H.6 (teilweise in eac-code via `build_tool_label`) |

**P0 Total: ~30-40 Tage, 6-8 Wochen**

---

## 7. P1/P2 (lokal, nice-to-have, später)

(Siehe oben — 141 ❌-Items minus 20 P0-Items = 121 verbleibend. Davon viele klein.)

**Beispiele:**
- Backup-CLI (1-2 Tage)
- Session-Export HTML/MD (2-3 Tage)
- Session-Recap (1 Tag)
- Redact-Engine (2 Tage)
- Error-Classifier full (1-2 Tage)
- Markdown-Tables-Parser (0.5 Tag)
- Message-Sanitization (1 Tag)
- i18n-Skelett (1 Tag, optional)
- Doctor-Live (1 Tag)
- Learning-Graph-View (2 Tage)
- Outbound-Webhooks (1-2 Tage)
- PTY-Session (1-2 Tage)
- Browser-Camofox (Stealth, optional, 1-2 Tage)
- Verification-Evidence (1-2 Tage)
- Checkpoint-Manager-Full (3-4 Tage)
- Image-Source (0.5 Tag)
- Model-Catalog (1-2 Tage)
- Model-Search (0.5 Tag)
- Profile-System (1-2 Tage)
- und ~90 weitere kleinere Items

**P1+P2 Total: ~120-150 Tage, 24-30 Wochen** (zu viel für v0.2.0)

---

## 8. Out-of-Scope (klar, nicht in v0.2.0)

**Cloud-only (alle RAUS):**
- ❌ TTS (Cloud, edge-tts lokal möglich aber nicht P0)
- ❌ STT
- ❌ Image-Gen
- ❌ Video-Gen
- ❌ Browser-Camofox (Stealth)
- ❌ Discord/Slack/Telegram/WhatsApp/Feishu
- ❌ OAuth-Flows (alle)
- ❌ HomeAssistant (Cloud-API)
- ❌ Spotify (OAuth)
- ❌ Web-UI
- ❌ Desktop-UI (Electron)
- ❌ Cross-Platform-Gateway
- ❌ Dashboard (Web)
- ❌ ACP-Adapter

**OS-bound (RAUS):**
- ❌ Computer-Use-OS-Access (lokal via cua-driver aber Hermes hat eigene Implementierung)
- ❌ Windows-PTY-Bridge (eac-code ist Linux-only)
- ❌ Battery
- ❌ Wake-Word (Audio)

**User-Plan-explizit out-of-scope (🚫):**
- ❌ Kanban (1-2 Wochen Aufwand)
- ❌ MoA (Mixture-of-Agents, 1 Woche)
- ❌ Pet-Mascots
- ❌ Skins
- ❌ Background-Image-Pickers
- ❌ LSP-Integration (nice-to-have, 0.5-1 Tag)
- ❌ Skills-Hub (Cloud-Sync)
- ❌ Skills-Bundles
- ❌ Provider-Credential-Pools (Multi-Key-Rotation)
- ❌ Memory-OAuth
- ❌ Image/Video/TTS-Provider-Registries

**Zu groß für v0.2.0:**
- ❌ TUI-Gateway (26422 LOC, 1-2 Wochen)
- ❌ Web-Server (17951 LOC, 2-3 Wochen)
- ❌ Main-CLI-Monolith (12805 LOC, 1 Woche)
- ❌ Hermes-cli 268 Files (1-2 Wochen)

---

## 9. Empfohlene v0.2.0-Scope (priorisiert, ~30-40 Tage, 6-8 Wochen)

| Prio | Items | Tage | Wochen |
|---|---|---|---|
| **P0 (1-7): Self-Improvement + Reliability** | Background-Review-Fork, Memory-Rewrite, File-State-Coordination, Hooks, Auxiliary-LLM (safeAuto), Memory-Nudge, Skill-Nudge | 14-18 | 3-4 |
| **P0 (8-20): Toolset-Parity + Hermes-Ports** | Skill-Linter, Skill-Provenance, Skill-Triggers, Skill-Manager-Extend, Cron-Full, Process-Full, Vision-Full, Delegate-Batch, Web-Extract, Search-Files, Title-Generator, AGENTS-Chain, Friendly-Verbs | 16-22 | 3-4 |
| **Total P0** | | **30-40** | **6-8** |

**P1/P2 (nach v0.2.0, in 0.3.0):**
- Redact-Engine, Error-Classifier-Full, Message-Sanitization
- Profile-System, Backup-CLI, Session-Export
- i18n, Doctor-Live, Learning-Graph
- Web-Extract-Full, Image-Source, Markdown-Tables-Parser
- und ~90 weitere

---

## 10. Was im User-Plan stand und noch offen ist (zur Erinnerung)

**User-Plan §9 — 62 Tasks Phasen 0-A-H-I:**

| Phase | Items | Status |
|---|---|---|
| 0 — Hygiene (0.1 archive done, 0.2 + 0.3 pending) | 3 | ⚠️ 1/3 done |
| A — errno 9 (subprocess_compat + bash + execute_code + git + suppress + run_worker + regression) | 7 | ❓ zu prüfen |
| B — REPL UX (modal, diff, reasoning, spinner, ctx%, sys-msg, multi-line) | 7 | ❓ zu prüfen |
| C — Guardrails (ToolClass + controller + wire + stream fence) | 4 | ✅ teilweise (guardrails.py + in loop) |
| D — Slash parity (/status /diff /compress /skills + /copy /cost) | 5 | ❓ zu prüfen |
| F — Input UX (registry + suggester + palette + @ + path) | 5 | ❓ zu prüfen |
| G — High-value (/status /diff /compress /copy /cost /titles /help) | 7 | ❓ zu prüfen |
| H — Ports (H.1 think-scrubber ✅, H.2 workspace ✅, H.3 @-refs 🟡, H.4 timeout ✅, H.5 mutation-verify ✅, H.6 verbs 🟡, H.7 jitter ✅, H.8 rate-limit ✅, H.9 AGENTS-chain ❌) | 9 | ⚠️ 7/9 done |
| I — Toolset parity (I.5 ✅, I.7 ✅, Rest offen) | 16 | ⚠️ 2/16 done |

**Gesamt: 65 Tasks, ~20 done, ~45 pending.**

---

## 11. Nächste Schritte (entscheidungs-abhängig)

1. **Welche der 141 noch fehlenden lokalen Features willst du in v0.2.0?**
   - Mein Vorschlag: alle 20 P0-Items (~30-40 Tage, 6-8 Wochen)
   - Aggressiver: nur Top-5 (Background-Review, Memory-Rewrite, File-State, Hooks, safeAuto) = ~14-18 Tage, 3-4 Wochen
   - Konservativer: nur Hermes-Ports nachholen (H.9, Skill-Linter etc.) = ~10-15 Tage, 2-3 Wochen
2. **REPL-Format global refactorieren?** (kein Panel.fit, keine cyan prefixes, ⎿ tool-call mit call-expression) — 1-2 Tage
3. **`safeAuto` Umbenennung bestätigen?** (statt `smart` lügen) — 0.5 Tag
4. **Memory-Layout 3-Files wirklich umsetzen?** (MEMORY/USER/SOUL) — 3 Tage
5. **Hooks-System ja oder nein?** (User-Plan hatte es nicht, aber Hermes-Pattern) — 2-3 Tage
6. **Cron/Process/Vision-Toolset-Full ja?** (User-Plan: I.1, I.2, I.3) — 4-5 Tage

**Sag mir die Prio-Liste, ich schreib den konkreten Sprint-Plan mit TDD-Steps.**
