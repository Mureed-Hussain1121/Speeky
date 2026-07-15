"use client";

import { useState } from "react";
import Link from "next/link";
import { api, ApiError } from "../lib/api";
import { ErrorMessage, Field, Message } from "../components/ui";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [message, setMessage] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r: any = await api.forgotPassword(email);
      setMessage(r.message);
      setSent(true);
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="container">
      <div className="card">
        <h1>Reset your password</h1>
        <p className="subtitle">Enter your email and we&apos;ll send a reset link.</p>
        <ErrorMessage error={error} />
        {sent ? (
          <>
            {/* Generic confirmation — never reveals whether the account exists. */}
            <Message kind="success">{message}</Message>
            <p className="muted">
              Email is mocked in this build — check <code>/dev/outbox</code> on the API for the reset link.
            </p>
            <Link href="/login">
              <button className="btn-secondary">Back to login</button>
            </Link>
          </>
        ) : (
          <form onSubmit={submit}>
            <Field
              label="Email"
              type="email"
              value={email}
              required
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
            />
            <button type="submit" className="btn-primary" disabled={busy}>
              {busy ? "Sending…" : "Send reset link"}
            </button>
          </form>
        )}
        <p className="helper">
          Remembered it? <Link href="/login">Log in</Link>
        </p>
      </div>
    </div>
  );
}
