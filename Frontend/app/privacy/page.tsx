"use client";

import { useEffect, useState } from "react";
import Protected from "../components/Protected";
import { api, ApiError } from "../lib/api";
import { ErrorMessage, Message, Spinner } from "../components/ui";

type Consent = {
  consent_type: string;
  label: string;
  mandatory: boolean;
  granted: boolean;
  policy_version: string;
  updated_at: string | null;
};

type HistoryEntry = {
  consent_type: string;
  granted: boolean;
  policy_version: string;
  created_at: string;
};

function PrivacyInner() {
  const [consents, setConsents] = useState<Consent[]>([]);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [message, setMessage] = useState("");

  async function load() {
    setLoading(true);
    try {
      const [c, h] = await Promise.all([api.consents(), api.consentHistory()]);
      setConsents(c);
      setHistory(h);
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function toggle(c: Consent) {
    setError(null);
    setMessage("");
    try {
      const r: any = await api.updateConsent(c.consent_type, !c.granted);
      setMessage(r.message);
      await load();
    } catch (err) {
      setError(err as ApiError);
    }
  }

  return (
    <div className="container wide">
      <div className="card">
        <h1>Privacy &amp; consent</h1>
        <p className="subtitle">Manage how your data is used. Mandatory items keep your account active.</p>

        <ErrorMessage error={error} />
        {message && <Message kind="success">{message}</Message>}

        {loading ? (
          <Spinner />
        ) : (
          consents.map((c) => (
            <div className="list-item row" key={c.consent_type}>
              <div>
                <div style={{ fontWeight: 600 }}>
                  {c.label}{" "}
                  {c.mandatory && <span className="badge">Required</span>}
                </div>
                <div className="muted">Policy v{c.policy_version}</div>
              </div>
              <label className="toggle" title={c.mandatory ? "Required — cannot be withdrawn" : ""}>
                <input
                  type="checkbox"
                  checked={c.granted}
                  disabled={c.mandatory}
                  onChange={() => toggle(c)}
                />
                <span className="track" />
                <span className="thumb" />
              </label>
            </div>
          ))
        )}
      </div>

      <div className="card">
        <h2>Consent history</h2>
        {history.length === 0 ? (
          <p className="muted">No changes recorded yet.</p>
        ) : (
          history.map((h, i) => (
            <div className="list-item row" key={i}>
              <span>
                {h.consent_type} — <b>{h.granted ? "granted" : "withdrawn"}</b>
              </span>
              <span className="muted">
                v{h.policy_version} · {new Date(h.created_at).toLocaleString()}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default function PrivacyPage() {
  return (
    <Protected>
      <PrivacyInner />
    </Protected>
  );
}
