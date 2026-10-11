import React, { useEffect, useRef, useState } from "react";
import {
  Map as MapLibreMap,
  Marker,
  NavigationControl,
  Popup,
  ScaleControl,
  GeolocateControl,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

const INCIDENT_SOURCE = "incidents";
const INCIDENT_LAYER = "incident-markers";
const CLUSTER_LAYER = "incident-clusters";
const CLUSTER_COUNT_LAYER = "incident-cluster-count";
const INCIDENT_RING_LAYER = "incident-conflicts";
const CONFLICT_IMAGE = "crowdsense-conflict-ring";
const MAP_STYLES = {
  dark: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
  light: "https://tiles.openfreemap.org/styles/liberty",
};

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

function incidentsToGeoJSON(incidents) {
  return {
    type: "FeatureCollection",
    features: locatedIncidents(incidents).map((incident) => ({
      type: "Feature",
      id: String(incident.id),
      geometry: {
        type: "Point",
        coordinates: [incident.longitude, incident.latitude],
      },
      properties: {
        id: String(incident.id),
        latitude: incident.latitude,
        longitude: incident.longitude,
        disaster_type: incident.disaster_type || "Unclassified",
        confidence: finiteNumber(incident.confidence) ?? 0,
        severity: finiteNumber(incident.severity) ?? 0,
        status: incident.status || "Requires Verification",
        report_count: finiteNumber(incident.report_count) ?? 0,
        has_contradiction: Boolean(incident.has_contradiction),
      },
    })),
  };
}

function incidentDataSignature(incidents) {
  return JSON.stringify(
    locatedIncidents(incidents)
      .map((incident) => [
        incident.id,
        incident.latitude,
        incident.longitude,
        incident.disaster_type,
        incident.confidence,
        incident.severity,
        incident.status,
        incident.report_count,
        incident.has_contradiction,
      ])
      .sort((first, second) => String(first[0]).localeCompare(String(second[0])))
  );
}

function fitIncidents(map, incidents) {
  const located = locatedIncidents(incidents);
  if (!located.length) return;
  if (located.length === 1) {
    map.flyTo({
      center: [located[0].longitude, located[0].latitude],
      zoom: 11,
      pitch: 45,
      duration: 1200,
    });
    return;
  }

  const longitudes = located.map((incident) => incident.longitude);
  const latitudes = located.map((incident) => incident.latitude);
  map.fitBounds(
    [
      [Math.min(...longitudes), Math.min(...latitudes)],
      [Math.max(...longitudes), Math.max(...latitudes)],
    ],
    { padding: 90, maxZoom: 12, duration: 1200, pitch: 45 }
  );
}

function createPopupContent(properties) {
  const content = document.createElement("div");
  content.className = "incident-popup";
  const title = document.createElement("strong");
  title.className = "incident-popup-title";
  title.textContent = properties.disaster_type || "Unclassified";
  const confidence = Math.max(0, Math.min(1, Number(properties.confidence) || 0));
  const confidenceRow = document.createElement("div");
  confidenceRow.className = "incident-popup-confidence";
  confidenceRow.innerHTML = `<span>Confidence</span><strong>${Math.round(confidence * 100)}%</strong>`;
  const track = document.createElement("div");
  track.className = "confidence-track";
  const fill = document.createElement("span");
  fill.style.width = `${confidence * 100}%`;
  track.append(fill);
  const details = document.createElement("div");
  details.className = "incident-popup-details";
  const severity = Math.max(0, Math.min(1, Number(properties.severity) || 0));
  details.textContent = `Severity ${Math.round(severity * 100)}% · ${properties.report_count || 0} reports`;
  const coordinates = document.createElement("div");
  coordinates.className = "incident-popup-coordinates";
  coordinates.textContent = `Location ${Number(properties.latitude).toFixed(5)}, ${Number(properties.longitude).toFixed(5)}`;
  const status = document.createElement("span");
  status.className = `status-chip ${String(properties.status).toLowerCase().includes("verified") ? "status-chip-verified" : "status-chip-pending"}`;
  status.textContent = String(properties.status || "Requires Verification")
    .replace("AI Detected - ", "")
    .replace("Requires Verification", "Requires verification");
  content.append(title, confidenceRow, track, details, coordinates, status);
  if (properties.has_contradiction) {
    const warning = document.createElement("span");
    warning.className = "popup-conflict";
    warning.textContent = "⚠ Conflicting reports";
    content.append(warning);
  }
  return content;
}

function addIncidentLayers(map, incidents) {
  if (map.getSource(INCIDENT_SOURCE)) {
    if (map.getLayer(INCIDENT_RING_LAYER)) map.removeLayer(INCIDENT_RING_LAYER);
    if (map.getLayer(INCIDENT_LAYER)) map.removeLayer(INCIDENT_LAYER);
    if (map.getLayer(CLUSTER_COUNT_LAYER)) map.removeLayer(CLUSTER_COUNT_LAYER);
    if (map.getLayer(CLUSTER_LAYER)) map.removeLayer(CLUSTER_LAYER);
    map.removeSource(INCIDENT_SOURCE);
  }
  if (!map.hasImage(CONFLICT_IMAGE)) {
    const canvas = document.createElement("canvas");
    canvas.width = 64;
    canvas.height = 64;
    const context = canvas.getContext("2d");
    if (context) {
      context.beginPath();
      context.setLineDash([7, 6]);
      context.lineWidth = 4;
      context.strokeStyle = "#f5b84b";
      context.arc(32, 32, 24, 0, Math.PI * 2);
      context.stroke();
      map.addImage(CONFLICT_IMAGE, canvas, { pixelRatio: 2 });
    }
  }
  map.addSource(INCIDENT_SOURCE, {
    type: "geojson",
    data: incidentsToGeoJSON(incidents),
    cluster: true,
    clusterRadius: 48,
    clusterMaxZoom: 14,
  });
  map.addLayer({
    id: CLUSTER_LAYER,
    type: "circle",
    source: INCIDENT_SOURCE,
    filter: ["has", "point_count"],
    paint: {
      "circle-radius": ["step", ["get", "point_count"], 18, 10, 21, 50, 25, 100, 29],
      "circle-color": "#587ee8",
      "circle-opacity": 0.95,
      "circle-stroke-color": "#ffffff",
      "circle-stroke-width": 2,
    },
  });
  map.addLayer({
    id: CLUSTER_COUNT_LAYER,
    type: "symbol",
    source: INCIDENT_SOURCE,
    filter: ["has", "point_count"],
    layout: {
      "text-field": ["get", "point_count_abbreviated"],
      "text-font": ["Open Sans Bold"],
      "text-size": 12,
      "text-allow-overlap": true,
    },
    paint: { "text-color": "#ffffff" },
  });
  map.addLayer({
    id: INCIDENT_LAYER,
    type: "circle",
    source: INCIDENT_SOURCE,
    filter: ["!", ["has", "point_count"]],
    paint: {
      "circle-radius": ["case", ["boolean", ["feature-state", "hover"], false], 10, 7],
      "circle-color": [
        "case",
        [">", ["get", "severity"], 0.7],
        "#f56b6b",
        [">=", ["get", "severity"], 0.4],
        "#f5b84b",
        "#44d18a",
      ],
      "circle-opacity": 0.94,
      "circle-stroke-color": "#ffffff",
      "circle-stroke-width": ["case", ["boolean", ["feature-state", "hover"], false], 3, 1.5],
    },
  });
  map.addLayer({
    id: INCIDENT_RING_LAYER,
    type: "symbol",
    source: INCIDENT_SOURCE,
    filter: ["all", ["!", ["has", "point_count"]], ["==", ["get", "has_contradiction"], true]],
    layout: {
      "icon-image": CONFLICT_IMAGE,
      "icon-size": 1,
      "icon-allow-overlap": true,
      "icon-ignore-placement": true,
    },
  });
}

export default function MapView({
  incidents,
  theme = "dark",
  onUserLocation,
  onHighlightIncident,
  highlightedIncidentId,
  focusIncident,
}) {
  const mapContainer = useRef(null);
  const mapRef = useRef(null);
  const incidentsRef = useRef(incidents);
  const userMarkerRef = useRef(null);
  const appliedThemeRef = useRef(theme);
  const activePopupRef = useRef(null);
  const toastTimerRef = useRef(null);
  const sourceSignatureRef = useRef("");
  const lastFittedSignature = useRef("");
  const [toast, setToast] = useState("");
  const [locating, setLocating] = useState(false);
  const locationRequestRef = useRef(false);
  incidentsRef.current = incidents;

  const showToast = (message) => {
    setToast(message);
    window.clearTimeout(toastTimerRef.current);
    toastTimerRef.current = window.setTimeout(() => setToast(""), 4200);
  };

  const reportLocationError = (code) => {
    locationRequestRef.current = false;
    setLocating(false);
    if (!window.isSecureContext) {
      showToast("Location requires a secure connection (HTTPS or localhost).");
      return;
    }
    if (code === 1) {
      showToast("Location permission was denied. Allow access in your browser settings.");
    } else if (code === 3) {
      showToast("Location request timed out. Please try again.");
    } else {
      showToast("Could not determine your location. Check your device settings.");
    }
  };

  const showUserLocation = (latitude, longitude) => {
    const map = mapRef.current;
    if (!map || !Number.isFinite(latitude) || !Number.isFinite(longitude)) {
      reportLocationError(2);
      return;
    }
    locationRequestRef.current = false;
    setLocating(false);
    onUserLocation?.({ latitude, longitude });
    if (!userMarkerRef.current) {
      const element = document.createElement("div");
      element.className = "user-location-marker";
      element.setAttribute("aria-label", "Your location");
      userMarkerRef.current = new Marker({ element, anchor: "center" }).addTo(map);
    }
    userMarkerRef.current.setLngLat([longitude, latitude]);
    map.flyTo({
      center: [longitude, latitude],
      zoom: Math.max(map.getZoom(), 14),
      pitch: 45,
      duration: 1000,
    });
  };

  const showIncident = (incident, position) => {
    const map = mapRef.current;
    if (!map) return;
    const latitude = finiteNumber(incident.latitude);
    const longitude = finiteNumber(incident.longitude);
    const center = position || [longitude, latitude];
    if (
      latitude == null ||
      longitude == null ||
      Math.abs(latitude) > 90 ||
      Math.abs(longitude) > 180
    ) return;
    map.flyTo({ center, zoom: Math.max(map.getZoom(), 10), pitch: 45, duration: 900 });
    activePopupRef.current?.remove();
    window.clearTimeout(toastTimerRef.current);
    activePopupRef.current = new Popup({ closeButton: true, closeOnClick: true, offset: 18 })
      .setLngLat(center)
      .setDOMContent(createPopupContent({
        disaster_type: incident.disaster_type || "Unclassified",
        confidence: finiteNumber(incident.confidence) ?? 0,
        severity: finiteNumber(incident.severity) ?? 0,
        status: incident.status,
        report_count: incident.report_count,
        has_contradiction: incident.has_contradiction,
        latitude,
        longitude,
      }))
      .addTo(map);
  };

  useEffect(() => {
    const map = new MapLibreMap({
      container: mapContainer.current,
      center: [78.9629, 20.5937],
      zoom: 4.4,
      pitch: 45,
      style: MAP_STYLES[theme],
      attributionControl: true,
    });
    mapRef.current = map;
    map.addControl(new NavigationControl({ showCompass: true, showZoom: true }), "top-right");
    map.addControl(new ScaleControl({ maxWidth: 100, unit: "metric" }), "bottom-left");
    const geolocate = new GeolocateControl({
      positionOptions: { enableHighAccuracy: true, timeout: 10000 },
      trackUserLocation: true,
      showAccuracyCircle: true,
      showUserHeading: true,
      fitBoundsOptions: { maxZoom: 14 },
    });
    map.addControl(geolocate, "top-right");
    map.on("click", (event) => {
      const activeLayers = [CLUSTER_LAYER, INCIDENT_LAYER].filter((layer) => map.getLayer(layer));
      if (!activeLayers.length) return;
      const feature = map.queryRenderedFeatures(event.point, { layers: activeLayers })[0];
      if (!feature) return;
      if (feature.layer.id === CLUSTER_LAYER) {
        const source = map.getSource(INCIDENT_SOURCE);
        source?.getClusterExpansionZoom(feature.properties.cluster_id, (error, zoom) => {
          if (error) {
            showToast("Could not expand this incident cluster. Try zooming in.");
            return;
          }
          map.easeTo({ center: feature.geometry.coordinates, zoom, duration: 650 });
        });
        return;
      }
      const [longitude, latitude] = feature.geometry.coordinates;
      showIncident({
        ...feature.properties,
        latitude,
        longitude,
        has_contradiction: feature.properties.has_contradiction === true ||
          feature.properties.has_contradiction === "true",
      });
    });
    map.on("mousemove", (event) => {
      const activeLayers = [CLUSTER_LAYER, INCIDENT_LAYER].filter((layer) => map.getLayer(layer));
      if (!activeLayers.length) return;
      const feature = map.queryRenderedFeatures(event.point, { layers: activeLayers })[0];
      map.getCanvas().style.cursor = feature ? "pointer" : "";
    });

    geolocate.on("geolocate", (event) => {
      const { longitude, latitude } = event.coords;
      showUserLocation(latitude, longitude);
    });
    geolocate.on("error", (event) => {
      reportLocationError(event.code);
    });

    const initializeStyle = () => {
      const style = map.getStyle();
      const buildingLayer = style.layers?.find((layer) =>
        layer["source-layer"] === "building" && layer.type !== "background"
      );
      const alreadyExtruded = style.layers?.some((layer) => layer.type === "fill-extrusion");
      if (buildingLayer && !alreadyExtruded && style.sources?.[buildingLayer.source]?.type === "vector") {
        map.addLayer({
          id: "crowdsense-3d-buildings",
          source: buildingLayer.source,
          "source-layer": buildingLayer["source-layer"],
          type: "fill-extrusion",
          minzoom: 14,
          paint: {
            "fill-extrusion-color": theme === "dark" ? "#27384a" : "#b8c7d4",
            "fill-extrusion-height": ["to-number", ["get", "render_height"], ["to-number", ["get", "height"], 8]],
            "fill-extrusion-base": ["to-number", ["get", "render_min_height"], ["to-number", ["get", "min_height"], 0]],
            "fill-extrusion-opacity": 0.78,
          },
        });
      }
      addIncidentLayers(map, incidentsRef.current);
      sourceSignatureRef.current = incidentDataSignature(incidentsRef.current);
      const signature = incidentsRef.current.map((item) => item.id).sort().join("|");
      if (signature && signature !== lastFittedSignature.current) {
        fitIncidents(map, incidentsRef.current);
        lastFittedSignature.current = signature;
      } else {
        map.flyTo({ center: [78.9629, 20.5937], zoom: 4.4, pitch: 45, duration: 1400 });
      }
    };
    map.on("load", initializeStyle);

    return () => {
      userMarkerRef.current?.remove();
      activePopupRef.current?.remove();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (appliedThemeRef.current === theme) return;
    appliedThemeRef.current = theme;
    map.setStyle(MAP_STYLES[theme]);
    const rebuild = () => {
      const style = map.getStyle();
      const buildingLayer = style.layers?.find((layer) =>
        layer["source-layer"] === "building" && layer.type !== "background"
      );
      const alreadyExtruded = style.layers?.some((layer) => layer.type === "fill-extrusion");
      if (buildingLayer && !alreadyExtruded && style.sources?.[buildingLayer.source]?.type === "vector") {
        map.addLayer({
          id: "crowdsense-3d-buildings",
          source: buildingLayer.source,
          "source-layer": buildingLayer["source-layer"],
          type: "fill-extrusion",
          minzoom: 14,
          paint: {
            "fill-extrusion-color": theme === "dark" ? "#27384a" : "#b8c7d4",
            "fill-extrusion-height": ["to-number", ["get", "render_height"], ["to-number", ["get", "height"], 8]],
            "fill-extrusion-base": ["to-number", ["get", "render_min_height"], ["to-number", ["get", "min_height"], 0]],
            "fill-extrusion-opacity": 0.78,
          },
        });
      }
      addIncidentLayers(map, incidentsRef.current);
      sourceSignatureRef.current = incidentDataSignature(incidentsRef.current);
      const signature = incidentsRef.current.map((item) => item.id).sort().join("|");
      if (signature && signature !== lastFittedSignature.current) {
        fitIncidents(map, incidentsRef.current);
        lastFittedSignature.current = signature;
      }
    };
    map.once("style.load", rebuild);
  }, [theme]);

  useEffect(() => {
    if (focusIncident) showIncident(focusIncident);
  }, [focusIncident]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    incidentsRef.current = incidents;
    if (map.isStyleLoaded()) {
      const dataSignature = incidentDataSignature(incidents);
      if (map.getSource(INCIDENT_SOURCE)) {
        if (sourceSignatureRef.current !== dataSignature) {
          map.getSource(INCIDENT_SOURCE).setData(incidentsToGeoJSON(incidents));
          sourceSignatureRef.current = dataSignature;
        }
      } else {
        addIncidentLayers(map, incidents);
        sourceSignatureRef.current = dataSignature;
      }
    }

    const signature = incidents.map((item) => `${item.id}:${item.longitude}:${item.latitude}`).sort().join("|");
    if (map.loaded() && signature && signature !== lastFittedSignature.current) {
      fitIncidents(map, incidents);
      lastFittedSignature.current = signature;
    }
  }, [incidents, onHighlightIncident]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.getSource(INCIDENT_SOURCE) || !map.getLayer(INCIDENT_LAYER)) return;
    const previousId = map.__crowdsenseHighlightedId;
    if (previousId != null) {
      map.setFeatureState({ source: INCIDENT_SOURCE, id: String(previousId) }, { hover: false });
    }
    if (highlightedIncidentId != null) {
      map.setFeatureState({ source: INCIDENT_SOURCE, id: String(highlightedIncidentId) }, { hover: true });
    }
    map.__crowdsenseHighlightedId = highlightedIncidentId;
  }, [highlightedIncidentId, incidents]);

  const hasLocatedIncidents = locatedIncidents(incidents).length > 0;

  return (
    <div className="map-view">
      <div ref={mapContainer} className="map-canvas" />
      {hasLocatedIncidents && (
        <button
          className="map-fit-button glass-panel"
          onClick={() => mapRef.current && fitIncidents(mapRef.current, incidentsRef.current)}
          type="button"
          aria-label="Show all incidents on map"
        >
          <span aria-hidden="true">⌖</span> Show all
        </button>
      )}
      <button
        className={`locate-me-button glass-panel${locating ? " is-locating" : ""}`}
        type="button"
        aria-label="Locate me"
        disabled={locating}
        onClick={() => {
          if (!window.isSecureContext) {
            reportLocationError(1);
            return;
          }
          if (!navigator.geolocation) {
            reportLocationError(2);
            return;
          }
          if (locationRequestRef.current) return;
          locationRequestRef.current = true;
          setLocating(true);
          navigator.geolocation.getCurrentPosition(
            ({ coords }) => showUserLocation(coords.latitude, coords.longitude),
            ({ code }) => reportLocationError(code),
            { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }
          );
        }}
      >
        <span aria-hidden="true">{locating ? "…" : "◎"}</span> {locating ? "Finding you…" : "Locate me"}
      </button>
      <div className="map-legend glass-panel" aria-label="Incident map legend">
        <strong>Incident severity</strong>
        <span><i className="legend-dot legend-low" /> Low</span>
        <span><i className="legend-dot legend-medium" /> Elevated</span>
        <span><i className="legend-dot legend-high" /> High</span>
        <span><i className="legend-dot legend-conflict" /> Dashed ring: conflicting reports</span>
      </div>
      {toast && <div className="location-toast" role="status">{toast}</div>}
      {!hasLocatedIncidents && (
        <div className="map-empty-notice glass-panel">
          {incidents.length
            ? "Incidents are loaded, but none have valid coordinates to display."
            : "No incidents to display yet. Submit a report to create one."}
        </div>
      )}
    </div>
  );
}
