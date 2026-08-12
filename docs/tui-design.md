# v0.0.1 — TUI Design Notes

The v0.0.1 TUI is built on three beliefs:

1. **Terminals are not web pages.** The user expects raw text in
   monospace, not panels, cards, or rounded borders. Every visual
   element is one ASCII character (`─`, `▸`, `‖`, `❯`, `⚡`, `[]`).
2. **The stream is the transcript.** Hermes/Claude Code don't render
   the live answer in a separate box — they write it directly into the
   transcript. v0.0.1 follows that rule.
3. **Inline is faster than modal.** Modal screens steal focus and
   interrupt the user's flow. The permission prompt in v0.0.1 is a
   few lines in the transcript itself, with a visible keyboard
   legend. `y` / `s` / `a` / `n` / `p` resolve it without leaving the
   composer.

## Layout

```
┌─────────────────────────────────────────────────────────────┐
│ Welcome to eaccode — autonomous coding agent.                │
│ Ask for code, files, commands, or reviews.  /help for …     │
│                                                             │
│ ┌──────────────────────┐                                    │
│ │ ❯ list the files…    │  ← may be hidden by slash overlay  │
│ └──────────────────────┘                                    │
│                                                             │
│ ⠋ list_files  ← running (tool card)                        │
│ ✓ list_files  / 12 results (tool result)                    │
│ Here are the files in src/eaccode:                          │
│   - agent.py   - cli.py   - tui/                            │
│                                                             │
│ ─ idle │ MiniMax-M3 │ 1.2k/200k (1%) │ $0.0000 │ ~/repo      │
└─────────────────────────────────────────────────────────────┘
```

The 3-line structure **(transcript) → (rule) → (composer)** is all
that's wired. No header, no footer, no side panels.

## Color roles

The colors are muted — a single accent (`cyan`) plus dim text. The
transcript is on the terminal's own background; nothing overlays it.

| Role | Color | Glyph |
|---|---|---|
| User prompt | cyan | `❯` |
| Assistant (tool glyph) | magenta | `⚡` |
| Tool line | dim | `⎿` (CHEVRON) |
| Permission prompt | dim | `‖` |
| Reasoning / hint | dim italic | `🧠` |
| Error | red | `✗` |
| Diff `-` | red | — |
| Diff `+` | green | — |
| Diff `@@` | cyan bold | — |
| Diff `---` / `+++` | blue bold | — |

## Status rule

The status rule is the single line at the bottom of the screen. It
progressive-discloses on narrow widths:

```
─ idle │ MiniMax-M3 │ 1.2k/200k (1%) │ $0.0000 │ ~/repo
```

- `─` is the idle mark; `⠋..⠧` when busy.
- `idle` / `working…` is the verb.
- Model name follows.
- Git branch (only when on a repo with a branch).
- Tokens used / model max + a low-resolution bar.
- Cost (only when > 0).
- The right label is the session title or working directory.

## Streaming

The stream lives in the transcript. Each delta is fed through
`StreamingMarkdownRenderer`, which:

1. Detects a partial marker at the end of the delta (e.g. `**bol`).
2. Holds the partial marker in a buffer; emits the rest as plain text.
3. On the next delta, if the marker closes, emits the markup span;
   otherwise keeps holding.

This is O(1) per delta. The transcript grows by the size of the
emitted fragment; we never re-tokenize the accumulated text.

The verification is `tools/repro_stream_50_deltas.py`:

```
$ python tools/repro_stream_50_deltas.py
deltas: 50
max feed size: 4
transcript fragments: 47
```

The `max feed size: 4` is the delta size — not the accumulated text
size. If the renderer were re-parsing the whole text, the max feed
size would be 200.

## Permission model

The permission prompt is rendered inline:

```
‖  Allow write?  src/foo.py · 14 bytes
‖   path: src/foo.py
‖   content: hello world
‖
‖   [y] once    [s] session    [a] always    [n] deny    [p] pause    [Esc] deny
```

The user types one letter. The `PermissionAwareInput` subclass
intercepts the key without inserting it as text — that's the Textual
8 dance that prevents the keys from being eaten (v0.4.0.x bug).

| Key | Meaning |
|---|---|
| `y` | Grant this call only. |
| `s` | Grant + remember for this session (no `allowlist.json` write). |
| `a` | Grant + remember forever (persistent). |
| `n` | Refuse. |
| `p` | Pause the session — no further tool calls until `/resume`. |
| `Esc` | Refuse (alias for `n`). |

## Why this matters

The v0.0.1 TUI is **fast** (no full re-parse), **clean** (no boxes,
no gradients), and **predictable** (a single Tool class, a single
prompt flow, a single renderer). The user's complaint about "es
sieht nicht aus wie Hermes" was a real gap: v0.0.1 closes it.
