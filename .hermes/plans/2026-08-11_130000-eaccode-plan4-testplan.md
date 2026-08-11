# eac-code PLAN-4 Testplan — REPL-Verifikation je Feature (v0.3.0)

> **Zweck:** Wie jedes Feature und jeder Command des Master-Plans (`2026-08-11_120000-eaccode-plan4-master-plan.md`)
> **selbst verifiziert** wird — primär in der eaccode-REPL (Textual), ergänzt durch CLI- und
> Agent-Run-Prüfungen, die ich (der Agent) automatisiert ausführen kann.
> **Regel:** Jede Testprozedur gilt NACH Implementierung des zugehörigen Tasks (TDD-RED war schon grün).
> **Repo-Stand:** `69de801` (Master-Plan committed).

---

## 0. Testumgebung & Grundregeln

| Element | Wert |
|---|---|
| Test-Workdir | `C:\Projekte\eaccode-testground` (git-Repo, 2–3 Mini-Dateien, ein Unterordner) |
| Test-Session | `eaccode` in Windows-cmd starten (User-Startweg); zweite Session parallel für Cross-Session-Tests |
| Test-Provider | MiniMax-M3 (Reasoning: großzügige Timeouts); Backup: opencode-go |
| Test-Hooks | `%LOCALAPPDATA%\eaccode\hooks\pre_tool_use.sh`, `post_tool_use.sh`, `session_start.sh`, `session_end.sh` (jeweils `echo marker-$event` + Exit 0) |
| Test-Skills | `%LOCALAPPDATA%\eaccode\skills\test-skill-<n>/SKILL.md` (Frontmatter title/description/triggers) |
| Sandbox | Tests nie im eaccode-Repo selbst; Datei-Writes nur im Test-Workdir |
| Protokoll | Pro Phase: Screenshot/Log der REPL; am Ende `git status` im Repo = sauber |

**Grundablauf jeder REPL-Testrunde:**
1. `export PYTHONPATH=` ignorieren (cmd); `eaccode` starten → Welcome-Log, Input-Fokus, `/help`-Liste.
2. Feature-Prozedur ausführen (Eingabe → erwartetes Ergebnis unten).
3. Bei Permission-Modal: `y` = einmal, `a` = immer, `n` = nein, `p` = Pause, Esc = deny.
4. Abschluss: `/status` (Kontext-%, Tokens), `/cost`, danach `exit`.

**Zwei Prüf-Ebenen je Task:**
- **REPL (manuell):** konkrete Eingaben + erwarteter Output — prüfbar durch mich via User-Beobachtung.
- **AUTO (ich):** `eaccode run "<prompt>" --print` / CLI-Call / Unit-Test — das führe ich selbst aus.

---

## 1. Command-Matrix — alle Slash-Commands

> Prüfprozedur: Command eingeben, erwarteten Output abgleichen. `◈` = bestehend, `✦` = geplant (Master-Plan-Task).

### 1.1 Kern-REPL

| Command | REPL-Eingabe | Erwartetes Ergebnis |
|---|---|---|
| ◈ `/help` | `/help` | Kommandoliste mit Kategorien, alle unten genannten sichtbar |
| ◈ `/status` | `/status` | Modus, Modell, Kontext-%, Tokens, Session-Info; ✦ E.20: + Version, Hooks-Status, Memory-Budget |
| ◈ `/model` | `/model` + `/model opencode-go/deepseek-v4-flash` | Liste bzw. Wechsel; Session-Neubau ohne Crash; ✦ E.7 erweitert |
| ◈ `/mode` | `/mode safeAuto` (✦ B.3), `/mode default` | Umbenennung funktioniert; unbekannter Modus → Usage-Hinweis |
| ◈ `/clear` | `/clear` | Konversation leer, System-Prompt bleibt |
| ◈ `/verbose` | `/verbose` ×2 | Tool-Darstellung wechselt (compact→full) |
| ◈ `/copy` | `/copy` + `/copy all` | Letzte Antwort bzw. alles auf Clipboard (Windows: clip.exe); ✦ H.9: + Bilder |
| ◈ `/cost` | `/cost` + `/cost reset` | Token/Cost je Session; Reset auf 0; ✦ F.11: + format_token_flow |
| ✦ `/version` | `/version` (E.18) | `eaccode <ver> (commit <sha>)` |
| ✦ `/context` | `/context` (F.18) | Grid: Tokens je Sektion (system/memory/skills/history) statt single % |
| ✦ `/tools` | `/tools search` (H.17) | Trefferliste aus Name+Description |

### 1.2 Konversation & History

| Command | REPL-Eingabe | Erwartetes Ergebnis |
|---|---|---|
| ◈ `/retry` | nach Fehler-Turn `/retry` | letzter Turn erneut; ✦ F.10: zustandsbasiert statt Regex |
| ◈ `/rollback` | `/rollback` + `/rollback 0` | Checkpoint-Liste; Restore; Datei-Inhalt wieder alt |
| ◈ `/compress` | bei großer History `/compress` + `/compress here 3` | Kompaktierung; ✦ F.16: Meldung was entfernt wurde |
| ✦ `/title` | `/title Test-Sitzung` (D.1) | Session-Titel user-gesetzt; Provenance `user`; in `/status` sichtbar |
| ✦ `/resume` | `/resume <id>` (D.7) | History geladen, Pause-Flag zurückgesetzt, Tool-Tails gestrippt (F.26) |

### 1.3 Permission & Safety

| Command | REPL-Eingabe | Erwartetes Ergebnis |
|---|---|---|
| ◈ `/pause` + `/resume` | Tool-Call anstoßen → Modal `p` → `/resume` | nach `p`: alle Tool-Calls abgelehnt mit Hint; nach `/resume`: wieder frei |
| ◈ `/allow` | `/allow bash "pytest *"` | Eintrag persistent (allowlist.json); `git -C <file> status` zeigt Datei |
| ◈ `/disallow` | `/disallow bash "pytest *"` | Eintrag entfernt; Policy fragt wieder |
| ✦ `/approve` / `/deny` | bei Edit-Diff ausstehend (B.4) | Diff annehmen/ablehnen per ID |
| ◈ `/mode plan` | dann "schreibe x" | Tool-Calls blockiert (plan), Antwort ohne Änderungen |

### 1.4 Memory & Skills

| Command | REPL-Eingabe | Erwartetes Ergebnis |
|---|---|---|
| ◈ `/memory` | `/memory` | MEMORY.md/USER.md/SOUL.md + Learned facts; leer → Hinweis |
| ◈ `/remember` | `/remember tests laufen mit pytest` | Zeile in MEMORY.md; Duplikat → kein zweiter Eintrag |
| ◈ `/forget` | `/forget pytest` | Zeile entfernt |
| ✦ `/memory trim` | `/memory trim` (A.12) | älteste Fakten weg bis Budget; Budget-Überschreitung → klare Meldung |
| ◈ `/skills` | `/skills` | Skill-Liste mit Status; ✦ A.2: + provenance-Filter |
| ✦ `/hooks` | `/hooks ls` + `/hooks run pre_tool_use` (E.12) | Dateien gelistet; manueller Run zeigt stdout |

### 1.5 System & Plugin

| Command | REPL-Eingabe | Erwartetes Ergebnis |
|---|---|---|
| ✦ `/plugins` | `/plugins ls` + `/plugins install <name>` (E.8) | Plugin-Status; Install legt Plugin an; `/help` zeigt neue Commands |
| ✦ `/debug` | `/debug stream` (J.2) | Stream-Diagnose-Output |
| ◈ `/stop` | während Agent läuft `/stop` (Ctrl+C) | Turn gecancelt, UI bleibt bedienbar |
| ◈ `exit` / Ctrl+C×2 | — | session_end-Hook läuft (Log-Datei prüfen), sauberer Exit |


---

## 2. CLI-Command-Matrix (außerhalb der REPL)

| Command | Eingabe | Erwartetes Ergebnis |
|---|---|---|
| ◈ `eaccode providers list/add/remove` | `eaccode providers list` | Provider-Tabelle; Keys nie im Output |
| ◈ `eaccode config get/set` | `eaccode config get compact_threshold` | Wert; Set persistiert in eaccode.yaml |
| ◈ `eaccode cron list/add/remove` | `eaccode cron add --name t --schedule "0 9 * * *" --prompt "hallo"` | Job angelegt; `--once` läuft einmal |
| ◈ `eaccode curator run/status` | `eaccode curator status` | Curator-Zustand; run beendet sauber |
| ◈ `eaccode queue status/pause` | `eaccode queue status` | Warteschlange; ✦ G.5: + deliver/no_agent/workdir |
| ◈ `eaccode sessions list/delete` | `eaccode sessions list` | Sessions mit Titel (✦ D.1–D.4) |
| ◈ `eaccode computer status/doctor` | `eaccode computer status` | Driver-Status (installed/missing) |
| ◈ `eaccode doctor` | `eaccode doctor` | Check-Liste ✓/✗; ✦ E.15: + hooks/memory/MCP |
| ✦ `eaccode setup` | frisch-löschen `%LOCALAPPDATA%\eaccode` → `eaccode setup` (E.2) | Provider-Prompt, Memory-Files, Hooks-Ordner, Skill-Sammlung |
| ✦ `eaccode init` | in leerem Ordner (E.19) | EACCODE.md + .eaccodeignore-Vorlage |
| ✦ `eaccode backup` | (E.13) | Zip in `~/eaccode-backups/`; Restore-Test: Zip entpacken → Dateien da |
| ✦ `eaccode update` | (E.14) | git pull + venv-Reinstall; ohne Repo: klare Meldung |
| ✦ `eaccode verify` | (F.23) | Settings-verify-Commands laufen; Ergebnis protokolliert |
| ✦ `eaccode dump` | (E.16) | YAML: Settings/Paths/Provider mit `***`-Keys |
| ✦ `eaccode model add/list/switch` | (E.7) | Provider aus providers.yaml; Wechsel wirkt in neuer Session |
| ✦ `eaccode hooks ls/run` | (E.12) | wie `/hooks` |
| ✦ `eaccode skills bundle install tdd` | (A.11) | Bundle nach `skills/` kopiert, Linter-Lauf grün |
| ✦ `eaccode sessions export <id> --format md\|html` | (D.3) | Datei mit Konversation; HTML öffnet im Browser |

**CLI-AUTO (ich):** jeder CLI-Call via `terminal`; Output-Strings mit CliRunner-Tests abgesichert.

---

## 3. Feature-Testprozeduren je Phase (A–K)

> Format je Task: **REPL** (Eingabe → erwartetes Ergebnis) + **AUTO** (was ich selbst ausführe).

### Phase A — Skill-System

| Task | REPL-Testprozedur | AUTO-Prüfung |
|---|---|---|
| A.1 Frontmatter | `skills/` legen mit kaputtem Frontmatter → Session-Start: Warnung, kein Crash; korrektes Frontmatter → Skill gelistet | `pytest tests/unit/test_skills.py` |
| A.2 Skill-Manager 5+ Actions | `/skills` zeigt Provenance; `/skills create test` (wenn Command) → SKILL.md entsteht; Prompt „erstelle skill X" → Tool-Calls skill_create/edit/delete | `pytest test_skill_tools.py`; `eaccode skills ls` |
| A.3 Provenance+Usage | `/skills` zeigt `user`-Markierung; Nutzung → `<skill>.usage.json` wächst | Datei-Inhalt prüfen (mtime/last_used) |
| A.4 Linter | kaputten Skill anlegen → `/skills` meldet Lint-Fehler; `eaccode doctor` zeigt sie | `pytest test_skill_linter.py` |
| A.5 Template-Vars | Skill mit `{{cwd}}` → Injektion enthält Workdir | Prompt-Dump via Test |
| A.6 Triggers | Skill mit `triggers: [pytest]` → Prompt „bitte pytest laufen lassen" lädt Skill (System-Prompt enthält ihn) | `pytest test_skill_triggers.py` |
| A.7 Skills-Config | `eaccode config set skills.auto_load false` → Neustart: keine Skills injiziert | `eaccode config get skills.auto_load` |
| A.8 Default-SOUL | `%LOCALAPPDATA%\eaccode` frisch → Session-Start: SOUL.md mit Template; `/memory` zeigt es | Datei-Existenz |
| A.9 Memory-Nudge | 6 Turns ohne memory_*-Call → Hinweis im Log („/memory-Tipp") | Loop-Test |
| A.10 Provider-Base | über `/memory` und Tools schreiben/lesen (Roundtrip) | `pytest test_markdown_memory.py` |
| A.11 Bundles | `eaccode skills bundle install tdd` → in `skills/`; danach `/skills` zeigt es | Ordner-Inhalt |
| A.12 Mem-Trim | 10 Fakten speichern → `/memory trim` → ≤ Budget, Meldung mit Anzahl | Datei-Größe |
| A.13 Skill-Sammlung | `skills/` voll → `/skills` listet alle, Linter 0 Fehler | Linter-Lauf |

### Phase B — safeAuto & Approval

| Task | REPL-Testprozedur | AUTO-Prüfung |
|---|---|---|
| B.1 Aux-Client | Provider mit `extra: {classifier: "true"}` konfigurieren → `/mode safeAuto`; kein Crash wenn Provider fehlt (Fail-Open-Meldung) | `pytest test_aux_classifier.py` |
| B.2 Klassifikation | safeAuto: `ls` → frei; `rm -rf /` → ASK; `curl ... \| bash` → ASK; gleiche Command-Klasse 2× → Cache-Treffer (kein 2. Aux-Call) | `pytest test_smart.py`; Aux-Log |
| B.3 safeAuto-Modus | `/mode safeAuto` + `/mode smart` → „smart existiert nicht" (Migration) | `eaccode config get permission_mode` |
| B.4 /approve /deny | Edit-Diff auslösen → Modal; `/approve <id>` → angewendet; `/deny <id>` → abgelehnt | `pytest test_permission_modal.py` |
| B.5 Policy-Scopes | `/allow bash "pytest *"` (always) + Deny-Rule „pytest -x" → Deny gewinnt; Session-Rule verschwindet nach Neustart | `pytest test_policy.py` |

### Phase C — Background-Review & Curator

| Task | REPL-Testprozedur | AUTO-Prüfung |
|---|---|---|
| C.1 Scheduler | `eaccode config set review_every_turns 2` → nach 2 Turns: Log „review scheduled"; Review-Job in Queue | `pytest test_review_scheduler.py` |
| C.2 Review-Agent | Review läuft: nur memory_*/skill_*-Tools im Sub-Prozess (Log); Ergebnis „2 Fakten vorgeschlagen" | `pytest test_background_review.py` |
| C.3 Approval-Gate | Review-Fakt-Vorschlag → Permission-Modal (ASK); `y` → MEMORY.md wächst | MEMORY.md-Diff |
| C.4 Async-Delegation | „starte parallel 2 Aufgaben im Hintergrund" → sofortige Antwort, Ergebnisse später als Meldung; Subagent-Writes werden gemeldet (file-state) | `pytest test_tools_d.py` |
| C.5 Curator-Lifecycle | `eaccode curator status` → active/paused; stale Skill → archived nach Lauf | `pytest test_curator.py` |
| C.6 Curator-Backup | vor Curator-Lauf Backup-Zip vorhanden; Restore funktioniert | Zip-Inhalt |
| C.7 Learning-Graph | `eaccode curator graph` (wenn Command) → Nodes/Edges; delete_node entfernt | `pytest test_learning_graph.py` |
| C.8 Learn-Prompt | Review schlägt Skill-Erstellung vor (Prompt enthält Kontext) | Log-Inspektion |

### Phase D — Sessions & Titel

| Task | REPL-Testprozedur | AUTO-Prüfung |
|---|---|---|
| D.1 Title-Generator | Session starten → Titel sofort deterministisch (erste Zeile); nach LLM-Upgrade besserer Titel; `/title Mein Titel` → Provenance user | `pytest test_titles.py`; Sessions-DB |
| D.2 Titel-Persistenz | `/title X`, Session beenden, `eaccode sessions list` → Titel X | CLI-Output |
| D.3 Session-Export | `eaccode sessions export <id> --format md` → Datei enthält Konversation; html → öffnet | Datei-Existenz |
| D.4 Listing+Filter | `eaccode sessions list --since 7d --query pytest` → gefilterte Liste | CLI-Output |
| D.5 Recap | `eaccode sessions recap <id>` → letzte N Nachrichten kompakt | CLI-Output |
| D.6 Metadaten | neue Session → DB-Eintrag mit workdir/provider/model | DB-Inspektion |
| D.7 Recovery | `/resume <id>` → History da, Tool-Tails gestrippt, weiterarbeiten möglich | `pytest test_sanitize.py` |
| D.8 Leases | 2 Sessions parallel → 2 Locks; eine beenden → Lock weg; verwaisten Lock manuell anlegen → Start räumt auf | `pytest test_leases.py` |

### Phase E — CLI & First-Run

| Task | REPL-Testprozedur | AUTO-Prüfung |
|---|---|---|
| E.1 Subcommands | `eaccode --help` → alle neuen Commands; jeder mit `--help` | CLI-Output |
| E.2 Setup | `%LOCALAPPDATA%\eaccode` sichern+löschen → `eaccode setup` → Provider, MEMORY.md/USER.md/SOUL.md, hooks/, skills/ da | Verzeichnis-Tree |
| E.3 Config-Sektionen | `eaccode config set hooks.enabled false` → Neustart: Hooks inaktiv; `config show` | `eaccode config get` |
| E.4 Migration | eaccode.yaml mit `permission_mode: smart` → Laden: safeAuto + Hinweis; `settings_version` gesetzt | `eaccode config get permission_mode` |
| E.5 Fallback | eaccode.yaml kaputt (YAML-Fehler) → Start mit Defaults + Warnung | Start-Log |
| E.6 Env-Loader | `.env` mit `TEST_VAR=x` → Bash-Tool `echo $TEST_VAR` → x; gesetzte Env bleibt | `eaccode run "echo $TEST_VAR"` |
| E.7 Model-Flows | `eaccode model add --provider minimax --model MiniMax-M3`; `/model` Wechsel | CLI + REPL |
| E.8 Plugins | `/plugins ls`; Test-Plugin installieren → `/help` zeigt Command; Plugin-Tool aufrufbar | `pytest test_context_engine.py` |
| E.9 Oneshot | `eaccode run "erstelle out.txt" --print` → Text + Datei; `--output-format json` → JSON | exit 0 + Datei |
| E.12 Hooks-CLI | `/hooks ls` zeigt 4 Test-Hooks; `/hooks run session_start` → stdout sichtbar | `pytest test_hooks.py` |
| E.13 Backup | `eaccode backup` → Zip; Dateien vergleichen | Zip-Listing |
| E.14 Update | `eaccode update` in Repo → pull ok; in Fremdordner → Meldung | git log |
| E.15 Doctor | `eaccode doctor` → alle Checks; absichtlich kaputten Hook → ✗ mit Tipp | CLI-Output |
| E.16 Dump | `eaccode dump` → YAML; API-Key als `***` | grep -i key |
| E.19 Init | `eaccode init` in leerem Ordner → EACCODE.md + .eaccodeignore | Datei-Existenz |
| E.20 Status | `/status` → Version, Modell, Hooks (n), Memory-Budget | REPL-Output |

### Phase F — Agent-Runtime

| Task | REPL-Testprozedur | AUTO-Prüfung |
|---|---|---|
| F.7 Finalizer | Turn mit Tool-Calls → Cost-Aggregation in `/cost` korrekt; History-Cap greift bei riesiger History | `pytest test_agent_loop.py` |
| F.9 Turn-Context | `@file:test.txt` + Text → expandiert; @folder: → Verzeichnis-Listing | `pytest test_context_refs.py` |
| F.12 Iteration-Budget | `max_tokens_per_turn` klein setzen → Abbruch mit Meldung | `pytest test_agent_loop.py` |
| F.13 Runtime-CWD | Bash-Tool `cd /tmp` dann `pwd` im nächsten Call → wieder Workdir | `eaccode run "cd ...; pwd"` |
| F.16 Compress-Feedback | `/compress` → Meldung „N Nachrichten demoted" | REPL-Output |
| F.17 @folder/@git | `@folder:src` und `@git:status` → Inhalte expandiert | `pytest test_context_refs.py` |
| F.18 Context-Grid | `/context` → 4 Zeilen mit Tokens | REPL-Output |
| F.19 Sanitization | Session mit abgebrochenem Tool-Call speichern → `/resume` → keine hängende Tool-Sequenz | `pytest test_sanitize.py` |
| F.21 Timeout-Guidance | MiniMax mit kurzem Timeout → verständliche Meldung + Tipp | Log |
| F.23 Verify | `eaccode verify` → Befehle laufen, Ergebnisdatei | exit-Codes |
| F.24 Verify-Nudge | Antwort-Ende → max 2 Nudges/Session; 3. Antwort: kein Nudge | Log |
| F.25 Redact | API-Key im Tool-Output → `/verbose full` zeigt maskiert | REPL-Output |
| F.26 Replay-Cleanup | unterbrochener Tool-Tail in JSONL → `/resume` strippt | `pytest test_sanitize.py` |
| F.27 Estop | `dat/estop` anlegen → alle Tool-Calls blockiert; löschen → frei | `eaccode run "ls"` |
| F.30 Parent-Chain | AGENTS.md im Parent → Regeln greifen; .cursorrules ebenso; nähere Datei gewinnt | `pytest test_project.py` |
| F.32 Error-Classifier | Provider 401 → AUTH-Meldung; Rate-Limit → RETRY mit Backoff | `pytest test_errors.py` |

### Phase G — Cron/Process/Vision/Web

| Task | REPL-Testprozedur | AUTO-Prüfung |
|---|---|---|
| G.1 PTY+Terminal | `eaccode run "führe interaktives python aus"` → PTY-Verhalten; env-Variable durchgereicht | `pytest test_process.py` |
| G.2 Process-Registry | Prozess starten, Session beenden, `/resume` → Prozess re-attached (Status sichtbar); stdin-Write an laufenden Prozess | `pytest test_process.py` |
| G.3 Daemon-Pool | `eaccode cron` Daemon läuft; keepalive/Heartbeat-Datei frisch | Heartbeat-mtime |
| G.4 MCP | mcp.yaml mit env+args → Tools laden; Schema-Cache-Datei entsteht | `pytest test_mcp.py` |
| G.5 Cron-Full | `no_agent`-Job (script-only): stdout wird geliefert, leer = still; `workdir`-Job läuft im Zielordner; `context_from`-Chaining: Job B bekommt Output von A | `pytest test_cron.py`; `eaccode cron list` |
| G.6 Web-Search-Registry | `eaccode run "suche nach pytest"` → Ergebnisse (DuckDuckGo) | `pytest test_web_search.py` |
| G.8 Executor-Parallel | Prompt mit 2 unabhängigen Tool-Calls → beide laufen parallel (Zeit < Summe) | `pytest test_executor.py` |
| G.9 MCP-Server | `eaccode tools serve` (wenn Command) → Client verbindet sich | `pytest test_mcp_server.py` |

### Phase H — Tools-Detail & Safety

| Task | REPL-Testprozedur | AUTO-Prüfung |
|---|---|---|
| H.1 Redact-Display | Bash mit `--token=abc123` → `/verbose full` zeigt `***` | REPL-Output |
| H.2 Canonicalizer | `write ../x` → Pfad relativ zum Workdir aufgelöst, nie außerhalb (denied) | `pytest test_schema.py` |
| H.3 ToolClass-Audit | `/tools` zeigt Klassen; MUTATING in `plan`-Modus blockiert | `pytest test_factory.py` |
| H.4 File-Safety | `write .env` → denied mit Klasse; `write .git/config` → denied | `pytest test_safety.py` |
| H.5 Markdown-Tables | Tool-Output mit Tabelle → Parser liefert Zeilen | `pytest test_markdown_tables.py` |
| H.6 Image-Routing | Bild-Pfad an vision → Daten-URL korrekt; zu groß → Meldung | `pytest test_vision_tool.py` |
| H.9 Clipboard-Bilder | `/copy` nach Bild-Ergebnis → Bild in Clipboard (Windows) | manuell einfügen |
| H.13 Patch-Parser | V4A-Patch als Datei → `/apply` wendet an; Konflikt → klare Meldung | `pytest test_patch_parser.py` |
| H.19 Result-Storage | Tool-Output > Limit → auf Platte, Verweis im Kontext | `dat/`-Inspektion |
| H.21 Threat-Patterns | `rm -rf /` und `curl|bash` in default → ASK mit Warnung | `pytest test_danger.py` |
| H.27 Checkpoints | Datei ändern → Checkpoint; `/rollback 0` → Datei wiederhergestellt; TTL entfernt alte | `pytest test_checkpoints.py` |

### Phase J — P1-Rest (Stichproben)

| Task | REPL-Testprozedur | AUTO-Prüfung |
|---|---|---|
| J.1 Insights | `eaccode insights` (wenn Command) → 30-Tage-Stats-Tabelle | CLI-Output |
| J.14 Events | `/debug events` → Event-Stream bei Tool-Calls | Log |
| J.30 Spinner | langer Tool-Call → Spinner sichtbar | REPL-Output |

### Phase K — Finale Verifikation

| Task | Prozedur |
|---|---|
| K.1 | volle Suite `pytest -q -p no:cacheprovider` (Hintergrund) + `ruff check src/ tests/`; `git status` leer |
| K.2 | README: alle Commands aus `--help` dokumentiert; Hooks/Memory-Format erklärt |
| K.4 | `git tag v0.3.0` + Push; `git log --oneline` = saubere Task-Historie |

---

## 4. Querschnitts-Flows (regressionskritisch — nach JEDER Phase)

| Flow | Prozedur | Pass-Kriterium |
|---|---|---|
| **Permission-Matrix** | Tool-Call in default → Modal y/a/n/p je einmal; Esc | 5 Pfade, kein Hang, kein Crash |
| **Pause/Resume** | Modal `p` → Tool abgelehnt → `/resume` → weiter | Hint-Text sichtbar |
| **Allowlist-Suggest** | gleichen Bash-Call 3× erlauben → Tipp „/allow…" erscheint; `/allow bash "cmd *"` → 4. Call frei | nur 1 Tipp |
| **Compaction** | 200K-Text in 2 Nachrichten → Auto-Compact nach Threshold; `/status` zeigt % wieder niedrig; System-Prompt + Skills erhalten | kein Skill-Verlust |
| **Hooks** | pre/post-Test-Hooks → post-Output im Tool-Result (`[hook output]`); session_start/end Log-Datei | 4 Events |
| **Memory-Roundtrip** | `/remember` → `/memory` → Neustart → `/memory` → `/forget` | Budget-Hinweis bei Overflow |
| **Subagent-Konflikt** | Main schreibt a.txt; Subagent schreibt a.txt → Ergebnis meldet „Subagent wrote: a.txt" | Meldung + kein Still-Crash |
| **Session-Recovery** | Session beenden → `/resume` → History + Titel + Pause-Reset | Tool-Tails gestrippt |
| **Cross-Session-Lease** | 2. Session parallel → eigener Lock; 1. beendet → Lock frei | verwaiste Locks weg |

---

## 5. Definition of Done (Testplan)

1. Jeder Task des Master-Plans hat nach Implementierung eine grüne Zeile in diesem Testplan (REPL-Prozedur durchgespielt ODER AUTO-Prüfung grün + Protokoll).
2. Querschnitts-Flows nach jeder Phase grün (max 5 min Aufwand).
3. Am Phasenende: `git status` sauber, Push, Testplan-Abschnitt aktualisiert (Checkbox/Häkchen je Task).
4. Fehlgeschlagene REPL-Prozedur → Bug-Ticket im Todo + Fix im selben Arbeitsschritt, danach Prozedur wiederholen.
