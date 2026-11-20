import { SlidingTabs } from '@precisa-saude/ui/navigation';
import type { ExpressionSpecification } from 'maplibre-gl';
import { useEffect, useMemo, useState } from 'react';

import {
  type CountsFile,
  type CountSurvey,
  filterSurveys,
  loadCounts,
  type Subject,
  SUBJECT_LABELS,
  toPoints,
} from '../../data/counts';
import { quantileBreaks } from '../../data/edom';
import { formatInteger } from '../../data/format';
import { FOCUS_CORRIDORS } from '../../data/load';
import type { LineCollection } from '../../map/PointMap';
import { PointMap } from '../../map/PointMap';
import { integerRange } from '../../viz/legend';
import { CATEGORICAL, SEQUENTIAL } from '../../viz/palette';
import { SourceNote } from '../SourceNote';
import { sequentialColor } from '../trips/shared';
import { SurveyDetail } from './SurveyDetail';

type ColorMode = 'metodo' | 'volume';
const SUBJECTS: Subject[] = ['veiculos', 'pedestres', 'ciclistas'];

function volumeColor(breaks: number[]): ExpressionSpecification {
  const stops: (number | string)[] = [sequentialColor(0)];
  breaks.forEach((value, i) => stops.push(value, sequentialColor(i + 1)));
  return ['step', ['get', 'peak'], ...stops] as unknown as ExpressionSpecification;
}

const METHOD_COLOR = [
  'case',
  ['get', 'exact'],
  CATEGORICAL[0],
  CATEGORICAL[1],
] as unknown as ExpressionSpecification;

export function CountsView() {
  const [data, setData] = useState<{ corridors: LineCollection; file: CountsFile } | null>(null);
  const [error, setError] = useState<null | string>(null);
  const [subject, setSubject] = useState<Subject>('veiculos');
  const [since, setSince] = useState(2015);
  const [corridor, setCorridor] = useState('');
  const [mode, setMode] = useState<ColorMode>('volume');
  const [selected, setSelected] = useState<null | string>(null);

  useEffect(() => {
    loadCounts().then(setData, (e: unknown) =>
      setError(e instanceof Error ? e.message : String(e)),
    );
  }, []);

  const surveys = useMemo(
    () => (data ? filterSurveys(data.file.surveys, { corridor, since, subject }) : []),
    [data, corridor, since, subject],
  );
  const points = useMemo(() => toPoints(surveys), [surveys]);
  const breaks = useMemo(
    () =>
      quantileBreaks(
        points.features.map((f) => Number(f.properties.peak)),
        SEQUENTIAL.length,
      ),
    [points],
  );
  const minimumPeak = useMemo(() => {
    const positive = points.features.map((f) => Number(f.properties.peak)).filter((v) => v > 0);
    return positive.length ? Math.min(...positive) : 0;
  }, [points]);
  const years = useMemo(() => {
    const all = (data?.file.surveys ?? []).map((s) => s.year ?? 0).filter((y) => y > 0);
    return all.length ? [Math.min(...all), Math.max(...all)] : [2015, 2026];
  }, [data]);
  const current: CountSurvey | undefined = data?.file.surveys.find((s) => s.id === selected);

  if (error) return <p role="alert">Não foi possível carregar os dados: {error}</p>;
  if (!data) return <p aria-busy="true">Carregando as contagens…</p>;

  const { summary } = data.file;
  const unread = summary.files - (summary.by_status.ok ?? 0);

  return (
    <section aria-labelledby="contagens-titulo" className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h2 className="text-2xl font-semibold" id="contagens-titulo">
          Contagens de tráfego
        </h2>
        <p className="text-muted-foreground max-w-prose">
          Contagens classificadas feitas pela EPTC em cruzamentos, em geral em um dia útil, das 7h
          às 20h, em intervalos de 15 minutos. Cada ponto é uma pesquisa; o mesmo cruzamento pode
          ter sido contado em anos diferentes.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-4">
        <SlidingTabs
          activeKey={subject}
          aria-label="Tipo de contagem"
          items={SUBJECTS.map((key) => ({ key, label: SUBJECT_LABELS[key] }))}
          size="sm"
          onChange={(key) => {
            setSubject(key as Subject);
            setSelected(null);
          }}
        />
        <label className="flex items-center gap-2 text-sm">
          Desde
          <select
            className="border-border bg-card rounded-md border px-2 py-1"
            value={since}
            onChange={(e) => setSince(Number(e.target.value))}
          >
            {Array.from({ length: (years[1] ?? 2026) - (years[0] ?? 2015) + 1 }, (_, i) => {
              const year = (years[0] ?? 2015) + i;
              return (
                <option key={year} value={year}>
                  {year}
                </option>
              );
            })}
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
        <SlidingTabs
          activeKey={mode}
          aria-label="Cor dos pontos"
          items={[
            { key: 'volume', label: 'Volume na hora pico' },
            { key: 'metodo', label: 'Localização' },
          ]}
          size="sm"
          onChange={(key) => setMode(key as ColorMode)}
        />
      </div>

      <PointMap
        color={mode === 'volume' ? volumeColor(breaks) : METHOD_COLOR}
        context={corridor ? undefined : data.corridors}
        label={`Mapa com ${surveys.length} contagens de ${SUBJECT_LABELS[subject].toLowerCase()}`}
        points={points}
        selectedId={selected}
        tooltip={(p) => [
          String(p.name),
          `${String(p.year)}: ${formatInteger(Number(p.peak))} na hora pico`,
          `Localizado por ${String(p.method)}`,
        ]}
        onSelect={setSelected}
      />
      <MapLegend breaks={breaks} minimum={minimumPeak} mode={mode} />
      <p className="text-muted-foreground text-xs">
        {formatInteger(surveys.length)} pesquisas no filtro. Das {formatInteger(summary.files)}{' '}
        planilhas encontradas, {formatInteger(summary.read_and_located)} foram lidas e localizadas e{' '}
        {formatInteger(unread)} não puderam ser lidas; a lista completa, com o motivo de cada uma,
        está no relatório do repositório (data/reports/counts.csv). As linhas cinzas são os quatro
        corredores de foco.
      </p>

      {current ? (
        <SurveyDetail survey={current} />
      ) : (
        <p className="text-muted-foreground text-sm">
          Clique em um ponto para ver o perfil da contagem.
        </p>
      )}
      <SourceNote
        sources={[{ href: data.file.source.href, label: `${data.file.source.name}: contagens` }]}
      />
    </section>
  );
}

function MapLegend({
  breaks,
  minimum,
  mode,
}: {
  breaks: number[];
  minimum: number;
  mode: ColorMode;
}) {
  if (mode === 'metodo') {
    return (
      <ul aria-label="Legenda do mapa" className="text-muted-foreground flex gap-4 text-xs">
        <li className="flex items-center gap-1.5">
          <span
            aria-hidden
            className="size-3 rounded-full"
            style={{ background: CATEGORICAL[0] }}
          />
          Exata: cruzamento ou endereço com número
        </li>
        <li className="flex items-center gap-1.5">
          <span
            aria-hidden
            className="size-3 rounded-full"
            style={{ background: CATEGORICAL[1] }}
          />
          Aproximada: trecho, vias próximas ou número estimado
        </li>
      </ul>
    );
  }
  const classes = [minimum, ...breaks];
  return (
    <ul aria-label="Legenda do mapa" className="text-muted-foreground flex flex-wrap gap-3 text-xs">
      <li className="font-medium">Volume na hora pico:</li>
      {classes.map((from, i) => (
        <li key={i} className="flex items-center gap-1.5">
          <span
            aria-hidden
            className="size-3 rounded-full"
            style={{ background: sequentialColor(i) }}
          />
          {integerRange(from, breaks[i])}
        </li>
      ))}
    </ul>
  );
}
