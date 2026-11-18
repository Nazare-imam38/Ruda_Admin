import { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { api } from '../api';

const STYLE = {
  version: 8,
  name: 'OpenStreetMap',
  glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
  sources: {
    osm: {
      type: 'raster', tileSize: 256,
      tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
      attribution: '&copy; OpenStreetMap contributors',
    },
  },
  layers: [{ id: 'osm-base', type: 'raster', source: 'osm' }],
};

const sourceId = (id) => `data-${id}`;
const drawIds = (id) => [`fill-${id}`, `outline-${id}`, `line-${id}`, `point-${id}`, `label-${id}`, `raster-${id}`];

function addLayer(map, item) {
  const source = sourceId(item.id);
  const color = item.style?.color || '#2563eb';
  if (item.geometry_type === 'Raster') {
    map.addSource(source,{type:'raster',tileSize:256,tiles:[`${window.location.origin}/api/layers/${item.id}/tile/?v=${item.version}&bbox={bbox-epsg-3857}`], ...(item.bbox?{bounds:item.bbox}:{})});
    map.addLayer({id:`raster-${item.id}`,type:'raster',source,paint:{'raster-opacity':item.style?.raster_opacity??1}});
    return;
  }
  map.addSource(source, { type: 'geojson', data: item.preview_geojson || { type: 'FeatureCollection', features: [] } });
  if (item.geometry_type === 'Polygon') {
    map.addLayer({
      id: `fill-${item.id}`, type: 'fill', source,
      paint: { 'fill-color': color, 'fill-opacity': item.style?.fill_opacity ?? 0.3 },
    });
    map.addLayer({
      id: `outline-${item.id}`, type: 'line', source,
      paint: { 'line-color': color, 'line-width': item.style?.line_width ?? 3 },
    });
  } else if (item.geometry_type === 'Line') {
    map.addLayer({
      id: `line-${item.id}`, type: 'line', source,
      paint: { 'line-color': color, 'line-width': item.style?.line_width ?? 3 },
      layout: { 'line-join': 'round', 'line-cap': 'round' },
    });
  } else {
    map.addLayer({
      id: `point-${item.id}`, type: 'circle', source,
      paint: {
        'circle-color': color, 'circle-radius': item.style?.point_radius ?? 6,
        'circle-stroke-color': '#ffffff', 'circle-stroke-width': 1.5,
      },
    });
  }
  if (item.show_labels && item.label_field) {
    map.addLayer({
      id: `label-${item.id}`, type: 'symbol', source, minzoom: item.label_min_zoom ?? 10,
      layout: {
        'text-field': ['to-string', ['coalesce', ['get', item.label_field], '']],
        'text-font': ['Open Sans Regular'],
        'text-size': item.label_size ?? 12,
        'text-anchor': item.geometry_type === 'Point' ? 'top' : 'center',
        'text-offset': item.geometry_type === 'Point' ? [0, 0.9] : [0, 0],
        'symbol-placement': item.geometry_type === 'Line' ? 'line' : 'point',
        'text-allow-overlap': false,
        'text-ignore-placement': false,
      },
      paint: {
        'text-color': '#182638',
        'text-halo-color': '#ffffff',
        'text-halo-width': 1.8,
      },
    });
  }
}

function openFeaturePopup(map, found, layer) {
  if (!layer?.show_popup) return;
  const body = document.createElement('div');
  body.className = 'feature-popup';
  const title = document.createElement('h4');
  title.textContent = layer.name;
  body.appendChild(title);
  const properties = found.properties || {};
  for (const name of (layer.popup_fields || []).slice(0, 60)) {
    const value = properties[name];
    if (value === null || value === undefined || value === '') continue;
    const row = document.createElement('div');
    row.className = 'popup-row';
    const key = document.createElement('strong');
    key.textContent = name;
    const val = document.createElement('span');
    val.textContent = String(value);
    row.append(key, val);
    body.appendChild(row);
  }
  new maplibregl.Popup({ maxWidth: '310px' })
    .setLngLat(found.geometry?.type === 'Point' ? found.geometry.coordinates : map.__popupLocation)
    .setDOMContent(body)
    .addTo(map);
}

export default function MapPanel({ layers, selectedLayer, onOpenAttributes, zoomTarget }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const drawIdsRef = useRef([]);
  const layersRef = useRef(layers);
  const [ready, setReady] = useState(false);
  const [viewportVersion, setViewportVersion] = useState(0);
  const [warning, setWarning] = useState('');
  layersRef.current = layers;

  useEffect(() => {
    const map = new maplibregl.Map({
      container: containerRef.current, style: STYLE,
      center: [74.32, 31.52], zoom: 10.7,
      attributionControl: true,
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl(), 'top-right');
    map.addControl(new maplibregl.ScaleControl({ maxWidth: 140, unit: 'metric' }), 'bottom-left');
    map.on('load', () => setReady(true));
    map.on('moveend', () => setViewportVersion(value => value + 1));
    map.on('click', (evt) => {
      const candidates = drawIdsRef.current.filter(id => map.getLayer(id) && !id.startsWith('label-') && !id.startsWith('raster-'));
      if (!candidates.length) return;
      const hits = map.queryRenderedFeatures(evt.point, { layers: candidates });
      if (hits.length === 0) return;
      const hit = hits[0];
      const layerId = hit.layer.id.split('-').slice(1).join('-');
      const layer = layersRef.current.find(item => item.id === layerId);
      map.__popupLocation = evt.lngLat;
      openFeaturePopup(map, hit, layer);
    });
    map.on('mousemove', evt => {
      const candidateLayers = drawIdsRef.current.filter(id => map.getLayer(id) && !id.startsWith('label-') && !id.startsWith('raster-'));
      const hits = candidateLayers.length ? map.queryRenderedFeatures(evt.point, { layers: candidateLayers }) : [];
      map.getCanvas().style.cursor = hits.length ? 'pointer' : '';
    });
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const oldDrawIds = drawIdsRef.current;
    for (const id of [...oldDrawIds].reverse()) {
      if (map.getLayer(id)) map.removeLayer(id);
    }
    for (const id of map.getStyle().sources ? Object.keys(map.getStyle().sources) : []) {
      if (id.startsWith('data-') && map.getSource(id)) map.removeSource(id);
    }
    const newDrawIds = [];
    for (const item of layers.filter(entry => entry.is_visible)) {
      addLayer(map, item);
      for (const id of drawIds(item.id)) if (map.getLayer(id)) newDrawIds.push(id);
    }
    drawIdsRef.current = newDrawIds;
    // Trigger data fetch after dynamic source recreation.
    setViewportVersion(value => value + 1);
  }, [layers, ready]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return undefined;
    const visible = layers.filter(item => item.is_visible && item.geometry_type!=='Raster' && !item.preview_geojson);
    if (visible.length === 0) { setWarning(''); return undefined; }
    const bounds = map.getBounds();
    const bbox = [
      Math.max(-180, bounds.getWest()), Math.max(-90, bounds.getSouth()),
      Math.min(180, bounds.getEast()), Math.min(90, bounds.getNorth()),
    ].map(n => n.toFixed(6)).join(',');
    const controller = new AbortController();
    Promise.all(visible.map(async item => {
      try {
        const geojson = await api.geojson(item.id, bbox, controller.signal);
        if (controller.signal.aborted) return null;
        const source = map.getSource(sourceId(item.id));
        if (source) source.setData(geojson);
        return geojson.meta?.truncated ? `${item.name}: only first 10,000 matching features drawn` : null;
      } catch (e) {
        if (e.name === 'AbortError') return null;
        return `Could not load ${item.name}: ${e.message}`;
      }
    })).then(alerts => {
      if (!controller.signal.aborted) setWarning(alerts.filter(Boolean).join(' • '));
    });
    return () => controller.abort();
  }, [layers, ready, viewportVersion]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !zoomTarget?.bbox) return;
    const [west, south, east, north] = zoomTarget.bbox;
    if (west === east && south === north) {
      map.flyTo({ center: [west, south], zoom: 15, duration: 650 });
    } else {
      map.fitBounds([[west, south], [east, north]], { padding: 80, duration: 650, maxZoom: 16 });
    }
  }, [zoomTarget, ready]);

  return (
    <section className="map-shell">
      <div className="map-container" ref={containerRef} />
      <div className="map-top-banner">
        <div className="status-dot" />
        <span>Dynamic WFS / WMS · legacy PostGIS</span>
      </div>
      {warning && <div className="map-warning">{warning}</div>}
      {layers.length === 0 && (
        <div className="empty-map-notice">
          <div className="empty-map-icon">◈</div>
          <h3>Ready for your first dataset</h3>
          <p>Upload a vector ZIP or GeoTIFF to add a GIS layer.</p>
        </div>
      )}
      {selectedLayer && selectedLayer.show_attributes !== false && (
        <button className="floating-attributes" onClick={onOpenAttributes}>▤ &nbsp; View {selectedLayer.name} attributes</button>
      )}
    </section>
  );
}
