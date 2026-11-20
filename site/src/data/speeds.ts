import type { PointCollection } from '../map/PointMap';
import { type Attribution, fetchJson, type FileSummary } from './load';

export interface SpeedSurvey {
  above_limit: null | number;
  address: string;
  by_class: Record<string, number>;
  corridors: string[];
  date: string;
  direction: string;
  flags: string[];
  histogram: number[];
  id: string;
  lat: number;
  limit_kmh: null | number;
  located_by: string;
  lon: number;
  median: number;
  p85: number;
  vehicles: number;
  year: null | number;
}

export interface SpeedsFile {
  bins_kmh: number[];
  source: Attribution;
  summary: FileSummary;
  surveys: SpeedSurvey[];
}

export function loadSpeeds(): Promise<SpeedsFile> {
  return fetchJson<SpeedsFile>('speeds/surveys.json');
}

/** Diferença entre o percentil 85 e a velocidade regulamentar, em km/h. */
export function excess(survey: SpeedSurvey): null | number {
  return survey.limit_kmh === null ? null : survey.p85 - survey.limit_kmh;
}

// Classes da escala divergente, em km/h acima (+) ou abaixo (-) do limite.
export const EXCESS_BREAKS = [-10, -5, -2, 2, 5, 10];

export function toPoints(surveys: SpeedSurvey[]): PointCollection {
  return {
    features: surveys.map((s) => ({
      geometry: { coordinates: [s.lon, s.lat], type: 'Point' as const },
      properties: {
        address: s.address,
        excess: excess(s) ?? 0,
        has_limit: s.limit_kmh !== null,
        id: s.id,
        limit: s.limit_kmh ?? 0,
        p85: s.p85,
        year: s.year ?? 0,
      },
      type: 'Feature' as const,
    })),
    type: 'FeatureCollection',
  };
}

/** Faixas do histograma sem as vazias das pontas, com uma faixa de margem de cada lado. */
export function trimmedHistogram(
  bins: number[],
  histogram: number[],
): { from: number; vehicles: number }[] {
  const used = histogram.flatMap((v, i) => (v > 0 ? [i] : []));
  if (used.length === 0) return [];
  const first = Math.max(0, (used[0] ?? 0) - 1);
  const last = Math.min(histogram.length - 1, (used.at(-1) ?? 0) + 1);
  return histogram
    .slice(first, last + 1)
    .map((vehicles, i) => ({ from: bins[first + i] ?? (bins.at(-1) ?? 0) + 5, vehicles }));
}

export const DIRECTION_LABELS: Record<string, string> = {
  BC: 'bairro → centro',
  CB: 'centro → bairro',
  LO: 'leste → oeste',
  NS: 'norte → sul',
  OL: 'oeste → leste',
  SN: 'sul → norte',
};
