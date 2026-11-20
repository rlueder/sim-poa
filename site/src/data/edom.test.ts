import { describe, expect, it } from 'vitest';

import { profileRows } from '../views/trips/profile';
import { sequentialColor, zoneLabel } from '../views/trips/shared';
import { SEQUENTIAL } from '../viz/palette';
import { cityBounds, quantileBreaks, type ZonesGeoJson, type ZoneStats, zoneValue } from './edom';
import { formatClock, formatHourRange, formatInteger, formatPercent } from './format';

const stats: ZoneStats = {
  attracted: 30,
  attracted_by_hour: Array.from({ length: 24 }, (_, h) => (h === 8 ? 30 : 0)),
  mode_share: { ativo: 0.5 },
  produced: 40,
  produced_by_hour: Array.from({ length: 24 }, (_, h) => (h === 7 ? 40 : 0)),
  records: 3,
  zone: 1,
};

describe('dados da EDOM', () => {
  it('escolhe o total do dia ou da hora', () => {
    expect(zoneValue(stats, 'produced', null)).toBe(40);
    expect(zoneValue(stats, 'produced', 7)).toBe(40);
    expect(zoneValue(stats, 'attracted', 7)).toBe(0);
    expect(zoneValue(stats, 'attracted', 8)).toBe(30);
  });

  it('calcula limites de classe crescentes e ignora zeros', () => {
    expect(quantileBreaks([0, 0, 1, 2, 3, 4, 5, 6, 7, 8], 4)).toEqual([3, 5, 7]);
    expect(quantileBreaks([5, 5, 5, 5], 4)).toEqual([5]);
    expect(quantileBreaks([0, 0], 4)).toEqual([]);
  });

  it('enquadra só as zonas da cidade', () => {
    const shapes: ZonesGeoJson = {
      features: [
        {
          geometry: {
            coordinates: [
              [
                [-51.2, -30.1],
                [-51.1, -30.0],
                [-51.2, -30.0],
              ],
            ],
            type: 'Polygon',
          },
          properties: { area_km2: 1, in_city: true, name: null, population: 10, zone: 1 },
          type: 'Feature',
        },
        {
          geometry: {
            coordinates: [
              [
                [
                  [-50, -29],
                  [-49, -28],
                  [-50, -28],
                ],
              ],
            ],
            type: 'MultiPolygon',
          },
          properties: { area_km2: 100, in_city: false, name: 'Viamão', population: 10, zone: 140 },
          type: 'Feature',
        },
      ],
      type: 'FeatureCollection',
    };
    expect(cityBounds(shapes)).toEqual([-51.2, -30.1, -51.1, -30.0]);
  });

  it('monta as linhas do gráfico na ordem dos motivos', () => {
    const rows = profileRows({
      series: { OUTROS: [1, 2], TRABALHO: [3, 4] },
      slot_minutes: 15,
      slots: [0, 15],
      window_minutes: 60,
    });
    expect(rows).toEqual([
      { ESTUDOS: 0, 'NÃO DOMICILIAR': 0, OUTROS: 1, slot: 0, TRABALHO: 3 },
      { ESTUDOS: 0, 'NÃO DOMICILIAR': 0, OUTROS: 2, slot: 15, TRABALHO: 4 },
    ]);
  });
});

describe('formatação e cores', () => {
  it('formata números e horários em pt-BR', () => {
    expect(formatInteger(1732140)).toBe('1.732.140');
    expect(formatPercent(0.251)).toBe('25,1%');
    expect(formatClock(1050)).toBe('17:30');
    expect(formatClock(24 * 60 + 20)).toBe('00:20');
    expect(formatHourRange(7)).toBe('07:00 às 08:00');
  });

  it('nomeia zonas da cidade e municípios vizinhos', () => {
    expect(zoneLabel({ in_city: true, name: null, zone: 12 })).toBe('Zona 12');
    expect(zoneLabel({ in_city: false, name: 'Canoas', zone: 120 })).toBe('Canoas');
  });

  it('limita a rampa sequencial às cores existentes', () => {
    expect(sequentialColor(-1)).toBe(SEQUENTIAL[0]);
    expect(sequentialColor(99)).toBe(SEQUENTIAL[SEQUENTIAL.length - 1]);
  });
});
