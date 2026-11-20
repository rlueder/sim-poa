import { ChartContainer, type ChartContainerProps } from '@precisa-saude/ui/charts';
import type { ExpressionSpecification } from 'maplibre-gl';
import { useEffect, useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { formatInteger, formatPercent } from '../../data/format';
import { FOCUS_CORRIDORS } from '../../data/load';
import {
  DIRECTION_LABELS,
  EXCESS_BREAKS,
  loadSpeeds,
  type SpeedsFile,
  type SpeedSurvey,
  toPoints,
  trimmedHistogram,
} from '../../data/speeds';
import { PointMap } from '../../map/PointMap';
import { CATEGORICAL, DIVERGING, INK } from '../../viz/palette';
import { SourceNote } from '../SourceNote';

const Responsive = ResponsiveContainer as unknown as ChartContainerProps['ResponsiveContainer'];

const EXCESS_COLOR = [
  'step',
  ['get', 'excess'],
  ...DIVERGING.flatMap((color, i) => (i === 0 ? [color] : [EXCESS_BREAKS[i - 1], color])),
] as unknown as ExpressionSpecification;

const LEGEND = [
  'mais de 10 abaixo',
  '5 a 10 abaixo',
  '2 a 5 abaixo',
  'no limite (±2)',
  '2 a 5 acima',
  '5 a 10 acima',
  'mais de 10 acima',
];

export function SpeedsView() {
  const [data, setData] = useState<null | SpeedsFile>(null);
  const [error, setError] = useState<null | string>(null);
  const [since, setSince] = useState(2003);
  const [corridor, setCorridor] = useState('');
  const [selected, setSelected] = useState<null | string>(null);

  useEffect(() => {
    loadSpeeds().then(setData, (e: unknown) =>
      setError(e instanceof Error ? e.message : String(e)),
    );
  }, []);

  const surveys = useMemo(
    () =>
      (data?.surveys ?? []).filter(
        (s) =>
          s.limit_kmh !== null &&
          (s.year ?? 0) >= since &&
          (corridor === '' || s.corridors.includes(corridor)),
      ),
    [data, since, corridor],
  );
  const points = useMemo(() => toPoints(surveys), [surveys]);
  const current = data?.surveys.find((s) => s.id === selected);

  if (error) return <p role="alert">Não foi possível carregar os dados: {error}</p>;
  if (!data) return <p aria-busy="true">Carregando as pesquisas de velocidade…</p>;

  return (
    <section aria-labelledby="velocidades-titulo" className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h2 className="text-2xl font-semibold" id="velocidades-titulo">
          Velocidade praticada
        </h2>
        <p className="text-muted-foreground max-w-prose">
          Pesquisas de velocidade pontual da EPTC, com radar portátil, de 2003 a 2021. A cor compara
          o percentil 85 (a velocidade que 85% dos veículos não ultrapassam) com a velocidade
          regulamentar do trecho. Essas pesquisas costumam ser feitas onde há queixa de excesso de
          velocidade, então os pontos não são uma amostra da cidade.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-4">
        <label className="flex items-center gap-2 text-sm">
          Desde
          <select
            className="border-border bg-card rounded-md border px-2 py-1"
            value={since}
            onChange={(e) => setSince(Number(e.target.value))}
          >
            {Array.from({ length: 19 }, (_, i) => 2003 + i).map((year) => (
              <option key={year} value={year}>
                {year}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm">
          Corredor
          <select
            className="border-border bg-card rounded-md border px-2 py-1"
            value={corridor}
            onChange={(e) => setCorridor(e.target.value)}
          >
            <option value="">Todos</option>
            {FOCUS_CORRIDORS.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
      </div>

      <PointMap
        color={EXCESS_COLOR}
        label={`Mapa com ${surveys.length} pesquisas de velocidade`}
        points={points}
        selectedId={selected}
        tooltip={(p) => [
          String(p.address),
          `${String(p.year)}: percentil 85 de ${formatInteger(Number(p.p85))} km/h`,
          `limite de ${formatInteger(Number(p.limit))} km/h`,
        ]}
        onSelect={setSelected}
      />
      <ul
        aria-label="Legenda do mapa"
        className="text-muted-foreground flex flex-wrap gap-3 text-xs"
      >
        <li className="font-medium">Percentil 85 em relação ao limite, km/h:</li>
        {LEGEND.map((label, i) => (
          <li key={label} className="flex items-center gap-1.5">
            <span
              aria-hidden
              className="size-3 rounded-full"
              style={{ background: DIVERGING[i] }}
            />
            {label}
          </li>
        ))}
      </ul>
      <p className="text-muted-foreground text-xs">
        {formatInteger(surveys.length)} pesquisas no filtro. Das {formatInteger(data.summary.files)}{' '}
        planilhas encontradas, {formatInteger(data.summary.read_and_located)} foram lidas e
        localizadas; a lista completa, com o motivo das demais, está em data/reports/speeds.csv.
      </p>

      {current ? (
        <SpeedDetail bins={data.bins_kmh} survey={current} />
      ) : (
        <p className="text-muted-foreground text-sm">
          Clique em um ponto para ver a distribuição das velocidades.
        </p>
      )}
      <SourceNote
        sources={[
          { href: data.source.href, label: `${data.source.name}: pesquisas de velocidade` },
        ]}
      />
    </section>
  );
}

function SpeedDetail({ bins, survey }: { bins: number[]; survey: SpeedSurvey }) {
  const rows = trimmedHistogram(bins, survey.histogram);
  return (
    <article className="border-border flex flex-col gap-3 rounded-lg border p-4">
      <header>
        <h3 className="font-semibold">{survey.address}</h3>
        <p className="text-muted-foreground text-sm">
          {survey.date || survey.year}
          {survey.direction &&
            ` · sentido ${DIRECTION_LABELS[survey.direction] ?? survey.direction}`}
          {` · ${formatInteger(survey.vehicles)} veículos medidos · localizado por ${survey.located_by}`}
        </p>
      </header>
      <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <Stat label="Limite" value={`${formatInteger(survey.limit_kmh ?? 0)} km/h`} />
        <Stat label="Mediana" value={`${formatInteger(survey.median)} km/h`} />
        <Stat label="Percentil 85" value={`${formatInteger(survey.p85)} km/h`} />
        <Stat
          label="Acima do limite"
          value={survey.above_limit === null ? 'sem limite' : formatPercent(survey.above_limit)}
        />
      </dl>
      <figure className="flex flex-col gap-2">
        <figcaption className="text-sm font-medium">
          Veículos por faixa de 5 km/h; a linha marca a faixa que contém o limite
        </figcaption>
        <ChartContainer height={200} ResponsiveContainer={Responsive}>
          <BarChart data={rows} margin={{ bottom: 0, left: 8, right: 16, top: 8 }}>
            <CartesianGrid stroke="#e1e0d9" vertical={false} />
            <XAxis dataKey="from" stroke={INK.muted} />
            <YAxis allowDecimals={false} stroke={INK.muted} width={40} />
            <Tooltip
              formatter={(value) => [formatInteger(Number(value)), 'veículos']}
              labelFormatter={(label) => `${String(label)} a ${Number(label) + 5} km/h`}
            />
            <Bar
              dataKey="vehicles"
              fill={CATEGORICAL[0]}
              isAnimationActive={false}
              radius={[4, 4, 0, 0]}
            />
            {survey.limit_kmh !== null && (
              <ReferenceLine
                stroke={INK.primary}
                strokeWidth={2}
                x={Math.floor(survey.limit_kmh / 5) * 5}
              />
            )}
          </BarChart>
        </ChartContainer>
      </figure>
    </article>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-lg font-semibold tabular-nums">{value}</dd>
    </div>
  );
}
