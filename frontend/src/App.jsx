import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Layers3, UploadCloud, Map, Database, CheckCircle2, AlertCircle,
  Eye, EyeOff, ChevronRight, Crosshair, Table2, SlidersHorizontal,
  RefreshCcw, FilePlus2, X,
} from 'lucide-react';
import { api } from './api';
import UploadForm from './components/UploadForm';
import MapPanel from './components/MapPanel';
import LayerSettings from './components/LayerSettings';
import AttributeTable from './components/AttributeTable';
import LandInformation from './pages/LandInformation/LandInformation';

function geometryIcon(type) {
  return type === 'Point' ? '●' : type === 'Line' ? '〰' : '⬡';
}

export default function App() {
  const [draftPreview, setDraftPreview] = useState(null);
  const [geoStatus, setGeoStatus] = useState('unchecked');
  const previewBounds = useMemo(()=>draftPreview?.bbox?.join(',') || '',[draftPreview]);
  const [layers, setLayers] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [activeTab, setActiveTab] = useState('layers');
  const [activePage, setActivePage] = useState('gis');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [tableOpen, setTableOpen] = useState(false);
  const [toast, setToast] = useState(null);
  const [serverStatus, setServerStatus] = useState('checking');
  const [zoomTarget, setZoomTarget] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(()=>{if(previewBounds) setZoomTarget({bbox:previewBounds.split(',').map(Number),token:Date.now()});},[previewBounds]);
  const selectedLayer = layers.find(item => item.id === selectedId) || null;

  const notify = useCallback((message, type = 'success') => {
    setToast({ message, type, key: Date.now() });
  }, []);

  const refresh = useCallback(async () => {
    const list = await api.layers();
    setLayers(list);
    setLoading(false);
    return list;
  }, []);

  useEffect(() => {
    Promise.all([api.health(), refresh()]).then(() => setServerStatus('connected'))
      .catch(e => { setServerStatus('offline'); setLoading(false); notify(`Cannot connect to backend: ${e.message}`, 'error'); });
  }, [refresh, notify]);

  const checkGeoServer = useCallback(async()=>{setGeoStatus('checking');try{await api.geoserverHealth();setGeoStatus('connected');}catch(e){setGeoStatus('offline');notify(e.message,'error');}},[notify]);
  const mapLayers = useMemo(()=>draftPreview?[...layers,draftPreview]:layers,[layers,draftPreview]);
  const allGroups = useMemo(() => Object.entries(layers.reduce((obj, layer) => {
    const key = layer.group || 'Uploaded Layers';
    (obj[key] ||= []).push(layer);
    return obj;
  }, {})), [layers]);

  const handleUpdated = async (id, patch, refreshOnly = false) => {
    if (!refreshOnly && patch) await api.update(id, patch);
    await refresh();
  };

  const onUploaded = async layer => {
    await refresh();
    setSelectedId(layer.id);
    setZoomTarget({ bbox: layer.bbox, token: Date.now() });
    setSettingsOpen(true);
    setActiveTab('layers');
  };

  const handleDeleted = async id => {
    await api.remove(id);
    if (selectedId === id) { setSelectedId(null); setSettingsOpen(false); setTableOpen(false); }
    await refresh();
  };

  const toggle = async (item) => {
    try { await api.update(item.id, { is_visible: !item.is_visible }); await refresh(); }
    catch (e) { notify(e.message, 'error'); }
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><div className="brand-logo"><Layers3 size={24}/></div><div><strong>GIS Automation</strong><span>LAB · GEOSERVER v3</span></div></div>
        <div className="environment-note"><span className="pulse-dot" /> SEPARATE TEST PROJECT <span className="environment-pill">SAFE LAB</span></div>
        <div className="sidebar-tabs">
          <button
              className={activePage === 'land' ? 'active' : ''}
             onClick={() => {
              window.location.href = '/land-information';
            }}
            >
              <Map size={17} /> Land Information
            </button>
          <button className={activeTab === 'layers' ? 'active' : ''} onClick={() => setActiveTab('layers')}><Layers3 size={17}/> Map Layers</button>
          <button className={activeTab === 'upload' ? 'active' : ''} onClick={() => setActiveTab('upload')}><UploadCloud size={17}/> Upload dataset</button>
        </div>
        {activePage === 'land' ? null : activeTab === 'upload' ? (
          <div className="sidebar-content"><div className="sidebar-content-title"><span>NEW DATASET</span><h3>Upload dataset</h3><p>Configure, then publish WFS or WMS.</p></div><UploadForm
  layers={layers}
  onUploaded={onUploaded}
  notify={notify}
  onPreview={setDraftPreview}
/></div>
        ) : (
          <div className="sidebar-content">
            <div className="list-title"><div><span className="mini-eyebrow">DATA CATALOG</span><h3>Published layers <em>{layers.length}</em></h3></div><button className="icon-button" title="Refresh layers" onClick={() => refresh().catch(e => notify(e.message, 'error'))}><RefreshCcw size={16}/></button></div>
            {loading ? <p className="sidebar-empty">Connecting to database…</p> : layers.length === 0 ? (
              <div className="no-layers"><FilePlus2 size={30}/><strong>No layers imported yet</strong><p>Start with a sample vector or raster.</p><button className="button primary" onClick={() => setActiveTab('upload')}>Upload first layer</button></div>
            ) : allGroups.map(([group, items]) => (
              <div key={group} className="layer-group"><div className="layer-group-header"><Database size={14}/>{group}<span>{items.length}</span></div>
                {items.map(layer => <div className={`layer-row ${selectedId === layer.id ? 'selected' : ''}`} key={layer.id}>
                  <button className="layer-visibility" aria-label={`${layer.is_visible ? 'Hide' : 'Show'} ${layer.name}`} title="Toggle visibility" onClick={() => toggle(layer)}>{layer.is_visible ? <Eye size={17}/> : <EyeOff size={17}/>}</button>
                  <button className="layer-select" onClick={() => { setSelectedId(layer.id); setSettingsOpen(true); }}>
                    <span className="layer-geometry-icon" style={{ color: layer.style?.color || '#2563eb' }}>{geometryIcon(layer.geometry_type)}</span>
                    <span className="layer-text"><strong>{layer.name}</strong><small>{layer.geometry_type==='Raster'?'WMS raster':`${layer.feature_count.toLocaleString()} features · ${layer.publication?.kind==='wfs'?'WFS':'PostGIS legacy'}`} </small></span>
                    <ChevronRight size={15}/>
                  </button>
                </div>)}
              </div>
            ))}
            {layers.length > 0 && <button className="button dashed full add-another" onClick={() => setActiveTab('upload')}><FilePlus2 size={16}/> Add another dataset</button>}
          </div>
        )}
        <div className="sidebar-bottom"><div className={`status-indicator ${serverStatus}`}><span className="status-dot"/>{serverStatus === 'connected' ? 'PostGIS connected' : serverStatus === 'checking' ? 'Checking server' : 'Backend offline'}</div><span className="muted">Database: gis_automation_test</span><button className="button secondary full" onClick={checkGeoServer} disabled={geoStatus==='checking'}>GeoServer: {geoStatus==='connected'?'connected':geoStatus==='checking'?'checking…':'test connection'}</button></div>
      </aside>
      <div className={activePage === 'land' ? 'main-column land-page-mode' : 'main-column'}>
        {activePage === 'land' ? (
          <div className="w-full h-full min-h-0 flex-1 overflow-hidden">
            <LandInformation />
          </div>
        ) : (
          <>
        <header className="topbar"><div className="topbar-title"><span>PROJECT / TEST ENVIRONMENT</span><h1>Dynamic GIS Layer Manager</h1></div><div className="topbar-actions"><span className="topbar-chip"><CheckCircle2 size={14}/> Independent of RUDA</span><button className="button topbar-upload" onClick={() => setActiveTab('upload')}><UploadCloud size={16}/> Upload dataset</button></div></header>
        <div className="workspace">
          <div className="map-workspace"><MapPanel layers={mapLayers} selectedLayer={selectedLayer} onOpenAttributes={() => setTableOpen(true)} zoomTarget={zoomTarget}/>
            {tableOpen && selectedLayer && <AttributeTable layer={selectedLayer} onClose={() => setTableOpen(false)}/>} 
          </div>
          {settingsOpen && selectedLayer && <LayerSettings
  layer={selectedLayer}
  layers={layers}
  onClose={() => setSettingsOpen(false)}
  onUpdated={handleUpdated}
  onDeleted={handleDeleted}
  onZoom={item => setZoomTarget({ bbox: item.bbox, token: Date.now() })}
  notify={notify}
/>} 
        </div>
        <footer className="statusbar"><span><Map size={13}/> OpenStreetMap basemap</span><span><Crosshair size={13}/> EPSG:4326 · WGS 84</span><span><Table2 size={13}/> WFS / WMS + legacy PostGIS</span><span className="statusbar-right">Built for RUDA workflow testing, not production</span></footer>
          </>
        )}
      </div>
      {toast && <div role="status" key={toast.key} className={`toast ${toast.type === 'error' ? 'error' : 'success'}`}>{toast.type === 'error' ? <AlertCircle size={19}/> : <CheckCircle2 size={19}/>}<span>{toast.message}</span><button aria-label="Dismiss notification" onClick={() => setToast(null)}><X size={16}/></button></div>}
    </div>
  );
}
