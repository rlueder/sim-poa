# Specific instructions — sim-poa

> This file holds ONLY the rules specific to this repository. The
> shared rules across the precisa-saude ecosystem (tone, git, hooks,
> reviews, worktrees, source verification, test coverage, code
> conventions) live in `@precisa-saude/agent-instructions`.
>
> **Read the shared base online:**
> https://github.com/Precisa-Saude/tooling/blob/main/packages/agent-instructions/AGENTS.md
>
> Claude Code loads both files (shared base + this one) via imports in
> `CLAUDE.md`. Update the base with:
> `pnpm update @precisa-saude/agent-instructions`.

## Overview

Open traffic simulation of Porto Alegre built from public data: a Python and
SUMO pipeline plus a static React site that shows observed traffic and compares
interventions against a baseline. This is a personal project that uses the
Precisa Saúde shared tooling; it is not a Precisa Saúde product.

Read `docs/development/IMPLEMENTATION_GUIDE.md` before starting any work. It
holds the verified data sources, the decisions already made, the phases and
their acceptance criteria.

## Structure

```
packages/
  ...
site/  (if applicable)
```

## Commit scopes

Valid scopes: `site`, `pipeline`, `sim`, `data`, `docs`, `ci`, `deps`.

## Worktree — specific values

Worktree flow and commands are in the shared base. The canonical config
lives in `package.json` under `"worktree"`. For quick reference:

| Field         | Value                                      |
| ------------- | ------------------------------------------ |
| Port registry | `/tmp/sim-poa-worktree-ports.json`         |
| Services      | (filled in when the repo adds dev servers) |

Launch a dev server in a feature worktree:

```bash
pnpm exec precisa-worktree dev --detach
```
