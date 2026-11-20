import {
  type ExpressionSpecification,
  type GeoJSONSource,
  type Map as MapLibreMap,
  type MapLayerMouseEvent,
  Popup,
} from 'maplibre-gl';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
  cityBounds,
  type EdomData,
  type Measure,
  quantileBreaks,
  type ZoneProperties,
  zoneValue,
} from '../../data/edom';
import { formatInteger } from '../../data/format';
import { BaseMap } from '../../map/BaseMap';
import { INK, NO_DATA, SEQUENTIAL } from '../../viz/palette';
import { MAX_LINES, sequentialColor, zoneLabel } from './shared';

interface TripsMapProps {
  data: EdomData;
  hour: null | number;
  measure: Measure;
  showLines: boolean;
}

function stepExpression(breaks: number[]): ExpressionSpecification {
  const stops: (number | string)[] = [sequentialColor(0)];
  breaks.forEach((value, i) => {
    stops.push(value, sequentialColor(i + 1));
  });
  return [
    'case',
    ['<=', ['get', 'value'], 0],
    NO_DATA,
    ['step', ['get', 'value'], ...stops],
  ] as unknown as ExpressionSpecification;
}

export function TripsMap({ data, hour, measure, showLines }: TripsMapProps) {
  const [map, setMap] = useState<MapLibreMap | null>(null);
  const popup = useRef<null | Popup>(null);

  // Viagens por km²: com o total absoluto, as zonas grandes ficariam escuras só por serem grandes.
  const { densities, totals } = useMemo(() => {
    const area = new Map(
      data.shapes.features.map((f) => [f.properties.zone, f.properties.area_km2]),
    );
    const totalsByZone = new Map<number, number>();
    const densityByZone = new Map<number, number>();
    for (const stats of data.zones.zones) {
      const total = zoneValue(stats, measure, hour);
      totalsByZone.set(stats.zone, total);
      const km2 = area.get(stats.zone);
      if (km2) densityByZone.set(stats.zone, total / km2);
    }
    return { densities: densityByZone, totals: totalsByZone };
  }, [data, hour, measure]);

  const breaks = useMemo(
    () => quantileBreaks([...densities.values()], SEQUENTIAL.length),
    [densities],
  );
  const minPositive = useMemo(
    () => Math.min(...[...densities.values()].filter((v) => v > 0)),
    [densities],
  );

  const zonesWithValues = useMemo(
    () => ({
      ...data.shapes,
      features: data.shapes.features.map((f) => ({
        ...f,
        properties: {
          ...f.properties,
          total: totals.get(f.properties.zone) ?? 0,
          value: densities.get(f.properties.zone) ?? 0,
        },
      })),
    }),
    [data.shapes, densities, totals],
  );

  const lines = useMemo(() => {
    const centroids = data.zones.centroids;
    return {
      features: data.lines.pairs.slice(0, MAX_LINES).flatMap((pair) => {
        const from = centroids[String(pair.o)];
        const to = centroids[String(pair.d)];
        if (!from || !to) return [];
        return [
          {
            geometry: { coordinates: [from, to], type: 'LineString' as const },
            properties: { trips: pair.trips },
            type: 'Feature' as const,
          },
        ];
      }),
      type: 'FeatureCollection' as const,
    };
  }, [data]);

  const onReady = useCallback(
    (instance: MapLibreMap) => {
      instance.addSource('zones', {
        data: { features: [], type: 'FeatureCollection' },
        type: 'geojson',
      });
      instance.addSource('lines', {
        data: { features: [], type: 'FeatureCollection' },
        type: 'geojson',
      });
      instance.addLayer({
        id: 'zones-fill',
        paint: { 'fill-color': NO_DATA, 'fill-opacity': 0.75 },
        source: 'zones',
        type: 'fill',
      });
      instance.addLayer({
        id: 'zones-outline',
        paint: { 'line-color': '#fcfcfb', 'line-width': 1 },
        source: 'zones',
        type: 'line',
      });
      instance.addLayer({
        id: 'lines',
        layout: { 'line-cap': 'round' },
        paint: {
          'line-color': INK.secondary,
          'line-opacity': 0.45,
          'line-width': ['interpolate', ['linear'], ['get', 'trips'], 1000, 0.75, 4500, 4],
        },
        source: 'lines',
        type: 'line',
      });
      popup.current = new Popup({ closeButton: false, closeOnClick: false });
      instance.fitBounds(cityBounds(data.shapes), { duration: 0, padding: 24 });
      setMap(instance);
    },
    [data.shapes],
  );

  useEffect(() => {
    if (!map) return;
    (map.getSource('zones') as GeoJSONSource).setData(zonesWithValues);
    map.setPaintProperty('zones-fill', 'fill-color', stepExpression(breaks));
  }, [map, zonesWithValues, breaks]);

  useEffect(() => {
    if (!map) return;
    (map.getSource('lines') as GeoJSONSource).setData(lines);
    map.setLayoutProperty('lines', 'visibility', showLines ? 'visible' : 'none');
  }, [map, lines, showLines]);

  useEffect(() => {
    if (!map) return undefined;
    const onMove = (event: MapLayerMouseEvent) => {
      const feature = event.features?.[0];
      if (!feature || !popup.current) return;
      const props = feature.properties as ZoneProperties & { total: number; value: number };
      map.getCanvas().style.cursor = 'pointer';
      const content = document.createElement('div');
      const title = document.createElement('strong');
      title.textContent = zoneLabel(props);
      const total = document.createElement('div');
      total.textContent = `${formatInteger(props.total)} viagens ${
        measure === 'produced' ? 'com origem' : 'com destino'
      } na zona`;
      const density = document.createElement('div');
      density.textContent = `${formatInteger(props.value)} por km²`;
      content.append(title, total, density);
      popup.current.setLngLat(event.lngLat).setDOMContent(content).addTo(map);
    };
    const onLeave = () => {
      map.getCanvas().style.cursor = '';
      popup.current?.remove();
    };
    map.on('mousemove', 'zones-fill', onMove);
    map.on('mouseleave', 'zones-fill', onLeave);
    return () => {
      map.off('mousemove', 'zones-fill', onMove);
      map.off('mouseleave', 'zones-fill', onLeave);
    };
  }, [map, measure]);

  return (
    <div className="flex flex-col gap-3">
      <BaseMap
        label={`Mapa das zonas de tráfego com viagens ${measure === 'produced' ? 'produzidas' : 'atraídas'}`}
        onReady={onReady}
      />
      <Legend breaks={breaks} minPositive={minPositive} />
    </div>
  );
}

function Legend({ breaks, minPositive }: { breaks: number[]; minPositive: number }) {
  const classes = [Number.isFinite(minPositive) ? minPositive : 0, ...breaks];
  return (
    <ul aria-label="Legenda do mapa" className="text-muted-foreground flex flex-wrap gap-3 text-xs">
      <li className="font-medium">Viagens por km²:</li>
      {classes.map((from, i) => {
        const to = breaks[i];
        return (
          <li key={from} className="flex items-center gap-1.5">
            <span
              aria-hidden
              className="inline-block size-3 rounded-sm"
              style={{ background: sequentialColor(i) }}
            />
            {to === undefined
              ? `${formatInteger(from)} ou mais`
              : `${formatInteger(from)} a ${formatInteger(to)}`}
          </li>
        );
      })}
      <li className="flex items-center gap-1.5">
        <span
          aria-hidden
          className="inline-block size-3 rounded-sm"
          style={{ background: NO_DATA }}
        />
        sem viagens na amostra
      </li>
    </ul>
  );
}
