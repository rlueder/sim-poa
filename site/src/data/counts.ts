import type { LineCollection, PointCollection } from '../map/PointMap';
import { type Attribution, fetchJson, type FileSummary } from './load';

export type Subject = 'ciclistas' | 'desconhecido' | 'pedestres' | 'veiculos';

export interface CountSurvey {
  classes: string;
  corridors: string[];
  date: string;
  flags: string[];
  hourly: (null | number)[];
  id: string;
  lat: number;
  located_by: string;
  lon: number;
  month: null | number;
  name: string;
  peak_hour: null | number;
  source: string;
  subject: Subject;
  year: null | number;
}

export interface CountsFile {
  source: Attribution;
  summary: FileSummary;
  surveys: CountSurvey[];
}

export interface QuarterProfile {
  first: number;
  step: number;
  values: (null | number)[];
}

export const SUBJECT_LABELS: Record<Subject, string> = {
  ciclistas: 'Ciclistas',
  desconhecido: 'Não identificado',
  pedestres: 'Pedestres',
  veiculos: 'Veículos',
};

export async function loadCounts(): Promise<{ corridors: LineCollection; file: CountsFile }> {
  const [file, corridors] = await Promise.all([
    fetchJson<CountsFile>('counts/surveys.json'),
    fetchJson<LineCollection>('counts/corridors.geojson'),
  ]);
  return { corridors, file };
}

const profileCache = new Map<number, Promise<Record<string, QuarterProfile>>>();

export function loadProfile(year: number, id: string): Promise<QuarterProfile | undefined> {
  let pending = profileCache.get(year);
  if (!pending) {
    pending = fetchJson<Record<string, QuarterProfile>>(`counts/profiles/${year}.json`);
    profileCache.set(year, pending);
  }
  return pending.then((byId) => byId[id]);
}

export function peakVolume(survey: CountSurvey): null | number {
  return survey.peak_hour === null ? null : (survey.hourly[survey.peak_hour] ?? null);
}

export interface CountFilters {
  corridor: string;
  since: number;
  subject: Subject;
}

export function filterSurveys(surveys: CountSurvey[], filters: CountFilters): CountSurvey[] {
  return surveys.filter(
    (s) =>
      s.subject === filters.subject &&
      (s.year ?? 0) >= filters.since &&
      (filters.corridor === '' || s.corridors.includes(filters.corridor)),
  );
}

export function toPoints(surveys: CountSurvey[]): PointCollection {
  return {
    features: surveys.map((s) => ({
      geometry: { coordinates: [s.lon, s.lat], type: 'Point' as const },
      properties: {
        exact: s.located_by === 'cruzamento' || s.located_by === 'endereço',
        id: s.id,
        method: s.located_by,
        name: s.name,
        peak: peakVolume(s) ?? 0,
        year: s.year ?? 0,
      },
      type: 'Feature' as const,
    })),
    type: 'FeatureCollection',
  };
}

/** Pontos de um perfil de 15 minutos como pares (início, contagem). */
export function profilePoints(profile: QuarterProfile): { count: null | number; start: number }[] {
  return profile.values.map((count, i) => ({ count, start: profile.first + i * profile.step }));
}
