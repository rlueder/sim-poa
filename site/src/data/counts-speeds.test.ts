import { describe, expect, it } from 'vitest';

import {
  type CountSurvey,
  filterSurveys,
  peakVolume,
  profilePoints,
  toPoints as countPoints,
} from './counts';
import { excess, type SpeedSurvey, toPoints as speedPoints, trimmedHistogram } from './speeds';

function count(overrides: Partial<CountSurvey>): CountSurvey {
  return {
    classes: 'MT VL VM VP',
    corridors: [],
    date: '2019-03-26',
    flags: [],
    hourly: Array.from({ length: 24 }, (_, h) => (h === 7 ? 900 : h === 18 ? 1200 : null)),
    id: 'a',
    lat: -30.03,
    located_by: 'cruzamento',
    lon: -51.2,
    month: 3,
    name: 'Av. A x Rua B',
    peak_hour: 18,
    source: 'pesquisas-fluxo',
    subject: 'veiculos',
    year: 2019,
    ...overrides,
  };
}

describe('contagens', () => {
  it('filtra por tipo, ano e corredor', () => {
    const surveys = [
      count({ id: 'a' }),
      count({ id: 'b', year: 2012 }),
      count({ id: 'c', subject: 'pedestres' }),
      count({ corridors: ['Av. Ipiranga'], id: 'd' }),
    ];
    const ids = (corridor: string) =>
      filterSurveys(surveys, { corridor, since: 2015, subject: 'veiculos' }).map((s) => s.id);
    expect(ids('')).toEqual(['a', 'd']);
    expect(ids('Av. Ipiranga')).toEqual(['d']);
  });

  it('usa o volume da hora pico e marca a localização exata', () => {
    expect(peakVolume(count({}))).toBe(1200);
    expect(peakVolume(count({ peak_hour: null }))).toBeNull();
    const [exact, approximate] = countPoints([
      count({}),
      count({ id: 'b', located_by: 'trecho' }),
    ]).features;
    expect(exact?.properties).toMatchObject({ exact: true, peak: 1200 });
    expect(approximate?.properties.exact).toBe(false);
  });

  it('desdobra o perfil de 15 minutos mantendo lacunas', () => {
    expect(profilePoints({ first: 420, step: 15, values: [5, null, 7] })).toEqual([
      { count: 5, start: 420 },
      { count: null, start: 435 },
      { count: 7, start: 450 },
    ]);
  });
});

function speed(overrides: Partial<SpeedSurvey>): SpeedSurvey {
  return {
    above_limit: 0.5,
    address: 'Av. Ipiranga, 1801',
    by_class: { VL: 10 },
    corridors: [],
    date: '2011-09-12',
    direction: 'BC',
    flags: [],
    histogram: [],
    id: 's',
    lat: -30.05,
    limit_kmh: 60,
    located_by: 'endereço',
    lon: -51.2,
    median: 58,
    p85: 66.5,
    vehicles: 100,
    year: 2011,
    ...overrides,
  };
}

describe('velocidades', () => {
  it('calcula o excesso do percentil 85 sobre o limite', () => {
    expect(excess(speed({}))).toBe(6.5);
    expect(excess(speed({ limit_kmh: null }))).toBeNull();
    expect(speedPoints([speed({})]).features[0]?.properties.excess).toBe(6.5);
  });

  it('corta as faixas vazias das pontas do histograma', () => {
    const bins = [0, 5, 10, 15, 20, 25];
    expect(trimmedHistogram(bins, [0, 0, 3, 0, 4, 0, 0])).toEqual([
      { from: 5, vehicles: 0 },
      { from: 10, vehicles: 3 },
      { from: 15, vehicles: 0 },
      { from: 20, vehicles: 4 },
      { from: 25, vehicles: 0 },
    ]);
    expect(trimmedHistogram(bins, [0, 0, 0])).toEqual([]);
  });
});
