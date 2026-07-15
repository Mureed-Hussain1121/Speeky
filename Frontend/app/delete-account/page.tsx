"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Protected from "../components/Protected";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { ErrorMessage, Field, Message, Spinner } from "../components/ui";

function DeleteInner() {
  const router = useRouter();
  const { user, refresh, logout } = useAuth();
  const [status, setStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [password, setPassword] = useState("");
  const [confirmChecked, setConfirmChecked] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const isSso = user?.auth_provider !== "email";

  async function load() {
    setLoading(true);
    try {
      setStatus(await api.deletionStatus());
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function requestDeletion(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const r: any = await api.requestDeletion(isSso ? undefined : password);
      setMessage(r.message);
      await load();
      await refresh();
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    setError(null);
    setBusy(true);
    try {
      const r: any = await api.cancelDeletion();
      setMessage(r.message);
      await load();
      await refresh();
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <Spinner />;

  return (
    <div className="container">
      <div className="card">
        <h1>Delete account</h1>

        <ErrorMessage error={error} />
        {message && <Message kind="success">{message}</Message>}

        {status?.is_pending_deletion ? (
          <>
            <Message kind="warn">
              Your account is scheduled for deletion on{" "}
              <b>{new Date(status.deletion_scheduled_for).toLocaleString()}</b>. You can still cancel and keep your
              account and all your data.
            </Message>
            <button className="btn-primary" onClick={cancel} disabled={busy}>
              {busy ? "Restoring…" : "Cancel deletion & restore account"}
            </button>
          </>
        ) : (
          <>
            <Message kind="info">
              This schedules permanent deletion after a grace period. During the grace period you can log back in and
              cancel. After it elapses, your data is erased for good.
            </Message>
            <form onSubmit={requestDeletion}>
              {!isSso ? (
                <Field
                  label="Confirm your password"
                  type="password"
                  value={password}
                  required
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                />
              ) : (
                <label style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 16 }}>
                  <input
                    type="checkbox"
                    style={{ width: "auto" }}
                    checked={confirmChecked}
                    onChange={(e) => setConfirmChecked(e.target.checked)}
                  />
                  I understand this will permanently delete my account.
                </label>
              )}
              <button type="submit" className="btn-danger" disabled={busy || (isSso && !confirmChecked)}>
                {busy ? "Processing…" : "Schedule account deletion"}
              </button>
            </form>
          </>
        )}

        <p className="helper">
          <a
            onClick={() => router.push("/profile")}
            style={{ cursor: "pointer" }}
          >
            ← Back to profile
          </a>
        </p>
      </div>
    </div>
  );
}

export default function DeleteAccountPage() {
  return (
    <Protected>
      <DeleteInner />
    </Protected>
  );
}
