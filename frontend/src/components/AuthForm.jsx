import React, { useState } from "react";
import { fetchCurrentUser, loginUser, registerUser } from "../api.js";

export default function AuthForm({ onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);

    try {
      if (mode === "register") {
        await registerUser(email, password);
      }
      const { access_token: token } = await loginUser(email, password);
      const user = await fetchCurrentUser(token);
      onAuthenticated(token, user);
    } catch (err) {
      setError(err.message || "Unable to authenticate. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-container">
      <section className="auth-card">
        <p className="auth-eyebrow">CrowdSense account</p>
        <h2>{mode === "login" ? "Welcome back" : "Create your account"}</h2>
        <p className="form-description">
          Sign in to access the incident dashboard, submit reports, and review intelligence.
        </p>

        {error && <div className="alert alert-error" role="alert">{error}</div>}

        <form className="auth-form" onSubmit={handleSubmit}>
          <label className="form-group" htmlFor="auth-email">
            <span>Email</span>
            <input
              id="auth-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
          <label className="form-group" htmlFor="auth-password">
            <span>Password</span>
            <input
              id="auth-password"
              type="password"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
          <button className="btn btn-submit" type="submit" disabled={submitting}>
            {submitting
              ? "Please wait..."
              : mode === "login"
                ? "Sign in"
                : "Create account"}
          </button>
        </form>

        <p className="auth-switch">
          {mode === "login" ? "New to CrowdSense?" : "Already have an account?"}{" "}
          <button
            type="button"
            className="text-button"
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setError("");
            }}
          >
            {mode === "login" ? "Create an account" : "Sign in"}
          </button>
        </p>
      </section>
    </div>
  );
}
