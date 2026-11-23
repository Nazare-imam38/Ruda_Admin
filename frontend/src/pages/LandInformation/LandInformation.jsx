import { useEffect, useRef, useState } from 'react';
import {
  AlertCircle,
  Blocks,
  Building2,
  CheckCircle2,
  Grid2X2,
  MapPin,
  Ruler,
} from 'lucide-react';
import { api } from '../../api';
import MapPanel from '../../components/MapPanel';
import LandFilters from './components/LandFilters';
import LandSubHeader from './components/LandSubHeader';
import LayerManager from './components/LayerManager';
import LeftToolbar from './components/LeftToolbar';

const LAND_MAP_CENTER = [69.3, 31.2];

function findDistrictFeature(geojson, districtName) {
  const expectedName = districtName.trim().toLowerCase();
  return geojson?.features?.find(feature => {
    const properties = feature.properties || {};
    const entries = Object.entries(properties);
    const nameFields = entries.filter(([key]) =>
      /name|district/i.test(key)
    );

    const matchesName = ([, value]) =>
      String(value ?? '').trim().toLowerCase() === expectedName;
    return nameFields.some(matchesName);
  });
}

function calculateBounds(feature) {
  const coordinates = [];

  function collect(value) {
    if (
      Array.isArray(value) &&
      value.length >= 2 &&
      typeof value[0] === 'number' &&
      typeof value[1] === 'number'
    ) {
      coordinates.push(value);
      return;
    }

    if (Array.isArray(value)) value.forEach(collect);
  }

  collect(feature?.geometry?.coordinates);

  if (!coordinates.length) return null;

  const longitudes = coordinates.map(point => point[0]);
  const latitudes = coordinates.map(point => point[1]);

  return [
    Math.min(...longitudes),
    Math.min(...latitudes),
    Math.max(...longitudes),
    Math.max(...latitudes),
  ];
}

function parseLayerBounds(bbox) {
  const values = Array.isArray(bbox)
    ? bbox
    : typeof bbox === 'string'
      ? bbox.split(',').map(Number)
      : [];

  return values.length === 4 && values.every(Number.isFinite)
    ? values
    : [60, 23, 78, 38];
}

export default function LandInformation() {
  const [layers, setLayers] = useState([]);
  const [selectedDistricts, setSelectedDistricts] = useState([]);
  const [zoomTarget, setZoomTarget] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTool, setActiveTool] = useState('layers');
  const [layerManagerOpen, setLayerManagerOpen] = useState(false);
  const originalDistrictLayer = useRef(null);

  useEffect(() => {
    api.layers()
      .then(list => {
        const districtLayer = list.find(item =>
          item.name.toLowerCase().includes('district')
        );
        if (districtLayer) {
          originalDistrictLayer.current = {
            id: districtLayer.id,
            is_visible: districtLayer.is_visible,
            style: districtLayer.style,
            preview_geojson: districtLayer.preview_geojson,
          };
        }
        setLayers(list);
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!layers.length) return undefined;

    const districtLayer = layers.find(item =>
      item.name.toLowerCase().includes('district')
    );

    if (!selectedDistricts.length) {
      if (districtLayer && originalDistrictLayer.current) {
        const original = originalDistrictLayer.current;
        setLayers(current =>
          current.map(item =>
            item.id === original.id
              ? {
                  ...item,
                  is_visible: original.is_visible,
                  style: original.style,
                  preview_geojson: original.preview_geojson,
                }
              : item
          )
        );
      }
      setError('');
      setZoomTarget(null);
      return undefined;
    }

    if (!districtLayer) {
      setError('District GIS layer was not found.');
      return undefined;
    }

    const controller = new AbortController();

    async function zoomToDistrict() {
      try {
        setError('');
        const [west, south, east, north] = parseLayerBounds(districtLayer.bbox);
        const geojson = await api.geojson(
          districtLayer.id,
          [west, south, east, north].join(','),
          controller.signal
        );

        if (controller.signal.aborted) return;

        const features = selectedDistricts
          .map(name => ({
            name,
            feature: findDistrictFeature(geojson, name),
          }));
        const missing = features.filter(item => !item.feature).map(item => item.name);
        if (missing.length) {
          setError(`Could not find ${missing.join(', ')} in the District GIS boundary data.`);
          return;
        }

        const matchedFeatures = features.map(item => item.feature);
        const bounds = matchedFeatures.map(calculateBounds).filter(Boolean);
        if (!bounds.length) {
          setError('Could not calculate the selected district boundary.');
          return;
        }
        const bbox = [
          Math.min(...bounds.map(bound => bound[0])),
          Math.min(...bounds.map(bound => bound[1])),
          Math.max(...bounds.map(bound => bound[2])),
          Math.max(...bounds.map(bound => bound[3])),
        ];
        const original = originalDistrictLayer.current;

        setLayers(current =>
          current.map(item =>
            item.id === districtLayer.id
              ? {
                  ...item,
                  is_visible: true,
                  style: {
                    ...original?.style,
                    color: '#d99000',
                    fill_opacity: 0.06,
                    line_width: 2.5,
                    layer_opacity: 1,
                  },
                  preview_geojson: {
                    type: 'FeatureCollection',
                    features: matchedFeatures,
                  },
                }
              : item
          )
        );
        setZoomTarget({ bbox, padding: 28, maxZoom: 15, token: Date.now() });
      } catch (err) {
        if (err.name !== 'AbortError') setError(err.message);
      }
    }

    zoomToDistrict();
    return () => controller.abort();
  }, [selectedDistricts, layers.length]);

  function updateLayer(layerId, updates) {
    setLayers(current =>
      current.map(layer =>
        layer.id === layerId ? { ...layer, ...updates } : layer
      )
    );
  }

  return (
    <div className="flex h-dvh min-h-0 w-full flex-col overflow-hidden bg-[#e6ece7] text-slate-100">
      <LandSubHeader />

      <div className="relative min-h-0 flex-1">
        <main className="absolute inset-0">
          <MapPanel
            layers={layers}
            selectedLayer={null}
            onOpenAttributes={() => {}}
            zoomTarget={zoomTarget}
            showEmptyNotice={false}
            showStatusBanner={false}
            showLandControls
            initialCenter={LAND_MAP_CENTER}
            initialZoom={5.5}
          />

          <div className="absolute left-1/2 top-4 z-30 -translate-x-1/2 max-sm:top-2">
            <LandFilters
              layers={layers}
              selectedDistricts={selectedDistricts}
              onSelectionChange={setSelectedDistricts}
            />
          </div>

          <LeftToolbar
            activeTool={activeTool}
            onToolChange={tool => {
              setActiveTool(tool);
              setLayerManagerOpen(tool === 'layers' ? open => !open : true);
            }}
          />

          {layerManagerOpen && (
            <LayerManager
              layers={layers}
              loading={loading}
              activeTool={activeTool}
              onClose={() => setLayerManagerOpen(false)}
              onLayerChange={updateLayer}
            />
          )}

          {(loading || error) && (
            <div
              className={`absolute left-20 top-[76px] z-20 flex max-w-[min(32rem,calc(100%-6rem))] items-center gap-2 rounded-md border px-3 py-2 text-sm shadow-lg ${
                error
                  ? 'border-red-300 bg-red-50 text-red-800'
                  : 'border-emerald-200 bg-white text-emerald-900'
              }`}
              role={error ? 'alert' : 'status'}
            >
              {error
                ? <AlertCircle size={16} />
                : <CheckCircle2 size={16} className="animate-pulse" />}
              <span>{error || 'Loading map layers...'}</span>
            </div>
          )}

          <div className="absolute bottom-2 left-[320px] right-4 z-20 grid grid-cols-6 gap-2 max-lg:bottom-[58px] max-lg:left-3 max-lg:right-3 max-lg:grid-cols-3 max-sm:grid-cols-2 max-[600px]:hidden">
            {[
              { label: 'Districts', singular: 'District', Icon: MapPin },
              { label: 'Tehsils', singular: 'Tehsil', Icon: Grid2X2 },
              { label: 'Mauzas', singular: 'Mauza', Icon: Building2 },
              { label: 'Khasras', singular: 'Khasra', Icon: Blocks },
              { label: 'Squares', singular: 'Square', Icon: Blocks },
              { label: 'Acres', singular: 'Acre', Icon: Ruler },
            ].map(({ label, singular, Icon }, index) => {
              const layer = layers.find(item => new RegExp(singular, 'i').test(item.name));
              const value = index === 0 && selectedDistricts.length
                ? selectedDistricts.length
                : layer?.feature_count?.toLocaleString() || '—';
              const colors = ['bg-emerald-600', 'bg-cyan-700', 'bg-amber-600', 'bg-violet-700', 'bg-rose-700', 'bg-teal-700'];
              return (
                <div key={label} className="min-w-0 rounded-lg border border-emerald-800 bg-[#062d24]/95 px-3 py-2.5 shadow-lg">
                  <p className="truncate text-[10px] font-semibold uppercase tracking-[0.12em] text-emerald-100/70">{label}</p>
                  <p className="mt-1 flex items-center justify-between text-sm font-bold text-white">
                    {value}
                    <span className={`ml-2 grid h-7 w-7 shrink-0 place-items-center rounded ${colors[index]}`}>
                      <Icon size={15} />
                    </span>
                  </p>
                </div>
              );
            })}
          </div>

          <div className="absolute bottom-2 left-3 z-30 flex h-11 items-center gap-2 rounded-lg border border-emerald-800 bg-[#062d24]/95 px-3 text-xs font-semibold text-white shadow-lg max-sm:bottom-2 max-sm:left-2">
            <span className="text-lime-300">☷</span>
            <span className="whitespace-nowrap">Select Multiple Khasra:</span>
            <select className="h-8 rounded-md border border-slate-300 bg-white px-2 text-xs font-semibold text-slate-700" disabled value="Disabled" onChange={() => {}}>
              <option>Disabled</option>
            </select>
          </div>
        </main>
      </div>
    </div>
  );
}
