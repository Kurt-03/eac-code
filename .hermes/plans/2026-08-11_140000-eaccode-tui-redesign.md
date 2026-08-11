# eaccode — TUI-Neubau-Plan (v0.4.0)

> **Ziel:** Klassischer Agent-CLI-Look (Claude Code, OpenCode TUI, Goose)
> statt „Kunterbunt-Boxen-TUI". Spartanisch, monospaced, **nur eine
> Farbe plus dim**, keine Boxes/Rahmen um den Log, **keine Modal-Buttons**.
> Permissions werden als Inline-Frage im Stream gestellt (Tasten y/n/a/p),
> kein zweites Fenster. Slash-Suggestion als gefilterte Liste (TUI-Overlay
> über der Input-Zeile), wie bei Hermes — nicht ein einzelner Vorschlag.
> Eingaben werden am Prompt mit echtem Cursor-Blink positioniert; keine
> Fokus-Kollisionen mehr.

---

## 0. Was weg / was kommt (Soll-Bild)

### Weg
- **Header + Footer** (`Header(show_clock=False)` / `Footer()`) — die zwei
  farbigen Boxen oben/unten weg.
- **`Screen { background: $background }`** und **`#log { background: $surface; border: none }`** — die Boxen-Hintergründe weg, Log ist flacher Volltext auf Terminal-Hintergrund.
- **`#input { border: round $accent }`** — der akzentfarbene Rahmen um die
  Input-Zeile wird zu einer einfachen horizontalen Trennlinie.
- **`#stream { color: $text-muted }`** — bleibt, aber ohne Box.
- **`PermissionModal` mit `Button` + `variant="primary/success/error/warning"`**
  — die bunten Buttons und der Modal-Screen weg. Ersetzt durch Inline-Frage.
- **Spinner mit `LoadingIndicator`** — ersetzt durch `⠋⠙⠸⠴⠦⠧` ASCII-Zeichen (Claude-Code-Stil), 100ms-Intervall.
- **Reasoning-Block mit eigener Farbe** — wird zu `[reasoning] ... [/reasoning]`
  als grau + einklappbar via `/verbose` (kein eigener Container).

### Kommt
- **Layout:** Header → flacher Log-Stream → einfache Trennlinie → Input.
- **Farbpalette:** nur `default` (durchsichtig) + `dim` (grau) + 1 Akzent
  (`cyan`, sparsam für Tool-Header `▸ read`, User-Input `›`).
- **Inline-Permission-Frage** im Log-Stream: zeigt Tool + Args (kanonisiert
  + redigiert) + 4 Tasten als ASCII-Legende. Antwort-Tasten bleiben gleich
  (y/a/n/p/Esc).
- **Slash-Overlay** (CmdP-Modal-light): bei `/` → flache Liste unter der
  Input-Zeile, gefiltert nach Tippen, sortiert alphabetisch wie Hermes,
  mit Beschreibung. `↑↓` navigieren, `Tab` ergänzt, `Enter` führt aus,
  `Esc` schließt. Keine Box, nur Zeilen mit `▸`-Marker.
- **@-Suggestion-Overlay:** wie Slash, analog.
- **Stream-Schreiber** ohne Rich-Markup-Salat: Assistant-Texte flach,
  Tool-Ergebnisse grau + eingerückt, Reasoning grau + eingerückt.
- **Tab-Spalte rechts (1/4 Breite):** Modell · Modus · Ctx% · Cost
  (immer eine Zeile, am unteren Rand). Bewusst klein.

---

## 1. Referenz-Stil (Vergleich)

| Element | Heute (v0.3.0) | Soll (v0.4.0) |
|---|---|---|
| Log-Hintergrund | `$surface` (dunkles Blau) | durchsichtig (Terminal-Default) |
| Log-Rahmen | `border: none` (eigentlich schon weg — aber Box drumherum) | nichts |
| Input-Rahmen | `border: round $accent` | nichts, nur `─` Trennlinie oben |
| Header | `Header(show_clock=False)` | weg |
| Footer | `Footer()` (Tasten-Box) | weg, durch Tastatur-Overlay nur bei Ctrl-K |
| Permission | Modal-Screen + 4 Buttons bunt | Inline-Frage im Stream |
| Spinner | `LoadingIndicator` (animiertes ASCII-Männchen) | `⠋⠙⠸⠴⠦⠧` 100ms |
| Tool-Header | farbiger Block | `▸ read path/to/file` grau |
| User-Input | kein Marker | `› <text>` mit `›` als Marker (cyan) |
| Slash-Liste | keine (Suggester = 1 Vorschlag) | Overlay unter Input, gefiltert + sortiert |
| Reasoning | eigener Container mit eigener Farbe | grau + eingerückt, mit `[reasoning]` Marker |

---

## 2. Phasen

### Phase A — Minimaler App-Layer (1–2 Tage, TDD)

**Ziel:** Klares 3-Zeilen-Layout. Keine Boxes/Rahmen/Footer/Header.
Spinner als ASCII-Spinner. Log füllt das Terminal.

**Tasks (TDD):**
- A.1 `tui/app.py::EaccodeApp.compose()` — nur `Header-Weg`, `RichLog` ohne CSS, `Static(trennlinie)`, `Input` ohne `border:round`. Header/Footer weg.
- A.2 `tui/spinner.py::Spinner` — Property `frame` rotiert durch 7 Frames in 100ms, async-update via `set_interval`.
- A.3 `tui/render.py::render_message(role, content, status=...)` — flache String-Formatierung:
    - user: `› {content}\n`
    - assistant: `{content}\n`
    - tool_call: `▸ {name} {args_summary}\n` (args_summary = `path/to/file` oder `cmd: ...`)
    - tool_result: 4-Space-Indent, grauer Text, `\n` am Ende.
    - reasoning: 4-Space-Indent + `[reasoning] ` Marker, dim.
    - error: `✗ {content}\n` in dim-red (eine Farbe).
- A.4 Status-Bar am unteren Rand (1 Zeile, immer sichtbar): Modell · Modus · Ctx% · Cost. Implementiert als `Footer`-Replacement (1/4 Spalte rechts).
- A.5 Tests: snapshot-basierte Golden-Tests für `render_message` + manueller Screenshot-Vergleich mit der Tabelle oben.

**Definition of Done:**
- `eaccode` startet ohne Header/Footer, log läuft im Volltext.
- Spinner zeigt `⠋⠙⠸⠴⠦⠧` während laufendem Agent.
- Status-Bar rechts unten zeigt Modell + Modus + Ctx% + Cost.
- `pytest tests/unit/test_tui_render.py` grün.
- Screenshot im Repo `docs/v0.4.0-tui-before-after.png`.

---

### Phase B — Permission-Inline-Frage (1 Tag)

**Ziel:** PermissionModal weg. Permission-Frage erscheint im Stream wie
eine User-Nachricht, mit klarer Anweisung und Tastatur-Legende.

**Tasks (TDD):**
- B.1 `tui/permission_inline.py::render_permission_prompt(tool, args, diff=None) -> str` — flacher String:
    ```
    ‖ Allow {tool}?
    ‖   {key1}: {value1}
    ‖   {key2}: {value2}
    ‖
    ‖   [y] allow once    [a] always allow    [n] deny    [p] pause    [Esc] deny
    ```
  (das `‖` ist nur ein optischer Marker, dim-grey; hilft beim Parsen
  der Logs.)
- B.2 `EaccodeApp._ask_permission_async` — statt `push_screen(modal)` einen
  Log-Eintrag mit `render_permission_prompt` + Listener auf y/a/n/p/Esc.
  Future wird gesetzt wie bisher.
- B.3 `permission_modal.py` löschen (oder als Re-Export-Stub behalten, falls
  Tests drauf zeigen).
- B.4 Tests: `test_permission_inline_format.py` (Goldens), `test_ask_permission_resolves` (Future-Wert nach Tastendruck).

**Definition of Done:**
- Permission-Frage erscheint im Stream, **kein Modal-Screen** mehr.
- `y/a/n/p/Esc` funktionieren wie vorher.
- `tests/unit/test_permission_inline_format.py` + `test_ask_permission.py` grün.

---

### Phase C — Slash-Overlay (1 Tag)

**Ziel:** Bei `/` flache Liste unter der Input-Zeile, gefiltert nach
Tippen, alphabetisch sortiert. Tasten: `↑↓` navigieren, `Tab` ergänzt,
`Enter` führt aus, `Esc` schließt. Analog für `@` (Context-Refs).

**Tasks (TDD):**
- C.1 `tui/overlay.py::SuggestionsOverlay(Widget)` — `Static`-Widget unter
  der Input-Zeile. Methoden: `set_items(items: list[(label, desc)])`,
  `move(delta)`, `current() -> str | None`. Kein Box-Rahmen, nur `▸` als
  Marker vor dem aktiven Eintrag, dim-grey für die anderen.
- C.2 `tui/suggester.py` neu — inspiriert vom alten `SlashCommandSuggester`,
  aber liefert **Liste** statt einzelnem Vorschlag, sortiert alphabetisch.
  Beim Tippen von `/hel` → `[("/help", "Show all commands")]`. Bei `@`
  analog.
- C.3 `EaccodeApp.on_input_changed` — bei `/`-Prefix oder `@`-Prefix
  `SuggestionsOverlay` einblenden + Items setzen. Bei leerem Input
  ausblenden.
- C.4 `EaccodeApp.on_key` — `Tab` ergänzt mit `current()`; `↑↓` navigieren;
  `Esc` blendet aus; `Enter` bei geöffnetem Overlay führt `current()` aus
  statt in die History zu senden.
- C.5 Hermes-ähnliche Sortierung: `len(name)` aufsteigend, dann
  alphabetisch (kürzere zuerst wie bei `lsc`-Output).

**Definition of Done:**
- `/` → Liste aller 30+ Commands sichtbar, sortiert.
- `/mo` → nur `/mode`, `/model`, `/monitor` (was auch immer passt).
- `↑↓` bewegt den `▸`-Marker.
- `Tab` ergänzt.
- `Enter` auf `/help` führt aus.
- `Esc` schließt.
- `@` analog.
- `tests/unit/test_tui_overlay.py` + `test_suggester_list.py` grün.

---

### Phase D — Wire-up + Verifikation (1 Tag)

**Ziel:** Alles in `__main__.py` integriert. Alte Tests grün. Neuer
End-to-End-Test auf `textual run --screenshot`.

**Tasks (TDD):**
- D.1 `eaccode/__main__.py::main()` → `EaccodeApp().run()` wie bisher.
- D.2 `permission_modal.py` löschen, Tests auf `permission_inline_format`
  migrieren.
- D.3 `repl.py` umbenennen zu `tui/app.py` (oder behalten, mit
  `# EaccodeApp lives here; old name kept for tests`). Refactor, sodass
  die Logik-Klasse `EaccodeApp` bleibt, die CSS-Boxen aber alle weg sind.
- D.4 Test: `tests/integration/test_tui_render.py::test_smoke_run`
  — startet die App via `textual run`, sendet `/help`, beendet,
  vergleicht Screenshot-Hash gegen Golden.
- D.5 Manueller End-to-End (per Hermes `computer-use` oder du selbst):
  - `eaccode` starten
  - Eingabe → Antwort
  - Permission-Frage auf Write → `y`
  - `/help` → Liste sichtbar
  - `Ctrl+C` ×2 → sauberer Exit
- D.6 Update `README.md` Features-Abschnitt: Screenshots vorher/nachher,
  Tastatur-Übersicht.

**Definition of Done:**
- `pytest` gesamt grün.
- `eaccode` startet in cmd ohne Header/Footer/Boxen.
- Permission-Frage inline.
- Slash-Overlay funktional.
- README-Screenshot vorher/nachher.

---

## 3. Was bleibt (von v0.3.0 → v0.4.0 unverändert)

- Agent-Loop, Tools, Permissions-Policy, Sessions, Memory, Skills,
  Background-Review, Curator, CLI-Subcommands — alles unverändert.
- `Textual` bleibt als Framework (nur die CSS-Boxen fliegen raus).
- Status-Bar ist neu, kommt von woanders als Footer.
- Reasoning-Anzeige bleibt, aber als Inline-Marker statt eigener Block.

---

## 4. Risiken / offene Fragen

| Risiko | Mitigation |
|---|---|
| Textual-Rendering ohne Boxen könnte auf älteren Windows-Terminals leer aussehen | Fallback: 1-Space-Inset, kein Rahmen — funktioniert überall |
| Slash-Overlay könnte Input-Fokus klauen | `on_key`-Reihenfolge: erst Overlay-Keys, dann Input |
| Manche Tasten (`Tab`, `Esc`) braucht Input weiterhin | Overlay konsumiert nur bei aktivem State, sonst durchreichen |
| Alte User-Sessions mit Modal-Habit | Migration: erste Session zeigt einmal Hinweis „v0.4.0: inline Permissions" |
| Performance bei 10k Messages im Log | `RichLog` virtualisiert; manuell testen mit synthetischer Last |

---

## 5. Schritte-Reihenfolge

1. **A.1** Layout schreiben + erstes visuelles Vergleichsfoto (`v0.4.0-tui-1.png`).
2. **A.3** `render_message` + Goldens (TDD-RED → GREEN).
3. **A.2** Spinner (TDD).
4. **B.1–B.4** Inline-Permission (TDD).
5. **C.1–C.5** Overlay + Suggester-Liste (TDD).
6. **D.1–D.6** Wire-up, Doku, Tag.

---

## 6. DoD

1. `pytest -q -p no:cacheprovider` grün.
2. `ruff check src/ tests/` sauber.
3. Screenshot vorher (v0.3.0) und nachher (v0.4.0) im Repo (`docs/`).
4. `git tag v0.4.0` + Push.
5. Manuelle End-to-End-Probe (du): starten, fragen, schreiben lassen,
   Permissions beantworten, `/help` benutzen — fühlt sich wie Claude
   Code / OpenCode TUI an.

---

**Geschätzter Aufwand:** 4–5 Tage, 22 TDD-Tasks. Keine neuen Python-Deps.
`textual` (bereits vorhanden) reicht.
