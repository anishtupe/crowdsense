import React, { useMemo } from "react";
import IncidentList from "./IncidentList.jsx";

export default function AdminDashboard({
  incidents,
  reports,
  health,
  healthError,
  loading,
  verifyingIncidentId,
  onVerify,
  onViewDetails,
  onRefresh,
}) {
  const pendingIncidents = useMemo(
    () => incidents.filter((incident) => incident.status.includes("Requires Verification")),
    [incidents]
  );
  const contradictionCount = incidents.filter((incident) => incident.has_contradiction).length;
  const classifiedReports = reports.filter(
    (report) => report.disaster_type && report.disaster_type !== "unclassified"
  ).length;

  return (
    <main className="workspace-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Administrator workspace</p>
          <h2>Operations overview</h2>
          <p className="page-description">
            Monitor incoming evidence, AI-generated incidents, and verification workload.
          </p>
        </div>
        <button className="btn btn-secondary" onClick={onRefresh} disabled={loading}>
          {loading ? "Refreshing..." : "Refresh data"}
        </button>
      </div>

      <div className="system-status">
        <span className={`system-indicator ${health && !healthError ? "online" : "offline"}`} />
        <strong>API service</strong>
        <span>{healthError || (health ? "Online" : "Checking...")}</span>
      </div>

      <div className="metric-grid">
        <article className="metric-card">
          <span>Reports loaded (latest 100)</span><strong>{reports.length}</strong>
        </article>
        <article className="metric-card">
          <span>Incidents</span><strong>{incidents.length}</strong>
        </article>
        <article className="metric-card metric-warning">
          <span>Awaiting verification</span><strong>{pendingIncidents.length}</strong>
        </article>
        <article className="metric-card">
          <span>Contradiction flags</span><strong>{contradictionCount}</strong>
        </article>
        <article className="metric-card">
          <span>Reports with a type label</span><strong>{classifiedReports}</strong>
        </article>
      </div>

      <div className="info-callout">
        <strong>Admin controls available in this backend</strong>
        <p>
          Administrators can approve or reject AI-detected incidents. The backend
          does not currently expose user/role management, audit history, or
          configuration endpoints, so this dashboard does not pretend to manage
          those resources.
        </p>
      </div>

      <section className="admin-review-panel">
        <div className="panel-heading">
          <div>
            <h3>Verification queue</h3>
            <p className="muted">Approve or reject incidents awaiting human review.</p>
          </div>
        </div>
        {pendingIncidents.length ? (
          <IncidentList
            incidents={pendingIncidents}
            canVerify
            verifyingIncidentId={verifyingIncidentId}
            onVerify={onVerify}
            onViewDetails={onViewDetails}
          />
        ) : (
          <p className="muted panel-empty">No incidents are awaiting verification.</p>
        )}
      </section>
    </main>
  );
}
