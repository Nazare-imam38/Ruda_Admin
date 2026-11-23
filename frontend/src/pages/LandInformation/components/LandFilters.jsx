import { useEffect, useState } from 'react';
import { Check, ChevronDown } from 'lucide-react';
import { api } from '../../../api';

const viewOptions = ['District', 'Tehsil', 'Mauza'];

function nameField(fields = [], kind) {
  const normalizedKind = kind.toLowerCase();
  return fields.find(field => field.trim().toLowerCase() === 'name')
    || fields.find(field => field.trim().toLowerCase() === normalizedKind)
    || fields.find(field => field.toLowerCase().includes(normalizedKind))
    || fields.find(field => /name/i.test(field));
}

async function loadLayerNames(layer, kind) {
  const firstPage = await api.attributes(layer.id, 1, 100);
  const field = nameField(firstPage.fields, kind);
  if (!field) throw new Error(`${kind} name field was not found.`);

  const rows = [...(firstPage.rows || [])];
  for (let page = 2; page <= firstPage.total_pages; page += 1) {
    const result = await api.attributes(layer.id, page, 100);
    rows.push(...(result.rows || []));
  }

  return [...new Set(
    rows.map(row => row[field])
      .filter(value => value != null && String(value).trim())
      .map(value => String(value).trim())
  )].sort((a, b) => a.localeCompare(b));
}

function FilterDropdown({
  id,
  label,
  translation,
  options,
  selected,
  multiple = true,
  loading = false,
  disabled = false,
  emptyMessage,
  open,
  onToggle,
  onSelect,
}) {
  const selectedLabel = selected.length === 0
    ? 'Select'
    : selected.length === 1
      ? selected[0]
      : `${selected.length} selected`;

  return (
    <div className="relative w-[122px] shrink-0 max-sm:w-[calc(50%-0.375rem)]">
      <button
        type="button"
        className="flex h-[43px] w-full items-center justify-between rounded-lg border border-slate-300 bg-white px-2.5 text-left text-slate-700 shadow-sm outline-none transition hover:border-emerald-500 focus:border-emerald-600 focus:ring-2 focus:ring-emerald-600/20 disabled:cursor-not-allowed disabled:opacity-70"
        aria-expanded={open}
        aria-controls={`${id}-options`}
        disabled={disabled}
        onClick={onToggle}
      >
        <span className="min-w-0">
          <span className="block truncate text-[9px] leading-3 text-slate-500">
            {label} — {translation}
          </span>
          <span className="block truncate text-xs font-semibold leading-4 text-slate-800">
            {loading ? 'Loading...' : selectedLabel}
          </span>
        </span>
        <ChevronDown size={14} className="ml-1 shrink-0 text-slate-500" />
      </button>

      {open && (
        <div
          id={`${id}-options`}
          className="absolute left-0 top-[47px] z-50 max-h-60 w-full min-w-[164px] overflow-y-auto rounded-md border border-slate-200 bg-white p-1.5 text-sm text-slate-700 shadow-xl"
          role="group"
          aria-label={`${label} options`}
        >
          {loading ? (
            <p className="px-2 py-2 text-xs text-slate-500">Loading options...</p>
          ) : options.length ? (
            options.map(option => {
              const isSelected = selected.includes(option);
              return (
                <button
                  type="button"
                  key={option}
                  className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left hover:bg-emerald-50"
                  role="option"
                  aria-selected={isSelected}
                  onClick={() => onSelect(option, multiple)}
                >
                  <span className={`grid h-3.5 w-3.5 shrink-0 place-items-center rounded-[3px] border ${
                    isSelected ? 'border-emerald-700 bg-emerald-700 text-white' : 'border-slate-400 bg-white'
                  }`}>
                    {isSelected && <Check size={11} strokeWidth={3} />}
                  </span>
                  <span className="truncate">{option}</span>
                </button>
              );
            })
          ) : (
            <p className="px-2 py-2 text-xs text-slate-500">
              {emptyMessage || 'No options available.'}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export default function LandFilters({
  layers,
  selectedDistricts,
  onSelectionChange,
}) {
  const [districts, setDistricts] = useState([]);
  const [loadedOptions, setLoadedOptions] = useState({ tehsil: [], mauza: [] });
  const [loadingKey, setLoadingKey] = useState('');
  const [error, setError] = useState('');
  const [openDropdown, setOpenDropdown] = useState('');
  const [selectedTehsils, setSelectedTehsils] = useState([]);
  const [selectedMauzas, setSelectedMauzas] = useState([]);
  const [viewBy, setViewBy] = useState([]);

  const districtLayer = layers.find(layer => /district/i.test(layer.name));
  const districtLayerId = districtLayer?.id;

  useEffect(() => {
    if (!districtLayerId) {
      setDistricts([]);
      return undefined;
    }

    let active = true;
    async function loadDistricts() {
      try {
        setLoadingKey('district');
        setError('');
        const layer = layers.find(item => item.id === districtLayerId);
        const names = await loadLayerNames(layer, 'district');
        if (active) setDistricts(names);
      } catch (err) {
        if (active) setError(err.message);
      } finally {
        if (active) setLoadingKey('');
      }
    }

    loadDistricts();
    return () => {
      active = false;
    };
  }, [districtLayerId]);

  async function openFilter(key) {
    const nextOpen = openDropdown === key ? '' : key;
    setOpenDropdown(nextOpen);
    if (!nextOpen || !['tehsil', 'mauza'].includes(key) || loadedOptions[key].length) return;

    const layer = layers.find(item => new RegExp(key, 'i').test(item.name));
    if (!layer) return;

    try {
      setLoadingKey(key);
      setError('');
      const options = await loadLayerNames(layer, key);
      setLoadedOptions(current => ({ ...current, [key]: options }));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingKey('');
    }
  }

  function toggleOption(option, multiple, selected, setSelected) {
    if (!multiple) {
      setSelected([option]);
      setOpenDropdown('');
      return;
    }
    const updated = selected.includes(option)
      ? selected.filter(value => value !== option)
      : [...selected, option];
    setSelected(updated);
  }

  function updateDistrict(option) {
    const updated = selectedDistricts.includes(option)
      ? selectedDistricts.filter(value => value !== option)
      : [...selectedDistricts, option];
    onSelectionChange(updated);
  }

  return (
    <div className="flex items-center gap-2 rounded-xl bg-[#064536]/95 p-2 shadow-xl ring-1 ring-white/15 max-sm:w-[min(100%,520px)] max-sm:flex-wrap">
      <FilterDropdown
        id="land-district"
        label="District"
        translation="ضلع"
        options={districts}
        selected={selectedDistricts}
        loading={loadingKey === 'district'}
        open={openDropdown === 'district'}
        onToggle={() => openFilter('district')}
        onSelect={updateDistrict}
        emptyMessage={error || 'No districts available.'}
      />
      <FilterDropdown
        id="land-tehsil"
        label="Tehsil"
        translation="تحصیل"
        options={loadedOptions.tehsil}
        selected={selectedTehsils}
        loading={loadingKey === 'tehsil'}
        open={openDropdown === 'tehsil'}
        onToggle={() => openFilter('tehsil')}
        onSelect={option => toggleOption(option, true, selectedTehsils, setSelectedTehsils)}
        emptyMessage={error || 'No tehsil layer available.'}
      />
      <FilterDropdown
        id="land-mauza"
        label="Mauza"
        translation="موضع"
        options={loadedOptions.mauza}
        selected={selectedMauzas}
        loading={loadingKey === 'mauza'}
        open={openDropdown === 'mauza'}
        onToggle={() => openFilter('mauza')}
        onSelect={option => toggleOption(option, true, selectedMauzas, setSelectedMauzas)}
        emptyMessage={error || 'No mauza layer available.'}
      />
      <FilterDropdown
        id="land-view-by"
        label="View By"
        translation="انتخاب کریں"
        options={viewOptions}
        selected={viewBy}
        multiple={false}
        open={openDropdown === 'viewBy'}
        onToggle={() => openFilter('viewBy')}
        onSelect={option => toggleOption(option, false, viewBy, setViewBy)}
      />
    </div>
  );
}
