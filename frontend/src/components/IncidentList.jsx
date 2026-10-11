import React, { useMemo, useState } from "react";

function severityLevel(severity) {
  const value = Number(severity) || 0;
  return value > 0.7 ? "high" : value >= 0.4 ? "medium" : "low";
}

function statusClass(status = "") {
  const normalized = status.toLowerCase();
  if (normalized.includes("verified")) return "verified";
  if (normalized.includes("rejected")) return "rejected";
  return "pending";
}

function statusLabel(status = "") {
  if (status.toLowerCase().includes("verified")) return "Verified";
  if (status.toLowerCase().includes("rejected")) return "Rejected";
  return "AI Detected - Requires Verification";
}

function distanceKm(first, second) {
  const radians = (degrees) => (degrees * Math.PI) / 180;
  const latitudeDelta = radians(second.latitude - first.latitude);
  const longitudeDelta = radians(second.longitude - first.longitude);
  const value =
    Math.sin(latitudeDelta / 2) ** 2 +
    Math.cos(radians(first.latitude)) *
      Math.cos(radians(second.latitude)) *
      Math.sin(longitudeDelta / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(value), Math.sqrt(1 - value));
}

export default function IncidentList({
  incidents,
  loading = false,
  canVerify = false,
  verifyingIncidentId = null,
  onVerify,
  onViewDetails,
  onSelectIncident,
  onHoverIncident,
  userLocation,
}) {
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [sortBy, setSortBy] = useState("recent");
  const types = useMemo(
    () => [...new Set(incidents.map((incident) => incident.disaster_type || "Unclassified"))].sort(),
    [incidents]
  );
  const nearest = useMemo(() => {
    if (!userLocation) return null;
    return incidents.reduce((closest, incident) => {
      if (
        incident.latitude == null ||
        incident.longitude == null ||
        String(incident.latitude).trim() === "" ||
        String(incident.longitude).trim() === ""
      ) return closest;
      const latitude = Number(incident.latitude);
      const longitude = Number(incident.longitude);
      if (
        !Number.isFinite(latitude) ||
        !Number.isFinite(longitude) ||
        Math.abs(latitude) > 90 ||
        Math.abs(longitude) > 180
      ) return closest;
      const distance = distanceKm(userLocation, { latitude, longitude });
      return !closest || distance < closest.distance
        ? { incident, distance }
        : closest;
    }, null);
  }, [incidents, userLocation]);
  const visibleIncidents = useMemo(() => {
    const query = search.trim().toLowerCase();
    const filtered = incidents.filter((incident) => {
      const type = incident.disaster_type || "Unclassified";
      const state = statusClass(incident.status);
      const matchesSearch = !query || `${type} ${incident.status || ""}`.toLowerCase().includes(query);
      return (
        matchesSearch &&
        (typeFilter === "all" || type === typeFilter) &&
        (statusFilter === "all" || state === statusFilter) &&
        (severityFilter === "all" || severityLevel(incident.severity) === severityFilter)
      );
    });
    return filtered.sort((first, second) => {
      if (sortBy === "severity") return (Number(second.severity) || 0) - (Number(first.severity) || 0);
      if (sortBy === "confidence") return (Number(second.confidence) || 0) - (Number(first.confidence) || 0);
      return new Date(second.created_at || 0) - new Date(first.created_at || 0);
    });
  }, [incidents, search, typeFilter, statusFilter, severityFilter, sortBy]);

  return (
    <section className="incident-list" aria-label="Incident list">
      <div className="incident-list-heading">
        <div>
          <p className="section-eyebrow">Live situation</p>
          <h2>Incidents <span>{visibleIncidents.length}</span></h2>
        </div>
        {nearest && (
          <div className="nearest-incident" title={nearest.incident.disaster_type || "Nearest incident"}>
            <span aria-hidden="true">↗</span>
            <span>Nearest incident: <strong>{nearest.distance < 10 ? nearest.distance.toFixed(1) : Math.round(nearest.distance)} km away</strong></span>
          </div>
        )}
      </div>
      <label className="incident-search">
        <span aria-hidden="true">⌕</span>
        <input
          type="search"
          placeholder="Search incidents..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          aria-label="Search incidents"
        />
        <kbd>/</kbd>
      </label>
      <div className="incident-filters" aria-label="Filter incidents">
        <label className="filter-chip">
          <span>Type</span>
          <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)} aria-label="Filter by disaster type">
            <option value="all">All types</option>
            {types.map((type) => <option key={type} value={type}>{type}</option>)}
          </select>
        </label>
        <label className="filter-chip">
          <span>Status</span>
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} aria-label="Filter by status">
            <option value="all">All</option>
            <option value="pending">Pending</option>
            <option value="verified">Verified</option>
            <option value="rejected">Rejected</option>
          </select>
        </label>
        <label className="filter-chip">
          <span>Severity</span>
          <select value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)} aria-label="Filter by severity">
            <option value="all">All</option>
            <option value="low">Low</option>
            <option value="medium">Elevated</option>
            <option value="high">High</option>
          </select>
        </label>
      </div>
      <div className="incident-list-toolbar">
        <span>{loading ? "Updating live feed…" : `${visibleIncidents.length} results`}</span>
        <label>
          Sort
          <select value={sortBy} onChange={(event) => setSortBy(event.target.value)} aria-label="Sort incidents">
            <option value="recent">Most recent</option>
            <option value="severity">Highest severity</option>
            <option value="confidence">Highest confidence</option>
          </select>
        </label>
      </div>

      {loading && incidents.length === 0 ? (
        <div className="incident-skeleton-list" aria-label="Loading incidents">
          {[0, 1, 2, 3].map((item) => (
            <div className="incident-skeleton" key={item}>
              <span /><span /><span />
            </div>
          ))}
        </div>
      ) : visibleIncidents.length === 0 ? (
        <div className="incident-empty">
          <span aria-hidden="true">⌕</span>
          <strong>{incidents.length ? "No matching incidents" : "All clear for now"}</strong>
          <p>{incidents.length ? "Try another filter or search term." : "New reports will appear here as they come in."}</p>
        </div>
      ) : (
        <ul className="incident-cards">
          {visibleIncidents.map((incident) => {
            const severity = Math.max(0, Math.min(1, Number(incident.severity) || 0));
            const confidence = Math.max(0, Math.min(1, Number(incident.confidence) || 0));
            const state = statusClass(incident.status);
            return (
              <li
                key={incident.id}
                className={`incident-card severity-${severityLevel(severity)}`}
                tabIndex={0}
                onMouseEnter={() => onHoverIncident?.(incident.id)}
                onMouseLeave={() => onHoverIncident?.(null)}
                onFocus={() => onHoverIncident?.(incident.id)}
                onBlur={() => onHoverIncident?.(null)}
                onClick={() => onSelectIncident?.(incident)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelectIncident?.(incident);
                  }
                }}
              >
                <div className="incident-card-header">
                  <span className="disaster-type">{incident.disaster_type || "Unclassified"}</span>
                  <span className={`status-chip status-chip-${state}`}>{statusLabel(incident.status)}</span>
                </div>
                <div className="incident-card-metrics">
                  <span>Confidence <strong>{Math.round(confidence * 100)}%</strong></span>
                  <span>Severity <strong>{Math.round(severity * 100)}%</strong></span>
                </div>
                <div className="confidence-track" aria-label={`Confidence ${Math.round(confidence * 100)} percent`}>
                  <span style={{ width: `${confidence * 100}%` }} />
                </div>
                <div className="incident-card-footer">
                  <span>{incident.report_count ?? 0} reports</span>
                  {incident.has_contradiction && <span className="conflict-label">⚠ Conflict</span>}
                  {onViewDetails && (
                    <button
                      className="incident-details-button"
                      onClick={(event) => {
                        event.stopPropagation();
                        onViewDetails(incident.id);
                      }}
                    >
                      Evidence <span aria-hidden="true">↗</span>
                    </button>
                  )}
                </div>
                {canVerify && incident.status?.includes("Requires Verification") && (
                  <div className="verification-actions" onClick={(event) => event.stopPropagation()}>
                    <button
                      className="btn btn-verify"
                      disabled={verifyingIncidentId === incident.id}
                      onClick={() => onVerify(incident.id, true)}
                    >
                      Verify
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
      )}
    </section>
  );
}
