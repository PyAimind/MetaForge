async function _request(url, options = {}) {
  const mergedHeaders = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  const res = await fetch(url, { ...options, headers: mergedHeaders });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.json();
}

export async function listProjects() {
  return _request("/api/projects");
}

export async function getProject(id) {
  return _request(`/api/projects/${id}`);
}

export async function createProject(name, idea) {
  return _request("/api/projects", {
    method: "POST",
    body: JSON.stringify({ name, idea }),
  });
}

export async function renameProject(id, name) {
  return _request(`/api/projects/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ name }),
  });
}

export async function deleteProject(id) {
  return _request(`/api/projects/${id}`, { method: "DELETE" });
}

export async function listModules(id) {
  return _request(`/api/projects/${id}/modules`);
}

export async function getModule(id, filename) {
  return _request(`/api/projects/${id}/modules/${encodeURIComponent(filename)}`);
}