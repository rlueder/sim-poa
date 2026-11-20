import { formatInteger } from '../data/format';

/**
 * Rótulo de uma classe de contagem inteira. Na expressão `step` do mapa, a classe
 * vai de `from` (inclusive) até o próximo limite (exclusive), então o rótulo
 * termina um antes dele.
 */
export function integerRange(from: number, next: number | undefined): string {
  if (next === undefined) return `${formatInteger(from)} ou mais`;
  const last = Math.ceil(next) - 1;
  return last <= from ? formatInteger(from) : `${formatInteger(from)} a ${formatInteger(last)}`;
}
