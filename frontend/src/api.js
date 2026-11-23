const ROOT = '/api';

async function request(path, options = {}) {
  const response = await fetch(`${ROOT}${path}`, options);
  let body;
  try { body = await response.json(); } catch { body = null; }
  if (!response.ok) {
    const details = body?.error || body?.detail || `Request failed (${response.status})`;
    throw new Error(typeof details === 'string' ? details : JSON.stringify(details));
  }
  return body;
}

export const api = {
  geoserverHealth: () => request('/geoserver/health/'),
  rollback: (id) => request(`/layers/${id}/rollback/`, { method: 'POST' }),
  health: () => request('/health/'),
  layers: () => request('/layers/'),
  preview: (data) => request('/layers/preview/', { method: 'POST', body: data }),
  upload: (data) => request('/layers/', { method: 'POST', body: data }),
  update: (id, patch) => request(`/layers/${id}/`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  }),
  replace: (id, data) => request(`/layers/${id}/replace/`, { method: 'POST', body: data }),
  remove: (id) => request(`/layers/${id}/`, { method: 'DELETE' }),
  geojson: (id, bbox, signal) => request(`/layers/${id}/features/?bbox=${encodeURIComponent(bbox)}`, { signal }),
  attributes: (id, page, pageSize = 25) => request(`/layers/${id}/attributes/?page=${page}&page_size=${pageSize}`),

  updateFeature: (layerId, featureId, patch) =>
    request(`/layers/${layerId}/features/${featureId}/update/`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    }),

  deleteFeature: (layerId, featureId) =>
    request(`/layers/${layerId}/features/${featureId}/delete/`, {
      method: 'DELETE',
    }),
};


