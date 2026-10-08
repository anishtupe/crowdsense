import React, { useEffect, useRef } from "react";
import { Map as MapLibreMap, NavigationControl, Popup } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

const INCIDENT_SOURCE = "incidents";
const INCIDENT_LAYER = "incident-markers";

function finiteNumber(value) {
  if (value == null || (typeof value === "string" && value.trim() === "")) return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function locatedIncidents(incidents) {
  return incidents.flatMap((incident) => {
    const latitude = finiteNumber(incident.latitude);
    const longitude = finiteNumber(incident.longitude);
    if (
      latitude == null ||
      longitude == null ||
      Math.abs(latitude) > 90 ||
      Math.abs(longitude) > 180
    ) {
      return [];
    }
    return [{ ...incident, latitude, longitude }];
  });
}

function incidentSignature(incidents) {
  return locatedIncidents(incidents)
    .map((incident) => `${incident.id}:${incident.longitude}:${incident.latitude}`)
    .sort()
    .join("|");
}

function incidentsToGeoJSON(incidents) {
  return {
    type: "FeatureCollection",
    features: locatedIncidents(incidents).map((incident) => ({
      type: "Feature",
      geometry: {
        type: "Point",
        coordinates: [incident.longitude, incident.latitude],
      },
      properties: {
        disaster_type: incident.disaster_type || "Unclassified",
        confidence: finiteNumber(incident.confidence) ?? 0,
        severity: finiteNumber(incident.severity) ?? 0,
        status: incident.status,
        has_contradiction: incident.has_contradiction,
      },
    })),
  };
}

function fitIncidents(map, incidents) {
  const located = locatedIncidents(incidents);
  if (!located.length) return;

  const longitudes = located.map((incident) => incident.longitude);
  const latitudes = located.map((incident) => incident.latitude);
  map.fitBounds(
    [
      [Math.min(...longitudes), Math.min(...latitudes)],
      [Math.max(...longitudes), Math.max(...latitudes)],
    ],
    { padding: 64, maxZoom: 12, duration: 700 }
  );
}

function createPopupContent(properties) {
  const content = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = properties.disaster_type;
  content.append(title, document.createElement("br"));
  content.append(
    document.createTextNode(`Confidence: ${(properties.confidence * 100).toFixed(0)}%`),
    document.createElement("br"),
    document.createTextNode(`Severity: ${(properties.severity * 100).toFixed(0)}%`),
    document.createElement("br"),
    document.createTextNode(`Status: ${properties.status}`)
  );

  if (properties.has_contradiction) {
    const warning = document.createElement("span");
    warning.style.color = "#b91c1c";
    warning.textContent = "⚠ Conflicting reports";
    content.append(document.createElement("br"), warning);
  }

  return content;
}

export default function MapView({ incidents }) {
  const mapContainer = useRef(null);
  const mapRef = useRef(null);
  const incidentsRef = useRef(incidents);
  const lastFittedSignature = useRef("");
  incidentsRef.current = incidents;

  useEffect(() => {
    const map = new MapLibreMap({
      container: mapContainer.current,
      center: [78.9629, 20.5937],
      zoom: 5,
      style: {
        version: 8,
        sources: {
          openstreetmap: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "&copy; OpenStreetMap contributors",
          },
          [INCIDENT_SOURCE]: {
            type: "geojson",
            data: incidentsToGeoJSON(incidentsRef.current),
          },
        },
        layers: [
          {
            id: "openstreetmap",
            type: "raster",
            source: "openstreetmap",
          },
          {
            id: INCIDENT_LAYER,
            type: "circle",
            source: INCIDENT_SOURCE,
            paint: {
              "circle-radius": ["+", 8, ["*", ["get", "severity"], 10]],
              "circle-color": [
                "case",
                [">=", ["get", "severity"], 0.7],
                "#b91c1c",
                [">=", ["get", "severity"], 0.4],
                "#b45309",
                "#15803d",
              ],
              "circle-opacity": 0.6,
              "circle-stroke-color": [
                "case",
                [">=", ["get", "severity"], 0.7],
                "#b91c1c",
                [">=", ["get", "severity"], 0.4],
                "#b45309",
                "#15803d",
              ],
            },
          },
        ],
      },
    });

    mapRef.current = map;
    map.addControl(new NavigationControl(), "top-right");
    map.on("load", () => {
      const currentIncidents = incidentsRef.current;
      map.getSource(INCIDENT_SOURCE).setData(incidentsToGeoJSON(currentIncidents));
      const signature = incidentSignature(currentIncidents);
      if (signature && signature !== lastFittedSignature.current) {
        fitIncidents(map, currentIncidents);
        lastFittedSignature.current = signature;
      }
    });

    map.on("click", INCIDENT_LAYER, (event) => {
      const feature = event.features?.[0];
      if (!feature) return;

      new Popup()
        .setLngLat(event.lngLat)
        .setDOMContent(createPopupContent(feature.properties))
        .addTo(map);
    });
    map.on("mouseenter", INCIDENT_LAYER, () => {
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", INCIDENT_LAYER, () => {
      map.getCanvas().style.cursor = "";
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const source = map?.getSource(INCIDENT_SOURCE);
    if (!source) return;
    const mapWasLoaded = map.loaded();
    source.setData(incidentsToGeoJSON(incidents));

    const signature = incidentSignature(incidents);
    if (mapWasLoaded && signature && signature !== lastFittedSignature.current) {
      fitIncidents(map, incidents);
      lastFittedSignature.current = signature;
    }
  }, [incidents]);

  const hasLocatedIncidents = locatedIncidents(incidents).length > 0;

  return (
    <div className="map-view">
      <div ref={mapContainer} style={{ height: "100%", width: "100%" }} />
      {hasLocatedIncidents && (
        <button
          className="map-fit-button"
          onClick={() => {
            if (mapRef.current) fitIncidents(mapRef.current, incidentsRef.current);
          }}
          type="button"
        >
          Show all incidents
        </button>
      )}
      {!hasLocatedIncidents && (
        <div className="map-empty-notice">
          {incidents.length
            ? "Incidents are loaded, but none have valid coordinates to display."
            : "No incidents to display yet. Submit a report to create one."}
        </div>
      )}
    </div>
  );
}
