// Tipos GeoJSON mínimos usados aqui, para não depender de @types/geojson.
type Position = number[];
interface Polygon {
  coordinates: Position[][];
  type: 'Polygon';
}
interface MultiPolygon {
  coordinates: Position[][][];
  type: 'MultiPolygon';
}
interface Feature<G, P> {
  geometry: G;
  properties: P;
  type: 'Feature';
}
interface FeatureCollection<G, P> {
  features: Feature<G, P>[];
  type: 'FeatureCollection';
}

export type ModeGroup = 'ativo' | 'coletivo' | 'individual' | 'outros';

export interface ZoneStats {
  attracted: number;
  attracted_by_hour: number[];
  mode_share: Partial<Record<ModeGroup, number>>;
  produced: number;
  produced_by_hour: number[];
  records: number;
  zone: number;
}

export interface ZonesFile {
  centroids: Record<string, [number, number]>;
  zones: ZoneStats[];
}

export interface ZoneProperties {
  area_km2: number;
  in_city: boolean;
  name: null | string;
  population: null | number;
  zone: number;
}

export type ZonesGeoJson = FeatureCollection<MultiPolygon | Polygon, ZoneProperties>;

export interface DesireLine {
  by_group: Partial<Record<ModeGroup, number>>;
  d: number;
  o: number;
  records: number;
  trips: number;
}

export interface DesireLinesFile {
  min_records: number;
  pairs: DesireLine[];
}

export interface ProfileFile {
  series: Record<string, number[]>;
  slot_minutes: number;
  slots: number[];
  window_minutes: number;
}

export interface ValidationCheck {
  name: string;
  note: string;
  ok: boolean;
  ours: number;
  report: null | number;
}

export interface ValidationFile {
  checks: ValidationCheck[];
  source: { dataset: string; href: string; name: string };
}

export interface EdomData {
  lines: DesireLinesFile;
  profile: ProfileFile;
  shapes: ZonesGeoJson;
  validation: ValidationFile;
  zones: ZonesFile;
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${import.meta.env.BASE_URL}data/${path}`);
  if (!response.ok) {
    throw new Error(`Falha ao carregar ${path}: HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function loadEdom(): Promise<EdomData> {
  const [zones, shapes, lines, profile, validation] = await Promise.all([
    fetchJson<ZonesFile>('edom/zones.json'),
    fetchJson<ZonesGeoJson>('edom/zones.geojson'),
    fetchJson<DesireLinesFile>('edom/desire_lines.json'),
    fetchJson<ProfileFile>('edom/profile.json'),
    fetchJson<ValidationFile>('edom/validation.json'),
  ]);
  return { lines, profile, shapes, validation, zones };
}

// Rótulos dos motivos como a planilha os grava.
export const PURPOSE_LABELS: Record<string, string> = {
  ESTUDOS: 'Estudo',
  'NÃO DOMICILIAR': 'Base não domiciliar',
  OUTROS: 'Outros motivos',
  TRABALHO: 'Trabalho',
};

export const PURPOSE_ORDER = ['TRABALHO', 'ESTUDOS', 'OUTROS', 'NÃO DOMICILIAR'];

export type Measure = 'attracted' | 'produced';

export function zoneValue(stats: ZoneStats, measure: Measure, hour: null | number): number {
  if (hour === null) return stats[measure];
  const byHour = measure === 'produced' ? stats.produced_by_hour : stats.attracted_by_hour;
  return byHour[hour] ?? 0;
}

/** Caixa envolvente [oeste, sul, leste, norte] das zonas de Porto Alegre. */
export function cityBounds(shapes: ZonesGeoJson): [number, number, number, number] {
  let [w, s, e, n] = [180, 90, -180, -90];
  const visit = (coords: unknown): void => {
    if (Array.isArray(coords) && typeof coords[0] === 'number') {
      const [x, y] = coords as [number, number];
      w = Math.min(w, x);
      e = Math.max(e, x);
      s = Math.min(s, y);
      n = Math.max(n, y);
    } else if (Array.isArray(coords)) {
      coords.forEach(visit);
    }
  };
  for (const feature of shapes.features) {
    if (feature.properties.in_city) visit(feature.geometry.coordinates);
  }
  return [w, s, e, n];
}

// Limites de classe por quantis dos valores positivos, para o mapa coroplético.
export function quantileBreaks(values: number[], classes: number): number[] {
  const sorted = values.filter((v) => v > 0).sort((a, b) => a - b);
  if (sorted.length === 0) return [];
  const breaks: number[] = [];
  for (let i = 1; i < classes; i += 1) {
    const value = sorted[Math.min(sorted.length - 1, Math.floor((i * sorted.length) / classes))];
    if (value !== undefined && (breaks.length === 0 || value > (breaks.at(-1) ?? 0))) {
      breaks.push(value);
    }
  }
  return breaks;
}
