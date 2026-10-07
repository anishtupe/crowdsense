import React, { useEffect, useState, useCallback } from "react";
import MapView from "./components/MapView.jsx";
import IncidentList from "./components/IncidentList.jsx";
import ReportForm from "./components/ReportForm.jsx";
import AuthForm from "./components/AuthForm.jsx";
import {
  connectIncidentSocket,
  fetchCurrentUser,
  fetchIncidents,
  verifyIncident,
} from "./api.js";

export default function App() {
  const [incidents, setIncidents] = useState([]);
  const [error, setError] = useState(null);
  const [token, setToken] = useState(() => window.localStorage.getItem("crowdsense_token"));
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(
    () => Boolean(window.localStorage.getItem("crowdsense_token"))
  );
  const [verifyingIncidentId, setVerifyingIncidentId] = useState(null);
  const [currentView, setCurrentView] = useState(() => {
    if (window.location.hash === "#/report") return "report";
    if (window.location.hash === "#/login") return "login";
    return "dashboard";
  });

  const reload = useCallback(() => {
    fetchIncidents().then(setIncidents).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!token) {
      setAuthLoading(false);
      return;
    }
    fetchCurrentUser(token)
      .then(setUser)
      .catch((e) => {
        window.localStorage.removeItem("crowdsense_token");
        setToken(null);
        setUser(null);
        setError(e.message);
      })
      .finally(() => setAuthLoading(false));
  }, [token]);

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
      } else if (window.location.hash === "#/login") {
        setCurrentView("login");
      } else {
        setCurrentView("dashboard");
      }
    };
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  const navigateTo = (view) => {
    setCurrentView(view);
    const hash = view === "report" ? "#/report" : view === "login" ? "#/login" : "#/";
    if (window.location.hash !== hash) window.location.hash = hash;
  };

  const handleAuthenticated = (newToken, authenticatedUser) => {
    window.localStorage.setItem("crowdsense_token", newToken);
    setToken(newToken);
    setUser(authenticatedUser);
    setError(null);
    navigateTo("report");
  };

  const handleSignOut = () => {
    window.localStorage.removeItem("crowdsense_token");
    setToken(null);
    setUser(null);
    navigateTo("dashboard");
  };

  const handleVerify = async (incidentId, approve) => {
    setVerifyingIncidentId(incidentId);
    setError(null);
    try {
      const updatedIncident = await verifyIncident(incidentId, approve, token);
      setIncidents((items) =>
        items.map((incident) => incident.id === updatedIncident.id ? updatedIncident : incident)
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setVerifyingIncidentId(null);
    }
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
          {user ? (
            <div className="account-controls">
              <span className="account-label">{user.email} · {user.role}</span>
              <button className="nav-btn" onClick={handleSignOut}>Sign out</button>
            </div>
          ) : (
            <button
              className={`nav-btn ${currentView === "login" ? "active" : ""}`}
              onClick={() => navigateTo("login")}
            >
              Sign in
            </button>
          )}
        </nav>
      </header>

      {error && <div className="error-banner">Couldn't reach the API: {error}</div>}

      {currentView === "dashboard" ? (
        <div className="app-body">
          <div className="map-pane">
            <MapView incidents={incidents} />
          </div>
          <div className="sidebar-pane">
            <IncidentList
              incidents={incidents}
              canVerify={Boolean(user && ["verifier", "analyst", "admin"].includes(user.role))}
              verifyingIncidentId={verifyingIncidentId}
              onVerify={handleVerify}
            />
          </div>
        </div>
      ) : currentView === "report" && user ? (
        <div className="app-body form-view-body">
          <ReportForm
            token={token}
            onReportSubmitted={() => reload()}
            onViewDashboard={() => navigateTo("dashboard")}
          />
        </div>
      ) : authLoading ? (
        <div className="form-view-body"><p className="muted">Checking your sign-in...</p></div>
      ) : (
        <div className="form-view-body">
          <AuthForm
            onAuthenticated={handleAuthenticated}
            onViewDashboard={() => navigateTo("dashboard")}
          />
        </div>
      )}
    </div>
  );
}
