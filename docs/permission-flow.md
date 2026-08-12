# v0.0.1 — Permission Flow

The v0.0.1 permission model has 5 user choices, modeled on Hermes /
Claude Code:

| Choice | Key | Effect |
|---|---|---|
| Allow once | `y` | Grant the current call. No state change. |
| Allow session | `s` | Grant + remember in `session_rules`. No persist. |
| Allow always | `a` | Grant + persist to `allowlist.json`. |
| Deny | `n` | Refuse the current call. |
| Pause | `p` | Refuse + set the session `PauseFlag`. |
| (Esc) | `Esc` | Alias for `n`. |

## `session_rules` vs `allowlist.json`

There are two storage mechanisms and they differ in lifetime:

- **`session_rules`** — in-memory list of `Rule` objects. Lives only
  for the current session. Lost on restart. Added by `s` (and `a`).
- **`allowlist.json`** — persistent file at
  `~/.eaccode/allowlist.json`. Survives restarts. Added only by `a`.

The logic is in `eaccode/permissions/prompts.py`:

```python
if choice == PermissionChoice.ALLOW_ALWAYS and session_rules is not None:
    _remember_rule(session_rules, tool, arguments)
# ALLOW_SESSION is granted (returns True) but adds nothing to the
# store — the caller's policy layer might still decide to remember
# in session_rules if it wants to.
```

The policy layer (`policy.py`) uses both stores: `allowlist.json`
via `AllowlistStore` and `session_rules` via `RuleSet`. The chain
order is allowlist → session → ASK → DENY.

## Inline prompt format

The prompt is rendered in the transcript by
`render_permission_prompt` (`tui/render.py`). It has:

1. A **bold header** with the tool name and a tool-specific subtitle.
2. The **arguments** listed below.
3. If the tool is `write` or `edit`, the **unified diff** of the
   proposed change (colored).
4. The **keyboard legend** at the bottom.

```
‖  Allow write?  src/foo.py · 14 bytes
‖   path: src/foo.py
‖   content: hello world
‖
‖   [y] once    [s] session    [a] always    [n] deny    [p] pause    [Esc] deny
```

## Color rules

The diff is colored per-line, not globally:

| Pattern | Color |
|---|---|
| `--- a/foo.py` | bold blue |
| `+++ b/foo.py` | bold blue |
| `@@ -1,1 +1,1 @@` | bold cyan |
| `-old line` | red |
| `+new line` | green |
| ` context` | dim |

The arguments and the legend are escaped (no Rich markup) so that
literal `[y]` / `[a]` / `[x for x in y]` don't get parsed as styles
(v0.5.3 bug).

## Allowlist suggestion

After 3 calls to the same tool + pattern are approved, the REPL
prints a hint:

```
[ i ] Approved bash 3x — save it permanently with /allow bash 'git *'
```

The user types `/allow bash "git *"` (or `git *`) to add the rule
to `allowlist.json`. This is implemented in
`EaccodeApp._on_approval_resolved`.

## Why `s` is its own quick-pick

Hermes and Claude Code both distinguish "session" and "always". The
reason is real workflow:

- **Always** (`a`) means "I will run this command forever in this
  project" — it's a high-trust decision. Users rarely want that
  even for `git status`.
- **Session** (`s`) means "right now I'm running these — don't ask
  me again this turn" — it's a low-risk, low-friction decision.

The `s` choice exists because users hit the same prompt multiple times
in a session and the modal friction grows. By offering both, the
user can choose the right level of trust at the moment, rather than
being forced to either allow-forever or deny-and-retry.

## Timeout

The REPL modal times out after **600 seconds** (10 minutes) — see
`MODAL_TIMEOUT_SECONDS` in `permissions/prompts.py`. The default
is DENY (fail closed). The user can extend the deadline by
interacting with any other UI element first.
