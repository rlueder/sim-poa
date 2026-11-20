import { ChartContainer, type ChartContainerProps } from '@precisa-saude/ui/charts';
import { useEffect, useMemo, useState } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { formatInteger } from '../../data/format';
import { cameraPoints, cameraSeries, type CameraSite, loadSupply } from '../../data/layers';
import { LayerMap, type MapLayer } from '../../map/LayerMap';
import { CATEGORICAL, INK } from '../../viz/palette';
import { SourceNote } from '../SourceNote';

const Responsive = ResponsiveContainer as unknown as ChartContainerProps['ResponsiveContainer'];
type Data = Awaited<ReturnType<typeof loadSupply>>;

const KIND_LABELS: Record<string, string> = {
  controlador: 'Controlador eletrônico',
  redutor: 'Redutor eletrônico (lombada)',
};

export function SupplyView() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<null | string>(null);
  const [show, setShow] = useState({ blue: true, cameras: true, signals: true });
  const [selected, setSelected] = useState<null | string>(null);

  useEffect(() => {
    loadSupply().then(setData, (e: unknown) =>
      setError(e instanceof Error ? e.message : String(e)),
    );
  }, []);

  const layers = useMemo<MapLayer[]>(() => {
    if (!data) return [];
    return [
      {
        data: data.blueZone,
        id: 'blue',
        interactive: true,
        paint: { 'line-color': CATEGORICAL[0], 'line-width': 3 },
        type: 'line',
        visible: show.blue,
      },
      {
        data: data.signals,
        id: 'signals',
        interactive: true,
        paint: {
          'circle-color': CATEGORICAL[1],
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 2, 15, 5],
        },
        type: 'circle',
        visible: show.signals,
      },
      {
        data: cameraPoints(data.cameras),
        id: 'cameras',
        interactive: true,
        paint: {
          'circle-color': CATEGORICAL[2],
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 4, 15, 8],
          'circle-stroke-color': '#fcfcfb',
          'circle-stroke-width': 1.5,
        },
        type: 'circle',
        visible: show.cameras,
      },
    ];
  }, [data, show]);

  if (error) return <p role="alert">Não foi possível carregar os dados: {error}</p>;
  if (!data) return <p aria-busy="true">Carregando as camadas…</p>;

  const spaces = data.blueZone.features.reduce((sum, f) => sum + f.properties.spaces, 0);
  const current = data.cameras.sites.find((s) => s.id === selected);
  const toggles = [
    {
      color: CATEGORICAL[0],
      key: 'blue' as const,
      label: `Área Azul (${formatInteger(spaces)} vagas)`,
    },
    {
      color: CATEGORICAL[1],
      key: 'signals' as const,
      label: `Semáforos (${formatInteger(data.signals.features.length)})`,
    },
    {
      color: CATEGORICAL[2],
      key: 'cameras' as const,
      label: `Controladores e redutores de velocidade (${formatInteger(data.cameras.sites.length)})`,
    },
  ];

  return (
    <section aria-labelledby="oferta-titulo" className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h2 className="text-2xl font-semibold" id="oferta-titulo">
          Estacionamento, semáforos e fiscalização
        </h2>
        <p className="text-muted-foreground max-w-prose">
          Cadastros da EPTC. Os semáforos não têm planos de tempo públicos, só a localização e o
          tipo. Os controladores e redutores de velocidade publicam o fluxo médio de um dia útil
          típico, por mês.
        </p>
      </header>

      <fieldset className="flex flex-wrap gap-4 text-sm">
        <legend className="sr-only">Camadas</legend>
        {toggles.map((t) => (
          <label key={t.key} className="flex items-center gap-2">
            <input
              checked={show[t.key]}
              type="checkbox"
              onChange={(e) => setShow((s) => ({ ...s, [t.key]: e.target.checked }))}
            />
            <span aria-hidden className="size-3 rounded-full" style={{ background: t.color }} />
            {t.label}
          </label>
        ))}
      </fieldset>

      <LayerMap
        label="Mapa da Área Azul, semáforos e controladores de velocidade"
        layers={layers}
        tooltip={(id, p) => {
          if (id === 'blue')
            return [
              `${String(p.street)}, ${String(p.number)}`,
              `${formatInteger(Number(p.spaces))} vagas, ${String(p.kind).toLowerCase()}`,
            ];
          if (id === 'signals')
            return [String(p.description), `Semáforo ${String(p.kind).toLowerCase()}`];
          return [
            String(p.label),
            KIND_LABELS[String(p.kind)] ?? String(p.kind),
            'Clique para ver o fluxo',
          ];
        }}
        onSelect={(id, p) => {
          if (id === 'cameras') setSelected(String(p.id));
        }}
      />

      {current ? (
        <CameraDetail site={current} unit={data.cameras.unit} />
      ) : (
        <p className="text-muted-foreground text-sm">
          Clique em um controlador para ver o fluxo de dia típico mês a mês.
        </p>
      )}
      <SourceNote
        sources={[
          { href: data.cameras.source.href, label: `${data.cameras.source.name}: cadastros` },
        ]}
      />
    </section>
  );
}

function CameraDetail({ site, unit }: { site: CameraSite; unit: string }) {
  const rows = cameraSeries(site);
  return (
    <article className="border-border flex flex-col gap-3 rounded-lg border p-4">
      <header>
        <h3 className="font-semibold">{site.label}</h3>
        <p className="text-muted-foreground text-sm">
          {KIND_LABELS[site.kind]}
          {site.limit_kmh ? ` · limite de ${site.limit_kmh} km/h` : ''}
          {site.lanes ? ` · ${site.lanes} faixas` : ''}
          {` · localizado por ${site.located_by}`}
        </p>
      </header>
      <figure className="flex flex-col gap-2">
        <figcaption className="text-sm font-medium">
          Fluxo de dia típico por mês, em {unit}
        </figcaption>
        <ChartContainer height={220} ResponsiveContainer={Responsive}>
          <LineChart data={rows} margin={{ bottom: 0, left: 8, right: 16, top: 8 }}>
            <CartesianGrid stroke="#e1e0d9" vertical={false} />
            <XAxis dataKey="month" minTickGap={24} stroke={INK.muted} />
            <YAxis stroke={INK.muted} tickFormatter={(v: number) => formatInteger(v)} width={64} />
            <Tooltip formatter={(value) => [formatInteger(Number(value)), 'fluxo']} />
            <Line
              connectNulls={false}
              dataKey="value"
              dot={{ r: 2 }}
              isAnimationActive={false}
              stroke={CATEGORICAL[0]}
              strokeWidth={2}
              type="linear"
            />
          </LineChart>
        </ChartContainer>
        <p className="text-muted-foreground text-xs">
          Meses sem valor ficam em branco: o equipamento não operou ou não teve dias típicos
          válidos.
        </p>
      </figure>
    </article>
  );
}
