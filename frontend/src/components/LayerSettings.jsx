import { useEffect, useState } from 'react';
import { Check, Compass, Palette, Replace, Save, Trash2, X, Tags, Table2, Database, Eye } from 'lucide-react';
import { api } from '../api';

const TABS = [
  { id: 'labels', name: 'Labels', icon: Tags },
  { id: 'attributes', name: 'Attributes', icon: Table2 },
  { id: 'relationship', name: 'Relationship', icon: Database },
  { id: 'appearance', name: 'Style', icon: Palette },
  { id: 'data', name: 'Data', icon: Database },
];

function FieldPicker({ names, selected, onChange, emptyText }) {
  const allSelected = names.length > 0 && names.every(name => selected.includes(name));
  const toggle = name => onChange(selected.includes(name) ? selected.filter(v => v !== name) : names.filter(v => v === name || selected.includes(v)));
  return (
    <div className="field-picker">
      <div className="field-picker-toolbar">
        <span>{selected.length} / {names.length} selected</span>
        <button type="button" onClick={() => onChange(allSelected ? [] : [...names])}>{allSelected ? 'Clear all' : 'Select all'}</button>
      </div>
      {names.length === 0 ? <span>{emptyText || 'No fields available'}</span> :
        <div className="field-picker-list">
          {names.map(name => <label key={name} className="field-pick-row">
            <input type="checkbox" checked={selected.includes(name)} onChange={() => toggle(name)}/>
            <span title={name}>{name}</span>
          </label>)}
        </div>}
    </div>
  );
}

export default function LayerSettings({ layer, layers = [], onClose, onUpdated, onDeleted, onZoom, notify }) {
  const isRaster = layer.geometry_type==='Raster';
  const published = !!layer.publication?.kind;
  const [draft, setDraft] = useState({});
  const [tab, setTab] = useState(isRaster?'appearance':'labels');
  const [busy, setBusy] = useState(false);
  const [replacing, setReplacing] = useState(false);
  useEffect(() => {
    setDraft({
      name: layer.name, group: layer.group, is_visible: layer.is_visible,
      show_labels: layer.show_labels, show_popup: layer.show_popup,
      show_attributes: layer.show_attributes ?? true,
      attribute_fields: [...(layer.attribute_fields || [])],
      popup_fields: [...(layer.popup_fields || [])],
      label_field: layer.label_field || '', label_min_zoom: layer.label_min_zoom ?? 10,
      label_size: layer.label_size ?? 12,
      style: { color: layer.style?.color || '#2563eb',
        fill_opacity: layer.style?.fill_opacity ?? 0.3,
        line_width: layer.style?.line_width ?? 3,
        point_radius: layer.style?.point_radius ?? 6, raster_opacity: layer.style?.raster_opacity ?? 1 },

        relationship: {
  parent_layer_id: layer.relationship?.parent_layer_id || '',
  parent_field: layer.relationship?.parent_field || '',
  child_field: layer.relationship?.child_field || '',
},
    });
  }, [layer]);
  useEffect(()=>{setTab(isRaster?'appearance':'labels');},[layer.id,isRaster]);
  const edit = (key, value) => setDraft(d => ({ ...d, [key]: value }));
  const editStyle = (key, value) => setDraft(d => ({ ...d, style: { ...d.style, [key]: value } }));
  const parentLayers = layers.filter(
  item => item.id !== layer.id && item.geometry_type !== 'Raster'
);

const relationship = draft.relationship || {};

const selectedParent = parentLayers.find(
  item => String(item.id) === String(relationship.parent_layer_id)
);

const editRelationship = (key, value) => {
  setDraft(d => ({
    ...d,
    relationship: {
      ...d.relationship,
      [key]: value,
    },
  }));
};

const changeParentLayer = (value) => {
  setDraft(d => ({
    ...d,
    relationship: {
      parent_layer_id: value,
      parent_field: '',
      child_field: '',
    },
  }));
};
const save = async () => {
  const relation = draft.relationship || {};

  if (
    relation.parent_layer_id &&
    (!relation.parent_field || !relation.child_field)
  ) {
    notify('Please select both the parent field and child reference field.', 'error');
    return;
  }

  const updatedDraft = {
    ...draft,
    relationship: relation.parent_layer_id
      ? {
          ...relation,
          type: 'many-to-one',
        }
      : {},
  };

  setBusy(true);

  try {
    await onUpdated(layer.id, updatedDraft);
    notify('Layer settings and relationship saved.', 'success');
  } catch (e) {
    notify(e.message, 'error');
  } finally {
    setBusy(false);
  }
};
  const replace = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    if (!window.confirm(`Replace the dataset for "${layer.name}"? Existing configuration will be preserved; incompatible uploads are rejected.`)) return;
    setReplacing(true);
    try {
      const fd = new FormData(); fd.append('file', file);
      const updated = await api.replace(layer.id, fd);
      notify(`Replaced ${updated.name} (v${updated.version}).`, 'success');
      await onUpdated(layer.id, null, true);
    } catch (e) { notify(e.message, 'error'); }
    finally { setReplacing(false); }
  };
  const remove = async () => {
    if (!window.confirm(`Remove "${layer.name}" from the lab? ${published?"Published server files will be retained for recovery.":"Its legacy PostGIS table will be deleted."}`)) return;
    setBusy(true);
    try { await onDeleted(layer.id); notify('Layer removed from the catalog.', 'success'); }
    catch (e) { notify(e.message, 'error'); setBusy(false); }
  };
  return (
    <aside className="settings-panel">
      <div className="settings-heading"><div><span className="mini-eyebrow">LAYER INSPECTOR</span><h3>Layer settings</h3></div><button className="icon-button" aria-label="Close settings" onClick={onClose}><X size={17}/></button></div>
      <div className="layer-summary-strip">
        <strong title={layer.name}>{layer.name}</strong>
        <span>{isRaster?'Raster imagery':`${layer.geometry_type} · ${layer.feature_count.toLocaleString()} records`}</span>
        <code>{published?`${layer.publication.kind.toUpperCase()}: ${layer.publication.workspace}:${layer.publication.name}`:`Legacy PostGIS: public.${layer.table_name||'pending'}`}</code>
      </div>
      <div className="settings-tabs" role="tablist" aria-label="Layer configuration sections">
        {TABS.filter(item=>!isRaster||['appearance','data'].includes(item.id)).map(item => <button key={item.id} type="button" role="tab" aria-selected={tab === item.id} className={tab === item.id ? 'selected' : ''} onClick={() => setTab(item.id)}>
          <item.icon size={15}/><span>{item.name}</span>
        </button>)}
      </div>
      <div className="settings-scroll" key={tab}>
        {!isRaster && tab === 'labels' && <>
          <div className="section-heading"><Tags size={17}/><strong>Labeling controls</strong></div>
          <p className="settings-help">Choose which shapefile attribute should appear as a label on the map.</p>
          <label className="switch-line"><span>Enable labels</span><input type="checkbox" checked={!!draft.show_labels} onChange={e => edit('show_labels', e.target.checked)}/></label>
          <div className="settings-field"><label>Label attribute column</label>
            <select value={draft.label_field || ''} onChange={e => edit('label_field', e.target.value)}>
              <option value="">Select an attribute</option>
              {layer.field_names.map(name => <option value={name} key={name}>{name}</option>)}
            </select>
          </div>
          <div className="settings-field"><label>Display labels from zoom <strong>{draft.label_min_zoom ?? 10}</strong></label><input type="range" min="0" max="22" step="1" value={draft.label_min_zoom ?? 10} onChange={e => edit('label_min_zoom', Number(e.target.value))}/></div>
          <div className="settings-field"><label>Label font size <strong>{draft.label_size ?? 12}px</strong></label><input type="range" min="8" max="26" step="1" value={draft.label_size ?? 12} onChange={e => edit('label_size', Number(e.target.value))}/></div>
          <p className="settings-help">Zoom 10 is the default. MapLibre automatically hides colliding labels.</p>
          <div className="section-separator" />
          <label className="switch-line"><span>Show layer on map</span><input type="checkbox" checked={!!draft.is_visible} onChange={e => edit('is_visible', e.target.checked)}/></label>
        </>}
        {!isRaster && tab === 'attributes' && <>
          <div className="section-heading"><Table2 size={17}/><strong>Attribute table</strong></div>
          <p className="settings-help">Choose the exact shapefile columns to show when you open the attribute table.</p>
          <label className="switch-line"><span>Enable attribute table</span><input type="checkbox" checked={!!draft.show_attributes} onChange={e => edit('show_attributes', e.target.checked)}/></label>
          <FieldPicker names={layer.field_names} selected={draft.attribute_fields || []} onChange={v => edit('attribute_fields', v)}/>
          <div className="section-separator" />
          <div className="section-heading"><Eye size={17}/><strong>Map popup fields</strong></div>
          <label className="switch-line"><span>Enable feature popup</span><input type="checkbox" checked={!!draft.show_popup} onChange={e => edit('show_popup', e.target.checked)}/></label>
          <p className="settings-help">Select the attributes shown when you click a map feature.</p>
          <FieldPicker names={layer.field_names} selected={draft.popup_fields || []} onChange={v => edit('popup_fields', v)}/>
        </>}
        {tab === 'appearance' && <>
          <div className="section-heading"><Palette size={17}/><strong>Appearance</strong></div>
          {isRaster ? <div className="settings-field"><label>Raster opacity <strong>{draft.style?.raster_opacity??1}</strong></label><input type="range" min="0" max="1" step="0.05" value={draft.style?.raster_opacity??1} onChange={e=>editStyle('raster_opacity',Number(e.target.value))}/></div> : <>
          <div className="settings-field color-field"><label>Layer color</label><input type="color" aria-label="Layer color" value={draft.style?.color || '#2563eb'} onChange={e => editStyle('color', e.target.value)}/><span>{draft.style?.color || '#2563eb'}</span></div>
          {layer.geometry_type === 'Polygon' && (
            <div className="settings-field"><label>Fill opacity <strong>{draft.style?.fill_opacity ?? 0.3}</strong></label><input type="range" min="0" max="1" step="0.05" value={draft.style?.fill_opacity ?? 0.3} onChange={e => editStyle('fill_opacity', Number(e.target.value))}/></div>
          )}
          {layer.geometry_type !== 'Point' ? (
            <div className="settings-field"><label>Line width <strong>{draft.style?.line_width ?? 3}px</strong></label><input type="range" min="0.5" max="12" step="0.5" value={draft.style?.line_width ?? 3} onChange={e => editStyle('line_width', Number(e.target.value))}/></div>
          ) : (
            <div className="settings-field"><label>Point radius <strong>{draft.style?.point_radius ?? 6}px</strong></label><input type="range" min="2" max="18" step="1" value={draft.style?.point_radius ?? 6} onChange={e => editStyle('point_radius', Number(e.target.value))}/></div>
          )}
          </>}
          <button className="button full secondary" onClick={() => onZoom(layer)}><Compass size={15}/> Zoom to layer</button>
        </>}
        {tab === 'data' && <>
        {!isRaster && tab === 'relationship' && <>
  <div className="section-heading">
    <Database size={17}/>
    <strong>Parent-child relationship</strong>
  </div>

  <p className="settings-help">
    Configure how this layer references another published layer.
    This saves relationship metadata only; original GIS attributes remain unchanged.
  </p>

  <div className="settings-field">
    <label>Parent layer</label>
    <select
      value={relationship.parent_layer_id || ''}
      onChange={e => changeParentLayer(e.target.value)}
    >
      <option value="">No parent layer</option>
      {parentLayers.map(item => (
        <option key={item.id} value={item.id}>{item.name}</option>
      ))}
    </select>
  </div>

  {relationship.parent_layer_id && (
    <>
      <div className="settings-field">
        <label>Parent field</label>
        <select
          value={relationship.parent_field || ''}
          onChange={e => editRelationship('parent_field', e.target.value)}
        >
          <option value="">Select parent field</option>
          {(selectedParent?.field_names || []).map(field => (
            <option key={field} value={field}>{field}</option>
          ))}
        </select>
      </div>

      <div className="settings-field">
        <label>Child reference field</label>
        <select
          value={relationship.child_field || ''}
          onChange={e => editRelationship('child_field', e.target.value)}
        >
          <option value="">Select child field</option>
          {(layer.field_names || []).map(field => (
            <option key={field} value={field}>{field}</option>
          ))}
        </select>
      </div>

      <p className="settings-help">
        Example: District.ID → Tehsil.DISTRICT_I
      </p>
    </>
  )}
</>}
          <div className="section-heading"><Database size={17}/><strong>Storage and service</strong></div>
          <div className="db-table-card"><span>{published?'GeoServer published layer':'Legacy PostgreSQL table'}</span><strong>{published?`${layer.publication.workspace}:${layer.publication.name}`:`public.${layer.table_name||'pending'}`}</strong><small>{published?`${layer.publication.kind.toUpperCase()} · File storage · v${layer.version}`:'PostGIS · legacy dataset'}</small></div>
          <div className="settings-field"><label>Layer name (display only)</label><input value={draft.name || ''} onChange={e => edit('name', e.target.value)} /></div>
          <div className="settings-field"><label>Group</label><input value={draft.group || ''} onChange={e => edit('group', e.target.value)} /></div>
          <div className="metadata-detail"><span>Original CRS</span><strong>{layer.source_crs}</strong></div>
          <div className="metadata-detail"><span>Source filename</span><strong title={layer.source_filename}>{layer.source_filename}</strong></div>
          <div className="metadata-detail"><span>Project ID</span><strong>{layer.project_id ?? 'Global / none'}</strong></div>
          <div className="section-separator" />
          <div className="section-heading"><Replace size={17}/><strong>Replace dataset</strong></div>
          <p className="settings-help">Replace the dataset while keeping the same layer identity and settings. Published file layers retain the previous version.</p>
          <label className={`button secondary full file-button ${replacing ? 'disabled' : ''}`}>
            <Replace size={15}/>{replacing ? 'Replacing…' : 'Choose replacement file'}
            <input disabled={replacing||busy} type="file" accept={isRaster?'.tif,.tiff':'.zip'} onChange={replace} />
          </label>
          {published&&layer.version>1&&<button className="button secondary full" disabled={busy||replacing} onClick={async()=>{if(!window.confirm('Switch back to the previous published data version?'))return;setBusy(true);try{await api.rollback(layer.id);await onUpdated(layer.id,null,true);notify('Previous publication restored.');}catch(e){notify(e.message,'error');}finally{setBusy(false);}}}>Rollback previous version</button>}
          <button className="button danger-text full" disabled={busy||replacing} onClick={remove}><Trash2 size={15}/> Remove layer</button>
        </>}
      </div>
      <div className="settings-footer"><button className="button primary full" onClick={save} disabled={busy||replacing}><Save size={16}/>{busy ? 'Saving…' : 'Save configuration'}</button></div>
    </aside>
  );
}
