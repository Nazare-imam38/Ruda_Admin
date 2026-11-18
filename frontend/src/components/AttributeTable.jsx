import { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, X, Table2 } from 'lucide-react';
import { api } from '../api';

export default function AttributeTable({ layer, onClose }) {
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => { setPage(1); }, [layer.id]);
  useEffect(() => {
    let active = true;
    setError('');
    setData(null);
    api.attributes(layer.id, page).then(v => { if (active) setData(v); })
      .catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [layer.id, layer.version, layer.updated_at, page]);
  return (
    <div className="attributes-panel">
      <div className="attributes-header">
        <div className="attributes-title"><Table2 size={18} /><strong>{layer.name}</strong><span>{layer.feature_count.toLocaleString()} features</span></div>
        <div className="attrs-pager">
          <button aria-label="Previous page" disabled={page <= 1} onClick={() => setPage(v => v - 1)}><ChevronLeft size={16}/></button>
          <span>Page {page} / {data?.total_pages || '...'}</span>
          <button aria-label="Next page" disabled={!data || page >= data.total_pages} onClick={() => setPage(v => v + 1)}><ChevronRight size={16}/></button>
          <button aria-label="Close attributes" className="attrs-close" onClick={onClose}><X size={17}/></button>
        </div>
      </div>
      {error ? <div className="panel-error">{error}</div> : !data ? <div className="panel-loading">Loading records…</div> : data.disabled ? <div className="panel-loading">Attribute table disabled in layer settings.</div> : data.fields.length === 0 ? <div className="panel-loading">No attribute columns selected. Open Layer settings → Attributes to select columns.</div> : (
        <div className="attributes-scroller">
          <table>
            <thead><tr><th>#</th>{data.fields.map(field => <th key={field}>{field}</th>)}</tr></thead>
            <tbody>
              {data.rows.map((row, i) => (
                <tr key={row._row_id ?? row.id ?? i}><td>{(page - 1) * data.page_size + i + 1}</td>
                  {data.fields.map(field => <td key={field} title={String(row[field] ?? '')}>{row[field] == null ? '—' : String(row[field])}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
