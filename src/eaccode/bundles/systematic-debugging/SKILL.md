---
name: systematic-debugging
description: Use when a bug appears — 4-phase root-cause debugging
triggers: [debug, bug, failing, traceback, error]
---

# Systematic Debugging

## Steps
1. **Reproduce** — get a minimal, deterministic repro.
2. **Read the code path** — trace the actual code, do not guess.
3. **Form one hypothesis** — verify it with a targeted probe.
4. **Fix the root cause** — then fix the class of bug, not just the site.

## Commands
```bash
pytest tests/unit/test_<module>.py::<test> -q -p no:cacheprovider -x
```

## Pitfalls
- Blame the code, not the tooling — check the evidence first.
- Fixes without a failing test are guesses.
