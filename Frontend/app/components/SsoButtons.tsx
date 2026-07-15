"use client";

import { useState } from "react";
import { api, ApiError, TokenResponse } from "../lib/api";
import { Message } from "./ui";

// The Apple/Google providers are MOCKED on the backend. These buttons expose a
// tiny simulator so the flows (Hide My Email, share email, provider failure) can
// be exercised without the real native prompts.

type Props = {
  learningGoal?: string;
  onSuccess: (res: TokenResponse) => void;
};

export default function SsoButtons({ learningGoal, onSuccess }: Props) {
  const [open, setOpen] = useState<"apple" | "google" | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  // Apple sim state
  const [appleEmail, setAppleEmail] = useState("");
  const [hideEmail, setHideEmail] = useState(true);
  const [appleFail, setAppleFail] = useState(false);

  // Google sim state
  const [googleEmail, setGoogleEmail] = useState("");
  const [googleName, setGoogleName] = useState("");
  const [googleFail, setGoogleFail] = useState(false);

  function stableSub(seed: string) {
    // Deterministic-ish mock id so repeated sign-ins map to the same account.
    return "mock-" + btoa(seed || "anon").replace(/=/g, "").slice(0, 20);
  }

  async function doApple() {
    setBusy(true);
    setError(null);
    try {
      const sub = stableSub(hideEmail ? "apple:" + (appleEmail || "hidden-user") : "apple:" + appleEmail);
      const res = await api.appleSso({
        mock_sub: sub,
        hide_email: hideEmail,
        real_email: hideEmail ? null : appleEmail,
        learning_goal: learningGoal,
        simulate_failure: appleFail,
      });
      onSuccess(res);
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setBusy(false);
    }
  }

  async function doGoogle() {
    setBusy(true);
    setError(null);
    try {
      const res = await api.googleSso({
        mock_sub: stableSub("google:" + googleEmail),
        email: googleEmail,
        name: googleName || null,
        learning_goal: learningGoal,
        simulate_failure: googleFail,
      });
      onSuccess(res);
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      {error && <Message kind="error">{error.message}</Message>}
      <div className="sso-buttons">
        <button
          type="button"
          className="btn-secondary"
          onClick={() => setOpen(open === "apple" ? null : "apple")}
        >
           Continue with Apple
        </button>
        {open === "apple" && (
          <div className="list-item">
            <p className="muted" style={{ marginTop: 0 }}>Mock Apple prompt</p>
            <label style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 10 }}>
              <input
                type="checkbox"
                style={{ width: "auto" }}
                checked={hideEmail}
                onChange={(e) => setHideEmail(e.target.checked)}
              />
              Hide My Email (use a private relay address)
            </label>
            {!hideEmail && (
              <input
                type="email"
                placeholder="your@icloud.com"
                value={appleEmail}
                onChange={(e) => setAppleEmail(e.target.value)}
                style={{ marginBottom: 10 }}
              />
            )}
            <label style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 10 }}>
              <input
                type="checkbox"
                style={{ width: "auto" }}
                checked={appleFail}
                onChange={(e) => setAppleFail(e.target.checked)}
              />
              Simulate provider failure (E-02)
            </label>
            <button type="button" className="btn-primary" onClick={doApple} disabled={busy}>
              {busy ? "Signing in…" : "Simulate Apple sign-in"}
            </button>
          </div>
        )}

        <button
          type="button"
          className="btn-secondary"
          onClick={() => setOpen(open === "google" ? null : "google")}
        >
          Continue with Google
        </button>
        {open === "google" && (
          <div className="list-item">
            <p className="muted" style={{ marginTop: 0 }}>Mock Google prompt</p>
            <input
              type="email"
              placeholder="your@gmail.com"
              value={googleEmail}
              onChange={(e) => setGoogleEmail(e.target.value)}
              style={{ marginBottom: 10 }}
            />
            <input
              type="text"
              placeholder="Full name (optional)"
              value={googleName}
              onChange={(e) => setGoogleName(e.target.value)}
              style={{ marginBottom: 10 }}
            />
            <label style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 10 }}>
              <input
                type="checkbox"
                style={{ width: "auto" }}
                checked={googleFail}
                onChange={(e) => setGoogleFail(e.target.checked)}
              />
              Simulate SSO timeout (E-02)
            </label>
            <button type="button" className="btn-primary" onClick={doGoogle} disabled={busy || !googleEmail}>
              {busy ? "Signing in…" : "Simulate Google sign-in"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
