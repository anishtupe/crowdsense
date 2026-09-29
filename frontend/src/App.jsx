import React, { useEffect, useState, useCallback } from "react";
import MapView from "./components/MapView.jsx";
import IncidentList from "./components/IncidentList.jsx";
import ReportForm from "./components/ReportForm.jsx";
import { fetchIncidents, connectIncidentSocket } from "./api.js";

export default function App() {
  const [incidents, setIncidents] = useState([]);
  const [error, setError] = useState(null);
  const [currentView, setCurrentView] = useState(() => {
    return window.location.hash === "#/report" ? "report" : "dashboard";
  });

  const reload = useCallback(() => {
    fetchIncidents().then(setIncidents).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    reload();
    const socket = connectIncidentSocket(() => {
      reload();
    });
    return () => socket.close();
  }, [reload]);

  useEffect(() => {
    const handleHashChange = () => {
      if (window.location.hash === "#/report") {
        setCurrentView("report");
      } else {
        setCurrentView("dashboard");
      }
    };
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  const navigateTo = (view) => {
    setCurrentView(view);
    window.location.hash = view === "report" ? "#/report" : "#/";
  };

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-header">
          <h1>CrowdSense</h1>
          <span className="subtitle">Real-Time Geospatial Incident Intelligence</span>
        </div>
        <nav className="header-nav">
          <button
            className={`nav-btn ${currentView === "dashboard" ? "active" : ""}`}
            onClick={() => navigateTo("dashboard")}
          >
            🗺️ Live Incidents Map
          </button>
          <button
            className={`nav-btn ${currentView === "report" ? "active" : ""}`}
            onClick={() => navigateTo("report")}
          >
            📢 Submit Citizen Report
          </button>
        </nav>
      </header>

      {error && <div className="error-banner">Couldn't reach the API: {error}</div>}

      {currentView === "dashboard" ? (
        <div className="app-body">
          <div className="map-pane">
            <MapView incidents={incidents} />
          </div>
          <div className="sidebar-pane">
            <IncidentList incidents={incidents} />
          </div>
        </div>
      ) : (
        <div className="app-body form-view-body">
          <ReportForm
            onReportSubmitted={() => reload()}
            onViewDashboard={() => navigateTo("dashboard")}
          />
        </div>
      )}
    </div>
  );
}

