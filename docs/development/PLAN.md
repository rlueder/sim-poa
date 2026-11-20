# Plan

Working plan for `sim-poa`. The phases, data sources and decisions are in
[IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md); this file tracks the
current phase, its acceptance criteria with evidence, and decisions made along
the way.

## Current status

- **Phase 0** merged in PR #1 on 20 November 2026; the manifest of the full
  download is on branch `chore/manifesto-dados`.
- **Phase 1** (atlas) merged in PR #2 on 20 November 2026 with only the EDOM
  data; the full build of every module is on the same branch. All acceptance
  criteria of both phases are met.

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
- [x] CI is green on the phase 0 pull request (#1, merged). Inactive jobs listed: `review`
      (needs `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`) and
      `deploy-site` (needs Cloudflare Pages and Slack secrets; runs only on
      pushes to `main`).
- [x] `pnpm data:fetch` on an empty data directory fetches the `default`
      group; a second run downloads nothing. Evidence (20 Nov): the full run
      downloaded 5,292 files (2,876.8 MB), found 265 unchanged from an earlier
      partial run and registered 17 already present, with no failures; the
      second run downloaded 0 and found 5,574 unchanged.
- [x] `data/manifest.csv` lists every downloaded file with URL, size, SHA-256
      and dates. Evidence: 5,574 rows, every listed file is on disk, and the
      row count per source equals the file count in each `data/raw/` folder.
      The Geofabrik extract of phase 2 is on disk but belongs to PR #4's
      source list; whichever of the two PRs merges second updates the
      manifest.
- [x] `uv run sumo --version` reports 1.28.0, and `netconvert` builds a
      network from a small OSM fixture in a pipeline test that also runs in
      CI. Local evidence: `Eclipse SUMO sumo 1.28.0`, built for
      `Darwin-24.6.0 arm64`; `tests/test_sumo.py` passes, in CI as well.
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

## Phase 1: what was found before planning

**EDOM 2023 reproduces.** A throwaway read of the trips sheet (26,304 rows)
expands to 1,732,137 weekday trips with `FE_IDADE_AJ`, against 1,732,140 in
the report. Mode shares by `MODO_PRINC` match the report's to the decimal:
car driver 25.1%, walk 24.0%, bus 21.4%, car passenger 12.9%, ride-hailing
9.6%, school transport 2.0%, motorcycle 1.6%, bicycle 1.4%.

Things the parser must handle:

- **Codes stored as dates.** Excel formats some numeric columns as dates, so
  mode code `10` reads as `1900-01-10` and travel time `45` as `1900-02-14`.
  Serial numbers below 60 need Excel's 1900 epoch rule (day 1 is 1900-01-01);
  converting with the usual 1899-12-30 epoch shifts every code by one, which
  is how the first attempt mislabelled every mode.
- **Peak hour has the report's own definition.** Counting trips that start
  between 07:00 and 08:00 gives 209,037, while the report gives 164,368 for
  its morning peak hour. The sheet carries an `HPM` flag and `FE_HPM` factor
  for that peak; the parser reconciles with those instead of inventing a
  window.
- `HOR_O` and `HOR_D` are proper times; coordinates are rounded to three
  decimals; a dictionary sheet names every column.

**Count templates** are described in [DATA_INVENTORY.md](DATA_INVENTORY.md):
the EPTC 15-minute template (1998 to now, classes `VL`, `VM`, `VP`, `MT`), the
developer template (classes `CA`, `LT`, `O`, `CM`, from 06:00), a consultancy
layout, the Centro study variant (`CA`, `TX`, `LT`, `O`, `CM`), and hourly
pedestrian and cyclist templates.

**Locating count sites.** Only some workbooks have a `GEO` sheet with
coordinates. The rest name the intersection in the filename and header
(`Azenha x Botafogo`). These can be placed offline by intersecting the two
named streets in the EPTC centreline layer, after normalising abbreviations
(`Av.`, `R.`, `Gen.`, missing accents).

**Basemap.** [OpenFreeMap](https://openfreemap.org/) serves OpenStreetMap
vector tiles with no key, registration or request limit, and its styles work
with MapLibre. Attribution: OpenFreeMap, © OpenMapTiles, data from
OpenStreetMap.

## Phase 1: design

**Pipeline** (`pipeline/src/sim_poa/atlas/`). One command, `pnpm atlas:build`,
reads `data/raw/` and writes two kinds of output:

- `data/derived/` (not committed, rebuilt on demand): tidy Parquet and
  GeoParquet tables at full resolution, such as every count interval and
  every survey trip.
- `site/public/data/` (committed): compact files the site loads, aggregated
  and simplified, with a size budget of 10 MB in total. Committing them means
  the site builds in CI without the 3 GB download.

Modules:

| Module    | Input                                     | Site output                                                                                                            |
| --------- | ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `edom`    | EDOM 2023 workbook and zones              | Trips by zone and hour, mode share by zone, desire lines between zones above a threshold, departure profile by purpose |
| `counts`  | Vehicle, pedestrian and cyclist workbooks | Sites with their 15-minute or hourly profiles; a parse report listing every file                                       |
| `speeds`  | Spot-speed workbooks                      | Sites with median and 85th-percentile speed against the posted limit                                                   |
| `geocode` | `GEO` sheets, EPTC centrelines            | Location and method for every count and speed site, or the reason it failed                                            |
| `cameras` | Speed-camera points and the yearly PDFs   | Typical-day flow by site and month                                                                                     |
| `transit` | GTFS                                      | Bus trips per hour by route and by street segment                                                                      |
| `bus_gps` | Centro bus GPS, October 2019 week         | Bus speed by street segment and hour in the Centro                                                                     |
| `supply`  | Área Azul, signals, bus corridors         | Simplified layers                                                                                                      |
| `crashes` | Crash records 2021 onward                 | Counts on a 250 m grid, by year and severity                                                                           |

The bus GPS view is not in the guide's minimum list; it is the only observed
speed by time of day available and is cheap to add. The July 2021 week stays
out of the atlas because it falls in the pandemic window.

**Site.** Views for trips, counts, speeds, buses, supply and crashes, each a
MapLibre map with an OpenFreeMap basemap plus charts, in pt-BR. Every view
shows its sources and the EPTC attribution. Survey views show zones only.

**Focus corridors** (decision 4). The pipeline tags count and speed sites
within 150 m of Av. Carlos Gomes, Av. Protásio Alves, Av. Ipiranga and Av.
Nilo Peçanha / Av. Nilópolis, and the site can filter to them.

## Phase 1: acceptance criteria

- [x] EDOM expansion reproduces the report: total within 1% of 1,732,140;
      each of the eight main mode shares within 1 percentage point; morning
      peak 07:00 to 08:00 using the report's definition, with its total
      within 1% of 164,368; evening peak 17:30 to 18:30 by the report's method,
      with the method written down. Evidence: 12 of 12 checks pass
      (`site/public/data/edom/validation.json`, shown in the site). Total
      1,732,137; shares exact to 0.1 point; motorised morning peak 07:00 with
      164,383; evening peak 17:30. Change to the criterion: the workbook has no
      `HPM` columns, so the method was recovered by testing (arrival time,
      one-hour windows in 15-minute steps) and is written down in
      `docs/ASSUMPTIONS.md` and `DATA_INVENTORY.md`.
- [x] The count parser writes a report listing every workbook found, read or
      not, with the reason for each unread one. Each template has a test with
      a small fixture. Evidence: `data/reports/counts.csv` lists 3,231
      workbooks: 2,704 read, 378 in an unsupported layout, 148 that fail to
      open and 1 empty, every unread one with its reason.
- [x] Every count and speed site has a location and the method used, or is
      listed as unresolved with the reason. The site has a spot-check map
      coloured by method. Evidence: 2,402 of 2,704 counts located (89%) and
      1,250 of 1,905 speed surveys (66%); every unlocated one has a reason in
      the report. The speed share is lower than the 91% seen on the partial
      download: 590 surveys name a single street with no crossing or number.
      Follow-up for phase 4: street names that are dates ("24 de Outubro")
      do not match the centreline names.
- [x] Sites near each focus corridor are listed in
      `data/reports/focus_corridors.csv`: Ipiranga 193, Protásio Alves 145,
      Nilo Peçanha / Nilópolis 70, Carlos Gomes 46.
- [x] `pnpm atlas:build` regenerates `site/public/data/` from `data/raw/`;
      the site builds to static files, runs locally with one command and loads
      its data without a backend; `site/public/data/` stays under 10 MB.
      Evidence: the full build writes 4.62 MB; `vite build` succeeds.
- [x] Every view names its sources with attribution to EPTC where its data is
      used; no file in the repository or the built site holds survey records
      below zone level. Evidence: every view ends with `SourceNote`, checked
      in the view tests; the EDOM outputs are zone summaries and zone pairs
      with at least 5 records (`edom/*.json`).
- [x] CI is green on the phase 1 pull request (#2, merged).

Out of scope: any simulation, the SUMO network, and calibration.

## Phase 1: decisions (20 November 2026)

1. **Python dependencies approved and installed**: `pandas`, `pyarrow`,
   `geopandas`, `openpyxl`, `xlrd`, `pdfplumber`.
2. **Site dependencies approved and installed**: `maplibre-gl`,
   `@precisa-saude/ui`, `@base-ui/react`, `recharts`.
3. **Generated site data is committed** (`site/public/data/`, under 10 MB).
   The maintainer asked whether the datasus-viz approach (Parquet on S3,
   queried in the browser with DuckDB-WASM) fits better. Not for phase 1:
   the atlas needs summaries and per-site profiles that fit in a few MB of
   static files, while DuckDB-WASM alone adds several MB of WebAssembly to
   download. It starts to pay off when a view needs ad hoc queries over
   detail too large to commit, such as every 15-minute count interval, the
   full bus GPS, or per-edge, per-hour results across scenarios and seeds in
   phases 5 and 6. To keep that path open, `data/derived/` is written as
   Parquet from the start. The storage would be Cloudflare R2 next to the
   Pages site rather than the Precisa Saúde S3 bucket, which belongs to the
   company.
4. **Publish the site** on Cloudflare Pages through the existing
   `deploy-site` job. It needs the maintainer to create the Pages project and
   add `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` as repository
   secrets. Without `SLACK_DEPLOY_WEBHOOK_URL`, the job's Slack step will fail
   after each deploy even when the deploy itself succeeds.
5. **Approved on 20 November 2026**: the phase 1 commits; `lucide-react`, so
   the site uses the shared navigation components instead of a local copy;
   `pandas-stubs` as a development dependency, so mypy checks pandas code.
   The maintainer creates the Cloudflare Pages project and the repository
   secrets for publishing.
