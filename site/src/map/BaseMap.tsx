import 'maplibre-gl/dist/maplibre-gl.css';

import { Map as MapLibreMap, NavigationControl, setWorkerUrl } from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
import { useEffect, useRef } from 'react';

// Basemap do OpenFreeMap: tiles vetoriais do OpenStreetMap, sem chave nem
// cadastro (https://openfreemap.org/). O estilo já traz a atribuição.
const BASEMAP_STYLE = 'https://tiles.openfreemap.org/styles/positron';

// O MapLibre 6 distribui o worker em arquivo separado. Sem apontar a URL,
// o Vite não o encontra e o mapa fica em branco.
setWorkerUrl(workerUrl);

const PORTO_ALEGRE: [number, number] = [-51.19, -30.06];

interface BaseMapProps {
  /** Descrição curta do que o mapa mostra, para leitores de tela. */
  label: string;
  /** Chamado uma vez, quando o estilo terminou de carregar. */
  onReady: (map: MapLibreMap) => void;
}

export function BaseMap({ label, onReady }: BaseMapProps) {
  const container = useRef<HTMLDivElement>(null);
  const ready = useRef(onReady);
  ready.current = onReady;

  useEffect(() => {
    if (!container.current) return undefined;
    const map = new MapLibreMap({
      attributionControl: { compact: false },
      center: PORTO_ALEGRE,
      container: container.current,
      maxZoom: 16,
      minZoom: 8,
      style: BASEMAP_STYLE,
      zoom: 10.6,
    });
    map.addControl(new NavigationControl({ showCompass: false }), 'top-right');
    map.on('load', () => ready.current(map));
    // O MapLibre mede o contêiner uma vez, ao nascer; se o layout ainda estava se
    // assentando, o mapa ocupa só parte da caixa. Acompanhar o tamanho resolve.
    const observer = new ResizeObserver(() => map.resize());
    observer.observe(container.current);
    return () => {
      observer.disconnect();
      map.remove();
    };
  }, []);

  return (
    <div
      ref={container}
      aria-label={label}
      className="border-border h-[480px] w-full overflow-hidden rounded-lg border"
      role="region"
    />
  );
}
