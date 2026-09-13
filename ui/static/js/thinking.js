// Live timeline display for an active run.

const TIMELINE_ID = "timeline";
const HOME_ID = "view-home";
const STORAGE_KEY = "metaforge.active_project_id";

let _ws = null;
let _autoScroll = true;
let _timelineEl = null;
let _isActive = false;
let _activeRows = new Map();
let _lastUnnamedSpinner = null;

function _wsUrl(projectId) {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  return proto + "//" + location.host + "/ws/run/" + projectId;
}

function _activeKey(title) {
  let m;
  if (title === "Running final verification") return "verify";
  if (title === "Verification passed") return "verify";
  if (title === "Verification failed") return "verify";
  if ((m = title.match(/^Writing (.+)$/))) return "write:" + m[1];
  if ((m = title.match(/^(.+) written$/))) return "write:" + m[1];
  if ((m = title.match(/^Testing (.+)$/))) return "test:" + m[1];
  if ((m = title.match(/^(.+) passed$/))) return "test:" + m[1];
  if ((m = title.match(/^(.+) failed$/))) return "test:" + m[1];
  return null;
}

function _defaultColor(type) {
  if (type === "run_completed") return "green";
  if (type === "run_failed") return "red";
  if (type === "run_interrupted") return "orange";
  return "blue";
}

function _defaultIcon(type) {
  if (type === "run_completed") return "check";
  if (type === "run_failed") return "cross";
  if (type === "run_interrupted") return "cross";
  return "dot";
}

function _defaultTitle(event) {
  if (event.type === "run_completed") return "All done!";
  if (event.type === "run_failed") return "Something went wrong";
  if (event.type === "run_interrupted") return "Stopped";
  return event.type || "";
}

function _buildRow(event) {
  const payload = event.payload || {};
  const color = payload.color || _defaultColor(event.type);
  const icon = payload.icon || _defaultIcon(event.type);
  const title = payload.title || _defaultTitle(event);
  const detail = payload.detail || "";

  const row = document.createElement("div");
  row.className = "timeline-row timeline-color-" + color;

  const iconEl = document.createElement("span");
  iconEl.className = "timeline-icon timeline-icon-" + icon;

  const body = document.createElement("div");
  body.className = "timeline-body";

  const titleEl = document.createElement("div");
  titleEl.className = "timeline-title";
  titleEl.textContent = title;
  body.appendChild(titleEl);

  const detailEl = document.createElement("div");
  detailEl.className = "timeline-detail";
  detailEl.textContent = detail;
  if (detail) body.appendChild(detailEl);

  row.appendChild(iconEl);
  row.appendChild(body);
  return row;
}

function _updateRow(row, event) {
  const payload = event.payload || {};
  const color = payload.color || _defaultColor(event.type);
  const icon = payload.icon || _defaultIcon(event.type);
  const title = payload.title || _defaultTitle(event);
  const detail = payload.detail || "";

  row.className = "timeline-row timeline-color-" + color;

  const iconEl = row.querySelector(".timeline-icon");
  if (iconEl) {
    iconEl.className = "timeline-icon timeline-icon-" + icon;
  }

  const titleEl = row.querySelector(".timeline-title");
  if (titleEl) {
    titleEl.textContent = title;
  }

  const body = row.querySelector(".timeline-body");
  let detailEl = row.querySelector(".timeline-detail");
  if (detail) {
    if (!detailEl && body) {
      detailEl = document.createElement("div");
      detailEl.className = "timeline-detail";
      body.appendChild(detailEl);
    }
    if (detailEl) detailEl.textContent = detail;
  } else if (detailEl) {
    detailEl.remove();
  }
}

function _markRowDone(row) {
  if (!row) return;
  const iconEl = row.querySelector(".timeline-icon");
  if (iconEl) {
    iconEl.className = "timeline-icon timeline-icon-check";
  }
}

function _appendEvent(event) {
  if (!_timelineEl) return;
  if (event.type === "run_started") return;

  const payload = event.payload || {};
  const title = payload.title || _defaultTitle(event);
  const icon = payload.icon || _defaultIcon(event.type);
  const key = _activeKey(title);

  if (key && _activeRows.has(key)) {
    _updateRow(_activeRows.get(key), event);
    if (icon !== "spinner") {
      _activeRows.delete(key);
    }
    if (_autoScroll) {
      _timelineEl.scrollTop = _timelineEl.scrollHeight;
    }
    return;
  }

  if (_lastUnnamedSpinner) {
    _markRowDone(_lastUnnamedSpinner);
    _lastUnnamedSpinner = null;
  }

  const row = _buildRow(event);
  _timelineEl.appendChild(row);

  if (key && icon === "spinner") {
    _activeRows.set(key, row);
  } else if (!key && icon === "spinner") {
    _lastUnnamedSpinner = row;
  }

  if (_autoScroll) {
    _timelineEl.scrollTop = _timelineEl.scrollHeight;
  }
}

function _handleMessage(msg) {
  if (msg.target !== _ws) return;

  let event;
  try {
    event = JSON.parse(msg.data);
  } catch (e) {
    console.warn("Invalid WS message:", msg.data);
    return;
  }
  if (!event || typeof event !== "object") return;

  _appendEvent(event);

  if (
    event.type === "run_completed" ||
    event.type === "run_failed" ||
    event.type === "run_interrupted"
  ) {
    if (_lastUnnamedSpinner) {
      _markRowDone(_lastUnnamedSpinner);
      _lastUnnamedSpinner = null;
    }
    for (const row of _activeRows.values()) {
      _markRowDone(row);
    }
    _activeRows.clear();

    localStorage.removeItem(STORAGE_KEY);
    _isActive = false;
    if (_ws) {
      try { _ws.close(); } catch (e) {}
      _ws = null;
    }
  }
}

function _setupScrollListener() {
  if (!_timelineEl) return;
  _timelineEl.addEventListener("scroll", () => {
    const near =
      _timelineEl.scrollHeight - _timelineEl.scrollTop - _timelineEl.clientHeight < 24;
    _autoScroll = near;
  });
}

function _openSocket(projectId) {
  let ws;
  try {
    ws = new WebSocket(_wsUrl(projectId));
  } catch (e) {
    console.error("WebSocket failed to construct:", e);
    _ws = null;
    return;
  }
  _ws = ws;
  ws.addEventListener("message", _handleMessage);
  ws.addEventListener("close", () => {
    if (_ws === ws) _ws = null;
  });
  ws.addEventListener("error", (e) => {
    console.error("WebSocket error:", e);
  });
}

export function initThinking() {
  _timelineEl = document.getElementById(TIMELINE_ID);
  if (!_timelineEl) return;
  _setupScrollListener();
}

export function connectToRun(projectId) {
  disconnect();
  _autoScroll = true;
  _isActive = true;
  _activeRows = new Map();
  _lastUnnamedSpinner = null;

  const home = document.getElementById(HOME_ID);
  if (home) home.classList.add("running");

  if (_timelineEl) {
    _timelineEl.innerHTML = "";
    _timelineEl.scrollTop = 0;
  }

  localStorage.setItem(STORAGE_KEY, projectId);
  _openSocket(projectId);
}

export function disconnect() {
  const ws = _ws;
  _ws = null;
  if (ws) {
    try { ws.close(); } catch (e) {}
  }
  _isActive = false;
  _activeRows = new Map();
  _lastUnnamedSpinner = null;

  const home = document.getElementById(HOME_ID);
  if (home) home.classList.remove("running");

  if (_timelineEl) {
    _timelineEl.innerHTML = "";
  }

  localStorage.removeItem(STORAGE_KEY);
}

export function isActive() {
  return _isActive;
}

export async function restoreIfActive() {
  const id = localStorage.getItem(STORAGE_KEY);
  if (!id) return false;
  try {
    const res = await fetch("/api/projects/" + id);
    if (!res.ok) {
      localStorage.removeItem(STORAGE_KEY);
      return false;
    }
    const project = await res.json();
    if (project.status !== "running" && project.status !== "pending") {
      localStorage.removeItem(STORAGE_KEY);
      return false;
    }
    connectToRun(id);
    return true;
  } catch (e) {
    localStorage.removeItem(STORAGE_KEY);
    return false;
  }
}