import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { EdomData } from '../../data/edom';
import { TripsView } from './TripsView';

// O MapLibre precisa de WebGL, que o jsdom não tem. O mapa em si é conferido
// no navegador; aqui valem os controles, o gráfico, a tabela e as fontes.
vi.mock('../../map/BaseMap', () => ({
  BaseMap: ({ label }: { label: string }) => <div aria-label={label} role="region" />,
}));

const data: EdomData = {
  lines: {
    min_records: 5,
    pairs: [{ by_group: { ativo: 10 }, d: 2, o: 1, records: 6, trips: 10 }],
  },
  profile: {
    series: { TRABALHO: Array.from({ length: 96 }, (_, i) => (i === 28 ? 100 : 0)) },
    slot_minutes: 15,
    slots: Array.from({ length: 96 }, (_, i) => i * 15),
    window_minutes: 60,
  },
  shapes: { features: [], type: 'FeatureCollection' },
  validation: {
    checks: [
      { name: 'Viagens por dia útil', note: 'tolerância de 1%', ok: true, ours: 100, report: 100 },
      { name: 'Hora pico da tarde', note: 'sem total', ok: false, ours: 5, report: null },
    ],
    source: { dataset: 'EDOM 2023', href: 'https://exemplo.test/eptc', name: 'EPTC' },
  },
  zones: { centroids: {}, zones: [] },
};

beforeEach(() => {
  globalThis.ResizeObserver ??= class {
    disconnect() {}
    observe() {}
    unobserve() {}
  };
  const files: Record<string, unknown> = {
    'desire_lines.json': data.lines,
    'profile.json': data.profile,
    'validation.json': data.validation,
    'zones.geojson': data.shapes,
    'zones.json': data.zones,
  };
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      const name = url.split('/').pop() ?? '';
      return Promise.resolve({
        json: () => Promise.resolve(files[name]),
        ok: name in files,
        status: 404,
      });
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('TripsView', () => {
  it('mostra o mapa, a conferência e a fonte com atribuição à EPTC', async () => {
    render(<TripsView />);
    expect(await screen.findByRole('heading', { name: 'Viagens dos moradores' })).toBeTruthy();
    expect(screen.getByRole('region', { name: /viagens produzidas/ })).toBeTruthy();
    expect(screen.getByText(/1 de 2 números reproduzidos/)).toBeTruthy();
    expect(screen.getByRole('link', { name: 'EPTC: EDOM 2023' }).getAttribute('href')).toBe(
      'https://exemplo.test/eptc',
    );
  });

  it('troca origem por destino e filtra por horário', async () => {
    render(<TripsView />);
    fireEvent.click(await screen.findByRole('tab', { name: 'Destino' }));
    expect(screen.getByRole('region', { name: /viagens atraídas/ })).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Horário'), { target: { value: '7' } });
    expect(screen.getByText(/07:00 às 08:00/, { selector: 'p' })).toBeTruthy();
  });

  it('alterna entre gráfico e tabela', async () => {
    render(<TripsView />);
    fireEvent.click(await screen.findByRole('button', { name: 'Ver tabela' }));
    expect(screen.getByRole('columnheader', { name: 'Trabalho' })).toBeTruthy();
    expect(screen.getByRole('rowheader', { name: '07:00' })).toBeTruthy();
  });

  it('avisa quando os dados não carregam', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve({ ok: false, status: 500 })),
    );
    render(<TripsView />);
    expect((await screen.findByRole('alert')).textContent).toMatch(/HTTP 500/);
  });
});
