import type { Collection } from './layers';
import { fetchJson } from './load';

export interface Road {
  highway: string;
  lanes: number;
  name: string;
  speed_kmh: number;
}

export type SignalStatus =
  | 'desligado'
  | 'fora do município'
  | 'ligado pelo cadastro'
  | 'na rede'
  | 'sem semáforo na rede'
  | 'só na rede';

export interface NetworkSignal {
  code: string;
  description: string;
  kind: string;
  source: 'cadastro' | 'rede';
  status: SignalStatus;
}

export interface Gate {
  direction: 'entrada' | 'saída';
  highway: string;
  lanes: number;
  name: string;
}

export interface Corridor {
  corridor: string;
  direction: 'ida' | 'volta';
  free_flow_min: number;
  length_km: number;
  routed: boolean;
  on_corridor: number;
}

type Counts = Record<
  | 'inventario'
  | 'inventario_casado'
  | 'inventario_sem_semaforo_na_rede'
  | 'rede'
  | 'rede_casada'
  | 'rede_sem_registro_no_inventario',
  number
>;

export interface NetworkSummary {
  network: {
    drivable_km: number;
    junctions: number;
    traffic_lights: number;
  };
  osm: { extract: string };
  reachability: { pairs: number; without_route: number };
  signals: {
    added: number;
    after: Counts;
    before: Counts;
    removed: number;
    unplaced: number;
    /** Pelo campo TIPO do cadastro; EXCLUSIVO são as travessias de pedestres. */
    unplaced_by_kind: Record<string, number>;
  };
  smoke_test: { inserted: number; teleports: number };
  zones: { city_zones: number };
}

export function loadNetwork() {
  return Promise.all([
    fetchJson<Collection<Road>>('network/roads.geojson'),
    fetchJson<Collection<NetworkSignal>>('network/signals.geojson'),
    fetchJson<Collection<Gate>>('network/gates.geojson'),
    fetchJson<Collection<Corridor>>('network/corridors.geojson'),
    fetchJson<NetworkSummary>('network/summary.json'),
  ]).then(([roads, signals, gates, corridors, summary]) => ({
    corridors,
    gates,
    roads,
    signals,
    summary,
  }));
}

/**
 * Três grupos para o mapa, um por cor. Os semáforos fora do município ficam de
 * fora: o cadastro da EPTC não cobre os vizinhos.
 */
export type SignalGroup = 'ambos' | 'so-cadastro' | 'so-rede';

export function signalGroup(status: SignalStatus): null | SignalGroup {
  switch (status) {
    case 'na rede':
    case 'ligado pelo cadastro':
      return 'ambos';
    case 'sem semáforo na rede':
      return 'so-cadastro';
    case 'só na rede':
    case 'desligado':
      return 'so-rede';
    case 'fora do município':
      return null;
  }
}

export function groupSignals(
  signals: Collection<NetworkSignal>,
): Collection<NetworkSignal & { group: SignalGroup }> {
  return {
    features: signals.features.flatMap((f) => {
      const group = signalGroup(f.properties.status);
      return group ? [{ ...f, properties: { ...f.properties, group } }] : [];
    }),
    type: 'FeatureCollection',
  };
}

/** Classes de cor das vias: o primeiro valor de cada classe, em ordem crescente. */
export const LANE_BREAKS = [1, 2, 3, 4] as const;
export const SPEED_BREAKS = [0, 40, 50, 60, 80] as const;

export interface CorridorRow {
  corridor: string;
  directions: Corridor[];
}

/** Uma linha por corredor, com os dois sentidos, na ordem do arquivo. */
export function corridorRows(corridors: Collection<Corridor>): CorridorRow[] {
  const rows = new Map<string, Corridor[]>();
  for (const f of corridors.features) {
    const list = rows.get(f.properties.corridor) ?? [];
    list.push(f.properties);
    rows.set(f.properties.corridor, list);
  }
  return [...rows].map(([corridor, directions]) => ({ corridor, directions }));
}

export function averageSpeed(c: Corridor): number {
  return c.length_km / (c.free_flow_min / 60);
}
