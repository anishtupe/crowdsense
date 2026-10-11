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
const INCIDENT_RING_LAYER = "incident-conflicts";
const CONFLICT_IMAGE = "crowdsense-conflict-ring";
const MAP_STYLES = {
  dark: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
  light: "https://tiles.openfreemap.org/styles/liberty",
};
const HIGH_DENSITY_THRESHOLD = 200;

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

function severityColor(severity) {
  if (severity > 0.7) return "#f56b6b";
  if (severity >= 0.4) return "#f5b84b";
  return "#44d18a";
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

function incidentMarker(incident, onClick, onHighlight) {
  const severity = finiteNumber(incident.severity) ?? 0;
  const element = document.createElement("button");
  element.type = "button";
  element.className = `incident-marker${incident.has_contradiction ? " has-conflict" : ""}`;
  element.style.setProperty("--incident-color", severityColor(severity));
  element.style.setProperty("--pulse-duration", `${Math.max(0.85, 2.25 - severity * 1.15)}s`);
  element.setAttribute("aria-label", `${incident.disaster_type || "Incident"}, severity ${Math.round(severity * 100)} percent${incident.has_contradiction ? ", conflicting reports" : ""}`);
  const ring = document.createElement("span");
  ring.className = "incident-marker-ring";
  const core = document.createElement("span");
  core.className = "incident-marker-core";
  element.append(ring, core);
  if (incident.has_contradiction) {
    const badge = document.createElement("span");
    badge.className = "incident-marker-warning";
    badge.textContent = "!";
    element.append(badge);
  }
  element.addEventListener("click", (event) => {
    event.stopPropagation();
    onClick(incident);
  });
  element.addEventListener("mouseenter", () => onHighlight(incident.id));
  element.addEventListener("mouseleave", () => onHighlight(null));
  return element;
}

function clusterMarker(incidents, onClick) {
  const element = document.createElement("button");
  element.type = "button";
  element.className = "incident-cluster-marker";
  element.textContent = String(incidents.length);
  element.setAttribute("aria-label", `${incidents.length} nearby incidents`);
  element.addEventListener("click", (event) => {
    event.stopPropagation();
    onClick(incidents);
  });
  return element;
}

function addIncidentLayers(map, incidents) {
  if (map.getSource(INCIDENT_SOURCE)) {
    if (map.getLayer(INCIDENT_RING_LAYER)) map.removeLayer(INCIDENT_RING_LAYER);
    if (map.getLayer(INCIDENT_LAYER)) map.removeLayer(INCIDENT_LAYER);
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
  });
  map.addLayer({
    id: INCIDENT_LAYER,
    type: "circle",
    source: INCIDENT_SOURCE,
    paint: {
      "circle-radius": ["case", ["boolean", ["feature-state", "hover"], false], 11, 7],
      "circle-color": [
        "case",
        [">", ["get", "severity"], 0.7],
        "#f56b6b",
        [">=", ["get", "severity"], 0.4],
        "#f5b84b",
        "#44d18a",
      ],
      "circle-opacity": 0.92,
      "circle-stroke-color": "#ffffff",
      "circle-stroke-width": ["case", ["boolean", ["feature-state", "hover"], false], 3, 1.5],
    },
  });
  map.addLayer({
    id: INCIDENT_RING_LAYER,
    type: "symbol",
    source: INCIDENT_SOURCE,
    filter: ["==", ["get", "has_contradiction"], true],
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
  const markerRecordsRef = useRef(new Map());
  const syncMarkersRef = useRef(null);
  const largeSourceSignatureRef = useRef("");
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

  const showIncidentCluster = (cluster, position) => {
    const map = mapRef.current;
    if (!map) return;
    map.flyTo({
      center: position,
      zoom: Math.min(17, Math.max(map.getZoom() + 2, 12)),
      pitch: 45,
      duration: 700,
    });
    const content = document.createElement("div");
    content.className = "incident-popup";
    const title = document.createElement("strong");
    title.className = "incident-popup-title";
    title.textContent = `${cluster.length} nearby incidents`;
    content.append(title);
    cluster.forEach((incident) => {
      const item = document.createElement("div");
      item.className = "incident-cluster-item";
      const name = document.createElement("strong");
      name.textContent = incident.disaster_type || "Unclassified";
      const detail = document.createElement("span");
      detail.textContent = `Severity ${Math.round((finiteNumber(incident.severity) ?? 0) * 100)}% · ${incident.report_count ?? 0} reports`;
      item.append(name, detail);
      content.append(item);
    });
    activePopupRef.current?.remove();
    activePopupRef.current = new Popup({ closeButton: true, closeOnClick: true, offset: 18 })
      .setLngLat(position)
      .setDOMContent(content)
      .addTo(map);
  };

  syncMarkersRef.current = () => {
    const map = mapRef.current;
    if (!map) return;
    const located = locatedIncidents(incidentsRef.current);
    if (located.length > HIGH_DENSITY_THRESHOLD) {
      markerRecordsRef.current.forEach(({ marker }) => marker.remove());
      markerRecordsRef.current.clear();
      if (map.isStyleLoaded()) {
        const dataSignature = located.map((incident) => [
          incident.id,
          incident.latitude,
          incident.longitude,
          incident.disaster_type,
          incident.confidence,
          incident.severity,
          incident.status,
          incident.report_count,
          incident.has_contradiction,
        ].join(":")).sort().join("|");
        if (map.getSource(INCIDENT_SOURCE)) {
          if (largeSourceSignatureRef.current !== dataSignature) {
            map.getSource(INCIDENT_SOURCE).setData(incidentsToGeoJSON(located));
            largeSourceSignatureRef.current = dataSignature;
          }
        } else {
          addIncidentLayers(map, located);
          largeSourceSignatureRef.current = dataSignature;
        }
      }
      return;
    }

    const pixelGroups = [];
    located.forEach((incident) => {
      const point = map.project([incident.longitude, incident.latitude]);
      const nearbyGroup = pixelGroups.find((group) =>
        Math.hypot(point.x - group.centerX, point.y - group.centerY) <= 34
      );
      if (nearbyGroup) {
        nearbyGroup.incidents.push(incident);
        const count = nearbyGroup.incidents.length;
        nearbyGroup.centerX += (point.x - nearbyGroup.centerX) / count;
        nearbyGroup.centerY += (point.y - nearbyGroup.centerY) / count;
      } else {
        pixelGroups.push({
          incidents: [incident],
          centerX: point.x,
          centerY: point.y,
        });
      }
    });

    const nextRecords = new Map();
    pixelGroups.forEach((group) => {
      const members = group.incidents;
      const key = members.length === 1
        ? `incident:${members[0].id}`
        : `cluster:${members.map((incident) => incident.id).sort().join("|")}`;
      const position = members.length === 1
        ? [members[0].longitude, members[0].latitude]
        : map.unproject([group.centerX, group.centerY]).toArray();
      const signature = members.length === 1
        ? [
          members[0].latitude,
          members[0].longitude,
          members[0].severity,
          members[0].has_contradiction,
          members[0].disaster_type,
          members[0].status,
          members[0].report_count,
        ].join(":")
        : `${position.map((coordinate) => coordinate.toFixed(6)).join(":")}:${members.length}`;
      const existing = markerRecordsRef.current.get(key);
      if (existing?.signature === signature) {
        nextRecords.set(key, existing);
        return;
      }

      existing?.marker.remove();
      const element = members.length === 1
        ? incidentMarker(
          members[0],
          (incident) => showIncident(incident),
          onHighlightIncident || (() => {})
        )
        : clusterMarker(members, (cluster) => showIncidentCluster(cluster, position));
      const marker = new Marker({ element, anchor: "center" })
        .setLngLat(position)
        .addTo(map);
      marker.__incidentId = members.length === 1 ? String(members[0].id) : null;
      nextRecords.set(key, { marker, signature });
    });

    markerRecordsRef.current.forEach(({ marker }, key) => {
      if (!nextRecords.has(key)) marker.remove();
    });
    markerRecordsRef.current = nextRecords;
    if (map.getSource(INCIDENT_SOURCE)) {
      if (map.getLayer(INCIDENT_RING_LAYER)) map.removeLayer(INCIDENT_RING_LAYER);
      if (map.getLayer(INCIDENT_LAYER)) map.removeLayer(INCIDENT_LAYER);
      map.removeSource(INCIDENT_SOURCE);
      largeSourceSignatureRef.current = "";
    }
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
      if (!map.getLayer(INCIDENT_LAYER)) return;
      const feature = map.queryRenderedFeatures(event.point, { layers: [INCIDENT_LAYER] })[0];
      if (!feature) return;
      const incident = locatedIncidents(incidentsRef.current).find(
        (item) => String(item.id) === String(feature.properties?.id)
      );
      if (incident) showIncident(incident);
    });
    map.on("mousemove", (event) => {
      if (!map.getLayer(INCIDENT_LAYER)) return;
      const feature = map.queryRenderedFeatures(event.point, { layers: [INCIDENT_LAYER] })[0];
      map.getCanvas().style.cursor = feature ? "pointer" : "";
    });
    const syncMarkers = () => syncMarkersRef.current?.();
    map.on("zoomend", syncMarkers);
    map.on("moveend", syncMarkers);

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
      const located = locatedIncidents(incidentsRef.current);
      if (located.length > HIGH_DENSITY_THRESHOLD && !map.getSource(INCIDENT_SOURCE)) {
        addIncidentLayers(map, incidentsRef.current);
      }
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
      map.off("zoomend", syncMarkers);
      map.off("moveend", syncMarkers);
      markerRecordsRef.current.forEach(({ marker }) => marker.remove());
      markerRecordsRef.current.clear();
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
      const located = locatedIncidents(incidentsRef.current);
      if (located.length > HIGH_DENSITY_THRESHOLD && !map.getSource(INCIDENT_SOURCE)) {
        addIncidentLayers(map, incidentsRef.current);
      }
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
    syncMarkersRef.current?.();

    const signature = incidents.map((item) => `${item.id}:${item.longitude}:${item.latitude}`).sort().join("|");
    if (map.loaded() && signature && signature !== lastFittedSignature.current) {
      fitIncidents(map, incidents);
      lastFittedSignature.current = signature;
    }
  }, [incidents, onHighlightIncident]);

  useEffect(() => {
    const map = mapRef.current;
    markerRecordsRef.current.forEach(({ marker }) => {
      marker.getElement().classList.toggle(
        "is-highlighted",
        highlightedIncidentId != null && marker.__incidentId === String(highlightedIncidentId)
      );
    });
    const source = map?.getSource(INCIDENT_SOURCE);
    if (!source || !map.getLayer(INCIDENT_LAYER)) return;
    const previousId = map.__crowdsenseHighlightedId;
    if (previousId != null) {
      map.setFeatureState({ source: INCIDENT_SOURCE, id: String(previousId) }, { hover: false });
    }
    if (highlightedIncidentId != null) {
      map.setFeatureState({ source: INCIDENT_SOURCE, id: String(highlightedIncidentId) }, { hover: true });
    }
    map.__crowdsenseHighlightedId = highlightedIncidentId;
  }, [highlightedIncidentId, incidents]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || incidents.length <= HIGH_DENSITY_THRESHOLD) return undefined;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reducedMotion) return undefined;
    let frame;
    const start = performance.now();
    const animate = (time) => {
      if (map.getLayer(INCIDENT_LAYER)) {
        const elapsed = time - start;
        const radius = (period) => 7 + (((elapsed % period) / period) * 6);
        const opacity = (period) => 0.92 - (((elapsed % period) / period) * 0.34);
        map.setPaintProperty(INCIDENT_LAYER, "circle-radius", [
          "case",
          ["boolean", ["feature-state", "hover"], false],
          11,
          [">", ["get", "severity"], 0.7],
          radius(950),
          [">=", ["get", "severity"], 0.4],
          radius(1500),
          radius(2200),
        ]);
        map.setPaintProperty(INCIDENT_LAYER, "circle-opacity", [
          "case",
          [">", ["get", "severity"], 0.7],
          opacity(950),
          [">=", ["get", "severity"], 0.4],
          opacity(1500),
          opacity(2200),
        ]);
      }
      frame = window.requestAnimationFrame(animate);
    };
    frame = window.requestAnimationFrame(animate);
    return () => window.cancelAnimationFrame(frame);
  }, [incidents.length]);

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
