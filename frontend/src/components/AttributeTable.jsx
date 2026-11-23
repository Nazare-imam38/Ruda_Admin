
import { useEffect, useState } from 'react';
import {
  ChevronLeft,
  ChevronRight,
  X,
  Table2,
  Pencil,
  Save,
  Trash2,
} from 'lucide-react';
import { api } from '../api';

export default function AttributeTable({ layer, onClose }) {
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [editValues, setEditValues] = useState({});
  const [busyId, setBusyId] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [toast, setToast] = useState(null); 

  useEffect(() => {
    setPage(1);
    setEditingId(null);
  }, [layer.id]);

  useEffect(() => {
    let active = true;

    setError('');
    setData(null);

    api.attributes(layer.id, page)
      .then((result) => {
        if (active) {
          setData(result);
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      });

    return () => {
      active = false;
    };
  }, [layer.id, layer.version, layer.updated_at, page, refreshKey]);

  function startEditing(row) {
    setEditingId(row.id);

    const values = {};
    data.fields.forEach((field) => {
      values[field] = row[field] ?? '';
    });

    setEditValues(values);
    setError('');
    setToast({ type: 'success', message: 'Editing started.' });
 }
  function cancelEditing() {
    setEditingId(null);
    setEditValues({});
  }

  async function saveRow(featureId) {
  try {
    setBusyId(featureId);
    setError('');
    setToast(null);

    await api.updateFeature(layer.id, featureId, editValues);

    setEditingId(null);
    setEditValues({});
    setToast({ type: 'success', message: 'Changes saved successfully.' });
    setRefreshKey((value) => value + 1);
  } catch (e) {
    setError(e.message);
    setToast({ type: 'error', message: e.message });
  } finally {
    setBusyId(null);
  }
}

async function deleteRow(featureId) {
  const confirmed = window.confirm(
    'Are you sure you want to permanently delete this feature?'
  );

  if (!confirmed) return;

  try {
    setBusyId(featureId);
    setError('');
    setToast(null);

    await api.deleteFeature(layer.id, featureId);

    setEditingId(null);
    setEditValues({});
    setToast({ type: 'success', message: 'Feature deleted successfully.' });

    if (data.rows.length === 1 && page > 1) {
      setPage((value) => value - 1);
    } else {
      setRefreshKey((value) => value + 1);
    }
  } catch (e) {
    setError(e.message);
    setToast({ type: 'error', message: e.message });
  } finally {
    setBusyId(null);
  }
}

  return (
    <div className="attributes-panel">

      {toast && (
      <div
        className={`attribute-toast ${toast.type}`}
        role="status"
      >
        {toast.message}
        <button onClick={() => setToast(null)} aria-label="Close notification">
          <X size={14} />
        </button>
      </div>
    )}

      <div className="attributes-header">
        <div className="attributes-title">
          <Table2 size={18} />
          <strong>{layer.name}</strong>
          <span>
            {(data?.count ?? layer.feature_count).toLocaleString()} features
          </span>
        </div>

        <div className="attrs-pager">
          <button
            aria-label="Previous page"
            disabled={page <= 1}
            onClick={() => setPage((value) => value - 1)}
          >
            <ChevronLeft size={16} />
          </button>

          <span>Page {page} / {data?.total_pages || '...'}</span>

          <button
            aria-label="Next page"
            disabled={!data || page >= data.total_pages}
            onClick={() => setPage((value) => value + 1)}
          >
            <ChevronRight size={16} />
          </button>

          <button
            aria-label="Close attributes"
            className="attrs-close"
            onClick={onClose}
          >
            <X size={17} />
          </button>
        </div>
      </div>

      {error ? (
        <div className="panel-error">{error}</div>
      ) : !data ? (
        <div className="panel-loading">Loading records…</div>
      ) : data.disabled ? (
        <div className="panel-loading">
          Attribute table disabled in layer settings.
        </div>
      ) : data.fields.length === 0 ? (
        <div className="panel-loading">
          No attribute columns selected. Open Layer settings → Attributes to
          select columns.
        </div>
      ) : (
        <div className="attributes-scroller">
          <table>
            <thead>
              <tr>
                <th>#</th>
                {data.fields.map((field) => (
                  <th key={field}>{field}</th>
                ))}
                <th>Actions</th>
              </tr>
            </thead>

            <tbody>
              {data.rows.map((row, i) => {
                const isEditing = editingId === row.id;
                const isBusy = busyId === row.id;

                return (
                  <tr key={row._row_id ?? row.id ?? i}>
                    <td>{(page - 1) * data.page_size + i + 1}</td>

                    {data.fields.map((field) => (
                      <td key={field}>
                        {isEditing ? (
                          <input
                            type="text"
                            value={editValues[field] ?? ''}
                            onChange={(e) =>
                              setEditValues((values) => ({
                                ...values,
                                [field]: e.target.value,
                              }))
                            }
                            disabled={isBusy}
                          />
                        ) : (
                          <span title={String(row[field] ?? '')}>
                            {row[field] == null ? '—' : String(row[field])}
                          </span>
                        )}
                      </td>
                    ))}

                    <td>
                      {isEditing ? (
                        <div style={{ display: 'flex', gap: '6px' }}>
                          <button
                            title="Save changes"
                            onClick={() => saveRow(row.id)}
                            disabled={isBusy}
                          >
                            <Save size={15} />
                          </button>

                          <button
                            title="Cancel editing"
                            onClick={cancelEditing}
                            disabled={isBusy}
                          >
                            <X size={15} />
                          </button>
                        </div>
                      ) : (
                        <div style={{ display: 'flex', gap: '6px' }}>
                          <button
                            title="Edit feature"
                            onClick={() => startEditing(row)}
                            disabled={busyId !== null || editingId !== null}
                          >
                            <Pencil size={15} />
                          </button>

                          <button
                            title="Delete feature"
                            onClick={() => deleteRow(row.id)}
                            disabled={busyId !== null || editingId !== null}
                          >
                            <Trash2 size={15} />
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
