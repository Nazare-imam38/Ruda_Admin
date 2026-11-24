import { useState, useEffect } from 'react';
import { ArrowUpFromLine, FileArchive, FileCheck2, LoaderCircle } from 'lucide-react';
import { api } from '../api';

const defaults = (preview) => ({
  style: { color: '#2563eb', line_width: 3, fill_opacity: .30, point_radius: 6, raster_opacity: 1 },
  show_labels: false, label_field: preview?.field_names?.[0] || '', label_size: 12, label_min_zoom: 10,
  show_attributes: preview?.geometry_type !== 'Raster', show_popup: preview?.geometry_type !== 'Raster',
  attribute_fields: preview?.field_names || [], popup_fields: preview?.field_names || [], is_visible: true,
});

function Fields({ names, value, change }) {
  return <div className="field-picker-list">{names.map(n => <label className="field-pick-row" key={n}>
    <input type="checkbox" checked={value.includes(n)} onChange={() => change(value.includes(n) ? value.filter(v=>v!==n) : [...value,n])}/><span>{n}</span>
  </label>)}</div>;
}
function Range({ name, value, min, max, step=1, change }) {
  return <div className="settings-field"><label>{name} <strong>{value}</strong></label><input type="range" min={min} max={max} step={step} value={value} onChange={e=>change(Number(e.target.value))}/></div>;
}
export default function UploadForm({ layers = [], onUploaded, notify, onPreview }) {
  const [file, setFile] = useState(null);
  const [name, setName] = useState('');
  const [group, setGroup] = useState('Uploaded Layers');
  const [projectId, setProjectId] = useState('');
  const [preview, setPreview] = useState(null);
  const [configuration, setConfiguration] = useState(defaults(null));
  const [busy, setBusy] = useState('');
  const [relationship, setRelationship] = useState({
  parent_layer_id: '',
  parent_field: '',
  child_field: '',
});

const parentLayers = layers.filter(
  layer => layer.geometry_type !== 'Raster'
);

const selectedParent = parentLayers.find(
  layer => String(layer.id) === relationship.parent_layer_id
);

const relationshipComplete =
  relationship.parent_layer_id &&
  relationship.parent_field &&
  relationship.child_field;

const relationshipStarted = Object.values(relationship).some(Boolean);
  const edit=(k,v)=>setConfiguration(c=>({...c,[k]:v}));
  const style=(k,v)=>setConfiguration(c=>({...c,style:{...c.style,[k]:v}}));
  const raster = preview?.geometry_type === 'Raster';
  const previewCount = preview?.preview_geojson?.features?.length ?? 0;
  const previewComplete = !!preview && previewCount === preview.feature_count;
  useEffect(()=>{
    onPreview(preview?.preview_geojson ? {...configuration, id:'draft-preview', name:name||'Draft preview', geometry_type:preview.geometry_type, bbox:preview.bbox, preview_geojson:preview.preview_geojson, is_visible:true} : null);
  },[preview,configuration,name,onPreview]);
  useEffect(()=>()=>onPreview(null),[onPreview]);
  const makeFileForm=()=>{const d=new FormData();d.append('file',file);return d;};
  const inspect=async()=>{
    setBusy('preview');setPreview(null);
    try{const p=await api.preview(makeFileForm());setPreview(p);setConfiguration(defaults(p));}
    catch(e){notify(e.message,'error');}finally{setBusy('');}
  };
  const publish=async e=>{
    e.preventDefault();
    if(!file||!preview||!name.trim())return;
    const d=makeFileForm();d.append('name',name.trim());d.append('group',group);if(projectId)d.append('project_id',projectId);
    if (relationshipStarted && !relationshipComplete) {
  notify('Please select the parent layer, parent field and child field.', 'error');
  return;
}

const uploadConfiguration = {
  ...configuration,
  relationship: relationshipComplete
    ? {
        ...relationship,
        type: 'many-to-one',
      }
    : {},
};

d.append('configuration', JSON.stringify(uploadConfiguration));
setBusy('publish');
    try{const created=await api.upload(d);notify(`${created.name} published through ${created.publication.kind.toUpperCase()}.`);setPreview(null);await onUploaded(created);}
    catch(e){notify(e.message,'error');}finally{setBusy('');}
  };
  return <form className="upload-form" onSubmit={publish}>
    <div className="upload-zone"><FileArchive size={25}/><strong>{file?file.name:'Choose a GIS dataset'}</strong><span>Shapefile ZIP or GeoTIFF</span>
      <input type="file" disabled={!!busy} accept=".zip,.tif,.tiff" aria-label="Select dataset" onChange={e=>{const f=e.target.files?.[0]||null;setFile(f);setPreview(null);if(f)setName(f.name.replace(/\.(zip|tiff?)$/i,'').replaceAll('_',' '));}}/>
    </div>
    <label className="field-label">Layer name</label><input required maxLength={120} value={name} onChange={e=>setName(e.target.value)}/>
    <label className="field-label">Layer group</label><select value={group} onChange={e=>setGroup(e.target.value)}>
      {['Uploaded Layers','MASTERPLAN','ADMINISTRATIVE','BASE DATA','Hydrology','Private Housing Schemes','Drone Imagery','Change Detection','Topographic'].map(g=><option key={g}>{g}</option>)}
    </select>
    <label className="field-label">Project ID (optional)</label><input type="number" min="1" value={projectId} onChange={e=>setProjectId(e.target.value)}/>
    <button className="button secondary full" type="button" disabled={!!busy||!file} onClick={inspect}>{busy==='preview'?<LoaderCircle className="spin" size={15}/>:<FileCheck2 size={15}/>} Inspect dataset</button>
    {preview&&<>
      <div className="preview-card"><strong>Validated · {raster?'WMS raster':'WFS vector'}</strong><div>{raster?`${preview.raster.width} × ${preview.raster.height} pixels · ${preview.raster.bands} bands`:`${preview.feature_count.toLocaleString()} ${preview.geometry_type} features`}</div><div>CRS: {preview.source_crs}</div><div>{raster?'Raster preview appears on map after publishing.':previewComplete?`Map preview: all ${previewCount.toLocaleString()} of ${preview.feature_count.toLocaleString()} features included.`:`Partial preview: ${previewCount.toLocaleString()} of ${preview.feature_count.toLocaleString()} features included. The preview limit does not restrict publication.`}</div></div>
      <div className="section-heading"><strong>Configure before publishing</strong></div>
      {!raster && (
  <>
    <div className="section-heading">
      <strong>Parent-child relationship (optional)</strong>
    </div>

    <label className="field-label">Parent layer</label>
    <select
      value={relationship.parent_layer_id}
      onChange={e => setRelationship({
        parent_layer_id: e.target.value,
        parent_field: '',
        child_field: '',
      })}
    >
      <option value="">No parent layer</option>
      {parentLayers.map(layer => (
        <option key={layer.id} value={layer.id}>
          {layer.name}
        </option>
      ))}
    </select>

    {relationship.parent_layer_id && (
      <>
        <label className="field-label">Parent field</label>
        <select
          value={relationship.parent_field}
          onChange={e => setRelationship(r => ({
            ...r,
            parent_field: e.target.value,
          }))}
        >
          <option value="">Select parent field</option>
          {(selectedParent?.field_names || []).map(field => (
            <option key={field} value={field}>{field}</option>
          ))}
        </select>

        <label className="field-label">Child reference field</label>
        <select
          value={relationship.child_field}
          onChange={e => setRelationship(r => ({
            ...r,
            child_field: e.target.value,
          }))}
        >
          <option value="">Select child field</option>
          {(preview.field_names || []).map(field => (
            <option key={field} value={field}>{field}</option>
          ))}
        </select>

        <p className="form-hint">
          The child field must contain values matching the selected parent field.
          Original GIS attributes will not be changed.
        </p>
      </>
    )}
  </>
)}
      {raster?<Range name="Raster opacity" value={configuration.style.raster_opacity} min={0} max={1} step={.05} change={v=>style('raster_opacity',v)}/>:<>
        <div className="settings-field color-field"><label>Color</label><input type="color" value={configuration.style.color} onChange={e=>style('color',e.target.value)}/></div>
        {preview.geometry_type==='Polygon'&&<Range name="Fill opacity" value={configuration.style.fill_opacity} min={0} max={1} step={.05} change={v=>style('fill_opacity',v)}/>}
        {preview.geometry_type==='Point'?<Range name="Point radius" value={configuration.style.point_radius} min={2} max={18} change={v=>style('point_radius',v)}/>:<Range name="Line width" value={configuration.style.line_width} min={.5} max={12} step={.5} change={v=>style('line_width',v)}/>}
        <label className="switch-line"><span>Enable labels</span><input type="checkbox" checked={configuration.show_labels} onChange={e=>edit('show_labels',e.target.checked)}/></label>
        {configuration.show_labels&&<><label className="field-label">Label field</label><select value={configuration.label_field} onChange={e=>edit('label_field',e.target.value)}>{preview.field_names.map(n=><option key={n}>{n}</option>)}</select>
        <Range name="Label size" value={configuration.label_size} min={8} max={26} change={v=>edit('label_size',v)}/><Range name="Minimum label zoom" value={configuration.label_min_zoom} min={0} max={22} change={v=>edit('label_min_zoom',v)}/></>}
        <label className="switch-line"><span>Attribute table</span><input type="checkbox" checked={configuration.show_attributes} onChange={e=>edit('show_attributes',e.target.checked)}/></label>
        {configuration.show_attributes&&<Fields names={preview.field_names} value={configuration.attribute_fields} change={v=>edit('attribute_fields',v)}/>}
        <label className="switch-line"><span>Feature popup</span><input type="checkbox" checked={configuration.show_popup} onChange={e=>edit('show_popup',e.target.checked)}/></label>
        {configuration.show_popup&&<Fields names={preview.field_names} value={configuration.popup_fields} change={v=>edit('popup_fields',v)}/>}
      </>}
      <button className="button primary full" type="submit" disabled={!!busy}>{busy==='publish'?<LoaderCircle className="spin" size={16}/>:<ArrowUpFromLine size={16}/>} {busy==='publish'?'Processing and publishing…':'Publish to GeoServer'}</button>
    </>}
    <p className="form-hint">Phase 1 lab: ordinary vectors and rasters. ZIP ≤40 MB / 50,000 features; GeoTIFF ≤250 MB. Linked cadastral upload is not yet enabled.</p>
  </form>;
}
