import {
  type ExpressionSpecification,
  type GeoJSONSource,
  type Map as MapLibreMap,
  type MapLayerMouseEvent,
  Popup,
} from 'maplibre-gl';
import { useCallback, useEffect, useRef, useState } from 'react';

import { BaseMap } from './BaseMap';

export interface PointFeature {
  geometry: { coordinates: [number, number]; type: 'Point' };
  properties: { id: string; [key: string]: unknown };
  type: 'Feature';
}

export interface PointCollection {
  features: PointFeature[];
  type: 'FeatureCollection';
}

export interface LineCollection {
  features: {
    geometry: { coordinates: unknown; type: 'LineString' | 'MultiLineString' };
    properties: Record<string, unknown>;
    type: 'Feature';
  }[];
  type: 'FeatureCollection';
}

interface PointMapProps {
  color: ExpressionSpecification | string;
  /** Linhas de contexto desenhadas sob os pontos (corredores, por exemplo). */
  context?: LineCollection;
  label: string;
  points: PointCollection;
  selectedId: null | string;
  /** Linhas do tooltip; o texto entra como texto, nunca como HTML. */
  tooltip: (properties: PointFeature['properties']) => string[];
  onSelect: (id: null | string) => void;
}

function popupContent(lines: string[]): HTMLElement {
  const root = document.createElement('div');
  lines.forEach((line, i) => {
    const element = document.createElement(i === 0 ? 'strong' : 'div');
    element.textContent = line;
    root.appendChild(element);
  });
  return root;
}

export function PointMap({
  color,
  context,
  label,
  onSelect,
  points,
  selectedId,
  tooltip,
}: PointMapProps) {
  const [map, setMap] = useState<MapLibreMap | null>(null);
  const popup = useRef<null | Popup>(null);
  const tooltipRef = useRef(tooltip);
  tooltipRef.current = tooltip;
  const selectRef = useRef(onSelect);
  selectRef.current = onSelect;

  const onReady = useCallback((instance: MapLibreMap) => {
    const empty = { features: [], type: 'FeatureCollection' as const };
    instance.addSource('context', { data: empty, type: 'geojson' });
    instance.addSource('points', { data: empty, type: 'geojson' });
    instance.addLayer({
      id: 'context',
      paint: { 'line-color': '#52514e', 'line-opacity': 0.5, 'line-width': 5 },
      source: 'context',
      type: 'line',
    });
    // Área de toque maior que o ponto, transparente: o ponteiro não precisa acertar o centro.
    instance.addLayer({
      id: 'points-hit',
      paint: { 'circle-opacity': 0, 'circle-radius': 12 },
      source: 'points',
      type: 'circle',
    });
    instance.addLayer({
      id: 'points',
      paint: {
        'circle-color': '#2a78d6',
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 4, 15, 8],
        'circle-stroke-color': '#fcfcfb',
        'circle-stroke-width': 1.5,
      },
      source: 'points',
      type: 'circle',
    });
    instance.addLayer({
      filter: ['==', ['get', 'id'], ''],
      id: 'points-selected',
      paint: {
        'circle-color': 'rgba(0,0,0,0)',
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 9, 15, 13],
        'circle-stroke-color': '#0b0b0b',
        'circle-stroke-width': 2.5,
      },
      source: 'points',
      type: 'circle',
    });
    popup.current = new Popup({ closeButton: false, closeOnClick: false, offset: 10 });
    const move = (event: MapLayerMouseEvent) => {
      const feature = event.features?.[0];
      if (!feature || !popup.current) return;
      instance.getCanvas().style.cursor = 'pointer';
      const lines = tooltipRef.current(feature.properties as PointFeature['properties']);
      popup.current.setLngLat(event.lngLat).setDOMContent(popupContent(lines)).addTo(instance);
    };
    instance.on('mousemove', 'points-hit', move);
    instance.on('mouseleave', 'points-hit', () => {
      instance.getCanvas().style.cursor = '';
      popup.current?.remove();
    });
    instance.on('click', (event) => {
      const hit = instance.queryRenderedFeatures(event.point, { layers: ['points-hit'] })[0];
      selectRef.current(hit ? String(hit.properties.id) : null);
    });
    setMap(instance);
  }, []);

  useEffect(() => {
    if (!map) return;
    (map.getSource('points') as GeoJSONSource).setData(points);
  }, [map, points]);

  useEffect(() => {
    if (!map) return;
    (map.getSource('context') as GeoJSONSource).setData(
      context ?? { features: [], type: 'FeatureCollection' },
    );
  }, [map, context]);

  useEffect(() => {
    if (!map) return;
    map.setPaintProperty('points', 'circle-color', color);
  }, [map, color]);

  useEffect(() => {
    if (!map) return;
    map.setFilter('points-selected', ['==', ['get', 'id'], selectedId ?? '']);
  }, [map, selectedId]);

  return <BaseMap label={label} onReady={onReady} />;
}
