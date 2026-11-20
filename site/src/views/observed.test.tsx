import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { CountsView } from './counts/CountsView';
import { SpeedsView } from './speeds/SpeedsView';

// O mapa precisa de WebGL. Aqui ele vira uma lista de botões, um por ponto, com o
// texto do tooltip: assim dá para conferir o que o mapa receberia e a seleção.
vi.mock('../map/PointMap', () => ({
  PointMap: ({
    label,
    onSelect,
    points,
    tooltip,
  }: {
    label: string;
    onSelect: (id: string) => void;
    points: { features: { properties: { id: string } }[] };
    tooltip: (p: { id: string }) => string[];
  }) => (
    <div aria-label={label} role="region">
      {points.features.map((f) => (
        <button key={f.properties.id} type="button" onClick={() => onSelect(f.properties.id)}>
          {tooltip(f.properties)[0]}
        </button>
      ))}
    </div>
  ),
}));

const source = { href: 'https://exemplo.test/eptc', name: 'EPTC' };
const files: Record<string, unknown> = {
  'counts/corridors.geojson': { features: [], type: 'FeatureCollection' },
  'counts/profiles/2019.json': { a: { first: 420, step: 15, values: [10, 20, null, 40] } },
  'counts/surveys.json': {
    source,
    summary: { by_status: { ok: 2, unsupported: 1 }, files: 3, read_and_located: 2 },
    surveys: [
      {
        classes: 'VL',
        corridors: ['Av. Ipiranga'],
        date: '2019-03-26',
        flags: ['incompleta'],
        hourly: Array.from({ length: 24 }, (_, h) => (h === 7 ? 70 : null)),
        id: 'a',
        lat: -30,
        located_by: 'cruzamento',
        lon: -51,
        month: 3,
        name: 'Av. Ipiranga x Rua B',
        peak_hour: 7,
        source: 'pesquisas-fluxo',
        subject: 'veiculos',
        year: 2019,
      },
      {
        classes: 'NA FAIXA',
        corridors: [],
        date: '2018-01-01',
        flags: [],
        hourly: [],
        id: 'p',
        lat: -30,
        located_by: 'endereço',
        lon: -51,
        month: 1,
        name: 'Pedestres na Rua C',
        peak_hour: null,
        source: 'pesquisas-fluxo',
        subject: 'pedestres',
        year: 2018,
      },
    ],
  },
  'speeds/surveys.json': {
    bins_kmh: [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50],
    source,
    summary: { by_status: { ok: 1 }, files: 1, read_and_located: 1 },
    surveys: [
      {
        above_limit: 0.877,
        address: 'R Sarmento Leite, 320',
        by_class: { VL: 100 },
        corridors: [],
        date: '2008-05-01',
        direction: 'CB',
        flags: [],
        histogram: [0, 0, 0, 0, 0, 0, 3, 3, 24, 33, 24, 0],
        id: 's',
        lat: -30.03,
        limit_kmh: 40,
        located_by: 'endereço',
        lon: -51.22,
        median: 48,
        p85: 55,
        vehicles: 106,
        year: 2008,
      },
    ],
  },
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

describe('CountsView', () => {
  it('lista as contagens do filtro, abre o perfil e cita a fonte', async () => {
    render(<CountsView />);
    const point = await screen.findByRole('button', { name: 'Av. Ipiranga x Rua B' });
    expect(screen.queryByRole('button', { name: 'Pedestres na Rua C' })).toBeNull();
    expect(screen.getByText(/3 planilhas encontradas, 2 foram lidas/)).toBeTruthy();
    fireEvent.click(point);
    expect(await screen.findByText(/pesquisa incompleta/)).toBeTruthy();
    fireEvent.click(await screen.findByText('Ver tabela'));
    expect(screen.getByRole('rowheader', { name: '07:30' })).toBeTruthy();
    expect(screen.getByText('sem dado')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'EPTC: contagens' })).toBeTruthy();
  });

  it('troca para pedestres e filtra por corredor', async () => {
    render(<CountsView />);
    fireEvent.click(await screen.findByRole('tab', { name: 'Pedestres' }));
    fireEvent.change(screen.getByLabelText('Desde'), { target: { value: '2018' } });
    expect(screen.getByRole('button', { name: 'Pedestres na Rua C' })).toBeTruthy();
    fireEvent.click(screen.getByRole('tab', { name: 'Veículos' }));
    fireEvent.change(screen.getByLabelText('Corredor'), { target: { value: 'Av. Ipiranga' } });
    expect(screen.getByRole('button', { name: 'Av. Ipiranga x Rua B' })).toBeTruthy();
  });
});

describe('SpeedsView', () => {
  it('mostra limite, percentis e o histograma da pesquisa escolhida', async () => {
    render(<SpeedsView />);
    fireEvent.click(await screen.findByRole('button', { name: 'R Sarmento Leite, 320' }));
    expect(screen.getByText('40 km/h')).toBeTruthy();
    expect(screen.getByText('55 km/h')).toBeTruthy();
    expect(screen.getByText('87,7%')).toBeTruthy();
    expect(screen.getByText(/centro → bairro/)).toBeTruthy();
    expect(screen.getByRole('link', { name: 'EPTC: pesquisas de velocidade' })).toBeTruthy();
  });
});
