import React, { useState } from "react";
import { submitReport } from "../api.js";

export default function ReportForm({ onReportSubmitted, onViewDashboard }) {
  const [text, setText] = useState("");
  const [mediaUrl, setMediaUrl] = useState("");
  const [mediaFile, setMediaFile] = useState(null);
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [locating, setLocating] = useState(false);
  const [locationError, setLocationError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [submittedReport, setSubmittedReport] = useState(null);

  const handleUseMyLocation = () => {
    if (!navigator.geolocation) {
      setLocationError("Geolocation is not supported by your browser");
      return;
    }
    setLocating(true);
    setLocationError("");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLatitude(position.coords.latitude.toFixed(6));
        setLongitude(position.coords.longitude.toFixed(6));
        setLocating(false);
      },
      (error) => {
        setLocationError(`Location error: ${error.message}`);
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setMediaFile(file);
      const reader = new FileReader();
      reader.onloadend = () => {
        setMediaUrl(reader.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitError("");

    if (!latitude || !longitude) {
      setSubmitError("Please specify a location (use GPS or enter coordinates).");
      return;
    }

    const latNum = parseFloat(latitude);
    const lonNum = parseFloat(longitude);
    if (isNaN(latNum) || isNaN(lonNum)) {
      setSubmitError("Latitude and Longitude must be valid numbers.");
      return;
    }

    if (!text.trim() && !mediaUrl) {
      setSubmitError("Please provide a text description or upload media.");
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        text: text.trim() || null,
        media_url: mediaUrl || null,
        latitude: latNum,
        longitude: lonNum,
        source: "citizen",
      };
      const result = await submitReport(payload);
      setSubmittedReport(result);
      if (onReportSubmitted) {
        onReportSubmitted(result);
      }
    } catch (err) {
      setSubmitError(err.message || "Failed to submit report. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleReset = () => {
    setText("");
    setMediaUrl("");
    setMediaFile(null);
    setLatitude("");
    setLongitude("");
    setSubmittedReport(null);
    setSubmitError("");
    setLocationError("");
  };

  if (submittedReport) {
    return (
      <div className="report-form-container confirmation-state">
        <div className="confirmation-card">
          <div className="confirmation-icon">✓</div>
          <h2>Report Submitted Successfully</h2>
          <p className="confirmation-subtitle">
            Thank you for helping keep your community safe. Your report has been dispatched to the CrowdSense AI pipeline.
          </p>
          <div className="report-details-box">
            <div className="detail-row">
              <span className="detail-label">Report ID:</span>
              <span className="detail-value font-mono">{submittedReport.id}</span>
            </div>
            {submittedReport.disaster_type && (
              <div className="detail-row">
                <span className="detail-label">Disaster Type:</span>
                <span className="detail-value capitalize">{submittedReport.disaster_type}</span>
              </div>
            )}
            <div className="detail-row">
              <span className="detail-label">Time:</span>
              <span className="detail-value">{new Date(submittedReport.reported_at).toLocaleString()}</span>
            </div>
          </div>
          <div className="confirmation-actions">
            <button className="btn btn-primary" onClick={handleReset}>
              Submit Another Report
            </button>
            {onViewDashboard && (
              <button className="btn btn-secondary" onClick={onViewDashboard}>
                View Live Incident Map
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="report-form-container">
      <div className="report-form-card">
        <h2>Submit Citizen Incident Report</h2>
        <p className="form-description">
          Report an emergency, hazard, or disaster event in real time to feed the geospatial intelligence pipeline.
        </p>

        {submitError && <div className="alert alert-error">{submitError}</div>}

        <form onSubmit={handleSubmit} className="report-form">
          <div className="form-group">
            <label htmlFor="description">Incident Description</label>
            <textarea
              id="description"
              rows="4"
              placeholder="Describe what you see (e.g., Heavy flooding near Main St bridge, water level rising rapidly...)"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label>Location Coordinates *</label>
            <div className="location-controls">
              <button
                type="button"
                className="btn btn-gps"
                onClick={handleUseMyLocation}
                disabled={locating}
              >
                {locating ? "Locating..." : "📍 Use My Location (GPS)"}
              </button>
            </div>

            {locationError && <div className="alert alert-warning">{locationError}</div>}

            <div className="coords-inputs">
              <div className="coord-field">
                <label htmlFor="latitude">Latitude</label>
                <input
                  id="latitude"
                  type="number"
                  step="any"
                  placeholder="e.g. 37.7749"
                  value={latitude}
                  onChange={(e) => setLatitude(e.target.value)}
                  required
                />
              </div>
              <div className="coord-field">
                <label htmlFor="longitude">Longitude</label>
                <input
                  id="longitude"
                  type="number"
                  step="any"
                  placeholder="e.g. -122.4194"
                  value={longitude}
                  onChange={(e) => setLongitude(e.target.value)}
                  required
                />
              </div>
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="media">Photo / Video Evidence</label>
            <input
              id="media"
              type="file"
              accept="image/*,video/*"
              onChange={handleFileChange}
              className="file-input"
            />
            <div className="or-divider">or enter image/video URL:</div>
            <input
              type="url"
              placeholder="https://example.com/photo.jpg"
              value={mediaUrl.startsWith("data:") ? "" : mediaUrl}
              onChange={(e) => setMediaUrl(e.target.value)}
            />
            {mediaUrl && (
              <div className="media-preview">
                {mediaUrl.startsWith("data:video") ? (
                  <video src={mediaUrl} controls className="preview-thumb" />
                ) : (
                  <img src={mediaUrl} alt="Upload preview" className="preview-thumb" />
                )}
              </div>
            )}
          </div>

          <button type="submit" className="btn btn-submit" disabled={submitting}>
            {submitting ? "Submitting Report..." : "Submit Incident Report"}
          </button>
        </form>
      </div>
    </div>
  );
}
