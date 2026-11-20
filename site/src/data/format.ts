const integer = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 });
const percent = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1, style: 'percent' });

export function formatInteger(value: number): string {
  return integer.format(value);
}

export function formatPercent(share: number): string {
  return percent.format(share);
}

export function formatClock(minutes: number): string {
  const h = Math.floor(minutes / 60) % 24;
  const m = minutes % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

export function formatHourRange(hour: number): string {
  return `${formatClock(hour * 60)} às ${formatClock((hour + 1) * 60)}`;
}
