import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { App } from './App';
import { SOURCES } from './sources';

afterEach(cleanup);

describe('App', () => {
  it('mostra o título e a situação do projeto', () => {
    render(<App />);
    expect(screen.getByRole('heading', { level: 1, name: 'sim-poa' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Em construção' })).toBeTruthy();
  });

  it('atribui cada fonte de dados com um link', () => {
    render(<App />);
    for (const source of SOURCES) {
      const link = screen.getByRole('link', { name: source.name });
      expect(link.getAttribute('href')).toBe(source.href);
    }
    expect(screen.getByText(/© colaboradores do OpenStreetMap/)).toBeTruthy();
    expect(screen.getByText(/não tem vínculo com a EPTC/)).toBeTruthy();
  });
});
