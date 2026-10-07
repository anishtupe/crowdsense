import React, { useMemo, useState } from "react";

const formatDate = (value) => new Date(value).toLocaleString();

function safeEvidenceHref(value) {
  if (/^data:(image|video)\/[a-z0-9.+-]+;base64,/i.test(value || "")) return value;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

export default function AIInsights({ reports, incidents, loading, error, onRefresh }) {
  const [search, setSearch] = useState("");
  const filteredReports = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return reports;
    return reports.filter((report) =>
      [report.text, report.disaster_type, report.sentiment, report.source]
        .filter(Boolean)
        .some((value) => value.toLowerCase().includes(query))
    );
  }, [reports, search]);

  const classifiedCount = reports.filter(
    (report) => report.disaster_type && report.disaster_type.toLowerCase() !== "unclassified"
  ).length;
  const incidentById = new Map(incidents.map((incident) => [incident.id, incident]));
  const typeCounts = reports.reduce((counts, report) => {
    const type = report.disaster_type || "Processing / unknown";
    counts.set(type, (counts.get(type) || 0) + 1);
    return counts;
  }, new Map());
  const topTypes = [...typeCounts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);

  return (
    <main className="workspace-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Evidence processing</p>
          <h2>AI report insights</h2>
          <p className="page-description">
            Review report classifications and their linked, fused incidents.
          </p>
        </div>
        <button className="btn btn-secondary" onClick={onRefresh} disabled={loading}>
          {loading ? "Refreshing..." : "Refresh data"}
        </button>
      </div>

      {error && <div className="alert alert-error" role="alert">{error}</div>}

      <div className="metric-grid metric-grid-three">
        <article className="metric-card">
          <span>Reports loaded</span><strong>{reports.length}</strong>
        </article>
        <article className="metric-card">
          <span>Classified reports</span><strong>{classifiedCount}</strong>
        </article>
        <article className="metric-card">
          <span>Fused incidents</span><strong>{incidents.length}</strong>
        </article>
      </div>

      <div className="info-callout">
        <strong>About the current AI pipeline</strong>
        <p>
          Disaster type and sentiment are produced by the backend's current
          keyword-based NLP implementation; duplicate matching and contradiction
          checks use heuristics. Image classification is a stub, not a trained
          vision model. New reports are processed in the background, so their
          AI fields may appear after refreshing.
        </p>
      </div>

      <section className="data-panel classification-panel">
        <div className="panel-heading"><h3>Report classification mix</h3></div>
        {topTypes.length ? (
          <div className="classification-bars">
            {topTypes.map(([type, count]) => (
              <div className="classification-row" key={type}>
                <div className="classification-label">
                  <span>{type}</span><strong>{count}</strong>
                </div>
                <div className="classification-track">
                  <span style={{ width: `${(count / reports.length) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="muted">Submit reports to see the current classification mix.</p>
        )}
      </section>

      <section className="data-panel">
        <div className="panel-heading">
          <h3>Processed reports</h3>
          <input
            className="table-search"
            type="search"
            aria-label="Search reports"
            placeholder="Search text, type, sentiment..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        {loading && reports.length === 0 ? (
          <p className="muted panel-empty">Loading reports...</p>
        ) : filteredReports.length === 0 ? (
          <p className="muted panel-empty">
            {reports.length ? "No reports match your search." : "No reports are available yet."}
          </p>
        ) : (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Report</th><th>Evidence</th><th>AI type</th><th>Sentiment</th>
                  <th>Incident</th><th>Source</th><th>Reported</th>
                </tr>
              </thead>
              <tbody>
                {filteredReports.map((report) => {
                  const linkedIncident = report.incident_id
                    ? incidentById.get(report.incident_id)
                    : null;
                  return (
                    <tr key={report.id}>
                      <td className="report-text-cell">
                        {report.text || (report.media_url ? "Media-only report" : "Empty report")}
                      </td>
                      <td>
                        {safeEvidenceHref(report.media_url) ? (
                          <a href={safeEvidenceHref(report.media_url)} target="_blank" rel="noreferrer">
                            Open evidence
                          </a>
                        ) : report.media_url ? "Unsupported media URL" : "—"}
                      </td>
                      <td><span className="tag">{report.disaster_type || "Processing / unknown"}</span></td>
                      <td>{report.sentiment || "Pending"}</td>
                      <td>
                        {linkedIncident
                          ? `${linkedIncident.disaster_type || "Unclassified"} · ${linkedIncident.status}`
                          : report.incident_id
                            ? "Incident linked"
                            : "Not linked yet"}
                      </td>
                      <td>{report.source}</td>
                      <td>{formatDate(report.reported_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
