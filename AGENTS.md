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
pipeline/            Python package `sim_poa` (uv project, Python 3.13), also a
                     pnpm workspace member so turbo runs its checks
  scripts/uv.sh      runs uv, or `pipx run uv` where uv is missing (CI)
  src/sim_poa/fetch/ download step for data/sources.toml
  tests/             pytest; `sumo` marker for tests that run SUMO binaries
site/                Vite + React 19 + Tailwind 4 static site (pt-BR)
data/
  sources.toml       every raw data source, its group and URL
  manifest.csv       one row per downloaded file (committed)
  raw/               downloads, not committed; shared by all worktrees
docs/development/    IMPLEMENTATION_GUIDE.md, PLAN.md, DATA_INVENTORY.md
```

## Commands

| Command                            | What it does                                                                                 |
| ---------------------------------- | -------------------------------------------------------------------------------------------- |
| `pnpm lint` / `typecheck` / `test` | Run ruff, mypy (strict) and pytest for the pipeline, and ESLint, tsc and Vitest for the site |
| `pnpm format:check`                | Prettier for the repo plus `ruff format --check`                                             |
| `pnpm data:fetch`                  | Download the `default` group into `data/raw/`                                                |
| `pnpm data:fetch --group centro`   | Download an opt-in group (`centro`, `edom-2003`)                                             |
| `pnpm data:fetch --frozen`         | Reproduce the manifest exactly; fail if a file changed                                       |
| `pnpm --filter @sim-poa/site dev`  | Run the site locally                                                                         |

Raw data lives in the main worktree's `data/raw/` so worktrees share one copy.
Set `SIM_POA_DATA_DIR` to put it elsewhere.

## Where changes go

| Change                        | Update                                                           |
| ----------------------------- | ---------------------------------------------------------------- |
| New or changed data source    | `data/sources.toml`, guide section 4, `DATA_INVENTORY.md` if new |
| Python dependency             | `pipeline/pyproject.toml` and `pipeline/uv.lock` (ask first)     |
| Site dependency               | `site/package.json` and `pnpm-lock.yaml` (ask first)             |
| Phase progress or decision    | `docs/development/PLAN.md`                                       |
| Assumption forced by the data | `docs/ASSUMPTIONS.md`                                            |

## Local deviations from the shared tooling

- `eslint.config.js` pins `settings.react.version` for `site/`, because
  `eslint-plugin-react` 7.37 crashes under ESLint 10 while detecting the React
  version. Remove the override once `@precisa-saude/eslint-config` fixes it.
- `site/vitest.config.ts` is separate from `vite.config.ts`: the root Vitest 2
  bundles Vite 5 and cannot load the Vite 8 plugins.
- No `renovate.json`: dependency updates are done by hand.
- Do not use Precisa Saúde's logo, brand composition or licensed fonts. This
  is a personal project, not a Precisa Saúde product.

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
