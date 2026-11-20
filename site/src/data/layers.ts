import { type Attribution, fetchJson } from './load';

type Geometry = { coordinates: unknown; type: string };
export interface Feature<P> {
  geometry: Geometry;
  properties: P;
  type: 'Feature';
}
export interface Collection<P> {
  features: Feature<P>[];
  type: 'FeatureCollection';
}

// ── Ônibus ─────────────────────────────────────────────────────────────────

export interface Stop {
  hourly: number[];
  id: string;
  lat: number;
  lon: number;
  name: string;
  routes: number;
  total: number;
}

export interface StopsFile {
  day: string;
  source: Attribution;
  stops: Stop[];
}

export interface BusCorridor {
  hours: string;
  kind: string;
  name: string;
  section: string;
  status: string;
}

export interface GpsSegment {
  /** Por hora: [mediana em movimento (km/h) ou null, parcela parada, pontos]. */
  hours: Record<string, [null | number, number, number]>;
  name: string;
  segment: number;
}

export interface GpsSummary {
  days: [string, string];
  min_points: number;
  moving_kmh: number;
  points: number;
  segments: number;
  snapped: number;
  source: Attribution & { dataset: string };
}

export function loadBuses() {
  return Promise.all([
    fetchJson<StopsFile>('transit/stops.json'),
    fetchJson<Collection<BusCorridor>>('supply/bus_corridors.geojson'),
    fetchJson<Collection<GpsSegment>>('bus_gps/segments.geojson'),
    fetchJson<GpsSummary>('bus_gps/summary.json'),
  ]).then(([stops, corridors, gps, gpsSummary]) => ({ corridors, gps, gpsSummary, stops }));
}

export function stopsAtHour(
  file: StopsFile,
  hour: null | number,
): Collection<{ buses: number; id: string; name: string; routes: number }> {
  return {
    features: file.stops.map((s) => ({
      geometry: { coordinates: [s.lon, s.lat], type: 'Point' },
      properties: {
        buses: hour === null ? s.total : (s.hourly[hour] ?? 0),
        id: s.id,
        name: s.name,
        routes: s.routes,
      },
      type: 'Feature',
    })),
    type: 'FeatureCollection',
  };
}

/** Segmentos do GPS com a velocidade na hora escolhida; sem amostra suficiente, saem do mapa. */
export function gpsAtHour(
  segments: Collection<GpsSegment>,
  hour: number,
): Collection<{ name: string; points: number; speed: number; stopped: number }> {
  return {
    features: segments.features.flatMap((f) => {
      const at = f.properties.hours[String(hour)];
      if (!at || at[0] === null) return [];
      return [
        {
          geometry: f.geometry,
          properties: { name: f.properties.name, points: at[2], speed: at[0], stopped: at[1] },
          type: 'Feature' as const,
        },
      ];
    }),
    type: 'FeatureCollection',
  };
}

// ── Oferta ─────────────────────────────────────────────────────────────────

export interface BlueZoneBlock {
  kind: string;
  number: string;
  side: string;
  spaces: number;
  street: string;
}

export interface Signal {
  code: string;
  description: string;
  detector: string;
  kind: string;
  status: string;
}

export interface CameraSite {
  corridors: string[];
  direction: string;
  id: string;
  kind: 'controlador' | 'redutor';
  label: string;
  lanes?: null | number;
  lat: number;
  limit_kmh?: null | number;
  located_by: string;
  lon: number;
  series: Record<string, (null | number)[]>;
}

export interface CamerasFile {
  sites: CameraSite[];
  source: Attribution;
  unit: string;
}

export function loadSupply() {
  return Promise.all([
    fetchJson<Collection<BlueZoneBlock>>('supply/blue_zone.geojson'),
    fetchJson<Collection<Signal>>('supply/signals.geojson'),
    fetchJson<CamerasFile>('cameras/sites.json'),
  ]).then(([blueZone, signals, cameras]) => ({ blueZone, cameras, signals }));
}

export function cameraPoints(
  file: CamerasFile,
): Collection<{ id: string; kind: string; label: string }> {
  return {
    features: file.sites.map((s) => ({
      geometry: { coordinates: [s.lon, s.lat], type: 'Point' },
      properties: { id: s.id, kind: s.kind, label: s.label },
      type: 'Feature',
    })),
    type: 'FeatureCollection',
  };
}

/** Série mensal de um equipamento em ordem cronológica, para o gráfico. */
export function cameraSeries(site: CameraSite): { month: string; value: null | number }[] {
  return Object.keys(site.series)
    .sort()
    .flatMap((year) =>
      (site.series[year] ?? []).map((value, i) => ({
        month: `${year}-${String(i + 1).padStart(2, '0')}`,
        value,
      })),
    );
}

// ── Sinistros ──────────────────────────────────────────────────────────────

export interface CrashCell {
  lat: number;
  lon: number;
  /** Por ano: [total, com feridos, com vítima grave ou fatal]. */
  years: Record<string, [number, number, number]>;
}

export interface CrashFile {
  cell_metres: number;
  cells: CrashCell[];
  fields: string[];
  source: Attribution;
  summary: {
    by_hour: number[];
    by_year: Record<string, [number, number, number]>;
    records: number;
    without_coordinates: number;
  };
}

export type Severity = 0 | 1 | 2;

export function loadCrashes(): Promise<CrashFile> {
  return fetchJson<CrashFile>('crashes/grid.json');
}

/** Quadrados da grade, com a contagem do ano e da gravidade escolhidos. */
export function crashSquares(
  file: CrashFile,
  year: string,
  severity: Severity,
): Collection<{ count: number }> {
  // Meia célula em graus, perto de Porto Alegre (30° S).
  const halfLat = file.cell_metres / 2 / 111_320;
  const halfLon = file.cell_metres / 2 / (111_320 * Math.cos((30 * Math.PI) / 180));
  return {
    features: file.cells.flatMap((cell) => {
      const count = cell.years[year]?.[severity] ?? 0;
      if (count === 0) return [];
      const { lat, lon } = cell;
      return [
        {
          geometry: {
            coordinates: [
              [
                [lon - halfLon, lat - halfLat],
                [lon + halfLon, lat - halfLat],
                [lon + halfLon, lat + halfLat],
                [lon - halfLon, lat + halfLat],
                [lon - halfLon, lat - halfLat],
              ],
            ],
            type: 'Polygon',
          },
          properties: { count },
          type: 'Feature' as const,
        },
      ];
    }),
    type: 'FeatureCollection',
  };
}
