import { useMemo, useState } from 'react';
import {
  ChevronDown,
  ChevronUp,
  Grid2X2,
  Layers3,
  X,
} from 'lucide-react';

const DEFAULT_COLORS = ['#d99a00', '#2865b0', '#131313', '#23a65b', '#758b00', '#a8600d'];

function layerColor(layer, index) {
  return layer.style?.color || DEFAULT_COLORS[index % DEFAULT_COLORS.length];
}

function LayerRow({ layer, index, onChange }) {
  const [expanded, setExpanded] = useState(false);
  const opacity = Math.round((layer.style?.layer_opacity ?? 1) * 100);

  function updateOpacity(value) {
    onChange(layer.id, {
      style: { ...layer.style, layer_opacity: Number(value) / 100 },
    });
  }

  return (
    <div className="border-b border-emerald-900/70 px-3 py-2.5 last:border-b-0">
      <div className="flex min-h-8 items-center gap-2.5">
        <input
          className="h-4 w-4 shrink-0 cursor-pointer accent-[#9fe47b]"
          type="checkbox"
          aria-label={`Show ${layer.name}`}
          checked={Boolean(layer.is_visible)}
          onChange={event => onChange(layer.id, { is_visible: event.target.checked })}
        />
        <span
          className="h-5 w-5 shrink-0 rounded-sm border border-white/25"
          style={{ backgroundColor: layerColor(layer, index) }}
          aria-hidden="true"
        />
        <span className="min-w-0 flex-1 truncate text-sm font-semibold text-slate-200" title={layer.name}>
          {layer.name}
        </span>
        <button
          type="button"
          className="grid h-8 w-8 shrink-0 place-items-center rounded text-slate-300 hover:bg-emerald-800 hover:text-white"
          aria-label={`Adjust ${layer.name} opacity`}
          title="Layer display options"
          onClick={() => setExpanded(value => !value)}
        >
          <Grid2X2 size={17} />
        </button>
        <button
          type="button"
          className="grid h-8 w-8 shrink-0 place-items-center rounded text-slate-300 hover:bg-emerald-800 hover:text-white"
          aria-label={`${expanded ? 'Collapse' : 'Expand'} ${layer.name}`}
          aria-expanded={expanded}
          onClick={() => setExpanded(value => !value)}
        >
          {expanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </button>
      </div>
      <div className="ml-7 mt-1 flex items-center gap-3">
        <input
          className="h-1.5 min-w-0 flex-1 cursor-pointer accent-[#9fe47b]"
          type="range"
          min="0"
          max="100"
          value={opacity}
          aria-label={`${layer.name} opacity`}
          onChange={event => updateOpacity(event.target.value)}
        />
        <span className="w-10 text-right text-xs font-semibold text-slate-400">{opacity}%</span>
      </div>
      {expanded && (
        <p className="ml-7 mt-1 text-[11px] text-emerald-100/70">
          {layer.geometry_type === 'Raster' ? 'Raster layer' : `${layer.geometry_type || 'Map'} boundary`}
        </p>
      )}
    </div>
  );
}

export default function LayerManager({
  layers,
  loading,
  activeTool,
  onClose,
  onLayerChange,
}) {
  const [expanded, setExpanded] = useState(true);

  const sortedLayers = useMemo(() => [...layers].sort((a, b) => {
    const aDistrict = /district/i.test(a.name);
    const bDistrict = /district/i.test(b.name);
    return Number(bDistrict) - Number(aDistrict) || a.name.localeCompare(b.name);
  }), [layers]);

  const layerList = activeTool === 'imagery'
    ? sortedLayers.filter(layer => layer.geometry_type === 'Raster')
    : activeTool === 'boundaries'
      ? sortedLayers.filter(layer => /district|tehsil|mauza|boundary/i.test(layer.name))
      : sortedLayers;
  const heading = activeTool === 'imagery'
    ? 'Map Imagery'
    : activeTool === 'boundaries'
      ? 'Administrative Boundaries'
      : activeTool === 'tools'
        ? 'Map Tools'
        : 'Layer Manager';

  return (
    <aside
      className="absolute left-[76px] top-6 z-20 flex max-h-[calc(100%-3rem)] w-[350px] max-w-[calc(100%-6rem)] flex-col overflow-hidden rounded-xl border border-emerald-800 bg-[#062d24]/[0.97] text-slate-100 shadow-2xl ring-1 ring-black/10 max-sm:left-[60px] max-sm:top-3 max-sm:max-h-[calc(100%-1.5rem)] max-sm:w-[min(350px,calc(100%-4.5rem))]"
      aria-label="Layer manager"
    >
      <div className="flex h-[56px] shrink-0 items-center justify-between border-b border-emerald-900 px-4">
        <div className="flex items-center gap-2.5">
          <Layers3 size={19} className="text-emerald-200" />
          <h2 className="text-base font-bold uppercase tracking-wide">{heading}</h2>
        </div>
        <button
          type="button"
          className="grid h-8 w-8 place-items-center rounded text-emerald-100/60 hover:bg-emerald-800 hover:text-white"
          aria-label="Close layer manager"
          onClick={onClose}
        >
          <X size={19} />
        </button>
      </div>

      <div className="mx-4 my-3 rounded-lg border border-emerald-800 bg-[#031f19] p-3.5">
        <p className="text-xs leading-5 text-emerald-50/90">
          Select a district above to zoom to its boundary. Toggle layers and adjust opacity below.
        </p>
      </div>

      <section className="mx-4 mb-4 min-h-0 overflow-hidden rounded-lg border border-emerald-800">
        <button
          type="button"
          className="flex min-h-[46px] w-full items-center justify-between bg-[#07382c] px-3.5 text-left text-sm font-bold"
          aria-expanded={expanded}
          onClick={() => setExpanded(value => !value)}
        >
          <span>Administrative Boundaries</span>
          {expanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </button>

        {expanded && (
          <div className="max-h-[min(52vh,520px)] overflow-y-auto">
            {loading ? (
              <p className="px-4 py-5 text-sm text-emerald-100/70">Loading map layers...</p>
            ) : layerList.length ? (
              layerList.map((layer, index) => (
                <LayerRow
                  key={layer.id}
                  layer={layer}
                  index={index}
                  onChange={onLayerChange}
                />
              ))
            ) : (
              <p className="px-4 py-5 text-sm text-emerald-100/70">No map layers available.</p>
            )}
          </div>
        )}
      </section>
    </aside>
  );
}
