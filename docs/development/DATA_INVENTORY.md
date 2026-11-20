# Data inventory

What the items marked **unverified** in section 4 of the
[implementation guide](IMPLEMENTATION_GUIDE.md) turned out to contain. Checked
on 19 and 20 November 2026 by listing the EPTC shares over WebDAV and opening
a sample of files from each folder. Samples were chosen at even intervals
through the sorted file list, so they span the years in each folder; they are
not exhaustive, and the phase 1 parsers must still report every file they
cannot read.

Sizes and counts come from the WebDAV listing of 20 November 2026.

## Summary

| Item (guide section)                  | Verdict                                                                                           |
| ------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Pedestrian and cyclist counts (4.3)   | Confirmed. Hourly, not 15-minute. Two templates, stable across years                              |
| Older counts up to 2019 (4.3)         | Confirmed. 15-minute vehicle counts back to 1998 in the current EPTC template, plus other layouts |
| Developer impact-study counts (4.3)   | Confirmed. 15-minute counts from 06:00, with a different vehicle class scheme                     |
| Centro Histórico mobility study (4.3) | Confirmed. Includes a cordon count around the Centro and two weeks of bus GPS                     |
| SUMO 1.28.0 on macOS 26 (4.5)         | Confirmed for the command-line tools. `sumo-gui` not tested                                       |
| Mesoscopic support for parking (4.5)  | Not checked. Belongs to phase 2                                                                   |

## Pedestrian and cyclist counts

Share `nPYCNzeyXSZGc2A`: `Pedestres/` has 376 files (138 MB) and
`Ciclistas/` has 128 files (14 MB).

**Cyclists** (`.xlsx`, one sheet `Tabulação`). Opened: 2018-11 Lima e Silva x
Luiz Afonso; 2025-10 José do Patrocínio x Lopo Gonçalves. The header gives
location and date; the table has **hourly** rows from 07:00 for each approach
(`Origem: A`, `B`, `C`, `D`), split by turning movement and by what appear to be
cyclist categories. The column codes are not defined in the sheet. The same
template is used in 2018 and 2025, under different EPTC departments in the
header.

**Pedestrians** (`.xls`, sheets `DADOS`, `ANÁLISE`, `TME`, sometimes
`CARACTERISTICAS DO LOCAL`). Opened: 2017-10 Francisco Silveira Bittencourt x
Ulisses de Alencastro Brandão; 2023-03 Érico Verissimo x Alcides Oliveira
Gomes. Same template in both years. Dates are stored as Excel serial numbers.

Things the parsers must handle:

- Filenames carry year, month and intersection, for example
  `(CICLISTAS) 2018-11 Lima e Silva x Luiz Afonso.xlsx`. Prefixes vary
  (`CICLISTA`, `CICLISTAS`).
- Incomplete surveys are marked in the filename (`_Incompleta`,
  `_INCOMPLETO`) and the header has a "Pesquisa encerrada às" field.
- At least one cyclist workbook sits in the pedestrian folder:
  `Pedestres/(CICLISTAS) 2023-07 Antenor Lemos x Jose de Alencar.xlsx`.
  Classify by the filename prefix, not the folder.

## Older counts up to 2019

Share `T6QGi7ikF2Hg5YD`, folder `Levantamentos CIT (Até 2019)/`: 2,366 files,
700 MB, under `Contagens/` with subfolders by year (`contagens_eptc/1998`,
`2003`, `2005`, `2007`, ...) and by consultancy (`Beck de Souza/`).

Opened five files from 1998 to 2007:

- **EPTC template, 1998 onward** (`DADOS` and `ANALISE` sheets): 15-minute
  rows from 07:00, one column group per numbered movement (`FLUXO 1`, `2`,
  ...), four classes `VL`, `VM`, `VP`, `MT` (veículos leves, médios, pesados, motos).
  This is the same layout as the current `Veículos/` counts, so one parser
  should cover both. The movement numbers refer to a sketch; a `GEO` sheet with
  coordinates appears in the 2007 sample but not in 1998 or 2005.
- **Pedestrian template, 2003** (`MOV.` and `Croqui` sheets).
- **Consultancy template** (`Beck de Souza/rel_1A_1/veic_princ_1.xls`, 2002):
  one sheet per survey day, 15-minute rows, classes `LEVES`, `MÉDIOS`,
  `PESADOS`, named main and secondary flows instead of numbered movements.
- Dates appear as Excel serials and as text (`19/11/98`).

The share root also holds `CAISMaua2021Contagens.zip` (15 MB, counts at Cais
Mauá from 2021), now in the `levantamentos-cit` source.

## Developer impact-study counts

Folder `Contagens Matricial/` in the same share: 215 files, 352 MB, one
subfolder per development (`Anchieta Circulação`, `Internacional 2016`,
`Melnick Protásio Alves`, ...).

Opened three files (2016, 2017, 2018). Same `DADOS` and `ANALISE` structure as
the EPTC template, but rows start at **06:00** and the vehicle classes are `CA`,
`LT`, `O`, `CM` instead of `VL`, `VM`, `VP`, `MT`. The sheets do not define
these codes; car, lotação, bus and truck is a likely reading, to be confirmed
from the `ANALISE` sheet or EPTC's documentation. The class scheme needs a mapping before these counts can be mixed
with EPTC's. One sample is on Av. Protásio Alves (2017-06-27), a focus corridor.

## Centro Histórico mobility study

Folder `Estudo de Mobilidade do Centro Histórico/` in the same share: 1,824
files, 8.6 GB. By size: shapefile attribute tables (3.2 GB), PDF reports and
maps (1.9 GB), zip archives (1.6 GB), shapefile geometry (0.7 GB),
spreadsheets (0.6 GB `.xlsx`, 0.2 GB `.csv`). Most deliverables appear twice,
under `2021_PLANO_CENTRO_MAPAS/` and at the top level (`P03-Contagens`,
`P05-PesquisasTempodePercurso`, `P06-...`, `P09-...`, `P12-Micromobilidade`,
`P14-Diagnóstico`, `P15_Plano de Ação`).

Two parts matter for this project.

**Cordon count around the Centro** (`P03-Contagens/.../CVC Cordon Line/`,
October 2021). Opened P101 (Av. Edvaldo Pereira Paiva) and P121, P122, P124
(Av. Castelo Branco, Rua da Conceição, Av. Júlio de Castilhos). 15-minute rows
from 06:00, classes `CA`, `TX`, `LT`, `O`, `CM` (undefined in the sheet;
probably car, taxi, lotação, bus, truck). This is a classified count of traffic crossing a line around the
Centro, which is close to what a zone entry fee needs as its baseline. October
2021 is inside the pandemic window the guide suggests excluding, so its
volumes need care.

The same folder has pedestrian and cyclist counts (P209 Praça da Alfândega x
Rua Gen. Câmara opened: classes `BI`, `BP`, `IFBI`, `IFBP`, `PE`, `CA`).

**Bus GPS** (`P05-PesquisasTempodePercurso/Anexos digitais/BusGPSCentro.zip`,
70 MB; 860 MB unpacked). Now in the `default` download group as
`centro-bus-gps`.

- Point shapefile in WGS 84, extent longitude −51.2414 to −51.2128 and
  latitude −30.0399 to −30.0199: the Centro Histórico and its approaches,
  about 2.7 km by 2.2 km.
- 4,572,378 points from 1,522 vehicles.
- Two full weeks: 20 to 26 October 2019 and 4 to 10 July 2021. Weekdays carry
  250,000 to 580,000 points each.
- Every hour of the day is present, with peaks at 08:00 and 17:00.
- Fields: `ID`, `LINHA`, `PREFIXO` (vehicle), `SENTIDO`, `VELOCIDADE` (km/h),
  `DIA`, `HORA` (seconds after midnight), `LINK`, `DISTLINK`, `LADOLINK`, and
  empty `LAT`/`LON` columns (coordinates are in the geometry). `LINK` looks
  like a road-segment identifier from map-matching, from an unknown network.
- `LINHA` is empty in 176,926 points (3.9%).
- In a 1-in-50 sample, median speed is 15 km/h, the 90th percentile 43 km/h,
  and 28% of points are at 0 km/h (stops, signals, queues).

This is observed speed by time of day on the Centro's bus routes, which the
guide says is not available anywhere for the city. It covers buses only and
only the Centro, and the July 2021 week falls in the pandemic window. The
October 2019 week is a clean pre-pandemic baseline. It can serve phase 4 as
speed validation in the area most likely to host the parking and entry-fee
examples.

## SUMO on macOS

`eclipse-sumo==1.28.0` installed by uv into the pipeline environment on macOS
26 (Apple Silicon). `sumo --version` reports
`Eclipse SUMO sumo 1.28.0`, built for `Darwin-24.6.0 arm64`. `netconvert`
converts an OSM fixture with the guide's import options; this runs as a test
in `pipeline/tests/test_sumo.py`, locally and in CI. `sumo-gui` and `netedit`
need XQuartz, which was not installed, so the GUI remains untested.

## Not checked yet

- Whether the BBBike extract reaches far enough along the entry highways to
  place the external gates (guide section 4.4). Phase 2.
- Mesoscopic support for parking areas and rerouters (guide section 4.5).
  Phase 2.
- The meaning of the column codes in the cyclist and pedestrian templates.
  Phase 1, from the `ANÁLISE` sheets or EPTC's documentation.
