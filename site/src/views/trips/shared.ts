import type { ZoneProperties } from '../../data/edom';
import { SEQUENTIAL } from '../../viz/palette';

// Quantos fluxos entre zonas aparecem no mapa, dos maiores para os menores.
export const MAX_LINES = 60;

export function zoneLabel(props: Pick<ZoneProperties, 'in_city' | 'name' | 'zone'>): string {
  return props.in_city ? `Zona ${props.zone}` : (props.name ?? `Zona ${props.zone}`);
}

/** Cor da classe `index` na rampa sequencial; classes além da rampa ficam na mais escura. */
export function sequentialColor(index: number): string {
  return SEQUENTIAL[Math.min(Math.max(index, 0), SEQUENTIAL.length - 1)] ?? SEQUENTIAL[5];
}
