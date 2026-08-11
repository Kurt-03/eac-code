---
name: tdd
description: Use when writing code — RED-GREEN-REFACTOR workflow
triggers: [tdd, test-first, red-green]
---

# Test-Driven Development

Write a failing test first, make it pass, then refactor.

## Steps
1. **RED** — write the failing test for the next behavior.
2. **GREEN** — implement the minimum code to pass it.
3. **REFACTOR** — clean up while keeping the suite green.
4. Repeat; run the full suite after each cycle.

## Commands
```bash
pytest tests/unit/test_<module>.py -q -p no:cacheprovider
```

## Pitfalls
- Never commit while the suite is red.
- A test that does not fail first tests nothing.
- Keep tests fast; avoid network and sleeps.
