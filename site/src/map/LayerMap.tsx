import {
  type GeoJSONSource,
  type LayerSpecification,
  type Map as MapLibreMap,
  type MapLayerMouseEvent,
  Popup,
} from 'maplibre-gl';
import { useCallback, useEffect, useRef, useState } from 'react';

import { BaseMap } from './BaseMap';

type GeoJsonData = { features: unknown[]; type: 'FeatureCollection' };
type Paint = NonNullable<
  Extract<LayerSpecification, { type: 'circle' | 'fill' | 'line' }>['paint']
>;

export interface MapLayer {
  data: GeoJsonData;
  id: string;
  /** Camadas interativas recebem tooltip e clique. */
  interactive?: boolean;
  paint: Paint;
  type: 'circle' | 'fill' | 'line';
  visible: boolean;
}

interface LayerMapProps {
  label: string;
  layers: MapLayer[];
  /** Linhas do tooltip de uma feição; o texto entra como texto, nunca como HTML. */
  tooltip: (layerId: string, properties: Record<string, unknown>) => string[];
  onSelect?: (layerId: string, properties: Record<string, unknown>) => void;
}

function content(lines: string[]): HTMLElement {
  const root = document.createElement('div');
  lines.forEach((line, i) => {
    const element = document.createElement(i === 0 ? 'strong' : 'div');
    element.textContent = line;
    root.appendChild(element);
  });
  return root;
}

/** Mapa com várias camadas GeoJSON. A ordem da lista é a ordem de desenho. */
export function LayerMap({ label, layers, onSelect, tooltip }: LayerMapProps) {
  const [map, setMap] = useState<MapLibreMap | null>(null);
  const tooltipRef = useRef(tooltip);
  tooltipRef.current = tooltip;
  const selectRef = useRef(onSelect);
  selectRef.current = onSelect;
  const known = useRef(new Set<string>());

  const onReady = useCallback((instance: MapLibreMap) => {
    setMap(instance);
  }, []);

  useEffect(() => {
    if (!map) return undefined;
    const popup = new Popup({ closeButton: false, closeOnClick: false, offset: 8 });
    const cleanups: (() => void)[] = [];
    for (const layer of layers) {
      if (!known.current.has(layer.id)) {
        map.addSource(layer.id, { data: layer.data as never, type: 'geojson' });
        map.addLayer({
          id: layer.id,
          paint: layer.paint,
          source: layer.id,
          type: layer.type,
        } as LayerSpecification);
        known.current.add(layer.id);
      } else {
        (map.getSource(layer.id) as GeoJSONSource).setData(layer.data as never);
        for (const [property, value] of Object.entries(layer.paint)) {
          map.setPaintProperty(layer.id, property as never, value as never);
        }
      }
      map.setLayoutProperty(layer.id, 'visibility', layer.visible ? 'visible' : 'none');
      if (!layer.interactive) continue;
      const move = (event: MapLayerMouseEvent) => {
        const feature = event.features?.[0];
        if (!feature) return;
        map.getCanvas().style.cursor = 'pointer';
        popup
          .setLngLat(event.lngLat)
          .setDOMContent(content(tooltipRef.current(layer.id, feature.properties)))
          .addTo(map);
      };
      const leave = () => {
        map.getCanvas().style.cursor = '';
        popup.remove();
      };
      const click = (event: MapLayerMouseEvent) => {
        const feature = event.features?.[0];
        if (feature) selectRef.current?.(layer.id, feature.properties);
      };
      map.on('mousemove', layer.id, move);
      map.on('mouseleave', layer.id, leave);
      map.on('click', layer.id, click);
      cleanups.push(() => {
        map.off('mousemove', layer.id, move);
        map.off('mouseleave', layer.id, leave);
        map.off('click', layer.id, click);
      });
    }
    return () => {
      cleanups.forEach((cleanup) => cleanup());
      popup.remove();
    };
  }, [map, layers]);

  return <BaseMap label={label} onReady={onReady} />;
}
