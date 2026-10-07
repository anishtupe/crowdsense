const API_BASE = "/api";

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function responseError(res, fallback) {
  const body = await res.json().catch(() => ({}));
  return new Error(body.detail || fallback);
}

export async function fetchIncidents() {
  const res = await fetch(`${API_BASE}/incidents`);
  if (!res.ok) throw await responseError(res, "Failed to fetch incidents");
  return res.json();
}

export async function registerUser(email, password) {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw await responseError(res, "Failed to create account");
  return res.json();
}

export async function loginUser(email, password) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username: email, password }),
  });
  if (!res.ok) throw await responseError(res, "Failed to sign in");
  return res.json();
}

export async function fetchCurrentUser(token) {
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: authHeaders(token),
  });
  if (!res.ok) throw await responseError(res, "Your session has expired");
  return res.json();
}

export async function submitReport(reportData, token) {
  const res = await fetch(`${API_BASE}/reports`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token),
    },
    body: JSON.stringify(reportData),
  });
  if (!res.ok) {
    throw await responseError(res, "Failed to submit report");
  }
  return res.json();
}

export async function verifyIncident(incidentId, approve, token) {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/verify`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token),
    },
    body: JSON.stringify({ approve }),
  });
  if (!res.ok) throw await responseError(res, "Failed to update incident");
  return res.json();
}

export function connectIncidentSocket(onMessage) {
  // In dev, Vite proxies /api to the backend but WebSockets need the
  // direct backend URL — adjust for production behind nginx (see
  // infra/nginx.conf, which does proxy /ws).
  const wsUrl =
    window.location.hostname === "localhost"
      ? "ws://localhost:8000/ws/incidents"
      : `wss://${window.location.host}/ws/incidents`;

  const socket = new WebSocket(wsUrl);
  socket.onmessage = (event) => {
    try {
      onMessage(JSON.parse(event.data));
    } catch {
      // ignore malformed messages
    }
  };
  return socket;
}
