import React from "react";

export default function IncidentDetails({ incident, reports, loading, error, onClose }) {
  const linkedReports = reports.filter((report) => report.incident_id === incident?.id);

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <section className="incident-modal" role="dialog" aria-modal="true" aria-labelledby="incident-title">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Incident details</p>
            <h2 id="incident-title">{incident?.disaster_type || "Unclassified incident"}</h2>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Close incident details">×</button>
        </div>
        {loading ? (
          <p className="muted">Loading incident details...</p>
        ) : error ? (
          <div className="alert alert-error" role="alert">{error}</div>
        ) : incident ? (
          <>
            <div className="incident-detail-grid">
              <div><span>Status</span><strong>{incident.status}</strong></div>
              <div><span>Confidence</span><strong>{(incident.confidence * 100).toFixed(0)}%</strong></div>
              <div><span>Severity</span><strong>{(incident.severity * 100).toFixed(0)}%</strong></div>
              <div><span>Reports</span><strong>{incident.report_count}</strong></div>
              <div><span>Coordinates</span><strong>
                {incident.latitude == null || incident.longitude == null
                  ? "Unavailable"
                  : `${incident.latitude.toFixed(5)}, ${incident.longitude.toFixed(5)}`}
              </strong></div>
              <div><span>Conflicting evidence</span><strong>{incident.has_contradiction ? "Flagged" : "Not flagged"}</strong></div>
            </div>
            <p className="detail-timestamp">Last updated: {new Date(incident.updated_at).toLocaleString()}</p>
            <h3 className="linked-reports-heading">Associated reports</h3>
            {linkedReports.length ? (
              <ul className="linked-report-list">
                {linkedReports.map((report) => (
                  <li key={report.id}>
                    <strong>{report.text || "Media-only report"}</strong>
                    <span>{report.disaster_type || "Type pending"} · {report.sentiment || "Sentiment pending"}</span>
                    <time>{new Date(report.reported_at).toLocaleString()}</time>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">No associated reports were returned in the latest report list.</p>
            )}
          </>
        ) : null}
      </section>
    </div>
  );
}
