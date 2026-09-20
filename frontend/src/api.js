const API_BASE = "/api";

export async function fetchIncidents() {
  const res = await fetch(`${API_BASE}/incidents`);
  if (!res.ok) throw new Error("Failed to fetch incidents");
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
