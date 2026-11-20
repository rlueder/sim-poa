# Plan

Working plan for `sim-poa`. The phases, data sources and decisions are in
[IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md); this file tracks the
current phase, its acceptance criteria with evidence, and decisions made along
the way.

## Current status

- **Phase 0** and **phase 1** are complete: PRs #1 and #2, then the full
  download manifest and the full atlas build in PR #5 (20 November 2026).
- **Phase 2** (road network), PR #4 on branch `feat/fase-2-rede`. Every check
  passes, buses from GTFS included.

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

## Phase 2: what was found before planning

- **The OSM extract chosen in phase 0 does not cover the city.** The BBBike
  "PortoAlegre" extract is a fixed box, longitude −51.28 to −51.05 and latitude
  −30.14 to −29.94. The municipality runs from −51.303 to −51.012 and from
  −30.269 to −29.932 (from the EDOM zone polygons). Sixteen of the 106 city
  zones extend outside the box, with 253,348 residents in 2022: the whole south
  (Restinga, Belém Novo, Lami, Ponta Grossa) and the eastern edge.
- **`netconvert` does not read `.pbf`.** It takes OSM XML (`--osm-files`), so
  the extract must be converted and clipped first.
- **Default speed limits.** Where OSM has no `maxspeed`, the typemap needs the
  urban defaults of the Brazilian traffic code (art. 61). From memory they are
  80, 60, 40 and 30 km/h by road class; `planalto.gov.br` did not respond on
  20 November, so they are **unverified** until the text is read.

## Phase 2: design

**Network source.** Geofabrik's southern Brazil extract, as a dated snapshot:
`https://download.geofabrik.de/south-america/brazil/sul/sul-261119.osm.pbf`
(431,147,733 bytes, 19 November 2026). Geofabrik lists dated files next to
`sul-latest`; how long it keeps them is not stated, so the manifest hash is
the real pin and the source can move to a newer date deliberately. The extract
is clipped to the municipal boundary plus a 2 km buffer, so each entry road
reaches past the boundary. Clipping and conversion to OSM XML use `pyosmium`,
keeping only roads, the ways turn restrictions refer to, signals and transit
relations.

**Build.** `pnpm network:build` runs, in order:

1. Clip and convert the OSM extract (`pyosmium`).
2. `netconvert` with the options in guide section 4.5 plus `--osm.turn-lanes`,
   `--output.street-names`, `--osm.sidewalks false`, and a Brazilian typemap:
   road classes from SUMO's urban typemap, default speeds from the traffic code
   once verified, lane counts from OSM where tagged.
3. External gates: the edges where motorway, trunk, primary and secondary
   roads cross the municipal boundary, named and listed.
4. Signals: compare the network's traffic lights with the 1,555-record city
   inventory by distance (match within 30 m), then correct the network with
   `--tls.set` and `--tls.unset` where the inventory is clearly right.
5. Buses: GTFS stops and routes with `gtfs2pt.py` for the phase 1 Wednesday.
6. Checks: zone-to-zone reachability for the 106 city zones, free-flow travel
   times on about ten named corridors (the four focus corridors among them),
   and a mesoscopic smoke test with random trips, counting teleports.

Outputs go to `data/derived/network/` (not committed: the `.net.xml` is tens of
MB) and a compact summary to the site: a new "Rede" tab with roads coloured by
lanes or speed, signals coloured by match status, and the corridor travel
times.

**Focus corridors** (decision 4): lanes, turn lanes and signals on Av. Carlos
Gomes, Av. Protásio Alves, Av. Ipiranga and Av. Nilo Peçanha / Av. Nilópolis
are checked against OSM, the EPTC signal inventory and the bus corridor layer,
and listed in a table for the maintainer to review.

## Phase 2: acceptance criteria

Evidence comes from `pnpm network:build` on 20 November 2026, recorded in
`data/reports/network.json`.

- [x] The network covers the whole municipality. **Reworded, approved (decision 4):**
      the original test (every zone centroid within 300 m of an edge) fails for
      ten large southern zones whose representative point lies 301 to 592 m from
      the nearest road, although each contains between 117 and 1,770 drivable
      edges. The check now asks that every city zone contain drivable edges:
      all 106 do, the fewest has 60.
- [x] `netconvert` warnings reviewed; the 2,108 are grouped below, each group
      with a reason.
- [x] Every city zone can reach every other by car: 11,130 of 11,130 pairs
      routed by `duarouter`.
- [x] Network signals compared with the 1,555 inventory records and mapped in
      the "Rede" tab: 1,255 matched before corrections and 1,477 after; 78
      left without a signal, 65 of them mid-block pedestrian signals.
- [x] Free-flow travel times on ten corridors, both directions, in the "Rede"
      tab, for the maintainer to judge.
- [x] Mesoscopic smoke test: 3,600 random trips in one hour, all arrived, 0
      teleports.
- [x] The default speeds cite art. 61 of the traffic code, read on
      planalto.gov.br on 20 November 2026 (`network/speeds.py`).
- [ ] CI is green. The build ran twice from `data/raw/` with the same results.

Step 5 of the design, buses from GTFS, is done (see "Buses" below); `rtree`
was approved as decision 3 for it.

Out of scope: lane-level corrections outside the focus corridors, and demand
(phase 3).

## Phase 2: results

**Build.** Clipping the 431 MB extract takes about a minute and 3.6 GB of
memory: 24,296 ways, 1,226 turn restrictions, 2,016 OSM signal nodes. The
network has 62,556 drivable edges (6,447 km), 26,127 junctions and 1,625
signal controllers. The whole build, checks included, takes about six minutes.

**Changes to the design found while building.**

- `--tls.discard-simple` is not used. It drops signals that are not at
  junctions, and half of the city inventory (797 records, type `EXCLUSIVO`) are
  mid-block pedestrian signals. Without it the inventory match rose from 683 to
  1,255 before any correction.
- The municipal boundary comes from the unsimplified zones: the simplified
  ones left gaps that made Av. Ipiranga a city entry.
- Corridor times follow the avenue (other roads cost 20 times their time).
  Unconstrained, the fastest route left Assis Brasil, Ipiranga and Nilo
  Peçanha for parallel roads, down to 6% of the length on the avenue.
- Signal corrections: 202 junctions switched on where the inventory has a
  signal and the network did not, 19 switched off inside the city where no
  record is within 80 m. Thresholds are in `docs/ASSUMPTIONS.md`.
- The site map merges the two directions of each road and joins runs with the
  same attributes, 1.1 MB instead of 4.5 MB.

**Gates.** 36 edges cross the boundary on motorway, trunk, primary and
secondary roads (18 in, 18 out): the Freeway, Ponte Lupicínio Rodrigues,
Ponte Luís Carlos Prestes, Ponte do Rio Jacuí, Baltazar de Oliveira Garcia, Bento Gonçalves, Estrada Caminho do Meio, Estrada
São Caetano and others, listed in the report. Protásio Alves and Assis Brasil
are not among them; whether they cross the boundary as a lower OSM class or
end before it is to check in phase 3, when external demand needs them.

**Corridors.** Free-flow averages of 46 to 60 km/h; most roads have no
`maxspeed` and take the 60 km/h arterial default. Edvaldo Pereira Paiva comes
out at 1.7 km because OSM gives that name to only 1.7 km. Ipiranga "volta"
keeps 82% of its length on the avenue and Baltazar "ida" 80%; where those
routes leave the avenue is not checked yet.

**Buses.** GTFS for Wednesday 29 October 2025, the day the atlas uses, with
the blank stop times filled in by stop order. `gtfs2pt.py` turned 12,527 of
the 12,565 trips into vehicles on 851 line variants and placed 5,142 of the
5,234 stops; 317 stop visits (out of 768,152) were left off routes they did
not fit. Matching takes about 50 minutes, so the result is cached by the
content of the network and of the day's GTFS. In 738 places a route loops
around to reach the next stop (median detour 8.5 times the straight line),
probably a stop on the wrong side of a divided road; to look at on the focus
corridors in phase 4. With the scheduled hold at every stop, a full day of
buses alone in mesoscopic mode had 85 teleports, all at one stop on Av.
Teresópolis: buses ran ahead of a timetable that is interpolated at most
stops, waited, and blocked the ones behind. Without the holds (buses leave on
schedule, then follow traffic) the same day has 0 teleports; the build now
checks this.

**`netconvert` warnings (2,108).**

| Group                                                                                           | Count                             | Reason                                                                                                                                                                                                                                    |
| ----------------------------------------------------------------------------------------------- | --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Junction clusters not joined or reduced                                                         | 718                               | `--junctions.join` declines clusters with parallel roads or slip lanes. The nodes stay separate, which leaves short internal edges at some large junctions. Harmless for routing; to look at on the focus corridors in phase 4.           |
| Turn restrictions ignored                                                                       | 385 messages, about 190 relations | netconvert cannot tell the direction of a restriction when the `from` way runs through the `via` node. Those turn bans are lost. Fixing it needs the ways split at the `via` nodes; left for phase 4 if the focus corridors are affected. |
| Turn-lane tags not applied                                                                      | 265                               | `turn:lanes` tags that do not match the lane count, or unknown lane-use values. netconvert falls back to its own lane connections on those approaches.                                                                                    |
| Geometry (sharp turns, slower turning speed, crossing left turns, junction shapes, roundabouts) | 555                               | OSM geometry at tight junctions. SUMO lowers the speed of tight turns, which is realistic. Crossing left turns matter only in microscopic runs.                                                                                           |
| U-turn ambiguity, unconnected lanes, one connection not set                                     | 86                                | Small local defects; none broke reachability.                                                                                                                                                                                             |
| Tags not understood                                                                             | 62                                | `maxspeed:type=urban` without a number (38 ways, which take the class default), combined types such as a road that is also a railway (23), one reversible one-way.                                                                        |
| Isolated fragments removed                                                                      | 37                                | Pieces cut off by the clip or not connected to anything, removed by `--remove-edges.isolated`.                                                                                                                                            |

## Phase 2: decisions (20 November 2026)

1. **Network source approved**: the dated Geofabrik `sul` snapshot replaces
   the BBBike extract in `data/sources.toml`.
2. **`osmium` (pyosmium) approved** as a pipeline dependency for clipping the
   extract and converting it to OSM XML.
3. **`rtree` approved** as a pipeline dependency, for SUMO's GTFS importer
   (`gtfs2pt.py`) and `sumolib`'s spatial lookups.
4. **Coverage criterion reworded and approved**: every city zone must contain
   drivable edges, instead of its centroid snapping to an edge within 300 m.
5. **Commit and open the PR now**; the bus step goes into the same PR.
