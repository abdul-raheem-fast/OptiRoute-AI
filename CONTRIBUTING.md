# Contributing to AetherFlow

Three-person team working on a shared development machine.

## Team

| Contributor | GitHub | Git email | Role |
|---|---|---|---|
| Abdul Raheem | `abdul-raheem-fast` | abdulraheemghauri@gmail.com | Project owner, core infrastructure, routing core |
| Umar Shoaib | `Umar-kh05` | umarshoaib66@gmail.com | Dataset validation, data pipeline, splits |
| Ahmad Rasheed | `ahmadrasheed10` | ahmad5116492@gmail.com | Analysis, visualization, results reporting |

## Authorship rules

- A commit is made under a contributor's identity **only** for work that
  contributor implemented, reviewed, or meaningfully modified.
- No impersonation, no fabricated history. The commit graph must reflect
  what actually happened.

## Session workflow (one shared machine)

At the **start** of each contributor's session, set the repository-local
identity (repo-local only — never change `--global`):

```powershell
# example: Umar's session
git config user.name  "Umar Shoaib"
git config user.email "umarshoaib66@gmail.com"
git config user.name; git config user.email   # verify before committing
```

Before every commit, check what is staged:

```powershell
git status --short
git diff --cached --stat
```

At the **end** of the session, restore the machine default or leave the
local identity for the next session owner to overwrite.

## Branch & merge workflow

1. Work on your feature branch: `feature/<task-id>-<short-name>`
   (task IDs tracked on the Phase 2 board).
2. Push the branch under **your own GitHub account** (each contributor
   authenticates themselves; never share tokens, passwords, or keys).
3. Open a Pull Request into `main`; paste the console output / figures the
   change produces into the PR description.
4. Another team member reviews and merges. No force-pushes to `main`.

## Data policy

`cleaned/` and all `*.csv` files are out of git (1.3 GB). Exchange datasets
out-of-band; every data-dependent script must print enough output for
reviewers to verify results without the data.
