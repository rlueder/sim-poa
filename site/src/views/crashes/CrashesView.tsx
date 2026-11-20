import { ChartContainer, type ChartContainerProps } from '@precisa-saude/ui/charts';
import { SlidingTabs } from '@precisa-saude/ui/navigation';
import type { ExpressionSpecification } from 'maplibre-gl';
import { useEffect, useMemo, useState } from 'react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import { quantileBreaks } from '../../data/edom';
import { formatInteger } from '../../data/format';
import { type CrashFile, crashSquares, loadCrashes, type Severity } from '../../data/layers';
import { LayerMap, type MapLayer } from '../../map/LayerMap';
import { integerRange } from '../../viz/legend';
import { CATEGORICAL, INK, SEQUENTIAL } from '../../viz/palette';
import { SourceNote } from '../SourceNote';
import { sequentialColor } from '../trips/shared';

const Responsive = ResponsiveContainer as unknown as ChartContainerProps['ResponsiveContainer'];
const SEVERITIES = ['Todos', 'Com feridos', 'Com vítima grave ou fatal'];

export function CrashesView() {
  const [data, setData] = useState<CrashFile | null>(null);
  const [error, setError] = useState<null | string>(null);
  const [year, setYear] = useState<string>('');
  const [severity, setSeverity] = useState<Severity>(0);

  useEffect(() => {
    loadCrashes().then(
      (file) => {
        setData(file);
        const years = Object.keys(file.summary.by_year).sort();
        // O ano corrente é parcial; o padrão é o último ano completo.
        setYear(years.at(-2) ?? years.at(-1) ?? '');
      },
      (e: unknown) => setError(e instanceof Error ? e.message : String(e)),
    );
  }, []);

  const squares = useMemo(
    () => (data && year ? crashSquares(data, year, severity) : null),
    [data, year, severity],
  );
  const breaks = useMemo(
    () => quantileBreaks(squares?.features.map((f) => f.properties.count) ?? [], SEQUENTIAL.length),
    [squares],
  );
  const layers = useMemo<MapLayer[]>(() => {
    if (!squares) return [];
    const stops: (number | string)[] = [sequentialColor(0)];
    breaks.forEach((value, i) => stops.push(value, sequentialColor(i + 1)));
    return [
      {
        data: squares,
        id: 'crashes',
        interactive: true,
        paint: {
          'fill-color': ['step', ['get', 'count'], ...stops] as unknown as ExpressionSpecification,
          'fill-opacity': 0.8,
        },
        type: 'fill',
        visible: true,
      },
    ];
  }, [squares, breaks]);

  if (error) return <p role="alert">Não foi possível carregar os dados: {error}</p>;
  if (!data || !squares) return <p aria-busy="true">Carregando os sinistros…</p>;

  const years = Object.keys(data.summary.by_year).sort();
  const byYear = years.map((y) => ({ value: data.summary.by_year[y]?.[severity] ?? 0, year: y }));
  const lastYear = years.at(-1);

  return (
    <section aria-labelledby="sinistros-titulo" className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h2 className="text-2xl font-semibold" id="sinistros-titulo">
          Sinistros de trânsito
        </h2>
        <p className="text-muted-foreground max-w-prose">
          Boletins de sinistros registrados pela EPTC desde 2021, contados em quadrados de{' '}
          {data.cell_metres} m. {lastYear} está incompleto: a base vai até o mês da última
          atualização.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-4">
        <label className="flex items-center gap-2 text-sm">
          Ano
          <select
            className="border-border bg-card rounded-md border px-2 py-1"
            value={year}
            onChange={(e) => setYear(e.target.value)}
          >
            {years.map((y) => (
              <option key={y} value={y}>
                {y}
                {y === lastYear ? ' (parcial)' : ''}
              </option>
            ))}
          </select>
        </label>
        <SlidingTabs
          activeKey={String(severity)}
          aria-label="Gravidade"
          items={SEVERITIES.map((label, i) => ({ key: String(i), label }))}
          size="sm"
          onChange={(key) => setSeverity(Number(key) as Severity)}
        />
      </div>

      <LayerMap
        label={`Mapa dos sinistros de ${year}`}
        layers={layers}
        tooltip={(_, p) => [
          `${formatInteger(Number(p.count))} sinistros em ${year}`,
          SEVERITIES[severity] ?? '',
        ]}
      />
      <ul
        aria-label="Legenda do mapa"
        className="text-muted-foreground flex flex-wrap gap-3 text-xs"
      >
        <li className="font-medium">Sinistros por quadrado:</li>
        {[1, ...breaks].map((from, i, all) => (
          <li key={i} className="flex items-center gap-1.5">
            <span
              aria-hidden
              className="size-3 rounded-sm"
              style={{ background: sequentialColor(i) }}
            />
            {integerRange(from, all[i + 1])}
          </li>
        ))}
      </ul>

      <figure className="flex flex-col gap-2">
        <figcaption className="text-sm font-medium">
          {SEVERITIES[severity]}: total na cidade por ano
        </figcaption>
        <ChartContainer height={200} ResponsiveContainer={Responsive}>
          <BarChart data={byYear} margin={{ bottom: 0, left: 8, right: 16, top: 16 }}>
            <CartesianGrid stroke="#e1e0d9" vertical={false} />
            <XAxis
              dataKey="year"
              stroke={INK.muted}
              tickFormatter={(y: string) => (y === lastYear ? `${y} (parcial)` : y)}
            />
            <YAxis stroke={INK.muted} tickFormatter={(v: number) => formatInteger(v)} width={64} />
            <Tooltip formatter={(value) => [formatInteger(Number(value)), 'sinistros']} />
            <Bar
              dataKey="value"
              fill={CATEGORICAL[0]}
              isAnimationActive={false}
              label={{
                fill: INK.secondary,
                fontSize: 11,
                formatter: (v: unknown) => formatInteger(Number(v)),
                position: 'top',
              }}
              radius={[4, 4, 0, 0]}
            />
          </BarChart>
        </ChartContainer>
      </figure>
      <SourceNote
        sources={[{ href: data.source.href, label: `${data.source.name}: sinistros de trânsito` }]}
      />
    </section>
  );
}
