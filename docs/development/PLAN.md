# Plan

Working plan for `sim-poa`. The phases, data sources and decisions are in
[IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md); this file tracks the
current phase, its acceptance criteria with evidence, and decisions made along
the way.

## Current status

Phase 0 (project setup and data acquisition), in progress. Branch
`feat/fase-0`. Decisions recorded under "Phase 0: decisions".

## Phase 0: what was found before planning

Listing the EPTC Nextcloud shares over WebDAV on 20 November 2026 (read only):

| Share                                      | Files | Size    |
| ------------------------------------------ | ----- | ------- |
| `nPYCNzeyXSZGc2A` counts and speed surveys | 2,945 | 1.63 GB |
| `T6QGi7ikF2Hg5YD` older counts and studies | 4,548 | 9.85 GB |
| `eENg6LkJP9d5gqd` EDOM 2003 and 2023       | 503   | 0.83 GB |
| `L4aLgjfKT8bSqN4` monthly reports (PDF)    | 43    | 0.05 GB |
| `X3oWmEQo5bNP4Sr` crashes                  | 2     | 0.03 GB |
| `LJp8MNCFmZKdPpD` city layers              | 17    | 0.01 GB |
| `SS2MDqnK24RqRLm` bus lines and garages    | 4     | 3 MB    |
| `eNwpddbxXW7fN6B` speed-camera locations   | 1     | < 1 MB  |

Inside `T6QGi7ikF2Hg5YD`, the Centro Histórico mobility study is 8.6 GB
across 1,824 files: shapefile attribute tables (3.2 GB), PDF reports and
maps (1.9 GB), zip archives (1.6 GB). Much of it appears twice, once under
`2021_PLANO_CENTRO_MAPAS/` and once at the top level. It contains a bus GPS
point layer (`BusGPSCentro`, 70 MB zipped, 860 MB unpacked), which section
4.3 of the guide says does not exist publicly for the city. It covers the
Centro only.

Other findings that affect phase 0:

- The shared checks workflow (`_checks.yml`) runs `pnpm lint`, `typecheck`,
  `format:check` and `test` on a plain Ubuntu runner with Node only. It has no
  input for extra setup steps, so Python tooling called from those scripts
  must install itself.
- `package.json` `worktree.buildCommand` filters `./packages/*`, which does not
  exist here, so `precisa-worktree setup` ends with an error (the worktree is
  still created).
- `.precisa.json` has no `siteSourcePath`; CI passes `site/` only.
- `@precisa-saude/ui` 3.5.3 has peer dependencies on `@base-ui/react`,
  `recharts`, `lucide-react` and `shiki`. `@precisa-saude/themes` is CSS only
  and expects Tailwind v4.

## Phase 0: design

**Layout**

```
pipeline/            Python package (uv project), pnpm workspace member
  pyproject.toml, uv.lock, .python-version
  src/sim_poa/fetch/  download step
  tests/
site/                Vite + React + TypeScript, pnpm workspace member
data/
  sources.toml       committed: every source, its group and URL
  manifest.csv       committed: one row per downloaded file
  raw/               not committed
docs/development/
  PLAN.md, IMPLEMENTATION_GUIDE.md, DATA_INVENTORY.md
```

**Python inside the pnpm toolchain.** `pipeline/package.json` exposes `lint`
(ruff check), `format:check` (ruff format --check), `typecheck` (mypy, strict)
and `test` (pytest). Each calls a small wrapper that runs `uv` when installed
and otherwise `pipx run uv`. GitHub's Ubuntu runners ship pipx, so the shared
checks job installs uv on demand and the shared workflow stays untouched. uv
installs the pinned Python and SUMO itself. If the first pull request shows
this is slow or brittle, the alternative is a `setup_python` input in the
tooling's `_checks.yml`, which is a change to the Precisa Saúde repository.

**Download step.** One command, `pnpm data:fetch`, which runs
`uv run sim-poa fetch`.

- Sources are declared in `data/sources.toml`: WebDAV shares with include
  and exclude path patterns, CKAN datasets by id, and plain URLs (OSM extract,
  IBGE microdata).
- Files go to `data/raw/<source>/<original path>`. The data directory resolves
  to the main worktree, so worktrees share one copy instead of 3 GB each.
  `SIM_POA_DATA_DIR` overrides it.
- Requests are sequential with a one-second pause, as the guide asks.
- A file is skipped when its local size and the server's ETag or
  Last-Modified match the manifest, so a second run downloads nothing.
- `data/manifest.csv` has one row per file: source, path, URL, size, SHA-256,
  server Last-Modified, download time. Sorted, so diffs are readable.
- Files that changed on the server since the manifest are downloaded again
  and reported. `--frozen` fails instead, for reproducing an earlier run.
- Groups: `default`, and opt-in groups selected with `--group`.

**Groups** (sizes from the listing):

| Group       | Contents                                                                                                                                                                                                                                                     | Size    |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------- |
| `default`   | EDOM 2023; Centro bus GPS (`BusGPSCentro.zip`); current counts, speed, pedestrian and cyclist surveys; counts up to 2019 and developer counts; monthly reports; crashes; city layers; bus lines; CKAN GTFS, signage, bairros; OSM extract; IBGE RS microdata | ~3.0 GB |
| `centro`    | The whole Centro Histórico study                                                                                                                                                                                                                             | 8.6 GB  |
| `edom-2003` | EDOM 2003                                                                                                                                                                                                                                                    | 0.9 GB  |

**Site skeleton.** A single pt-BR page saying the project is in progress, with
the attribution block from the README, built with the shared themes and one
Vitest test so the root scripts cover the site. Maps and charts arrive in
phase 1.

**Scaffold fixes.**

- `worktree.buildCommand` changed to build `site` instead of `./packages/*`.
- `siteSourcePath: ["site/"]` declared in `.precisa.json`. Phase 1 will add
  the directory where pipeline outputs for the site live.
- `AGENTS.md` structure section and change-type table filled in.

**Inventory.** `docs/development/DATA_INVENTORY.md` records, for each item the
guide marks unverified, what it contains, from the listing plus opening a
sample of files. It also covers the bus GPS layer and the duplication inside
the Centro study.

## Phase 0: acceptance criteria

- [x] `precisa doctor` passes, and the root `lint`, `typecheck`,
      `format:check` and `test` scripts run both the pipeline and the site
      checks. Evidence (20 Nov, local): doctor reports 0 pending requirements;
      `pnpm turbo run lint typecheck test build --force` runs 7 of 7 tasks:
      ruff, mypy strict (14 files), pytest (27 passed), ESLint, tsc, Vitest
      (2 passed), Vite build. `pnpm format:check` runs Prettier and
      `ruff format --check`.
- [ ] CI is green on the phase 0 pull request. Inactive jobs listed: `review`
      (needs `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`) and
      `deploy-site` (needs Cloudflare Pages and Slack secrets; runs only on
      pushes to `main`).
- [ ] `pnpm data:fetch` on an empty data directory fetches the `default`
      group; a second run downloads nothing. Evidence: both run summaries.
- [ ] `data/manifest.csv` lists every downloaded file with URL, size, SHA-256
      and dates. Evidence: row count against files on disk.
- [ ] `uv run sumo --version` reports 1.28.0, and `netconvert` builds a
      network from a small OSM fixture in a pipeline test that also runs in
      CI. Local evidence: `Eclipse SUMO sumo 1.28.0`, built for
      `Darwin-24.6.0 arm64`; `tests/test_sumo.py` passes. Waiting on CI.
- [x] `DATA_INVENTORY.md` covers every item marked unverified in section 4 of
      the guide. Evidence: [DATA_INVENTORY.md](DATA_INVENTORY.md), from 15
      sample files plus the WebDAV listings. Mesoscopic parking support is
      deferred to phase 2, where it is first needed.

Download timing: the first run averages about 4 seconds per file (one second
of deliberate pause, the rest server time), so the `default` group of about
5,700 files takes roughly 6 to 7 hours.

Out of scope: parsing beyond what the inventory needs, and downloading the
opt-in groups (the inventory samples them instead).

## Phase 0: decisions (20 November 2026)

1. **Dependencies approved** as proposed: `eclipse-sumo==1.28.0`; `ruff`,
   `mypy` and `pytest` for development; React 19, Vite 8,
   `@vitejs/plugin-react`, Tailwind 4 with `@tailwindcss/vite`,
   `@precisa-saude/themes`, the React type packages, `jsdom` and
   `@testing-library/react` for the site. `@precisa-saude/ui` and its peer
   dependencies wait for phase 1.
2. **Download scope approved**: the `default` group, with the Centro bus GPS
   archive included in it. The rest of the Centro Histórico study and EDOM
   2003 are opt-in.
3. **`renovate.json` removed.** Dependency updates are done by hand.

## Phase 0: notes for the maintainer

- **Shared tooling bug.** `@precisa-saude/eslint-config/react` crashes under
  ESLint 10, which the scaffold installs: `eslint-plugin-react` 7.37 detects
  the React version through an API ESLint 10 removed. `sim-poa` works around
  it by declaring the React version (see `AGENTS.md`). `datasus-viz` does not
  use the React preset at all, which may be the same problem. Worth a fix in
  the tooling repository.
- **Language rule conflict, resolved in favour of the shared rules.** The
  guide said code comments and commit messages stay in English; the shared
  rules say pt-BR for both. Code comments, CLI messages and commit
  descriptions are now pt-BR, and the guide's section 3.1 says so.
- **New data worth knowing about** (details in the inventory): a classified
  cordon count around the Centro from October 2021, and two weeks of bus GPS
  in the Centro (October 2019 and July 2021, 4.6 million points).
