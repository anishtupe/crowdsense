import React, { useEffect, useState, useCallback } from "react";
import MapView from "./components/MapView.jsx";
import IncidentList from "./components/IncidentList.jsx";
import { fetchIncidents, connectIncidentSocket } from "./api.js";

export default function App() {
  const [incidents, setIncidents] = useState([]);
  const [error, setError] = useState(null);

  const reload = useCallback(() => {
    fetchIncidents().then(setIncidents).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    reload();
    const socket = connectIncidentSocket(() => {
      // Any incident_updated event triggers a refetch. For higher traffic,
      // apply the diff from the message instead of refetching everything.
      reload();
    });
    return () => socket.close();
  }, [reload]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>CrowdSense</h1>
        <span className="subtitle">Real-Time Geospatial Incident Intelligence</span>
      </header>

      {error && <div className="error-banner">Couldn't reach the API: {error}</div>}

      <div className="app-body">
        <div className="map-pane">
          <MapView incidents={incidents} />
        </div>
        <div className="sidebar-pane">
          <IncidentList incidents={incidents} />
        </div>
      </div>
    </div>
  );
}
