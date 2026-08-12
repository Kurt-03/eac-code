# v0.0.1 — Manuelle End-to-End-Probefahrt

> **Stand:** v0.0.1-redesign ready for tag v0.1.0
> **Ziel:** Der Benutzer führt die Probe selbst durch, damit Look &
> Feel mit Hermes/Claude Code übereinstimmen.

## 1. Voraussetzungen

```bash
cd "C:\Projekte\EACcode V3"
.venv/Scripts/python.exe -m pip install -e ".[all]"
.venv/Scripts/python.exe -m eaccode providers add --provider minimax --model MiniMax-M3
.venv/Scripts/python.exe -c "import eaccode; print(eaccode.__version__)"
# erwartete Ausgabe: 0.0.1
```

## 2. Smoke-Test (zwei Minuten)

```bash
.venv/Scripts/python.exe -m eaccode
```

Erwartung am Prompt:

```
─────────────────────────────────────────────────
  ❯ ask eaccode…  (/ for commands)
─────────────────────────────────────────────────
─ idle │ MiniMax-M3 │ 1.2k/200k (1%) │ $0.0000 │ C:\Projekte\EACcode V3
```

Was hier zu sehen sein muss:

1. **Welcome** in dim grau, **ohne Box** drumherum.
2. **Slash-Overlay** bei `/` (gefilterte Liste, sortiert).
3. **Komposition** mit `❯` Glyph (1 Zeichen + 1 Space).
4. **Status-Rule** mit allen Feldern: Modell, Branch, Kontext, Cost.
5. **Trennlinie** `─` zwischen Transcript und Composer.

## 3. Stream-Test (Live-Modell)

Tippe eine einfache Frage:

```
list the files in src/eaccode
```

Erwartung:

- ASCII-Spinner `⠋⠙⠸⠴⠦⠧` während der Agent arbeitet.
- **Streaming in der Transcript** (kein separates Widget, kein "schwebender" Block).
- **Kein Flackern** — der Text erscheint progressiv, ohne Full-Re-Parse.
- **Kein doppelter Render** — der finale Text steht genau einmal in der Transcript.
- **Markdown-Render** bei Code-Blöcken: ```.py\n...\n``` → grau monospaced.

## 4. Permission-Test

Tippe:

```
create a file at test_demo.txt with "hello"
```

Sobald der `write`-Tool-Call ansteht:

```
‖  Allow write?  test_demo.txt · 5 bytes
‖   path: test_demo.txt
‖   content: hello
‖
‖   [y] once    [s] session    [a] always    [n] deny    [p] pause    [Esc] deny
```

Was hier zu sehen sein muss:

1. **Header mit Tool-Subtitle** (`test_demo.txt · 5 bytes`).
2. **Argumente** aufgelistet.
3. **Legend** mit allen 5 Quick-Pick-Buchstaben.
4. **Tasten** `y` / `s` / `a` / `n` / `p` / `Esc` reagieren sofort.

Für Tools ohne Diff (`bash`, `read`) — kein Diff-Block.

Für Tools mit Diff (`write`, `edit`) — Diff erscheint mit **Farben**:
- `--- a/foo.py` / `+++ b/foo.py` → blau
- `@@ -1,1 +1,1 @@` → cyan
- `-alte Zeile` → rot
- `+neue Zeile` → grün
- ` Kontext` → dim

Test:

```
s
```

Akzeptiert + merkt sich für diese Session (nicht persistent).

```
a
```

Akzeptiert + persistiert in `~/.eaccode/allowlist.json`.

## 5. Mode-Test

```
/mode safeAuto
```

Erwartung: Status-Rule zeigt jetzt `safeAuto` als Modus.

```
/mode default
```

Erwartung: Modus zurück auf `default`.

## 6. Slash-Commands

```
/help
```

Erwartung: kategorisierte Liste (Session, Configuration, Tools & Skills, Info, Exit).

```
@fil
```

Erwartung: Overlay zeigt `@file:` (kompletiert mit Tab).

## 7. Ctrl+K

```
Strg+K
```

Erwartung: Command-Palette (filterbare Liste) öffnet sich.

## 8. Sauberes Beenden

```
exit
```

Erwartung: `Goodbye.` und sauberer Exit. Falls ein Hook konfiguriert ist, läuft `session_end`.

## 9. Verifikation der Fixes

### Bug 1 — Stream außerhalb Transcript
- Status: ✅ vor v0.0.1 war `Static #stream` zwischen Overlay und Composer (visueller Whitespace).
- Status: ✅ ab v0.0.1 lebt der Stream in der Transcript RichLog.

### Bug 2 — Streaming re-rendert komplett + schluckt Exceptions
- Status: ✅ `StreamingMarkdownRenderer` (neu seit v0.0.1) — Delta wird nur inkrementell verarbeitet.
- Verifikation: `tools/repro_stream_50_deltas.py` zeigt `max feed size: 4` (vorher: 200 = full re-parse).

### Bug 3 — Permission-Diff ohne Farben
- Status: ✅ Per-Zeile Markup: rot/grün/cyan/blau (`tui/render.py:_render_diff_line`).
- Verifikation: `tests/unit/test_tui_permission_inline.py::test_diff_uses_color_markup`.

### Bug 4 — `PermissionChoice.ALLOW_SESSION` fehlt
- Status: ✅ Quick-Pick `s` (session-only remember, kein Persist).
- Verifikation: `tests/unit/test_prompts.py::test_session_choice_*`.

### Bug 5 — Composer-Glyph 2 Spalten
- Status: ✅ Glyph 3 Spalten (1 Glyph + 2 Padding).

### Bug 6 — `PermissionModal` ist Dead Code
- Status: ✅ Entfernt; `permission_diff.py` → `diff_renderer.py` (nur die `build_unified_diff` / `diff_for_write`).
- Verifikation: `tests/unit/test_repl_no_modal.py::test_repl_permission_does_not_push_modal`.

### Bug 7 — Doppelter Render am Turn-Ende
- Status: ✅ Stream wird bei jedem Delta ins Transkript geschrieben; am Turn-Ende nur `finalize()` flushen.

## 10. Akzeptanzkriterien

Alle 7 Bugs reproduzieren nicht mehr. Visuelle Inspektion:

- [ ] Stream erscheint **in** der Transcript, nicht in einem separaten Block.
- [ ] Stream **ruckelt nicht** bei langen Antworten.
- [ ] Stream **doppelt nicht** beim Turn-Ende.
- [ ] Permission-Diff ist **farbig** (rot/grün/cyan/blau).
- [ ] Permission-Header zeigt **Tool-Subtitle**.
- [ ] Quick-Pick-Legend zeigt **alle 5 Buchstaben** (y/s/a/n/p).
- [ ] Status-Rule zeigt **Modell + Branch + Kontext + Cost**.

Wenn eines nicht erfüllt ist: Bug-Issue, Fix, Regression-Test, Commit.
