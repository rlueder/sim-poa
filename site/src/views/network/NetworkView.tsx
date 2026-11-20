import { useEffect, useMemo, useState } from 'react';

import { formatInteger, formatPercent } from '../../data/format';
import {
  averageSpeed,
  corridorRows,
  groupSignals,
  LANE_BREAKS,
  loadNetwork,
  type SignalGroup,
  SPEED_BREAKS,
} from '../../data/network';
import { LayerMap, type MapLayer } from '../../map/LayerMap';
import { integerRange } from '../../viz/legend';
import { CATEGORICAL, INK, SEQUENTIAL } from '../../viz/palette';
import { SourceNote } from '../SourceNote';

type Data = Awaited<ReturnType<typeof loadNetwork>>;
type ColourBy = 'lanes' | 'speed';

const EPTC = 'https://prefeitura.poa.br/eptc/projetos/observamob';
const OSM = 'https://www.openstreetmap.org/copyright';
const decimal = new Intl.NumberFormat('pt-BR', {
  maximumFractionDigits: 1,
  minimumFractionDigits: 1,
});

// Faixas usam quatro passos da rampa e velocidades, cinco; o passo mais claro fica
// de fora, porque some sobre o mapa base.
const LANE_COLOURS = [SEQUENTIAL[1], SEQUENTIAL[3], SEQUENTIAL[4], SEQUENTIAL[5]];
const SPEED_COLOURS = [SEQUENTIAL[1], SEQUENTIAL[2], SEQUENTIAL[3], SEQUENTIAL[4], SEQUENTIAL[5]];

const SIGNAL_GROUPS: { colour: string; key: SignalGroup; label: string }[] = [
  { colour: CATEGORICAL[0], key: 'ambos', label: 'No cadastro e na rede' },
  { colour: CATEGORICAL[1], key: 'so-cadastro', label: 'Só no cadastro da EPTC' },
  { colour: CATEGORICAL[2], key: 'so-rede', label: 'Só na rede (OpenStreetMap)' },
];

const STATUS_TEXT: Record<string, string> = {
  desligado: 'Estava no OpenStreetMap, sem registro no cadastro: desligado na rede',
  'ligado pelo cadastro': 'Faltava no OpenStreetMap: ligado na rede a partir do cadastro',
  'na rede': 'Já vinha do OpenStreetMap',
  'sem semáforo na rede': 'Sem cruzamento da rede a 30 m para pôr o semáforo',
  'só na rede': 'Na rede, sem registro no cadastro a 80 m',
};

function step(property: string, breaks: readonly number[], colours: string[]): unknown {
  const expression: unknown[] = ['step', ['get', property], colours[0]];
  breaks.slice(1).forEach((value, i) => expression.push(value, colours[i + 1]));
  return expression;
}

function roadLegend(by: ColourBy): { colour: string; label: string }[] {
  if (by === 'lanes')
    return LANE_BREAKS.map((from, i) => ({
      colour: LANE_COLOURS[i] ?? INK.muted,
      label: `${integerRange(from, LANE_BREAKS[i + 1])} ${from === 1 && i + 1 < LANE_BREAKS.length ? 'faixa' : 'faixas'}`,
    }));
  return SPEED_BREAKS.map((from, i) => ({
    colour: SPEED_COLOURS[i] ?? INK.muted,
    label:
      i === 0
        ? `menos de ${SPEED_BREAKS[1]} km/h`
        : i === SPEED_BREAKS.length - 1
          ? `${from} km/h ou mais`
          : `${integerRange(from, SPEED_BREAKS[i + 1])} km/h`,
  }));
}

export function NetworkView() {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<null | string>(null);
  const [colourBy, setColourBy] = useState<ColourBy>('lanes');
  const [show, setShow] = useState({ gates: false, signals: true });
  const [corridor, setCorridor] = useState<null | string>(null);

  useEffect(() => {
    loadNetwork().then(setData, (e: unknown) =>
      setError(e instanceof Error ? e.message : String(e)),
    );
  }, []);

  const signals = useMemo(() => (data ? groupSignals(data.signals) : null), [data]);

  const layers = useMemo<MapLayer[]>(() => {
    if (!data || !signals) return [];
    const colour =
      colourBy === 'lanes'
        ? step('lanes', LANE_BREAKS, LANE_COLOURS)
        : step('speed_kmh', SPEED_BREAKS, SPEED_COLOURS);
    return [
      {
        data: data.roads,
        id: 'roads',
        interactive: true,
        paint: {
          'line-color': colour as never,
          'line-width': ['interpolate', ['linear'], ['zoom'], 10, 1, 15, 4],
        },
        type: 'line',
        visible: true,
      },
      {
        data: {
          features: data.corridors.features.filter((f) => f.properties.corridor === corridor),
          type: 'FeatureCollection',
        },
        id: 'corridor',
        paint: { 'line-color': INK.primary, 'line-width': 5 },
        type: 'line',
        visible: corridor !== null,
      },
      {
        data: data.gates,
        id: 'gates',
        interactive: true,
        paint: { 'line-color': INK.primary, 'line-width': 7 },
        type: 'line',
        visible: show.gates,
      },
      {
        data: signals,
        id: 'signals',
        interactive: true,
        paint: {
          'circle-color': [
            'match',
            ['get', 'group'],
            'ambos',
            CATEGORICAL[0],
            'so-cadastro',
            CATEGORICAL[1],
            CATEGORICAL[2],
          ],
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 2.5, 15, 6],
          'circle-stroke-color': '#fcfcfb',
          'circle-stroke-width': 1,
        },
        type: 'circle',
        visible: show.signals,
      },
    ];
  }, [data, signals, colourBy, show, corridor]);

  if (error) return <p role="alert">Não foi possível carregar os dados: {error}</p>;
  if (!data || !signals) return <p aria-busy="true">Carregando a rede…</p>;

  const { summary } = data;
  const counts = new Map<SignalGroup, number>();
  for (const f of signals.features)
    counts.set(f.properties.group, (counts.get(f.properties.group) ?? 0) + 1);
  const outside = data.signals.features.length - signals.features.length;
  const before = summary.signals.before;
  const after = summary.signals.after;
  const tiles = [
    { label: 'km de vias para carros', value: formatInteger(summary.network.drivable_km) },
    { label: 'cruzamentos', value: formatInteger(summary.network.junctions) },
    { label: 'controladores semafóricos', value: formatInteger(summary.network.traffic_lights) },
    {
      label: 'pares de zonas com rota',
      value: `${formatInteger(summary.reachability.pairs - summary.reachability.without_route)} de ${formatInteger(summary.reachability.pairs)}`,
    },
  ];

  return (
    <section aria-labelledby="rede-titulo" className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h2 className="text-2xl font-semibold" id="rede-titulo">
          Rede viária do modelo
        </h2>
        <p className="text-muted-foreground max-w-prose">
          A rede que o simulador (SUMO) usa, convertida do OpenStreetMap ({summary.osm.extract})
          para o município e uma margem de 2 km. Onde o OpenStreetMap não informa a velocidade
          máxima, vale o padrão do Código de Trânsito (art. 61): 80 km/h nas vias de trânsito
          rápido, 60 nas arteriais, 40 nas coletoras e 30 nas locais. O mapa mostra só as vias
          coletoras e maiores.
        </p>
      </header>

      <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {tiles.map((t) => (
          <div key={t.label} className="border-border flex flex-col gap-1 rounded-lg border p-3">
            <dt className="text-muted-foreground text-xs">{t.label}</dt>
            <dd className="text-xl font-semibold tabular-nums">{t.value}</dd>
          </div>
        ))}
      </dl>

      <div className="flex flex-col gap-3 text-sm">
        <fieldset className="flex flex-wrap items-center gap-4">
          <legend className="sr-only">Cor das vias</legend>
          <span className="font-medium">Cor das vias:</span>
          {(
            [
              ['lanes', 'faixas por sentido'],
              ['speed', 'velocidade máxima'],
            ] as const
          ).map(([key, label]) => (
            <label key={key} className="flex items-center gap-2">
              <input
                checked={colourBy === key}
                name="cor-das-vias"
                type="radio"
                onChange={() => setColourBy(key)}
              />
              {label}
            </label>
          ))}
        </fieldset>
        <ul aria-label="Legenda das vias" className="flex flex-wrap gap-4">
          {roadLegend(colourBy).map((item) => (
            <li key={item.label} className="flex items-center gap-2">
              <span aria-hidden className="h-1 w-5 rounded" style={{ background: item.colour }} />
              {item.label}
            </li>
          ))}
        </ul>
        <fieldset className="flex flex-wrap gap-4">
          <legend className="sr-only">Camadas</legend>
          <label className="flex items-center gap-2">
            <input
              checked={show.signals}
              type="checkbox"
              onChange={(e) => setShow((s) => ({ ...s, signals: e.target.checked }))}
            />
            Semáforos
          </label>
          <label className="flex items-center gap-2">
            <input
              checked={show.gates}
              type="checkbox"
              onChange={(e) => setShow((s) => ({ ...s, gates: e.target.checked }))}
            />
            Entradas e saídas da cidade ({formatInteger(data.gates.features.length)})
          </label>
        </fieldset>
        {show.signals && (
          <ul aria-label="Legenda dos semáforos" className="flex flex-wrap gap-4">
            {SIGNAL_GROUPS.map((g) => (
              <li key={g.key} className="flex items-center gap-2">
                <span
                  aria-hidden
                  className="size-3 rounded-full"
                  style={{ background: g.colour }}
                />
                {g.label} ({formatInteger(counts.get(g.key) ?? 0)})
              </li>
            ))}
          </ul>
        )}
      </div>

      <LayerMap
        label="Mapa da rede viária do modelo, com semáforos e entradas da cidade"
        layers={layers}
        tooltip={(id, p) => {
          if (id === 'roads')
            return [
              String(p.name) || 'Via sem nome',
              `${String(p.lanes)} ${Number(p.lanes) === 1 ? 'faixa' : 'faixas'} por sentido · ${formatInteger(Number(p.speed_kmh))} km/h`,
            ];
          if (id === 'gates')
            return [
              String(p.name) || 'Via sem nome',
              `${p.direction === 'entrada' ? 'Entrada' : 'Saída'} da cidade · ${String(p.lanes)} ${Number(p.lanes) === 1 ? 'faixa' : 'faixas'}`,
            ];
          return [
            p.source === 'cadastro' ? String(p.description) : 'Semáforo do OpenStreetMap',
            STATUS_TEXT[String(p.status)] ?? String(p.status),
          ];
        }}
      />

      <div className="flex max-w-prose flex-col gap-2 text-sm">
        <h3 className="text-base font-semibold">Semáforos: rede e cadastro</h3>
        <p>
          Dos {formatInteger(before.inventario)} semáforos do cadastro da EPTC,{' '}
          {formatInteger(before.inventario_casado)} já vinham do OpenStreetMap, a até 30 m de um
          semáforo da rede. A conferência ligou mais{' '}
          {formatInteger(after.inventario_casado - before.inventario_casado)} no cruzamento mais
          próximo e desligou {formatInteger(summary.signals.removed)} que não tinham registro a 80
          m. Ficaram {formatInteger(after.inventario_sem_semaforo_na_rede)} sem semáforo na rede,{' '}
          {formatInteger(summary.signals.unplaced_by_kind.EXCLUSIVO ?? 0)} deles de travessia de
          pedestres no meio da quadra, onde a rede não tem um nó. Outros {formatInteger(outside)}{' '}
          semáforos da rede ficam nos municípios vizinhos, fora do cadastro, e não aparecem no mapa.
        </p>
      </div>

      <figure className="flex flex-col gap-2">
        <figcaption className="flex flex-col gap-1">
          <span className="font-semibold">Tempo em fluxo livre nos corredores</span>
          <span className="text-muted-foreground max-w-prose text-sm">
            Extensão de ponta a ponta dividida pela velocidade máxima de cada trecho, sem semáforos,
            conversões nem outros veículos. Serve para conferir a rede, não para estimar o tempo de
            viagem. Teste mesoscópico com {formatInteger(summary.smoke_test.inserted)} viagens
            aleatórias: {formatInteger(summary.smoke_test.teleports)} teletransportes.
          </span>
        </figcaption>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-muted-foreground text-left">
              <tr>
                <th className="py-2 pr-4 font-medium" scope="col">
                  Corredor
                </th>
                <th className="py-2 pr-4 font-medium" scope="col">
                  Sentido
                </th>
                <th className="py-2 pr-4 text-right font-medium" scope="col">
                  Extensão (km)
                </th>
                <th className="py-2 pr-4 text-right font-medium" scope="col">
                  Fluxo livre (min)
                </th>
                <th className="py-2 pr-4 text-right font-medium" scope="col">
                  Média (km/h)
                </th>
                <th className="py-2 pr-4 text-right font-medium" scope="col">
                  Na avenida
                </th>
                <th className="py-2 font-medium" scope="col">
                  <span className="sr-only">Mapa</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {corridorRows(data.corridors).flatMap((row) =>
                row.directions.map((c, i) => (
                  <tr key={`${row.corridor}-${c.direction}`} className="border-border border-t">
                    <th className="py-2 pr-4 text-left font-normal" scope="row">
                      {i === 0 ? row.corridor : <span className="sr-only">{row.corridor}</span>}
                    </th>
                    <td className="py-2 pr-4">{c.direction}</td>
                    <td className="py-2 pr-4 text-right tabular-nums">
                      {decimal.format(c.length_km)}
                    </td>
                    <td className="py-2 pr-4 text-right tabular-nums">
                      {decimal.format(c.free_flow_min)}
                    </td>
                    <td className="py-2 pr-4 text-right tabular-nums">
                      {formatInteger(averageSpeed(c))}
                    </td>
                    <td className="py-2 pr-4 text-right tabular-nums">
                      {formatPercent(c.on_corridor)}
                    </td>
                    <td className="py-2">
                      {i === 0 && (
                        <button
                          aria-pressed={corridor === row.corridor}
                          className="underline underline-offset-2"
                          type="button"
                          onClick={() =>
                            setCorridor((current) =>
                              current === row.corridor ? null : row.corridor,
                            )
                          }
                        >
                          {corridor === row.corridor ? 'tirar do mapa' : 'ver no mapa'}
                        </button>
                      )}
                    </td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
      </figure>

      <SourceNote
        sources={[
          { href: OSM, label: 'OpenStreetMap (extrato Geofabrik), © colaboradores, ODbL' },
          { href: EPTC, label: 'EPTC, Prefeitura de Porto Alegre: cadastro semafórico' },
        ]}
      />
    </section>
  );
}
