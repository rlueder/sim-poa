import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { App } from './App';
import { SOURCES } from './sources';

// A visualização de viagens carrega dados e o MapLibre; aqui só importa a navegação.
vi.mock('./views/trips/TripsView', () => ({
  TripsView: () => <h2>Viagens dos moradores</h2>,
}));

afterEach(() => {
  cleanup();
  window.location.hash = '';
});

describe('App', () => {
  it('abre na visualização de viagens', async () => {
    render(<App />);
    expect(screen.getByRole('heading', { level: 1, name: 'sim-poa' })).toBeTruthy();
    expect(await screen.findByRole('heading', { name: 'Viagens dos moradores' })).toBeTruthy();
    expect(screen.getByText(/não tem vínculo com a EPTC/)).toBeTruthy();
  });

  it('a aba Sobre atribui cada fonte de dados com um link', async () => {
    window.location.hash = '#sobre';
    render(<App />);
    expect(await screen.findByRole('heading', { name: 'Em construção' })).toBeTruthy();
    for (const source of SOURCES) {
      const link = screen.getByRole('link', { name: source.name });
      expect(link.getAttribute('href')).toBe(source.href);
    }
    expect(screen.getByText(/© colaboradores do OpenStreetMap/)).toBeTruthy();
  });

  it('segue mudanças no endereço', async () => {
    render(<App />);
    act(() => {
      window.location.hash = '#sobre';
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    });
    expect(await screen.findByRole('heading', { name: 'Em construção' })).toBeTruthy();
  });
});
