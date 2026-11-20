import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  cameraSeries,
  type CrashFile,
  crashSquares,
  gpsAtHour,
  stopsAtHour,
  type StopsFile,
} from '../data/layers';
import { integerRange } from '../viz/legend';
import { BusesView } from './buses/BusesView';
import { CrashesView } from './crashes/CrashesView';
import { SupplyView } from './supply/SupplyView';

// O mapa vira uma lista: uma entrada por feição visível, com o texto do tooltip,
// clicável quando a camada é interativa.
vi.mock('../map/LayerMap', () => ({
  LayerMap: ({
    label,
    layers,
    onSelect,
    tooltip,
  }: {
    label: string;
    layers: {
      data: { features: { properties: Record<string, unknown> }[] };
      id: string;
      interactive?: boolean;
      visible: boolean;
    }[];
    onSelect?: (id: string, p: Record<string, unknown>) => void;
    tooltip: (id: string, p: Record<string, unknown>) => string[];
  }) => (
    <div aria-label={label} role="region">
      {layers
        .filter((l) => l.visible && l.interactive)
        .flatMap((l) =>
          l.data.features.map((f, i) => (
            <button
              key={`${l.id}-${i}`}
              type="button"
              onClick={() => onSelect?.(l.id, f.properties)}
            >
              {tooltip(l.id, f.properties).join(' | ')}
            </button>
          )),
        )}
    </div>
  ),
}));

const source = { href: 'https://exemplo.test/eptc', name: 'EPTC' };
const stopsFile: StopsFile = {
  day: '2025-10-29',
  source: { href: 'https://exemplo.test/gtfs', name: 'Portal (GTFS)' },
  stops: [
    {
      hourly: Array.from({ length: 24 }, (_, h) => (h === 8 ? 12 : 1)),
      id: 'A',
      lat: -30,
      lon: -51,
      name: 'Parada A',
      routes: 3,
      total: 35,
    },
  ],
};
const crashFile: CrashFile = {
  cell_metres: 250,
  cells: [
    { lat: -30.03, lon: -51.2, years: { '2025': [5, 2, 1] } },
    { lat: -30.04, lon: -51.2, years: { '2026': [3, 0, 0] } },
  ],
  fields: ['total', 'com feridos', 'com vítima grave ou fatal'],
  source,
  summary: {
    by_hour: Array(24).fill(0),
    by_year: { '2025': [5, 2, 1], '2026': [3, 0, 0] },
    records: 8,
    without_coordinates: 0,
  },
};
const files: Record<string, unknown> = {
  'bus_gps/segments.geojson': {
    features: [
      {
        geometry: {
          coordinates: [
            [-51.2, -30.03],
            [-51.21, -30.03],
          ],
          type: 'LineString',
        },
        properties: { hours: { '8': [14.5, 0.3, 120] }, name: 'BORGES DE MEDEIROS', segment: 1 },
        type: 'Feature',
      },
    ],
    type: 'FeatureCollection',
  },
  'bus_gps/summary.json': {
    days: ['2019-10-21', '2019-10-25'],
    min_points: 30,
    moving_kmh: 3,
    points: 10,
    segments: 1,
    snapped: 10,
    source: { ...source, dataset: 'Estudo de Mobilidade do Centro Histórico' },
  },
  'cameras/sites.json': {
    sites: [
      {
        corridors: [],
        direction: 'BC',
        id: 'c1',
        kind: 'controlador',
        label: 'Av. Assis Brasil 4908 - BC',
        lanes: 3,
        lat: -30,
        limit_kmh: 60,
        located_by: 'cadastro',
        lon: -51.1,
        series: { '2025': [23093, null, ...Array(10).fill(22000)] },
      },
    ],
    source,
    unit: 'UVP',
  },
  'crashes/grid.json': crashFile,
  'supply/blue_zone.geojson': {
    features: [
      {
        geometry: { coordinates: [], type: 'LineString' },
        properties: {
          kind: 'CONVENCIONAL',
          number: '841',
          side: 'OPOSTO',
          spaces: 2,
          street: 'AV. MAUA',
        },
        type: 'Feature',
      },
    ],
    type: 'FeatureCollection',
  },
  'supply/bus_corridors.geojson': { features: [], type: 'FeatureCollection' },
  'supply/signals.geojson': {
    features: [
      {
        geometry: { coordinates: [-51.2, -30], type: 'Point' },
        properties: {
          code: 'X',
          description: 'BORGES X RIACHUELO',
          detector: 'NAO',
          kind: 'MISTO',
          status: 'ATIVO',
        },
        type: 'Feature',
      },
    ],
    type: 'FeatureCollection',
  },
  'transit/stops.json': stopsFile,
};

beforeEach(() => {
  globalThis.ResizeObserver ??= class {
    disconnect() {}
    observe() {}
    unobserve() {}
  };
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      const key = url.replace(/^.*\/data\//, '');
      return Promise.resolve({
        json: () => Promise.resolve(files[key]),
        ok: key in files,
        status: 404,
      });
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('helpers das camadas', () => {
  it('conta ônibus da hora ou do dia', () => {
    expect(stopsAtHour(stopsFile, 8).features[0]?.properties.buses).toBe(12);
    expect(stopsAtHour(stopsFile, null).features[0]?.properties.buses).toBe(35);
  });

  it('só publica trechos de GPS com velocidade na hora', () => {
    const segments = files['bus_gps/segments.geojson'] as Parameters<typeof gpsAtHour>[0];
    expect(gpsAtHour(segments, 8).features[0]?.properties).toEqual({
      name: 'BORGES DE MEDEIROS',
      points: 120,
      speed: 14.5,
      stopped: 0.3,
    });
    expect(gpsAtHour(segments, 9).features).toEqual([]);
  });

  it('desenha quadrados só onde houve sinistro no ano e gravidade', () => {
    expect(crashSquares(crashFile, '2025', 2).features).toHaveLength(1);
    expect(crashSquares(crashFile, '2026', 2).features).toHaveLength(0);
  });

  it('ordena a série mensal dos controladores', () => {
    const series = cameraSeries({
      corridors: [],
      direction: 'BC',
      id: 'c',
      kind: 'redutor',
      label: 'x',
      lat: 0,
      located_by: 'cadastro',
      lon: 0,
      series: { '2024': [1, 2], '2023': [3] },
    });
    expect(series.map((r) => r.month)).toEqual(['2023-01', '2024-01', '2024-02']);
  });

  it('rotula classes inteiras sem sobreposição', () => {
    expect(integerRange(1, 2)).toBe('1');
    expect(integerRange(2, 5)).toBe('2 a 4');
    expect(integerRange(13, undefined)).toBe('13 ou mais');
  });
});

describe('visualizações das camadas', () => {
  it('ônibus: paradas por hora e GPS do Centro', async () => {
    render(<BusesView />);
    expect(
      await screen.findByRole('button', { name: /Parada A \| 12 ônibus 08:00 às 09:00/ }),
    ).toBeTruthy();
    fireEvent.click(screen.getByLabelText('Velocidade dos ônibus no Centro (GPS)'));
    expect(screen.getByRole('button', { name: /BORGES DE MEDEIROS \| 15 km\/h/ })).toBeTruthy();
    expect(screen.getByText(/2019-10-21 a 2019-10-25/)).toBeTruthy();
  });

  it('oferta: liga camadas e abre o fluxo do controlador', async () => {
    render(<SupplyView />);
    fireEvent.click(await screen.findByRole('button', { name: /Av. Assis Brasil 4908 - BC/ }));
    expect(screen.getByText(/limite de 60 km\/h · 3 faixas/)).toBeTruthy();
    fireEvent.click(screen.getByLabelText(/Semáforos/));
    expect(screen.queryByRole('button', { name: /BORGES X RIACHUELO/ })).toBeNull();
    expect(screen.getByRole('button', { name: /AV. MAUA, 841 \| 2 vagas/ })).toBeTruthy();
  });

  it('sinistros: começa no último ano completo e troca a gravidade', async () => {
    render(<CrashesView />);
    expect(await screen.findByRole('button', { name: /5 sinistros em 2025/ })).toBeTruthy();
    expect(screen.getByRole('option', { name: '2026 (parcial)' })).toBeTruthy();
    fireEvent.click(screen.getByRole('tab', { name: 'Com vítima grave ou fatal' }));
    expect(screen.getByRole('button', { name: /1 sinistros em 2025/ })).toBeTruthy();
  });
});
