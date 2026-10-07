import React from "react";

export default function IncidentList({
  incidents,
  canVerify = false,
  verifyingIncidentId = null,
  onVerify,
  onViewDetails,
}) {
  return (
    <div className="incident-list">
      <h2>Incidents ({incidents.length})</h2>
      {incidents.length === 0 && <p className="muted">No incidents yet.</p>}
      <ul>
        {incidents.map((incident) => {
          const statusClass = incident.status.toLowerCase().includes("verified")
            ? "verified"
            : incident.status.toLowerCase().includes("rejected")
              ? "rejected"
              : "pending";
          return (
            <li key={incident.id} className="incident-card">
              <div className="incident-card-header">
                <span className="disaster-type">{incident.disaster_type || "Unclassified"}</span>
                <span className={`status status-${statusClass}`}>{incident.status}</span>
              </div>
              <div className="incident-card-body">
                <span>Confidence: {(incident.confidence * 100).toFixed(0)}%</span>
                <span>Severity: {(incident.severity * 100).toFixed(0)}%</span>
                <span>{incident.report_count} report(s)</span>
                {incident.has_contradiction && <span className="warning">⚠ Conflicting</span>}
              </div>
              {onViewDetails && (
                <button className="incident-details-button" onClick={() => onViewDetails(incident.id)}>
                  View evidence and details
                </button>
              )}
              {canVerify && incident.status.includes("Requires Verification") && (
                <div className="verification-actions">
                  <button
                    className="btn btn-verify"
                    disabled={verifyingIncidentId === incident.id}
                    onClick={() => onVerify(incident.id, true)}
                  >
                    Approve
                  </button>
                  <button
                    className="btn btn-reject"
                    disabled={verifyingIncidentId === incident.id}
                    onClick={() => onVerify(incident.id, false)}
                  >
                    Reject
                  </button>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
