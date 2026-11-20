import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { Collection } from '../data/layers';
import {
  averageSpeed,
  type Corridor,
  corridorRows,
  groupSignals,
  type NetworkSignal,
  type NetworkSummary,
  signalGroup,
} from '../data/network';
import { NetworkView } from './network/NetworkView';

// O mapa vira uma lista: uma entrada por feição visível de camada interativa,
// com o texto do tooltip.
vi.mock('../map/LayerMap', () => ({
  LayerMap: ({
    label,
    layers,
    tooltip,
  }: {
    label: string;
    layers: {
      data: { features: { properties: Record<string, unknown> }[] };
      id: string;
      interactive?: boolean;
      visible: boolean;
    }[];
    tooltip: (id: string, p: Record<string, unknown>) => string[];
  }) => (
    <div aria-label={label} role="region">
      {layers
        .filter((l) => l.visible)
        .flatMap((l) =>
          l.data.features.map((f, i) => (
            <p key={`${l.id}-${i}`}>
              {l.interactive ? tooltip(l.id, f.properties).join(' | ') : `${l.id}: destaque`}
            </p>
          )),
        )}
    </div>
  ),
}));

const point = { coordinates: [-51.2, -30.03], type: 'Point' };
const line = { coordinates: [], type: 'LineString' };

function signal(code: string, status: NetworkSignal['status']) {
  return {
    geometry: point,
    properties: {
      code,
      description: `${code} X PEDESTRE`,
      kind: 'MISTO',
      source: status === 'só na rede' || status === 'desligado' ? 'rede' : 'cadastro',
      status,
    } satisfies NetworkSignal,
    type: 'Feature' as const,
  };
}

const signals: Collection<NetworkSignal> = {
  features: [
    signal('A', 'na rede'),
    signal('B', 'ligado pelo cadastro'),
    signal('C', 'sem semáforo na rede'),
    signal('D', 'só na rede'),
    signal('E', 'fora do município'),
  ],
  type: 'FeatureCollection',
};

function corridor(name: string, direction: Corridor['direction'], minutes: number) {
  return {
    geometry: line,
    properties: {
      corridor: name,
      direction,
      free_flow_min: minutes,
      length_km: 6,
      on_corridor: 0.9,
      routed: true,
    } satisfies Corridor,
    type: 'Feature' as const,
  };
}

const corridors: Collection<Corridor> = {
  features: [
    corridor('Ipiranga', 'ida', 6),
    corridor('Ipiranga', 'volta', 7.5),
    corridor('Sertório', 'ida', 9),
  ],
  type: 'FeatureCollection',
};

const counts = {
  inventario: 4,
  inventario_casado: 2,
  inventario_sem_semaforo_na_rede: 2,
  rede: 3,
  rede_casada: 2,
  rede_sem_registro_no_inventario: 1,
};

const summary: NetworkSummary = {
  network: { drivable_km: 6447, junctions: 26127, traffic_lights: 1625 },
  osm: { extract: 'sul-261119.osm.pbf' },
  reachability: { pairs: 11130, without_route: 0 },
  signals: {
    added: 1,
    after: { ...counts, inventario_casado: 3, inventario_sem_semaforo_na_rede: 1 },
    before: counts,
    removed: 1,
    unplaced: 1,
    unplaced_by_kind: { EXCLUSIVO: 1 },
  },
  smoke_test: { inserted: 3600, teleports: 0 },
  zones: { city_zones: 106 },
};

const files: Record<string, unknown> = {
  'network/corridors.geojson': corridors,
  'network/gates.geojson': {
    features: [
      {
        geometry: line,
        properties: { direction: 'entrada', highway: 'motorway', lanes: 3, name: 'Freeway' },
        type: 'Feature',
      },
    ],
    type: 'FeatureCollection',
  },
  'network/roads.geojson': {
    features: [
      {
        geometry: line,
        properties: { highway: 'primary', lanes: 3, name: 'Avenida Ipiranga', speed_kmh: 60 },
        type: 'Feature',
      },
    ],
    type: 'FeatureCollection',
  },
  'network/signals.geojson': signals,
  'network/summary.json': summary,
};

beforeEach(() => {
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

describe('helpers da rede', () => {
  it('agrupa os semáforos em três cores e tira os de fora do município', () => {
    expect(signalGroup('ligado pelo cadastro')).toBe('ambos');
    expect(signalGroup('desligado')).toBe('so-rede');
    expect(signalGroup('fora do município')).toBeNull();
    expect(groupSignals(signals).features.map((f) => f.properties.group)).toEqual([
      'ambos',
      'ambos',
      'so-cadastro',
      'so-rede',
    ]);
  });

  it('junta os dois sentidos de cada corredor', () => {
    const rows = corridorRows(corridors);
    expect(rows.map((r) => [r.corridor, r.directions.length])).toEqual([
      ['Ipiranga', 2],
      ['Sertório', 1],
    ]);
    expect(averageSpeed(corridors.features[0]!.properties)).toBe(60);
  });
});

describe('NetworkView', () => {
  it('mostra os números da rede, os semáforos e os corredores', async () => {
    render(<NetworkView />);
    expect(await screen.findByText('Rede viária do modelo')).toBeTruthy();
    expect(screen.getByText('11.130 de 11.130')).toBeTruthy();
    expect(screen.getByText(/Só no cadastro da EPTC \(1\)/)).toBeTruthy();
    expect(
      screen.getByText('C X PEDESTRE | Sem cruzamento da rede a 30 m para pôr o semáforo'),
    ).toBeTruthy();
    expect(
      screen.getByText(/Outros 1 semáforos da rede ficam nos municípios vizinhos/),
    ).toBeTruthy();
    expect(screen.getByText('Avenida Ipiranga | 3 faixas por sentido · 60 km/h')).toBeTruthy();
    expect(screen.getAllByRole('row')).toHaveLength(4);
  });

  it('troca a cor das vias, mostra entradas e destaca um corredor', async () => {
    render(<NetworkView />);
    await screen.findByText('Rede viária do modelo');
    expect(screen.getByText('4 ou mais faixas')).toBeTruthy();
    fireEvent.click(screen.getByLabelText('velocidade máxima'));
    expect(screen.getByText('menos de 40 km/h')).toBeTruthy();
    expect(screen.getByText('80 km/h ou mais')).toBeTruthy();

    fireEvent.click(screen.getByLabelText(/Entradas e saídas da cidade/));
    expect(screen.getByText('Freeway | Entrada da cidade · 3 faixas')).toBeTruthy();

    fireEvent.click(screen.getAllByRole('button', { name: 'ver no mapa' })[0]!);
    expect(screen.getAllByText('corridor: destaque')).toHaveLength(2);
    expect(screen.getByRole('button', { name: 'tirar do mapa' })).toBeTruthy();
  });
});
