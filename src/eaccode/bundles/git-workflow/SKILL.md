---
name: git-workflow
description: Use when working with git repos — safe commit hygiene
triggers: [git, commit, branch, merge]
---

# Git Workflow

## Steps
1. `git status` + `git diff` first — know what you are about to commit.
2. Small commits per feature; messages: `feat|fix|refactor|chore(<scope>): <desc>`.
3. Verify tests + lint BEFORE committing (`pytest`, `ruff check`).
4. Guard pushes with the real exit code (pipefail), never `cmd | tail`.

## Pitfalls
- Never `--force` push to a shared branch.
- Never commit while tests are red.
- Never rewrite pushed history.
