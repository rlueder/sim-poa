# Porto Alegre traffic simulation: implementation guide

Written 19 November 2026 for the agent that will build this. Everything under
"What is known" was checked against live pages and files on that date unless it
is marked **unverified**. Re-check anything unverified before relying on it.

## 1. What this is and who it is for

This is a side project that simulates road traffic in Porto Alegre at
different times of day, using open-source tools and open data. It has two
purposes, in this order:

1. **See the real city.** Maps and charts of observed traffic: volumes, speeds,
   trip patterns, crashes, bus service, parking.
2. **Try interventions.** Change the network or the rules and compare against a
   baseline: converting streets to one-way, changing on-street parking,
   charging a fee to enter a zone, retiming signals.

It is a hobby project, built on a Mac (Apple Silicon), with no budget for paid
data. The maintainer reviews everything, so prefer a small number of well-evidenced
steps over a lot of code.

The honest target is a model good enough to compare scenario A against
scenario B in relative terms, with its calibration error stated openly. It will
not predict absolute travel times on a given street, and no output should
suggest it does.

## 2. Decisions already made

These were weighed during research. Do not reopen them without a concrete
reason found during the work.

| Decision                                                                                    | Reason                                                                                                                                                                           |
| ------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **SUMO 1.28.0** is the simulator                                                            | One-way changes, signals and parking are first-class; maintained; native arm64 wheel                                                                                             |
| **Mesoscopic** (`--mesosim`) city-wide, **microscopic** on cut-out areas                    | Meso is fast enough for the whole city and tolerant of network errors; signals and parking need micro                                                                            |
| Demand comes from the **EDOM 2023** household survey, corrected against **EPTC counts**     | Both are public; see section 4                                                                                                                                                   |
| Network comes from **OpenStreetMap**                                                        | The city's centreline layer has no direction, lanes or hierarchy; OSM arterials are 94% tagged for lanes and speed                                                               |
| Zone fees are modelled as **generalized cost plus a simple demand-response step**           | SUMO has no toll object and no mode choice                                                                                                                                       |
| **MATSim is deferred**                                                                      | Best tool for pricing with behavioural response, but needs a synthetic population pipeline and JDK 25. Revisit only after phase 6, and only if pricing becomes the main interest |
| **A/B Street is not used**                                                                  | In maintenance mode since 2024; no demand data path for Brazil                                                                                                                   |
| **Python** for the data and simulation pipeline, reproducible from raw downloads to results | So any result can be regenerated and reviewed                                                                                                                                    |
| **Precisa Saúde shared tooling** for the repository and the front-end                       | The maintainer's standard setup; see section 3.1                                                                                                                                 |
| The atlas and scenario comparisons are a **static React site** in `site/`                   | Uses the shared UI package and design tokens instead of one-off HTML exports                                                                                                     |

## 3. How to work

- The repository is scaffolded with the Precisa Saúde CLI (section 3.1). If
  `.precisa.json`, `AGENTS.md` and `CLAUDE.md` are missing from the root, stop
  and ask; do not scaffold it yourself.
- `AGENTS.md` and the shared rules it imports govern commits, pull requests,
  hooks, worktrees, dependencies and writing style. Where this guide and those
  rules disagree, the rules win; tell the maintainer about the conflict.
- Write acceptance criteria before implementing and keep the plan in
  `docs/development/PLAN.md`.
- Work phase by phase (section 6). Each phase has acceptance criteria. Copy
  them into `PLAN.md`, and at the end of the phase check each one off with its
  evidence: a number, a file, a screenshot.
- **Stop at the end of each phase** and report to the maintainer before starting the
  next. Phases 1 and 4 in particular produce things they will want to look at.
- Ask the maintainer before: installing system-level software (Homebrew casks,
  XQuartz, QGIS), creating accounts with any provider, or sending email to EPTC
  or anyone else.
- Report calibration results as they are. If only 40% of count sites meet the
  target, write 40% and say what was tried. A model described as calibrated
  when it is not would make every later scenario comparison worthless.
- Where the data forces an assumption (a missing column, an ambiguous code, a
  count with no date), record it in `docs/ASSUMPTIONS.md` with the reason. Do
  not silently pick one.

### 3.1 Repository tooling

The repository was created with `@precisa-saude/cli` (profile `oss-site`), the
shared tooling of the maintainer's company, from
`github.com/Precisa-Saude/tooling`. This is a personal project and the first
consumer outside that organisation, so some defaults need adapting.

What the scaffold gives:

- A pnpm and Turborepo workspace with shared ESLint, Prettier, TypeScript and
  commitlint configs, husky hooks, and a CI workflow that calls the tooling's
  reusable workflows.
- `AGENTS.md` (repo-specific) plus the shared agent rules from
  `@precisa-saude/agent-instructions`, loaded through `CLAUDE.md`.
- `precisa doctor`, which requires `lint`, `typecheck`, `format:check` and
  `test` scripts in `package.json` and in pull-request CI.
- For the front-end: `@precisa-saude/ui` (React components, including chart
  containers), `@precisa-saude/themes` (design tokens) and the `react` ESLint
  and TypeScript presets. `Precisa-Saude/datasus-viz` is an existing map-based
  site built on the same stack and is the closest reference.

What needs care here:

- **Two languages in one repository.** The Python pipeline is not something the
  scaffold knows about. Put it in its own directory with its own environment
  and lockfile, and wire its linter, type checker and tests into the root
  `lint`, `typecheck` and `test` scripts so the hooks, CI and `precisa doctor`
  cover both halves. CI will need Python and SUMO installed for the pipeline
  tests; keep those tests small enough to run there, and keep full simulation
  runs out of CI.
- **The site reads pipeline outputs.** Decide early how results reach the site
  (static files in a compact format, sized for a browser) and declare every
  directory the site reads in `siteSourcePath` in `.precisa.json`.
- **Language follows the shared rules.** Interface text, README, code
  comments, CLI messages and commit descriptions are in Brazilian Portuguese
  with full accents. Identifiers and agent-facing documents (this guide,
  `AGENTS.md`, `PLAN.md`, `DATA_INVENTORY.md`) are in English.
- **Use the design tokens and shared components** for the site. Do not copy
  the company's logo or brand composition into this project; it is not a
  Precisa Saúde product.
- **Workflows that need secrets** (site deploy, automated review, release) will
  not work until the maintainer adds them to this repository. Do not add
  secrets or enable those jobs yourself; say which ones are inactive.
- **Dependency updates are done by hand.** The maintainer keeps Renovate
  switched off.
- The licence is MIT, not the template's Apache-2.0.

## 4. What is known about the data

### 4.1 Access points

| Source                       | Address                                                         | Access                                                                                                                                                            |
| ---------------------------- | --------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| City open data portal (CKAN) | `https://dadosabertos.poa.br/`                                  | No login. API at `/api/3/action/package_list`, `package_show`, `datastore_search`. Licence CC-BY                                                                  |
| EPTC ObservaMOB index page   | `https://prefeitura.poa.br/eptc/projetos/observamob`            | Links to public Nextcloud shares                                                                                                                                  |
| ObservaMOB shares            | `https://drive.procempa.com.br/s/<token>`                       | No login. Scripted access by WebDAV at `https://drive.procempa.com.br/public.php/webdav/<path>`, share token as username, blank password; recursive listing works |
| City GIS server              | `https://gis-smamus.portoalegre.rs.gov.br/server/rest/services` | Public FeatureServer; no licence stated                                                                                                                           |

ObservaMOB states that data may be reproduced, distributed and adapted with
attribution to EPTC. There is no formal licence name and no licence file in the
shares. Contact: `observamob@eptc.prefpoa.com.br`.

`datapoa.com.br` is dead even though EPTC's readme still links to it.

Download each file once, politely (sequential requests, a pause between them),
into `data/raw/` with a manifest recording URL, download date and SHA-256. The
count and speed folders are still being added to, so the manifest is what makes
a run reproducible.

### 4.2 Demand

**EDOM 2023 household travel survey.** Share token `eENg6LkJP9d5gqd`, folder
`EDOM 2023/`.

- `EDOM-2023_BANCO_DE_DADOS_ATUALIZADO_ANONIMIZADO.xlsx` (25.7 MB). Three data
  sheets plus dictionary sheets. Read the dictionaries first; do not guess
  codes.
  - Households: 10,021 rows. Car and motorcycle counts, zone, coordinates,
    expansion factor.
  - Residents: 20,696 rows. Age band, income band, work and school coordinates
    and zone, remote-work pattern.
  - Trips: 26,304 rows. Origin and destination coordinates and zone, purpose at
    both ends, start and arrival time, up to four mode legs, bus lines used,
    parking, and three expansion factors (all-day, motorised, AM peak). The
    all-day factor is `FE_IDADE_AJ` and the origin start time is `HOR_O`.
- `ZONAS_OD.zip`: zone shapefile in SIRGAS 2000 / UTM 22S. The survey uses 139
  zones: 106 inside Porto Alegre and one for each of 33 other metropolitan
  municipalities. The shapefile holds 629 polygons because it also carries the
  rest of the state.
- `P15___Relatorio_Final_REV02.pdf`: the final report, including results of
  cordon-line surveys at the city's entry points. The raw cordon data was not
  found in the folder.
- Coordinates are rounded to three decimals, about 100 m.

Expanded weekday figures from the report, for checking your own expansion:

| Quantity          | Value                      |
| ----------------- | -------------------------- |
| Trips per weekday | 1,732,140                  |
| Residents         | 1,332,197                  |
| Trips per person  | 1.30                       |
| AM peak hour      | 07:00–08:00, 164,368 trips |
| PM peak hour      | 17:30–18:30                |
| Car driver        | 25.1%                      |
| Walk              | 24.0%                      |
| Bus               | 21.4%                      |
| Car passenger     | 12.9%                      |
| Ride-hailing      | 9.6%                       |
| School transport  | 2.0%                       |
| Motorcycle rider  | 1.6%                       |
| Bicycle           | 1.4%                       |

**EDOM 2003** is in the same share (`EDOM_2003/`): OD matrices by mode, an
Access database, old counts. Useful only for comparison.

**IBGE Census 2022**, for commuters who live outside the city:

- Sample microdata for Rio Grande do Sul:
  `https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Microdados_e_Areas_de_Ponderacao/Microdados_de_acesso_Publico/csv/43_RS.zip`
  (69 MB). Variables: municipality of work when different from residence
  (P1130/P1140), main mode to work (P1170), travel time (P1180/P1190),
  municipality of study (P0810/P0820).
- It gives workplace only at municipality level and no departure times.
- Tract aggregates, tract geometry, the statistical grid and the CNEFE address
  registry are all on IBGE's FTP. The Python and R packages `geobr` (2.0.0) and
  `censobr` (1.0.0) wrap most of them.

**Totals for sanity checks.** SENATRAN, September 2026: 961,642 vehicles
registered in Porto Alegre, of which 613,192 cars and 129,536 motorcycles and
scooters.

### 4.3 Observed traffic

| Dataset                         | Where                                                         | What it holds                                                                                                                                                                                   |
| ------------------------------- | ------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Intersection vehicle counts     | Token `nPYCNzeyXSZGc2A`, folder `Veículos`                    | About 520 workbooks, 2015 to this month. 15-minute bins per turning movement, four vehicle classes (VL/VM/VP/MT), a sheet with coordinates. The one sampled covered 07:00–20:00 on a single day |
| Spot-speed surveys              | Same token, folder `Velocidade`                               | About 2,000 workbooks, 2003 to November 2024. Individual vehicle speeds with class, per site and direction                                                                                      |
| Pedestrian and cyclist counts   | Same token                                                    | About 376 and 128 workbooks, 2015–2026 (**unverified**: not opened)                                                                                                                             |
| Speed-camera typical-day flow   | Token `L4aLgjfKT8bSqN4`, yearly folders                       | PDF only. Monthly average weekday (Tue–Thu) flow per site and direction, 2020 to September 2026. No hourly breakdown                                                                            |
| Speed-camera locations          | Token `eNwpddbxXW7fN6B`, `_MEV_20261109.zip`                  | 160 points with direction, lane count, speed limit                                                                                                                                              |
| Congestion index                | Token `L4aLgjfKT8bSqN4`                                       | PDF, citywide monthly, derived from Waze, 2020 to August 2025                                                                                                                                   |
| Older counts                    | Token `T6QGi7ikF2Hg5YD`                                       | About 2,000 workbooks up to 2019 (**unverified**: not opened)                                                                                                                                   |
| Centro Histórico mobility study | Token `T6QGi7ikF2Hg5YD`                                       | Counts, travel-time surveys, a bus GPS archive, parking, freight, 2021–2023 (**unverified**: listed, not opened)                                                                                |
| Crashes                         | Token `X3oWmEQo5bNP4Sr`, `ACIDENTES_TRANSITO_2010_202611.zip` | 268,420 records, 2010 to now, with coordinates. A CKAN version covers 2021 onward                                                                                                               |

There is **no** public per-segment speed data, no hourly detector data, and no
real-time bus position feed.

**TomTom Traffic Index** publishes citywide figures for Porto Alegre at
`https://www.tomtom.com/traffic-index/porto-alegre-traffic/`, including an
hour-by-day-of-week table. 2025 values: 26 min 54 s per 10 km on average; 20
km/h in the morning rush; 16.5 km/h in the evening rush. Use these as a
citywide sanity check. The page states no reuse licence, so do not scrape or
republish the table; the maintainer can copy values by hand if wanted.

**Commercial speed APIs** (TomTom, HERE, Google, Mapbox) all prohibit keeping a
derived dataset under their standard terms. Do not build on them.

### 4.4 Network and supply

| Dataset                           | Where                                                                                                                                             | Notes                                                                                                               |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| OpenStreetMap extract             | `https://download.bbbike.org/osm/bbbike/PortoAlegre/PortoAlegre.osm.pbf` (25 MB) or Geofabrik `sul-latest.osm.pbf` (431 MB) clipped with `osmium` | Check that the BBBike extract reaches the entry highways you need                                                   |
| Signal inventory                  | Token `LJp8MNCFmZKdPpD`, `_EPS_CadastroSemaforico_20261021.zip`                                                                                   | 1,555 records with coordinates, controller type, detector flag. **No timing plans exist publicly**                  |
| Paid street parking (Área Azul)   | Same token, `AAE_ZONAAZUL_20260817.zip`                                                                                                           | 7,747 spaces, each a segment with street and side                                                                   |
| Regulated bays                    | Same token, `VAGASESTACIONAMENTO_EPTC_20250519.zip`                                                                                               | 694 records                                                                                                         |
| Bus corridors and exclusive lanes | Same token, `_CorredoresFaixasExclusivas_20261021.zip`                                                                                            | 47 records with operating hours                                                                                     |
| Street centrelines                | Same token, `EixosLogradouros20260128.zip`                                                                                                        | Names and address ranges only. Use for geocoding count sites, not as the network                                    |
| Bus GTFS                          | `https://dadosabertos.poa.br/dataset/gtfs`                                                                                                        | 395 routes, about 5,900 stops. The feed's calendar runs 2025-09-18 to 2025-12-18, so pick a date inside that window |
| Current bus routes and stops      | Token `SS2MDqnK24RqRLm`; stops in `LJp8MNCFmZKdPpD`                                                                                               | Shapefiles dated November 2026                                                                                      |
| Road signage inventory            | `https://dadosabertos.poa.br/dataset/sinalizacao-grafica`                                                                                         | Every sign with coordinates; could confirm one-way streets and parking rules                                        |
| Bairros, planning regions         | CKAN                                                                                                                                              | Polygons                                                                                                            |

City layers use "SIRGAS 2000 / Porto Alegre TM", a local projection. Read the
`.prj` file; do not assume an EPSG code.

**OpenStreetMap quality**, counted on the municipal boundary (relation 242397):

- Roads of tertiary class and above (8,658 ways): `lanes` on 94%, `maxspeed` on
  94%.
- `turn:lanes` on 3.5%; `parking:*` on 3% of all drivable ways. Turn lanes and
  on-street parking are effectively unmapped.
- 2,093 signal nodes and 1,168 turn-restriction relations.

### 4.5 Tools

- **SUMO 1.28.0** (8 October 2026). `pip install eclipse-sumo` installs a native
  arm64 wheel; `libsumo`, `traci` and `sumolib` are on PyPI at the same version.
  `sumo-gui` and `netedit` need XQuartz. Not tested on macOS 26
  (**unverified**).
- OSM import options recommended by the SUMO docs:
  `--geometry.remove --ramps.guess --junctions.join --tls.guess-signals
--tls.discard-simple --tls.join --tls.default-type actuated`. The bundled
  urban typemap has German defaults and needs a Brazilian override.
- `routeSampler.py` fits candidate routes to edge counts, turn counts or OD
  relations per time interval. `marouter` does macroscopic assignment from OD
  matrices. `duaIterate.py` iterates toward user equilibrium.
- Mesoscopic mode gained a link transmission model (`--meso-ltm`) and actuated
  signals in 1.28.0. Whether parking areas and rerouters work in meso is
  **unverified**; assume not until tested.
- `traceExporter.py --keplerjson-output` exists for animated vehicle traces.
  `tools/output/edgeDataDiff.py` and `tripinfoDiff.py` compare runs.
- The best template for a counts-based build is the Wildau scenario in
  `github.com/DLR-TS/sumo-scenarios`. For city-wide meso structure, see
  `github.com/marcorapelli/TuSTScenario`.
- No reusable Porto Alegre scenario exists. The UFRGS group's public network is
  a 152-edge abstraction from 2013.

## 5. Where the difficulty is

Read this before planning. These are the places where an obvious approach
produces something that runs and is wrong.

**The survey is too thin for direct hourly matrices.** 26,304 trip records
spread over 106 × 106 zones and 24 hours leave almost every cell empty.
Expanding and binning directly gives a matrix that is mostly zeros with a few
cells worth hundreds of trips each. Separate the problem instead: estimate a
daily OD pattern at a coarser level or with smoothing (a gravity or
iterative-proportional-fitting model fitted to the survey's zone totals and
trip-length distribution), estimate departure-time profiles by purpose from the
full sample, then let the counts correct the result.

**The survey covers residents only.** People who live in Canoas, Viamão,
Alvorada and the rest of the metropolitan region and drive into the city are
absent, as are freight and through traffic. Without them the entry highways
will be badly under-loaded. Build external demand from the Census 2022 commuter
flows and the cordon results in the EDOM final report, entering at gates on the
network boundary. Freight has no source; scale it from the heavy-vehicle share
in the classified counts and say so.

**The survey under-reports.** 1.30 trips per person is low (2003 measured
1.65). Short and non-home-based trips are likely missing. Expect the counts to
ask for more traffic than the survey supplies, and let calibration scale it.

**Counts are scattered across eleven years.** Each workbook is one site on one
day. The set spans the pandemic and the May 2024 flood, during which part of
the city was under water. Choose an inclusion window, justify it, and make it a
configuration value. Excluding March 2020 to end 2021 and May to August 2024 is
a reasonable starting point. The EDOM fieldwork ran from August 2023 into 2024
and may itself overlap the flood; check the report.

**Count workbooks are hand-made.** Expect several templates, merged cells and
inconsistent movement labels across 520 files. Build the parser against a
sample of files from different years, make it fail loudly on a layout it does
not recognise, and report how many files it could read. Do not let unparsed
files drop out silently.

**Matching counts to the network is the fiddliest step.** A turning movement
must be mapped to an inbound and an outbound SUMO edge at a junction that
`--junctions.join` may have merged. Start with approach totals per inbound
edge, which are far easier to match, and add turning movements later if needed.

**Calibration can overfit.** `routeSampler` will happily match every count it
is given. Hold out about 20% of sites, chosen before fitting, and report the
fit on those.

**Calibrated routes must not be frozen into scenarios.** The baseline fit
produces routes. A scenario needs the same travellers free to choose new
routes. Keep calibrated demand as trips (origin, destination, departure time)
and re-run assignment for every scenario, baseline included, with the same
procedure and seeds. Otherwise the comparison measures the assignment method,
not the intervention.

**Signals have no public timings.** The inventory gives locations and
controller types only. Use the inventory to correct where OSM import places
signals, then generate plans (actuated, or `tlsCycleAdaptation.py`). Signal
retiming experiments are therefore relative to generated plans, not to the
city's real ones. State this wherever such results appear.

**Simulation noise can exceed the effect.** A single run of baseline against
scenario proves little. Run several seeds per scenario and report the spread
alongside the difference.

**SUMO teleports hide gridlock.** When vehicles are stuck, SUMO removes and
reinserts them. A run with many teleports has a broken network or too much
demand, and its travel times are meaningless. Track the count and treat a high
number as a failed run.

## 6. Phases

### Phase 0: project setup and data acquisition

Adapt the scaffold as described in section 3.1, set up the Python environment
(pin SUMO at 1.28.0), and add a download step that fetches every dataset in
section 4 into `data/raw/` with a manifest. Raw data stays out of git.

Acceptance:

- `precisa doctor` passes, and the root `lint`, `typecheck`, `format:check` and
  `test` scripts cover both the Python pipeline and the site.
- CI is green on a pull request, with the inactive secret-dependent jobs
  listed.
- One command rebuilds `data/raw/` from nothing, and re-running it downloads
  nothing new.
- The manifest lists every file with URL, date and hash.
- `sumo --version` reports 1.28.0 and a bundled SUMO tool runs.
- A short data inventory records, for each item marked unverified in section 4,
  what it turned out to contain.

Out of scope: any parsing beyond what the inventory needs.

### Phase 1: atlas of observed data

This is the "see the real city" deliverable and is useful by itself even if
nothing after it gets built. Parse the observed datasets into tidy tables
(GeoParquet is a good fit) and present them as interactive maps and charts in
the site (section 3.1).

Minimum content:

- Trip origins and destinations by zone and time of day from EDOM 2023, with
  desire lines for the main flows, and mode share by zone.
- Departure-time profile by purpose.
- Count sites with their 15-minute profiles.
- Spot-speed sites with observed speed against the posted limit.
- Speed-camera typical-day flows by site.
- Bus network with service frequency by hour.
- Área Azul spaces, signals, bus corridors, crash density.

Acceptance:

- The EDOM expansion reproduces the report's figures in section 4.2: total
  trips and mode shares within 1%, peak hours matching.
- The count parser reports files read against files found, with the unread ones
  listed by reason.
- Every count and speed site is geocoded, with a map for the maintainer to
  spot-check.
- The site builds to static files, runs locally with one command, and loads
  its data without a backend.
- Every view names its source, with attribution to EPTC where its data is
  used, and survey views are aggregated to zones or coarser (section 8,
  decision 5).

Out of scope: any simulation.

### Phase 2: network

Build the SUMO network from OSM. The study area is the municipality, with an
external gate where each major entry road crosses the boundary (identify them
from the map and the EDOM cordon points; BR-116, BR-290 and RS-040 are among
them). Write a Brazilian typemap. Reconcile signals with the
city inventory. Import bus stops and routes from GTFS.

Acceptance:

- `netconvert` warnings are reviewed and the remaining ones are listed with a
  reason each.
- Every zone centroid can reach every other by car, checked by routing.
- Signal controllers after import are compared with the 1,555 inventory
  records, and the mismatch is quantified and mapped.
- Free-flow travel times on about ten well-known corridors are plausible.
  The maintainer knows the city and should look at these.
- A smoke-test run with random trips completes in meso with near-zero
  teleports.

Out of scope: lane-level correction of turn lanes outside the areas later cut
out for micro runs.

### Phase 3: demand

Build weekday vehicle demand as trips with origin, destination, departure time
and vehicle type.

- Internal: car-driver, motorcycle and ride-hailing trips from EDOM 2023, using
  the approach in section 5. Decide and document how ride-hailing trips become
  vehicles.
- External: commuters from the Census 2022 and the cordon results, entering at
  the gates.
- Freight: scaled from classified counts.
- Buses: from GTFS, as scheduled vehicles.
- Origins and destinations placed on edges inside each zone, weighted by
  something better than uniform (survey coordinates, CNEFE addresses or
  population grid).

Acceptance:

- Daily internal car-driver trips match the survey expansion.
- The trip-length distribution of the synthetic demand matches the survey's.
- The hourly profile matches the survey's and shows both peaks.
- External inbound volumes are compared with the cordon figures in the report.
- All assumptions are in `docs/ASSUMPTIONS.md`.

Out of scope: walking, cycling and bus passengers as simulated persons.

### Phase 4: baseline assignment and calibration

Assign the demand to the network in meso for a full weekday, correct it against
the counts, and validate.

Validation measures:

- **GEH statistic** per hourly count. The usual professional target is GEH
  below 5 at 85% of sites. Report the percentage achieved on fitted sites and
  on held-out sites separately; do not expect to reach 85% on the held-out
  set.
- Daily flow at speed-camera sites against the typical-day figures (an
  independent source, not used in fitting).
- Simulated speeds against spot-speed surveys where traffic is light, and
  citywide mean speed by hour against the TomTom Traffic Index figures.
- Teleport count.

Acceptance:

- A calibration report with the measures above, scatter plots of simulated
  against observed flow, and a map of the worst-fitting sites.
- A written judgement of which parts of the city and which hours the model can
  be trusted for, and which it cannot.
- The baseline run is reproducible from one command and a fixed seed.

This is the phase most likely to need several rounds. If the fit is poor,
suspect in this order: count-to-edge matching, network errors near the bad
sites, missing external demand, then the demand model.

### Phase 5: scenario framework and first experiments

A scenario is a small declarative file describing changes to the baseline. The
framework applies it, re-runs assignment with the same procedure and seeds as
the baseline, and produces a comparison.

Support these intervention types:

1. **Street direction and lane changes.** City-wide in meso.
2. **Signal changes.** Micro, on a cut-out corridor.
3. **On-street parking changes.** Micro, on a cut-out area such as the Centro
   Histórico, using the Área Azul layer for existing supply. Removing parking
   to add a lane is the simplest version and works in meso as a lane change.
4. **Zone entry fee.** A polygon, a fee schedule by time of day, and a value of
   time. Applied as extra generalized cost on entering edges for route choice,
   plus a demand-response step that reduces or retimes car trips into the zone.
   Use a simple, documented elasticity or incremental logit, and report results
   across a range of its parameters, since the response strength is an
   assumption and not something this data can estimate.

Comparison outputs: total vehicle-hours and vehicle-kilometres, mean speed by
period, delay against free flow, travel time on named corridors, bus travel
time by route, a difference map of flow and speed by edge, and for fee
scenarios the trips removed and revenue. Each with the spread across seeds.

Acceptance:

- A scenario that changes nothing gives differences within seed noise.
- One worked example of each intervention type, chosen with the maintainer, with its
  comparison report.
- Each report states the model's limits for that intervention, in particular
  generated signal plans and the assumed pricing response.

### Phase 6: presentation

In the site: animated vehicle traces for selected periods and side-by-side
baseline and scenario maps. Plus a short document on how to define and run a
new scenario.

Acceptance:

- The maintainer can define a new one-way scenario and get a comparison report
  without reading the code.

### Later: contributions from other people

The maintainer wants other people to be able to propose interventions, each
working on an area of a shared map, and to see the effect quickly. Do not build
this in phases 0 to 6. Three choices in those phases keep it possible, and they
are requirements:

- **Scenarios reference stable identifiers.** SUMO edge IDs change whenever the
  network is rebuilt from newer OSM data. Pin the OSM snapshot used for a
  network version, record that version in every scenario file, and key changes
  by OSM way ID where possible, so a scenario written by someone else still
  applies or fails loudly.
- **Area cut-outs are first-class.** A cut-out is a named polygon, its
  sub-network, and the traffic entering at its edges taken from the city-wide
  baseline. Phase 5 already needs this for signals and parking; build it so
  any polygon works, not only the worked examples.
- **Running a scenario goes through one interface**: scenario file in, result
  files out. Today it is a local command; later it can be a job on a server.

Expected stages, for orientation only:

1. **Contributions by pull request.** Someone adds a scenario file; a runner
   executes it; the site lists scenarios with their comparison against the
   baseline. Needs no backend beyond a machine to run jobs.
2. **Live shared editing.** Several people edit scenarios on one map and see
   each other's changes immediately, with a cut-out simulation streamed to the
   map as it runs. This needs a sync service, a compute worker, accounts and
   moderation, so the site stops being purely static.

A cut-out run cannot show traffic diverting around the area, which is often the
main effect of an intervention. Results from a cut-out are a preview; only a
city-wide run supports a conclusion. The interface must say so.

### Later, only if wanted

A MATSim model with a synthetic population, built by adapting the eqasim São
Paulo pipeline (`github.com/eqasim-org/sao_paulo`) to Census 2022 and EDOM 2023. This gives pricing and parking-cost experiments a proper behavioural
response, including mode shift to bus. It is a project of its own.

## 7. Licences and data handling

- Attribute EPTC wherever its data appears, and OpenStreetMap contributors
  (ODbL) wherever the network appears.
- Keep raw EPTC and IBGE files out of the repository; commit the download
  script and manifest.
- EDOM microdata is anonymised but holds household-level records with rounded
  coordinates. Show it aggregated to zones or coarser.
- See decision 5 in section 8 for what may be committed and published.
- Nothing from a commercial traffic API goes into the repository.

## 8. Maintainer decisions (19 November 2026)

1. **Study area: the municipality only.** External traffic enters at gates on
   the municipal boundary. Do not model neighbouring cities' road networks.
2. **No HERE speed sample for now.** Speed validation in phase 4 uses the EPTC
   spot-speed surveys and the citywide TomTom Traffic Index figures only.
3. **No request to EPTC.** Work with what is public. Signal plans stay
   generated, and speed-camera flows stay at monthly typical-day resolution.
   Do not contact EPTC about anything, including the licence, without asking
   the maintainer first.
4. **Focus corridors for the phase 5 worked examples:** Av. Carlos Gomes,
   Av. Protásio Alves, Av. Ipiranga, and Av. Nilo Peçanha / Av. Nilópolis.
   Give these extra care from phase 1 onward: prioritise count and speed sites
   on or near them, check their lanes, turn lanes and signals by hand in
   phase 2, and report calibration fit for them separately in phase 4. The
   zone for the entry-fee example and the area for the parking example are
   not chosen yet; ask at the start of phase 5.
5. **The repository is public, and all public EPTC data may be used with
   attribution.** The maintainer decided this knowing that EPTC states its
   reuse terms on a web page only and has not been asked. Derived files (demand,
   OD matrices, aggregates, parsed counts and speeds) may be committed and shown
   on the site, each with visible attribution to EPTC and a link to the source.
   Two limits remain, for other reasons:
   - Raw downloads stay out of git, because they are large and still changing;
     the download script and manifest reproduce them.
   - The site shows survey results aggregated to zones or coarser. It does not
     plot individual households, people or trips, even though the published
     microdata would allow it.
6. **Name and home:** the project is `sim-poa`, at `github.com/rlueder/sim-poa`,
   MIT licensed.
