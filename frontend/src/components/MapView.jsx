import React from "react";
import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";

const SEVERITY_COLOR = (severity) => {
  if (severity >= 0.7) return "#b91c1c"; // high — red
  if (severity >= 0.4) return "#b45309"; // medium — amber
  return "#15803d"; // low — green
};

export default function MapView({ incidents }) {
  const center = [20.5937, 78.9629]; // default: India; recenter as needed

  return (
    <MapContainer center={center} zoom={5} style={{ height: "100%", width: "100%" }}>
      <TileLayer
        attribution='&copy; OpenStreetMap contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {incidents
        .filter((i) => i.latitude != null && i.longitude != null)
        .map((incident) => (
          <CircleMarker
            key={incident.id}
            center={[incident.latitude, incident.longitude]}
            radius={8 + incident.severity * 10}
            pathOptions={{
              color: SEVERITY_COLOR(incident.severity),
              fillColor: SEVERITY_COLOR(incident.severity),
              fillOpacity: 0.6,
            }}
          >
            <Popup>
              <strong>{incident.disaster_type || "Unclassified"}</strong>
              <br />
              Confidence: {(incident.confidence * 100).toFixed(0)}%
              <br />
              Severity: {(incident.severity * 100).toFixed(0)}%
              <br />
              Status: {incident.status}
              {incident.has_contradiction && (
                <>
                  <br />
                  <span style={{ color: "#b91c1c" }}>⚠ Conflicting reports</span>
                </>
              )}
            </Popup>
          </CircleMarker>
        ))}
    </MapContainer>
  );
}
