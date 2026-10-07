import React, { useCallback, useEffect, useState } from "react";
import AdminDashboard from "./components/AdminDashboard.jsx";
import AIInsights from "./components/AIInsights.jsx";
import AuthForm from "./components/AuthForm.jsx";
import IncidentDetails from "./components/IncidentDetails.jsx";
import IncidentList from "./components/IncidentList.jsx";
import MapView from "./components/MapView.jsx";
import ReportForm from "./components/ReportForm.jsx";
import {
  connectIncidentSocket,
  fetchCurrentUser,
  fetchHealth,
  fetchIncident,
  fetchIncidents,
  fetchReports,
  verifyIncident,
} from "./api.js";

const roleCanVerify = (role) => ["verifier", "analyst", "admin"].includes(role);

function viewFromHash(hash) {
  if (hash === "#/report") return "report";
  if (hash === "#/insights") return "insights";
  if (hash === "#/admin") return "admin";
  return "dashboard";
}

export default function App() {
  const [incidents, setIncidents] = useState([]);
  const [reports, setReports] = useState([]);
  const [error, setError] = useState("");
  const [token, setToken] = useState(() => window.localStorage.getItem("crowdsense_token"));
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(
    () => Boolean(window.localStorage.getItem("crowdsense_token"))
  );
  const [dataLoading, setDataLoading] = useState(false);
  const [health, setHealth] = useState(null);
  const [healthError, setHealthError] = useState("");
  const [verifyingIncidentId, setVerifyingIncidentId] = useState(null);
  const [selectedIncidentId, setSelectedIncidentId] = useState(null);
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [incidentDetailLoading, setIncidentDetailLoading] = useState(false);
  const [incidentDetailError, setIncidentDetailError] = useState("");
  const [currentView, setCurrentView] = useState(() =>
    window.localStorage.getItem("crowdsense_token")
      ? viewFromHash(window.location.hash)
      : "login"
  );

  const reloadData = useCallback(async () => {
    setDataLoading(true);
    const [incidentResult, reportResult] = await Promise.allSettled([
      fetchIncidents(),
      fetchReports(),
    ]);
    const errors = [];
    if (incidentResult.status === "fulfilled") {
      setIncidents(incidentResult.value);
    } else {
      errors.push(incidentResult.reason.message);
    }
    if (reportResult.status === "fulfilled") {
      setReports(reportResult.value);
    } else {
      errors.push(reportResult.reason.message);
    }
    setError(errors.join(" · "));
    setDataLoading(false);
  }, []);

  const checkHealth = useCallback(async () => {
    try {
      setHealth(await fetchHealth());
      setHealthError("");
    } catch (err) {
      setHealth(null);
      setHealthError(err.message);
    }
  }, []);

  const navigateTo = useCallback((view) => {
    if (!user) {
      setCurrentView("login");
      return;
    }
    if (view === "admin" && user.role !== "admin") {
      setCurrentView("dashboard");
      return;
    }
    setCurrentView(view);
    const hash = view === "dashboard" ? "#/" : `#/${view}`;
    if (window.location.hash !== hash) window.location.hash = hash;
  }, [user]);

  useEffect(() => {
    if (!token) {
      setUser(null);
      setAuthLoading(false);
      return;
    }
    let active = true;
    setAuthLoading(true);
    fetchCurrentUser(token)
      .then((currentUser) => {
        if (active) setUser(currentUser);
      })
      .catch((err) => {
        if (!active) return;
        window.localStorage.removeItem("crowdsense_token");
        setToken(null);
        setUser(null);
        setCurrentView("login");
        setError(err.message);
      })
      .finally(() => {
        if (active) setAuthLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token]);

  useEffect(() => {
    if (!user) return undefined;
    reloadData();
    const interval = window.setInterval(reloadData, 10000);
    const socket = connectIncidentSocket(reloadData);
    return () => {
      window.clearInterval(interval);
      socket.close();
    };
  }, [user, reloadData]);

  useEffect(() => {
    const handleHashChange = () => {
      if (!user) {
        setCurrentView("login");
        return;
      }
      const nextView = viewFromHash(window.location.hash);
      if (nextView === "admin" && user.role !== "admin") {
        setCurrentView("dashboard");
        window.location.hash = "#/";
        return;
      }
      setCurrentView(nextView);
    };
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, [user]);

  useEffect(() => {
    if (user && currentView === "admin" && user.role !== "admin") {
      navigateTo("dashboard");
    }
  }, [user, currentView, navigateTo]);

  useEffect(() => {
    if (!user || user.role !== "admin" || currentView !== "admin") return;
    checkHealth();
  }, [user, currentView, checkHealth]);

  const handleAuthenticated = (newToken, authenticatedUser) => {
    window.localStorage.setItem("crowdsense_token", newToken);
    setToken(newToken);
    setUser(authenticatedUser);
    setError("");
    setCurrentView("dashboard");
    window.location.hash = "#/";
  };

  const handleSignOut = () => {
    window.localStorage.removeItem("crowdsense_token");
    setToken(null);
    setUser(null);
    setCurrentView("login");
    window.location.hash = "#/login";
  };

  const handleVerify = async (incidentId, approve) => {
    setVerifyingIncidentId(incidentId);
    setError("");
    try {
      const updatedIncident = await verifyIncident(incidentId, approve, token);
      setIncidents((items) =>
        items.map((incident) =>
          incident.id === updatedIncident.id ? updatedIncident : incident
        )
      );
      setReports(await fetchReports());
    } catch (err) {
      setError(err.message);
    } finally {
      setVerifyingIncidentId(null);
    }
  };

  const handleViewIncident = async (incidentId) => {
    setSelectedIncidentId(incidentId);
    setSelectedIncident(incidents.find((incident) => incident.id === incidentId) || null);
    setIncidentDetailError("");
    setIncidentDetailLoading(true);
    try {
      setSelectedIncident(await fetchIncident(incidentId));
    } catch (err) {
      setIncidentDetailError(err.message);
    } finally {
      setIncidentDetailLoading(false);
    }
  };

  if (authLoading) {
    return <div className="auth-loading">Restoring your CrowdSense session...</div>;
  }

  if (!user) {
    return (
      <div className="login-shell">
        <div className="login-brand">
          <span className="brand-mark">C</span>
          <div>
            <h1>CrowdSense</h1>
            <p>Geospatial incident intelligence</p>
          </div>
        </div>
        {error && <div className="alert alert-error login-error" role="alert">{error}</div>}
        <AuthForm onAuthenticated={handleAuthenticated} />
        <p className="login-footer">Secure access for incident reporting and response.</p>
      </div>
    );
  }

  const canVerify = roleCanVerify(user.role);
  const isAdmin = user.role === "admin";

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-header">
          <h1>CrowdSense</h1>
          <span className="subtitle">Real-Time Geospatial Incident Intelligence</span>
        </div>
        <nav className="header-nav" aria-label="Main navigation">
          <button className={`nav-btn ${currentView === "dashboard" ? "active" : ""}`} onClick={() => navigateTo("dashboard")}>
            Live map
          </button>
          <button className={`nav-btn ${currentView === "report" ? "active" : ""}`} onClick={() => navigateTo("report")}>
            Submit report
          </button>
          <button className={`nav-btn ${currentView === "insights" ? "active" : ""}`} onClick={() => navigateTo("insights")}>
            AI insights
          </button>
          {isAdmin && (
            <button className={`nav-btn ${currentView === "admin" ? "active" : ""}`} onClick={() => navigateTo("admin")}>
              Admin
            </button>
          )}
          <div className="account-controls">
            <span className="account-label">{user.email} · {user.role}</span>
            <button className="nav-btn" onClick={handleSignOut}>Sign out</button>
          </div>
        </nav>
      </header>

      {error && <div className="error-banner" role="alert">{error}</div>}

      {currentView === "dashboard" && (
        <div className="app-body dashboard-layout">
          <div className="map-pane"><MapView incidents={incidents} /></div>
          <aside className="sidebar-pane">
            <div className="sidebar-toolbar">
              <span className="refresh-note">Auto-refreshes every 10 seconds</span>
              <button className="icon-button" onClick={reloadData} disabled={dataLoading} aria-label="Refresh incidents and reports">
                {dataLoading ? "…" : "↻"}
              </button>
            </div>
            <IncidentList
              incidents={incidents}
              canVerify={canVerify}
              verifyingIncidentId={verifyingIncidentId}
              onVerify={handleVerify}
              onViewDetails={handleViewIncident}
            />
          </aside>
        </div>
      )}

      {currentView === "report" && (
        <div className="app-body form-view-body">
          <ReportForm
            token={token}
            onReportSubmitted={() => reloadData()}
            onViewDashboard={() => navigateTo("dashboard")}
          />
        </div>
      )}

      {currentView === "insights" && (
        <AIInsights
          reports={reports}
          incidents={incidents}
          loading={dataLoading}
          error={error}
          onRefresh={reloadData}
        />
      )}

      {currentView === "admin" && isAdmin && (
        <AdminDashboard
          incidents={incidents}
          reports={reports}
          health={health}
          healthError={healthError}
          loading={dataLoading}
          verifyingIncidentId={verifyingIncidentId}
          onVerify={handleVerify}
          onViewDetails={handleViewIncident}
          onRefresh={() => {
            reloadData();
            checkHealth();
          }}
        />
      )}

      {selectedIncidentId && (
        <IncidentDetails
          incident={selectedIncident}
          reports={reports}
          loading={incidentDetailLoading}
          error={incidentDetailError}
          onClose={() => {
            setSelectedIncidentId(null);
            setIncidentDetailError("");
          }}
        />
      )}
    </div>
  );
}
