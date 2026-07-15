"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Protected from "../components/Protected";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { ErrorMessage, Message, Spinner } from "../components/ui";

type Session = {
  id: string;
  device_label: string;
  location: string;
  ip_address: string | null;
  created_at: string;
  last_active_at: string;
  is_current: boolean;
};

function SecurityInner() {
  const router = useRouter();
  const { logout } = useAuth();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [message, setMessage] = useState("");

  async function load() {
    setLoading(true);
    try {
      const s = await api.sessions();
      setSessions(s);
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function terminate(id: string) {
    setError(null);
    try {
      await api.terminateSession(id);
      setMessage("Session terminated.");
      await load();
    } catch (err) {
      setError(err as ApiError);
    }
  }

  async function logoutOthers() {
    setError(null);
    try {
      await api.logoutAll();
      setMessage("Signed out of all other devices.");
      await load();
    } catch (err) {
      setError(err as ApiError);
    }
  }

  return (
    <div className="container wide">
      <div className="card">
        <h1>Security &amp; devices</h1>
        <p className="subtitle">These devices are currently signed in to your account.</p>

        <ErrorMessage error={error} />
        {message && <Message kind="success">{message}</Message>}

        {loading ? (
          <Spinner />
        ) : (
          <>
            {sessions.map((s) => (
              <div className="list-item row" key={s.id}>
                <div>
                  <div style={{ fontWeight: 600 }}>
                    {s.device_label}{" "}
                    {s.is_current && <span className="badge green">This device</span>}
                  </div>
                  <div className="muted">
                    {s.location} · {s.ip_address || "unknown IP"} · last active{" "}
                    {new Date(s.last_active_at).toLocaleString()}
                  </div>
                </div>
                {!s.is_current && (
                  <button className="btn-ghost" onClick={() => terminate(s.id)}>
                    Log out
                  </button>
                )}
              </div>
            ))}

            {sessions.length > 1 && (
              <button className="btn-secondary" style={{ marginTop: 8 }} onClick={logoutOthers}>
                Log out all other devices
              </button>
            )}
          </>
        )}
      </div>

      <div className="card">
        <div className="row">
          <div>
            <h2 style={{ marginBottom: 4 }}>Sign out</h2>
            <p className="muted">End your session on this device.</p>
          </div>
          <button
            className="btn-secondary"
            onClick={async () => {
              await logout();
              router.push("/login");
            }}
          >
            Log out
          </button>
        </div>
      </div>
    </div>
  );
}

export default function SecurityPage() {
  return (
    <Protected>
      <SecurityInner />
    </Protected>
  );
}
