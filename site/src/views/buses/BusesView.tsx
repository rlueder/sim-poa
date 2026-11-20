import type { ExpressionSpecification } from 'maplibre-gl';
import { useEffect, useMemo, useState } from 'react';

import { quantileBreaks } from '../../data/edom';
import { formatHourRange, formatInteger, formatPercent } from '../../data/format';
import { gpsAtHour, loadBuses, stopsAtHour } from '../../data/layers';
import { LayerMap, type MapLayer } from '../../map/LayerMap';
import { integerRange } from '../../viz/legend';
import { INK, SEQUENTIAL } from '../../viz/palette';
import { SourceNote } from '../SourceNote';
import { sequentialColor } from '../trips/shared';

type Data = Awaited<ReturnType<typeof loadBuses>>;

// Faixas fixas de velocidade dos ônibus em movimento, em km/h.
const SPEED_BREAKS = [10, 15, 20, 25, 30];

function stepColor(property: string, breaks: number[]): ExpressionSpecification {
  const stops: (number | string)[] = [sequentialColor(0)];
  breaks.forEach((value, i) => stops.push(value, sequentialColor(i + 1)));
  return ['step', ['get', property], ...stops] as unknown as ExpressionSpecification;
}

export function BusesView() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<null | string>(null);
  const [hour, setHour] = useState<null | number>(8);
  const [showCorridors, setShowCorridors] = useState(true);
  const [showGps, setShowGps] = useState(false);

  useEffect(() => {
    loadBuses().then(setData, (e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  const stops = useMemo(() => (data ? stopsAtHour(data.stops, hour) : null), [data, hour]);
  const breaks = useMemo(
    () => quantileBreaks(stops?.features.map((f) => f.properties.buses) ?? [], SEQUENTIAL.length),
    [stops],
  );
  const gpsHour = hour ?? 8;
  const gps = useMemo(() => (data ? gpsAtHour(data.gps, gpsHour) : null), [data, gpsHour]);

  const layers = useMemo<MapLayer[]>(() => {
    if (!data || !stops || !gps) return [];
    return [
      {
        data: data.corridors,
        id: 'corridors',
        paint: { 'line-color': INK.secondary, 'line-opacity': 0.6, 'line-width': 4 },
        type: 'line',
        visible: showCorridors,
      },
      {
        data: gps,
        id: 'gps',
        interactive: true,
        paint: { 'line-color': stepColor('speed', SPEED_BREAKS), 'line-width': 5 },
        type: 'line',
        visible: showGps,
      },
      {
        data: stops,
        id: 'stops',
        interactive: true,
        paint: {
          'circle-color': stepColor('buses', breaks),
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 2.5, 15, 6],
          'circle-stroke-color': '#fcfcfb',
          'circle-stroke-width': 0.5,
        },
        type: 'circle',
        visible: !showGps,
      },
    ];
  }, [data, stops, gps, breaks, showCorridors, showGps]);

  if (error) return <p role="alert">Não foi possível carregar os dados: {error}</p>;
  if (!data || !stops) return <p aria-busy="true">Carregando os dados de ônibus…</p>;

  const period = hour === null ? 'no dia todo' : formatHourRange(hour);
  return (
    <section aria-labelledby="onibus-titulo" className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h2 className="text-2xl font-semibold" id="onibus-titulo">
          Ônibus
        </h2>
        <p className="text-muted-foreground max-w-prose">
          Ônibus programados por parada, a partir do GTFS da Prefeitura para uma quarta-feira (
          {data.stops.day}). O GTFS só tem horário nos pontos de controle; nas outras paradas, a
          hora de passagem foi interpolada.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-4">
        <label className="flex items-center gap-2 text-sm">
          Horário
          <select
            className="border-border bg-card rounded-md border px-2 py-1"
            value={hour ?? ''}
            onChange={(e) => setHour(e.target.value === '' ? null : Number(e.target.value))}
          >
            <option value="">Dia todo</option>
            {Array.from({ length: 24 }, (_, h) => (
              <option key={h} value={h}>
                {formatHourRange(h)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            checked={showCorridors}
            type="checkbox"
            onChange={(e) => setShowCorridors(e.target.checked)}
          />
          Corredores e faixas exclusivas
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input checked={showGps} type="checkbox" onChange={(e) => setShowGps(e.target.checked)} />
          Velocidade dos ônibus no Centro (GPS)
        </label>
      </div>

      <LayerMap
        label={showGps ? 'Velocidade dos ônibus no Centro' : `Ônibus por parada ${period}`}
        layers={layers}
        tooltip={(id, p) =>
          id === 'stops'
            ? [
                String(p.name),
                `${formatInteger(Number(p.buses))} ônibus ${period}`,
                `${formatInteger(Number(p.routes))} linhas no dia`,
              ]
            : [
                String(p.name),
                `${formatInteger(Number(p.speed))} km/h em movimento (mediana)`,
                `${formatPercent(Number(p.stopped))} dos registros parados`,
              ]
        }
      />
      <ul
        aria-label="Legenda do mapa"
        className="text-muted-foreground flex flex-wrap gap-3 text-xs"
      >
        <li className="font-medium">
          {showGps ? 'Velocidade em movimento, km/h:' : `Ônibus ${period}:`}
        </li>
        {(showGps ? [0, ...SPEED_BREAKS] : [0, ...breaks]).map((from, i, all) => (
          <li key={i} className="flex items-center gap-1.5">
            <span
              aria-hidden
              className="size-3 rounded-full"
              style={{ background: sequentialColor(i) }}
            />
            {integerRange(from, all[i + 1])}
          </li>
        ))}
      </ul>
      {showGps && (
        <p className="text-muted-foreground text-xs">
          GPS dos ônibus no Centro Histórico, dias úteis de {data.gpsSummary.days[0]} a{' '}
          {data.gpsSummary.days[1]}, {formatHourRange(gpsHour)}. Cada ponto foi associado à via mais
          próxima; o mapa mostra a mediana da velocidade dos ônibus em movimento (acima de{' '}
          {data.gpsSummary.moving_kmh} km/h) nos trechos com pelo menos {data.gpsSummary.min_points}{' '}
          registros na hora. É a única medição de velocidade por horário disponível para a cidade, e
          cobre só o Centro.
        </p>
      )}
      <SourceNote
        sources={[
          { href: data.stops.source.href, label: data.stops.source.name },
          {
            href: data.gpsSummary.source.href,
            label: `${data.gpsSummary.source.name}: ${data.gpsSummary.source.dataset} e corredores`,
          },
        ]}
      />
    </section>
  );
}
